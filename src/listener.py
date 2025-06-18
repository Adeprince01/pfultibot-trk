"""Telegram message listener and handler for crypto calls.

This module provides the core functionality for connecting to Telegram,
listening for messages, filtering crypto calls, and handling channel configurations.
"""

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol

from telethon import TelegramClient, events
from telethon.errors import AuthKeyError, FloodWaitError
from telethon.tl.types import Message

from src.parser import parse_crypto_call

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ChannelConfig:
    """Configuration for a Telegram channel to monitor.

    Attributes:
        channel_id: Telegram channel ID (negative for channels/groups)
        channel_name: Human-readable channel name
        is_active: Whether to actively monitor this channel
        keywords: Keywords that identify crypto call messages
        priority: Channel priority ("high", "medium", "low")
        retry_count: Number of retry attempts for failed operations
        timeout: Timeout in seconds for operations
        rate_limit: Rate limit for message processing
    """

    channel_id: int
    channel_name: str
    is_active: bool = True
    keywords: List[str] = field(default_factory=lambda: ["Entry", "Peak", "x"])
    priority: str = "medium"
    retry_count: int = 3
    timeout: int = 30
    rate_limit: int = 10

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChannelConfig":
        """Create ChannelConfig from dictionary with validation.
        
        Args:
            data: Dictionary containing channel configuration
            
        Returns:
            ChannelConfig instance
            
        Raises:
            ValueError: If configuration is invalid
            TypeError: If data types are incorrect
        """
        # Validate required fields
        if not isinstance(data.get("channel_id"), int):
            raise TypeError("channel_id must be an integer")
        
        if not isinstance(data.get("channel_name"), str):
            raise TypeError("channel_name must be a string")
            
        # Validate retry_count if present
        if "retry_count" in data and data["retry_count"] < 0:
            raise ValueError("retry_count must be non-negative")
            
        # Validate timeout if present  
        if "timeout" in data and data["timeout"] <= 0:
            raise ValueError("timeout must be positive")
            
        # Validate priority if present
        valid_priorities = ["high", "medium", "low"]
        if "priority" in data and data["priority"] not in valid_priorities:
            raise ValueError(f"priority must be one of {valid_priorities}")
            
        return cls(**data)
    
    @staticmethod
    def sort_by_priority(channels: List["ChannelConfig"]) -> List["ChannelConfig"]:
        """Sort channels by priority (high -> medium -> low).
        
        Args:
            channels: List of channel configurations
            
        Returns:
            Sorted list of channels by priority
        """
        priority_order = {"high": 0, "medium": 1, "low": 2}
        return sorted(channels, key=lambda ch: priority_order.get(ch.priority, 1))


class StorageProtocol(Protocol):
    """Protocol for storage implementations."""

    def append_row(self, data: Dict[str, Any]) -> None:
        """Store a parsed crypto call.
        
        Args:
            data: Dictionary containing the crypto call data with required fields:
                - token_name, entry_cap, peak_cap, x_gain, vip_x (from parser)
                - message_id, channel_id, channel_name, timestamp (metadata)
        """
        ...


