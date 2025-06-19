"""Tests for the Telegram listener module."""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest
from telethon import TelegramClient, events
from telethon.errors import AuthKeyError, FloodWaitError
from telethon.tl.types import Channel, Chat, Message, User

from src.listener import ChannelConfig, MessageHandler, TelegramListener


class TestTelegramListener:
    """Test cases for TelegramListener class."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        mock_settings = Mock()
        mock_settings.api_id = 12345
        mock_settings.api_hash = "test_hash"
        mock_settings.tg_session = "test_session"
        return mock_settings

    @pytest.fixture
    def listener(self, mock_settings):
        """Create a TelegramListener instance for testing."""
        return TelegramListener(mock_settings)

    @pytest.mark.asyncio
    async def test_listener_initialization(self, listener, mock_settings):
        """Test that listener initializes with correct settings."""
        assert listener.api_id == mock_settings.api_id
        assert listener.api_hash == mock_settings.api_hash
        assert listener.session_name == mock_settings.tg_session
        assert listener.client is not None
        assert listener.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_success(self, listener):
        """Test successful connection to Telegram."""
        # Setup mock client (replace the existing client)
        mock_client = AsyncMock()
        mock_client.connect.return_value = None
        mock_client.is_user_authorized.return_value = True
        listener.client = mock_client

        # Test connection
        result = await listener.connect()

        assert result is True
        assert listener.is_connected is True
        mock_client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_auth_error(self, listener):
        """Test connection with authentication error."""
        # Setup mock client to raise auth error
        mock_client = AsyncMock()
        mock_client.connect.side_effect = AuthKeyError(None, "Auth failed")
        listener.client = mock_client

        # Test connection failure
        result = await listener.connect()

        assert result is False
        assert listener.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_flood_wait_error(self, listener):
        """Test connection with flood wait error."""
        # Setup mock client to raise flood wait error
        mock_client = AsyncMock()
        mock_client.connect.side_effect = FloodWaitError(None, 60)
        listener.client = mock_client

        # Test connection failure
        result = await listener.connect()

        assert result is False
        assert listener.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect_success(self, listener):
        """Test successful disconnection from Telegram."""
        # Setup connected state
        listener.client = AsyncMock()
        listener.is_connected = True

        # Test disconnection
        await listener.disconnect()

        assert listener.is_connected is False
        listener.client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_when_not_connected(self, listener):
        """Test disconnect when already disconnected."""
        # Ensure not connected
        listener.is_connected = False
        listener.client = AsyncMock()

        # Test disconnection
        await listener.disconnect()

        # Should not call disconnect on client
        listener.client.disconnect.assert_not_called()

    @pytest.mark.asyncio
    async def test_disconnect_with_client_error(self, listener):
        """Test disconnect handling client errors gracefully."""
        # Setup connected state with failing client
        listener.client = AsyncMock()
        listener.client.disconnect.side_effect = Exception("Connection error")
        listener.is_connected = True

        # Test disconnection (should not raise)
        await listener.disconnect()

        # Should still mark as disconnected
        assert listener.is_connected is False


class TestMessageHandler:
    """Test cases for MessageHandler class."""

    @pytest.fixture
    def channel_configs(self) -> List[ChannelConfig]:
        """Mock channel configurations for testing."""
        return [
            ChannelConfig(
                channel_id=-1001234567890,
                channel_name="test_crypto_channel",
                is_active=True,
                keywords=["Entry", "Peak", "x"],
            ),
            ChannelConfig(
                channel_id=-1001234567891,
                channel_name="test_inactive_channel",
                is_active=False,
                keywords=["Entry", "Peak"],
            ),
        ]

    @pytest.fixture
    def mock_storage(self):
        """Mock storage interface for testing."""
        return Mock()

    @pytest.fixture
    def message_handler(self, channel_configs, mock_storage):
        """Create a MessageHandler instance for testing."""
        return MessageHandler(channel_configs, mock_storage)

    @pytest.fixture
    def mock_message(self):
        """Create a mock Telegram message for testing."""
        message = Mock(spec=Message)
        message.text = "🚀 CA: 0x123 Entry: 45K MC Peak: 180K MC (4x)"
        message.chat_id = -1001234567890
        message.id = 12345
        message.date = Mock()
        message.from_id = Mock()
        return message

    @pytest.fixture
    def mock_non_crypto_message(self):
        """Create a mock non-crypto Telegram message for testing."""
        message = Mock(spec=Message)
        message.text = "Hello everyone! How are you today?"
        message.chat_id = -1001234567890
        message.id = 12346
        message.date = Mock()
        message.from_id = Mock()
        return message

    @pytest.mark.parametrize(
        "message_text,expected_is_crypto",
        [
            ("🚀 CA: 0x123 Entry: 45K MC Peak: 180K MC (4x)", True),
            ("⚡️ $TOKEN Entry 50k Peak 250k (5x VIP)", True),
            ("Entry: 100K MC Peak: 500K MC (5x)", True),
            ("Hello everyone! How are you today?", False),
            ("Just a regular message with no crypto keywords", False),
            ("This mentions Entry but not in the right context", False),
            ("", False),
            (None, False),
        ],
    )
    def test_is_crypto_call_message(
        self, message_handler, message_text, expected_is_crypto
    ):
        """Test crypto call message detection with various inputs."""
        result = message_handler.is_crypto_call_message(message_text)
        assert result == expected_is_crypto

    def test_is_channel_active(self, message_handler):
        """Test active channel detection."""
        # Active channel
        assert message_handler.is_channel_active(-1001234567890) is True

        # Inactive channel
        assert message_handler.is_channel_active(-1001234567891) is False

        # Unknown channel
        assert message_handler.is_channel_active(-1001234567892) is False

    def test_get_channel_config(self, message_handler, channel_configs):
        """Test channel configuration retrieval."""
        # Known active channel
        config = message_handler.get_channel_config(-1001234567890)
        assert config is not None
        assert config.channel_name == "test_crypto_channel"
        assert config.is_active is True

        # Known inactive channel
        config = message_handler.get_channel_config(-1001234567891)
        assert config is not None
        assert config.channel_name == "test_inactive_channel"
        assert config.is_active is False

        # Unknown channel
        config = message_handler.get_channel_config(-1001234567892)
        assert config is None

    @pytest.mark.asyncio
    async def test_handle_message_crypto_call(
        self, message_handler, mock_message, mock_storage
    ):
        """Test handling of crypto call messages."""
        with patch("src.listener.parse_crypto_call") as mock_parse:
            mock_parse.return_value = {
                "token_name": None,
                "entry_cap": 45000.0,
                "peak_cap": 180000.0,
                "x_gain": 4.0,
                "vip_x": None,
            }

            result = await message_handler.handle_message(mock_message)

            assert result is True
            mock_parse.assert_called_once_with(mock_message.text)
            mock_storage.append_row.assert_called_once()

            # Verify the data passed to storage includes metadata
            call_args = mock_storage.append_row.call_args[0][0]
            assert "token_name" in call_args
            assert "entry_cap" in call_args
            assert "message_id" in call_args
            assert "channel_id" in call_args
            assert "timestamp" in call_args

    @pytest.mark.asyncio
    async def test_handle_message_non_crypto(
        self, message_handler, mock_non_crypto_message, mock_storage
    ):
        """Test handling of non-crypto messages."""
        result = await message_handler.handle_message(mock_non_crypto_message)

        assert result is False
        mock_storage.append_row.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_inactive_channel(self, message_handler, mock_storage):
        """Test handling messages from inactive channels."""
        # Create message from inactive channel
        message = Mock(spec=Message)
        message.text = "🚀 CA: 0x123 Entry: 45K MC Peak: 180K MC (4x)"
        message.chat_id = -1001234567891  # Inactive channel
        message.id = 12345
        message.date = Mock()
        message.from_id = Mock()

        result = await message_handler.handle_message(message)

        assert result is False
        mock_storage.append_row.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_unknown_channel(self, message_handler, mock_storage):
        """Test handling messages from unknown channels."""
        # Create message from unknown channel
        message = Mock(spec=Message)
        message.text = "🚀 CA: 0x123 Entry: 45K MC Peak: 180K MC (4x)"
        message.chat_id = -1001234567892  # Unknown channel
        message.id = 12345
        message.date = Mock()
        message.from_id = Mock()

        result = await message_handler.handle_message(message)

        assert result is False
        mock_storage.append_row.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_parse_error(
        self, message_handler, mock_message, mock_storage
    ):
        """Test handling when parser fails."""
        with patch("src.listener.parse_crypto_call") as mock_parse:
            mock_parse.return_value = None  # Parser failed

            result = await message_handler.handle_message(mock_message)

            assert result is False
            mock_storage.append_row.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_message_storage_error(
        self, message_handler, mock_message, mock_storage
    ):
        """Test handling when storage fails."""
        with patch("src.listener.parse_crypto_call") as mock_parse:
            mock_parse.return_value = {
                "token_name": None,
                "entry_cap": 45000.0,
                "peak_cap": 180000.0,
                "x_gain": 4.0,
                "vip_x": None,
            }
            mock_storage.append_row.side_effect = Exception("Storage failed")

            # Should not raise, but should log the error
            result = await message_handler.handle_message(mock_message)

            assert result is False


class TestTelegramListenerWithMessageHandler:
    """Test cases for TelegramListener with message handling capabilities."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        mock_settings = Mock()
        mock_settings.api_id = 12345
        mock_settings.api_hash = "test_hash"
        mock_settings.tg_session = "test_session"
        return mock_settings

    @pytest.fixture
    def channel_configs(self):
        """Mock channel configurations for testing."""
        return [
            ChannelConfig(
                channel_id=-1001234567890,
                channel_name="test_crypto_channel",
                is_active=True,
                keywords=["Entry", "Peak", "x"],
            )
        ]

    @pytest.fixture
    def mock_storage(self):
        """Mock storage interface for testing."""
        return Mock()

    @pytest.fixture
    def listener_with_handler(self, mock_settings, channel_configs, mock_storage):
        """Create a TelegramListener with message handler for testing."""
        listener = TelegramListener(mock_settings)
        listener.setup_message_handler(channel_configs, mock_storage)
        return listener

    def test_setup_message_handler(self, listener_with_handler):
        """Test message handler setup."""
        assert listener_with_handler.message_handler is not None
        assert isinstance(listener_with_handler.message_handler, MessageHandler)

    @pytest.mark.asyncio
    async def test_start_listening(self, listener_with_handler):
        """Test starting message listening."""
        # Mock the client and its 'on' method
        mock_client = AsyncMock()
        mock_on_decorator = Mock()
        mock_client.on = Mock(return_value=mock_on_decorator)
        listener_with_handler.client = mock_client
        listener_with_handler.is_connected = True

        # Test starting listener
        result = await listener_with_handler.start_listening()

        # Verify start was successful
        assert result is True
        # Verify client.on was called with NewMessage event class
        from telethon import events

        mock_client.on.assert_called_once()
        call_args = mock_client.on.call_args[0][0]
        assert call_args == events.NewMessage

    @pytest.mark.asyncio
    async def test_stop_listening(self, listener_with_handler):
        """Test stopping message listening."""
        # Mock the client
        mock_client = AsyncMock()
        listener_with_handler.client = mock_client
        listener_with_handler.is_connected = True

        # Set up an event handler to remove
        mock_handler = Mock()
        listener_with_handler._event_handler = mock_handler

        # Test stopping listener
        await listener_with_handler.stop_listening()

        # Verify event handler was removed
        mock_client.remove_event_handler.assert_called_once_with(mock_handler)
        # Verify handler reference was cleared
        assert listener_with_handler._event_handler is None

    @pytest.mark.asyncio
    async def test_start_listening_not_connected(self, listener_with_handler):
        """Test starting listening when not connected."""
        listener_with_handler.is_connected = False

        result = await listener_with_handler.start_listening()

        assert result is False

    @pytest.mark.asyncio
    async def test_start_listening_no_handler(self, mock_settings):
        """Test starting listening without message handler setup."""
        listener = TelegramListener(mock_settings)
        listener.is_connected = True

        result = await listener.start_listening()

        assert result is False


class TestChannelConfig:
    """Test cases for ChannelConfig dataclass."""

    def test_channel_config_creation(self):
        """Test ChannelConfig creation."""
        config = ChannelConfig(
            channel_id=-1001234567890,
            channel_name="test_channel",
            is_active=True,
            keywords=["Entry", "Peak", "x"],
        )

        assert config.channel_id == -1001234567890
        assert config.channel_name == "test_channel"
        assert config.is_active is True
        assert config.keywords == ["Entry", "Peak", "x"]

    def test_channel_config_defaults(self):
        """Test ChannelConfig with default values."""
        config = ChannelConfig(channel_id=-1001234567890, channel_name="test_channel")

        assert config.is_active is True
        assert config.keywords == ["Entry", "Peak", "x"]
