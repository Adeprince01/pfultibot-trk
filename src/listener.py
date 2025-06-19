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

            logger.debug(f"Processing message {message.id} from channel {message.chat_id} ({channel_name})")
            
            # Store raw message for analysis BEFORE any filtering
            if hasattr(self.storage, 'store_raw_message'):
                raw_message_data = {
                    "message_id": message.id,
                    "channel_id": message.chat_id,
                    "channel_name": getattr(message.chat, 'title', str(message.chat_id)),
                    "message_text": message.text or "",
                    "message_date": message.date,
                    "reply_to_message_id": message.reply_to.reply_to_msg_id if message.reply_to else None,
                }
                try:
                    # Use the dedicated method if storage supports it
                    self.storage.store_raw_message(raw_message_data)
                    logger.info(f"✅ Raw message {message.id} stored: {(message.text or '')[:50]}...")
                except Exception as e:
                    logger.error(f"❌ Failed to store raw message {message.id}: {e}")
            else:
                logger.warning(f"❌ Storage does not support store_raw_message method!")

            # SECOND: Attempt classification and parsing
            crypto_call_detected = False
            
            # Check if message appears to be a crypto call
            if self.is_crypto_call_message(message.text):
                logger.debug(f"Message {message.id} appears to be a crypto call, attempting to parse")
                
                # Parse the crypto call with enhanced error handling
                try:
                    parsed_data = parse_crypto_call(message.text)
                    
                    if parsed_data:
                        # --- START: NEW LINKING AND INHERITANCE LOGIC ---
                        
                        # Check if this is a reply to another message
                        if message.reply_to and message.reply_to.reply_to_msg_id:
                            # Use the storage layer to find the original call's database ID
                            original_call_id = self.storage.get_crypto_call_by_message_id(
                                message.reply_to.reply_to_msg_id
                            )
                            
                            if original_call_id:
                                # This is a confirmed update to an existing call.
                                # Set the link in our parsed data.
                                parsed_data['linked_crypto_call_id'] = original_call_id
                                
                                # Inherit token name if the update doesn't have one (e.g., "bonded" or "2.5x" messages)
                                if not parsed_data.get('token_name'):
                                    # We need to fetch the original call to get its name
                                    original_call = self.storage.get_crypto_call_by_id(original_call_id)
                                    if original_call and original_call.get('token_name'):
                                        parsed_data['token_name'] = original_call['token_name']
                                        logger.info(f"Inherited token '{parsed_data['token_name']}' for update message {message.id}")
                                
                                logger.info(f"✅ Linked update message {message.id} to discovery call ID {original_call_id}")
                            else:
                                logger.debug(f"Message {message.id} is a reply, but no matching discovery call found for message {message.reply_to.reply_to_msg_id}")

                        # --- END: NEW LINKING AND INHERITANCE LOGIC ---

                        # Format data for storage with all required metadata
                        channel_config = self.get_channel_config(message.chat_id)
                        channel_name = channel_config.channel_name if channel_config else "Unknown"
                        
                        storage_data = {
                            "token_name": parsed_data.get("token_name"),
                            "entry_cap": parsed_data.get("entry_cap"),
                            "peak_cap": parsed_data.get("peak_cap"),
                            "x_gain": parsed_data.get("x_gain"),
                            "vip_x": parsed_data.get("vip_x"),
                            "message_type": parsed_data.get("message_type"),
                            "contract_address": parsed_data.get("contract_address"),
                            "time_to_peak": parsed_data.get("time_to_peak"),
                            "linked_crypto_call_id": parsed_data.get("linked_crypto_call_id"),
                            "message_id": message.id,
                            "channel_name": channel_name,
                            "timestamp": datetime.now().isoformat(),
                        }
                        
                        # Apply rate limiting and store the data
                        await self.apply_rate_limit(message.chat_id)
                        self.storage.append_row(storage_data)
                        
                        logger.info(f"Successfully processed and stored crypto call from message {message.id}")
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
    """Telegram client wrapper for listening to crypto call channels."""

    def __init__(self, settings: Any) -> None:
        """Initialize Telegram listener with API settings.

        Args:
            settings: Application settings with API ID, hash, and session name
        """
        self.api_id = settings.api_id
        self.api_hash = settings.api_hash
        self.session_name = settings.tg_session
        self.client = TelegramClient(self.session_name, self.api_id, self.api_hash)
        self.is_connected = self.client.is_connected()
        self.message_handler: Optional[MessageHandler] = None
        self.active_channels: List[int] = []

        logger.info(f"TelegramListener initialized with session: {self.session_name}")

    async def connect(self) -> bool:
        """Connect to Telegram and authenticate if necessary.

        Returns:
            True if connection is successful, False otherwise
            
        Raises:
            Exception: If connection fails after retries
        """
        if self.client.is_connected():
            logger.info("Already connected to Telegram")
            return True

        try:
            # Connect to client
            await self.client.connect()
            
            # Check if user is authorized
            if not await self.client.is_user_authorized():
                logger.warning("User is not authorized. Manual authentication required.")
                # Add authentication logic if needed (e.g., phone, password, 2FA)
                # For now, we assume authentication is handled
                
            self.is_connected = True
            logger.info("Successfully connected to Telegram")
            return True

        except AuthKeyError:
            logger.error(f"Authentication key error: {AuthKeyError}")
            self.is_connected = False
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Telegram: {e}")
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
    ) -> bool:
        """Setup message handler with channel configurations and storage.

        Args:
            channel_configs: List of channels to monitor
            storage: Storage implementation for persisting data
        """
        self.message_handler = MessageHandler(channel_configs, storage)
        logger.info("Message handler configured")

        try:
            active_channels = [config.channel_id for config in channel_configs if config.is_active]
            
            @self.client.on(events.NewMessage(chats=active_channels))
            async def event_handler(event: events.NewMessage.Event) -> None:
                """Main event handler for new messages."""
                message = event.message
                logger.debug(f"Received message {message.id} from channel {message.chat_id}")
                
                # Add to pending messages for graceful shutdown
                self.message_handler.pending_messages.append(message)
                
                # Handle message with retry logic
                await self.message_handler.handle_message_with_retry(message)
                
                # Remove from pending after handling
                self.message_handler.pending_messages.remove(message)
        
        except Exception as e:
            logger.error(f"Error setting up message handler: {e}")
            return False
            
        return True

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
            # The event handler was already set up in setup_message_handler
            logger.info("Message listener started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting message listener: {e}")
            return False

    async def stop_listening(self) -> None:
        """Stop listening for new messages."""
        if self.client and self.client.is_connected():
            logger.info("Stopping message listeners...")
            self.client.remove_event_handler(self.event_handler)
            logger.info("Message listeners stopped")

    async def run_until_disconnected(self) -> None:
        """Run client until it is disconnected."""
        if self.client:
            await self.client.run_until_disconnected()

    async def auto_reconnect(self, max_retries: int = 5) -> bool:
        """Automatically reconnect to Telegram with exponential backoff.

        Args:
            max_retries: Maximum number of reconnection attempts

        Returns:
            True if reconnection is successful, False otherwise
        """
        logger.warning("Connection lost, attempting to reconnect...")
        for i in range(max_retries):
            try:
                delay = (2 ** i) + random.uniform(0, 1)
                logger.info(f"Reconnection attempt {i + 1}/{max_retries} in {delay:.2f} seconds...")
                await asyncio.sleep(delay)

                if await self.connect():
                    logger.info("✅ Reconnection successful")
                    return True
            except Exception as e:
                logger.error(f"Reconnection attempt {i + 1} failed: {e}")

        logger.error("Failed to reconnect after all attempts")
        return False

    async def handle_connection_error(self, error: Exception) -> Dict[str, Any]:
        """Handle connection-related errors with structured responses.

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
            if not await self.setup_message_handler(self.get_active_channels(), self.storage):
                logger.error("Failed to start listening")
                return False

            logger.info("Running with reliability features enabled")
            
            # Run until disconnected with network failure recovery
            while True:
                try:
                    await self.run_until_disconnected()
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