class MessageHandler:
    """Handles incoming Telegram messages and processes crypto calls.

    This class manages message filtering, crypto call detection,
    and integration with the parser and storage systems.
    """

    def __init__(
        self, channel_configs: List[ChannelConfig], storage: StorageProtocol
    ) -> None:
        """Initialize the message handler.

        Args:
            channel_configs: List of channel configurations to monitor
            storage: Storage implementation for persisting crypto calls
        """
        self.channel_configs = {config.channel_id: config for config in channel_configs}
        self.storage = storage
        self.pending_messages = []  # For graceful shutdown

        logger.info(f"MessageHandler initialized with {len(channel_configs)} channels")

    def is_crypto_call_message(self, message_text: Optional[str]) -> bool:
        """Determine if a message appears to be a crypto call.

        Args:
            message_text: The message text to analyze

        Returns:
            True if the message appears to be a crypto call, False otherwise
        """
        if not message_text:
            return False

        message_lower = message_text.lower()

        # Check for discovery format: "[token (symbol)] ... Cap: XXK"
        has_discovery_format = (
            "cap:" in message_lower and 
            any(symbol in message_text for symbol in ["(", ")", "[", "]"]) and
            any(char.isdigit() for char in message_text)
        )

        # Check for traditional result format: "entry" and "peak" 
        has_result_format = all(keyword in message_lower for keyword in ["entry", "peak"])

        # Check for @pfultimate update format: "🎉 X.Xx ... From ... ↗️" 
        has_update_format = (
            any(emoji in message_text for emoji in ["🎉", "🔥", "🌕", "⚡️", "🚀", "🌙"]) and 
            "from" in message_lower and 
            "↗️" in message_text and
            any(char.isdigit() for char in message_text)
        )
        
        # Check for bonding messages
        has_bonding_format = "bonded" in message_lower and "achieved" in message_lower

        # Additional indicators for any format
        has_multiplier = "x" in message_lower and any(char.isdigit() for char in message_text)
        has_mc = "mc" in message_lower
        has_crypto_symbols = any(symbol in message_text for symbol in ["🚀", "⚡️", "$", "CA:"])

        # Accept discovery calls (what we want to capture)
        if has_discovery_format:
            return True
            
        # Accept result/update formats (for completeness, but parser will handle appropriately)
        if has_result_format and (has_multiplier or has_mc or has_crypto_symbols):
            return True
            
        # Accept update formats (price progress updates)
        if has_update_format:
            return True
            
        # Accept bonding messages (important lifecycle events)
        if has_bonding_format:
            return True

        return False

    def is_channel_active(self, channel_id: int) -> bool:
        """Check if a channel is actively being monitored.

        Args:
            channel_id: The Telegram channel ID

        Returns:
            True if the channel is active, False otherwise
        """
        config = self.channel_configs.get(channel_id)
        return config is not None and config.is_active

    def get_channel_config(self, channel_id: int) -> Optional[ChannelConfig]:
        """Get configuration for a specific channel.

        Args:
            channel_id: The Telegram channel ID

        Returns:
            ChannelConfig if found, None otherwise
        """
        return self.channel_configs.get(channel_id)

    def get_active_channels(self) -> List[ChannelConfig]:
        """Get list of active channel configurations.

        Returns:
            List of active channel configurations
        """
        return [config for config in self.channel_configs.values() if config.is_active]

    def get_processing_order(self, messages: List[Message]) -> List[Message]:
        """Sort messages by channel priority for processing.

        Args:
            messages: List of messages to sort

        Returns:
            Messages sorted by channel priority (high -> medium -> low)
        """
        def get_priority_order(message: Message) -> int:
            config = self.get_channel_config(message.chat_id)
            if not config:
                return 3  # Lowest priority for unknown channels
            
            priority_order = {"high": 0, "medium": 1, "low": 2}
            return priority_order.get(config.priority, 1)

        return sorted(messages, key=get_priority_order)

    async def apply_rate_limit(self, channel_id: int) -> None:
        """Apply rate limiting for a specific channel.

        Args:
            channel_id: The channel ID to apply rate limiting to
        """
        config = self.get_channel_config(channel_id)
        if not config:
            return

        # Simple rate limiting - sleep based on rate_limit setting
        if config.rate_limit > 0:
            delay = 60.0 / config.rate_limit  # Convert rate per minute to delay in seconds
            await asyncio.sleep(delay)

    def record_channel_stats(
        self, channel_id: int, success: bool, processing_time: float
    ) -> None:
        """Record channel processing statistics.

        Args:
            channel_id: The channel ID
            success: Whether processing was successful
            processing_time: Time taken to process the message in seconds
        """
        # Initialize stats storage if needed
        if not hasattr(self, '_channel_stats'):
            self._channel_stats = {}
        
        if channel_id not in self._channel_stats:
            self._channel_stats[channel_id] = {
                'total_messages': 0,
                'successful_messages': 0,
                'failed_messages': 0,
                'total_processing_time': 0.0,
                'average_processing_time': 0.0,
            }
        
        stats = self._channel_stats[channel_id]
        stats['total_messages'] += 1
        stats['total_processing_time'] += processing_time
        
        if success:
            stats['successful_messages'] += 1
        else:
            stats['failed_messages'] += 1
        
        # Update average
        stats['average_processing_time'] = (
            stats['total_processing_time'] / stats['total_messages']
        )
        
        logger.debug(
            f"Channel {channel_id} stats: {stats['successful_messages']}/{stats['total_messages']} "
            f"success rate, avg time: {stats['average_processing_time']:.2f}s"
        )

    def get_channel_stats(self, channel_id: int) -> Dict[str, Any]:
        """Get processing statistics for a channel.

        Args:
            channel_id: The channel ID

        Returns:
            Dictionary containing channel statistics
        """
        if not hasattr(self, '_channel_stats'):
            return {}
        
        return self._channel_stats.get(channel_id, {})

    def _format_storage_data(
        self, parsed_data: Dict[str, Any], message: Message
    ) -> Dict[str, Any]:
        """Format parsed data for storage with metadata.
        
        Args:
            parsed_data: Dict from parser with crypto call data
            message: Telegram message object
            
        Returns:
            Dict formatted for storage with all required fields
        """
        channel_config = self.get_channel_config(message.chat_id)
        channel_name = channel_config.channel_name if channel_config else "Unknown"
        
        return {
            # Parser data
            "token_name": parsed_data.get("token_name"),
            "entry_cap": parsed_data.get("entry_cap"),
            "peak_cap": parsed_data.get("peak_cap"),
            "x_gain": parsed_data.get("x_gain"),
            "vip_x": parsed_data.get("vip_x"),
            # Enhanced parser data
            "message_type": parsed_data.get("message_type"),
            "contract_address": parsed_data.get("contract_address"),
            "time_to_peak": parsed_data.get("time_to_peak"),
            "linked_to_call_id": parsed_data.get("linked_to_call_id"),
            # Message metadata
            "message_id": message.id,
            "channel_id": message.chat_id,
            "channel_name": channel_name,
            "timestamp": datetime.now().isoformat(),
        }

    async def handle_message_with_retry(
        self, message: Message, max_retries: int = 3
    ) -> bool:
        """Handle message with retry logic for failed operations.

        Args:
            message: The Telegram message object
            max_retries: Maximum number of retry attempts

        Returns:
            True if message was successfully processed, False otherwise
        """
        for attempt in range(max_retries + 1):
            try:
                return await self.handle_message(message)
            except Exception as e:
                if attempt == max_retries:
                    logger.error(
                        f"Failed to process message {message.id} after {max_retries} "
                        f"retries: {e}"
                    )
                    return False
                
                # Exponential backoff with jitter
                delay = min(2 ** attempt, 30)  # Cap at 30 seconds
                jitter = random.uniform(0.9, 1.1)  # 10% jitter
                actual_delay = delay * jitter
                
                logger.warning(
                    f"Attempt {attempt + 1} failed for message {message.id}, "
                    f"retrying in {actual_delay:.1f}s: {e}"
                )
                await asyncio.sleep(actual_delay)
        
        return False

    async def handle_message(self, message: Message) -> bool:
        """Process an incoming Telegram message.

        Args:
            message: The Telegram message object

        Returns:
            True if message was processed as a crypto call, False otherwise
        """
        try:
            # Validate message object
            if message is None:
                logger.debug("Received None message object")
                return False
                
            if not hasattr(message, 'chat_id') or not hasattr(message, 'id'):
                logger.debug("Message object missing required attributes")
                return False

            # Check if channel is monitored and active
            if not self.is_channel_active(message.chat_id):
                logger.debug(
                    f"Ignoring message from inactive/unknown channel {message.chat_id}"
                )
                return False

            # FIRST: Store ALL raw messages from monitored channels
            channel_config = self.get_channel_config(message.chat_id)
            channel_name = channel_config.channel_name if channel_config else "Unknown"

            # Store raw message data
            raw_message_data = {
                "message_id": message.id,
                "channel_id": message.chat_id,
                "channel_name": channel_name,
                "message_text": message.text or "",
                "message_date": message.date.isoformat() if message.date else datetime.now().isoformat(),
            }

            # Store raw message (this happens for ALL messages from monitored channels)
            try:
                if hasattr(self.storage, 'store_raw_message'):
                    self.storage.store_raw_message(raw_message_data)
                    logger.debug(f"Stored raw message {message.id} from channel {message.chat_id}")
            except Exception as e:
                logger.error(f"Failed to store raw message {message.id}: {e}")
                # Continue processing even if raw storage fails

            # SECOND: Attempt classification and parsing
            crypto_call_detected = False
            
            # Check if message appears to be a crypto call
            if self.is_crypto_call_message(message.text):
                logger.debug(f"Message {message.id} appears to be a crypto call, attempting to parse")
                
                # Parse the crypto call with enhanced error handling
                try:
                    parsed_data = parse_crypto_call(message.text)
                    if parsed_data is not None:
                        # Format data for storage
                        storage_data = self._format_storage_data(parsed_data, message)
                        
                        # Apply rate limiting for the channel
                        await self.apply_rate_limit(message.chat_id)

                        # Store the crypto call
                        self.storage.append_row(storage_data)
                        logger.info(
                            f"Successfully processed crypto call from message {message.id} "
                            f"in channel {message.chat_id}"
                        )
                        crypto_call_detected = True
                        
                except Exception as e:
                    logger.error(
                        f"Parser/storage error for message {message.id} in channel {message.chat_id}: {e}"
                    )
                    # Continue - we still have the raw message stored
            else:
                logger.debug(
                    f"Message {message.id} from channel {message.chat_id} is not classified as crypto call"
                )

            return crypto_call_detected

        except Exception as e:
            logger.error(f"Unexpected error handling message {getattr(message, 'id', 'unknown')}: {e}")
            return False


class TelegramListener:
    """Telegram client wrapper for listening to messages.

    This class manages the Telegram connection, authentication,
    and event handling for incoming messages.
    """

    def __init__(self, settings: Any) -> None:
        """Initialize the Telegram listener.

        Args:
            settings: Settings object containing API credentials
        """
        self.api_id = settings.api_id
        self.api_hash = settings.api_hash
        self.session_name = settings.tg_session

        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)

        self.is_connected = False
        self.message_handler: Optional[MessageHandler] = None
        self._event_handler: Optional[Any] = None

        logger.info(f"TelegramListener initialized with session: {self.session_name}")

    async def connect(self) -> bool:
        """Connect to Telegram with enhanced error handling.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("Connecting to Telegram...")
            await self.client.connect()

            if not await self.client.is_user_authorized():
                logger.error("User not authorized. Please run authentication first.")
                return False

            self.is_connected = True
            logger.info("Successfully connected to Telegram")
            return True

        except AuthKeyError as e:
            logger.error(f"Authentication key error: {e}")
            self.is_connected = False
            return False

        except FloodWaitError as e:
            logger.error(f"Flood wait error, need to wait {e.seconds} seconds: {e}")
            self.is_connected = False
            return False

        except Exception as e:
            logger.error(f"Unexpected error connecting to Telegram: {e}")
            self.is_connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from Telegram gracefully."""
        if not self.is_connected:
            logger.debug("Already disconnected from Telegram")
            return

        try:
            logger.info("Disconnecting from Telegram...")
            await self.client.disconnect()
            logger.info("Successfully disconnected from Telegram")
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
        finally:
            self.is_connected = False

    def setup_message_handler(
        self, channel_configs: List[ChannelConfig], storage: StorageProtocol
    ) -> None:
        """Setup message handler with channel configurations and storage.

        Args:
            channel_configs: List of channels to monitor
            storage: Storage implementation for persisting data
        """
        self.message_handler = MessageHandler(channel_configs, storage)
        logger.info("Message handler configured")

    async def start_listening(self) -> bool:
        """Start listening for messages with enhanced error handling.

        Returns:
            True if listening started successfully, False otherwise
        """
        if not self.is_connected:
            logger.error("Cannot start listening: not connected to Telegram")
            return False

        if self.message_handler is None:
            logger.error("Cannot start listening: message handler not configured")
            return False

        try:
            logger.info("Starting message listener...")

            @self.client.on(events.NewMessage)
            async def event_handler(event: events.NewMessage.Event) -> None:
                """Handle incoming messages with error isolation."""
                try:
                    if self.message_handler:
                        await self.message_handler.handle_message(event.message)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}")
                    # Continue processing other messages despite errors

            self._event_handler = event_handler
            logger.info("Message listener started successfully")
            return True

        except Exception as e:
            logger.error(f"Error starting message listener: {e}")
            return False

    async def stop_listening(self) -> None:
        """Stop listening for messages."""
        if self._event_handler:
            try:
                self.client.remove_event_handler(self._event_handler)
                self._event_handler = None
                logger.info("Message listener stopped")
            except Exception as e:
                logger.error(f"Error stopping message listener: {e}")

    async def run_until_disconnected(self) -> None:
        """Run the client until disconnected."""
        if not self.is_connected:
            logger.error("Cannot run: not connected to Telegram")
            return

        try:
            logger.info("Running Telegram client...")
            await self.client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Error running client: {e}")
        finally:
            await self.stop_listening()

    async def auto_reconnect(self, max_retries: int = 5) -> bool:
        """Attempt to reconnect to Telegram with exponential backoff.

        Args:
            max_retries: Maximum number of reconnection attempts

        Returns:
            True if reconnection successful, False otherwise
        """
        # First check if we're really connected and authorized
        if self.is_connected:
            try:
                if await self.client.is_user_authorized():
                    logger.debug("Already connected and authorized")
                    return True
                else:
                    logger.warning("Connected but not authorized, need to reconnect")
                    self.is_connected = False
            except Exception as e:
                logger.warning(f"Connection check failed: {e}")
                self.is_connected = False

        logger.info(f"Starting auto-reconnect with max {max_retries} retries")
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Reconnection attempt {attempt + 1}/{max_retries}")
                
                # Try to connect
                await self.client.connect()
                
                if await self.client.is_user_authorized():
                    self.is_connected = True
                    logger.info("Auto-reconnect successful")
                    return True
                else:
                    logger.error("User not authorized during reconnect")
                    return False
                    
            except Exception as e:
                logger.warning(f"Reconnection attempt {attempt + 1} failed: {e}")
                
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s, 8s, 16s
                    delay = min(2 ** attempt, 16)
                    logger.info(f"Waiting {delay}s before next attempt")
                    await asyncio.sleep(delay)
        
        logger.error(f"Auto-reconnect failed after {max_retries} attempts")
        return False

    async def handle_connection_error(self, error: Exception) -> Dict[str, Any]:
        """Handle connection errors and determine retry strategy.

        Args:
            error: The connection error that occurred

        Returns:
            Dict with should_retry flag and delay information
        """
        if isinstance(error, AuthKeyError):
            logger.error(f"Authentication key error: {error}")
            return {"should_retry": False, "delay": 0}
        
        elif isinstance(error, FloodWaitError):
            delay = error.seconds
            logger.warning(f"Flood wait error, need to wait {delay} seconds")
            await asyncio.sleep(delay)  # Actually wait for FloodWaitError
            return {"should_retry": True, "delay": delay}
        
        elif isinstance(error, (Exception, type)):
            # Handle both exception instances and exception types
            if isinstance(error, type) and issubclass(error, AuthKeyError):
                logger.error(f"Authentication key error type: {error}")
                return {"should_retry": False, "delay": 0}
            else:
                logger.warning(f"Network error: {error}")
                return {"should_retry": True, "delay": 1}

    async def retry_with_backoff(
        self, 
        func: callable, 
        max_retries: int = 3,
        base_delay: float = 1.0
    ) -> Any:
        """Retry a function with exponential backoff and jitter.

        Args:
            func: The function to retry
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds

        Returns:
            Result of the function if successful

        Raises:
            The last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # Handle both async and sync functions
                result = func()
                if hasattr(result, '__await__'):
                    return await result
                else:
                    return result
            except Exception as e:
                last_exception = e
                
                if attempt == max_retries:
                    logger.error(f"Function failed after {max_retries} retries: {e}")
                    raise e
                
                # Exponential backoff with jitter
                delay = base_delay * (2 ** attempt)
                jitter = random.uniform(0.5, 1.5)  # 50% jitter
                actual_delay = delay * jitter
                
                logger.warning(
                    f"Attempt {attempt + 1} failed, retrying in {actual_delay:.1f}s: {e}"
                )
                await asyncio.sleep(actual_delay)
        
        if last_exception:
            raise last_exception

    async def handle_network_failure(self) -> None:
        """Handle network failure by attempting to reconnect.
        
        This method provides graceful degradation during network issues.
        """
        logger.warning("Handling network failure")
        
        try:
            # Mark as disconnected
            self.is_connected = False
            
            # Attempt to reconnect
            success = await self.auto_reconnect()
            
            if success:
                logger.info("Successfully recovered from network failure")
            else:
                logger.error("Failed to recover from network failure")
                
        except Exception as e:
            logger.error(f"Error during network failure handling: {e}")

    async def run_with_reliability(self) -> bool:
        """Run the listener with full reliability features enabled.

        Returns:
            True if ran successfully, False otherwise
        """
        try:
            # Connect with retry
            if not await self.connect():
                logger.error("Failed to connect to Telegram")
                return False

            # Start listening with retry
            if not await self.start_listening():
                logger.error("Failed to start listening")
                return False

            logger.info("Running with reliability features enabled")
            
            # Run until disconnected with network failure recovery
            while True:
                try:
                    await self.client.run_until_disconnected()
                    break  # Normal exit
                except Exception as e:
                    logger.error(f"Connection lost: {e}")
                    await self.handle_network_failure()
                    
                    # If reconnection failed, exit
                    if not self.is_connected:
                        logger.error("Unable to maintain connection, exiting")
                        return False

            return True
            
        except Exception as e:
            logger.error(f"Error in run_with_reliability: {e}")
            return False

    async def shutdown_gracefully(self, timeout: int = 30) -> None:
        """Shutdown the listener gracefully, completing pending operations.

        Args:
            timeout: Maximum time to wait for pending operations to complete
        """
        logger.info(f"Starting graceful shutdown with {timeout}s timeout")
        
        try:
            # Stop accepting new messages
            await self.stop_listening()
            
            # Process any pending messages
            if self.message_handler and hasattr(self.message_handler, 'pending_messages'):
                pending_count = len(self.message_handler.pending_messages)
                if pending_count > 0:
                    logger.info(f"Processing {pending_count} pending messages")
                    
                    # Set a timeout for processing pending messages
                    async def process_pending():
                        for message in self.message_handler.pending_messages:
                            try:
                                await self.message_handler.handle_message(message)
                            except Exception as e:
                                logger.error(f"Error processing pending message: {e}")
                        self.message_handler.pending_messages.clear()
                    
                    try:
                        await asyncio.wait_for(process_pending(), timeout=timeout)
                        logger.info("Successfully processed all pending messages")
                    except asyncio.TimeoutError:
                        logger.warning(f"Timeout waiting for pending messages, some may be lost")
            
            # Disconnect from Telegram
            await self.disconnect()
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            # Force disconnect as fallback
            try:
                await self.disconnect()
            except Exception:
                pass
