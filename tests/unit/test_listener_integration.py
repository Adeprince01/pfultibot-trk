"""Integration tests for Listener Module Phase 2: Parser and Storage Integration.

These tests focus on the integration layer between the listener, parser, and storage
components, emphasizing error handling and graceful degradation.
"""

from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.listener import ChannelConfig, MessageHandler
from src.parser import parse_crypto_call
from src.storage import StorageProtocol


class MockStorage:
    """Mock storage implementation for testing."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.stored_calls: List[Dict[str, Any]] = []

    def append_row(self, data: Dict[str, Any]) -> None:
        """Mock append_row method matching StorageProtocol."""
        if self.should_fail:
            raise Exception("Storage failure")
        self.stored_calls.append(data)

    def get_records(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Mock get_records method."""
        return self.stored_calls[:limit] if limit else self.stored_calls

    def close(self) -> None:
        """Mock close method."""
        pass


class TestParserIntegration:
    """Test parser integration with enhanced error handling."""

    @pytest.fixture
    def channel_configs(self) -> List[ChannelConfig]:
        """Test channel configurations."""
        return [
            ChannelConfig(
                channel_id=-1001234567890, channel_name="test_channel", is_active=True
            )
        ]

    @pytest.fixture
    def mock_storage(self):
        """Mock storage for testing."""
        return MockStorage()

    @pytest.fixture
    def message_handler(self, channel_configs, mock_storage):
        """Message handler with mock storage."""
        return MessageHandler(channel_configs, mock_storage)

    @pytest.mark.parametrize(
        "message_text,should_parse_successfully,expected_token",
        [
            ("🚀 $TOKEN Entry: 45K MC Peak: 180K MC (4x)", True, "TOKEN"),
            ("⚡️ Entry 50k Peak 250k (5x VIP)", True, None),
            ("CA: 0x123 Entry: 100K MC Peak: 400K MC (4x)", True, None),
            ("Invalid message with no structure", False, None),
            ("Entry: Peak: (incomplete)", False, None),
            ("Entry: 50K Peak: (missing peak value)", False, None),
            ("", False, None),
        ],
    )
    @pytest.mark.asyncio
    async def test_parser_integration_various_messages(
        self, message_handler, message_text, should_parse_successfully, expected_token
    ):
        """Test parser integration with various message formats."""
        # Create mock message
        mock_message = Mock()
        mock_message.text = message_text
        mock_message.chat_id = -1001234567890
        mock_message.id = 12345

        # Process message
        result = await message_handler.handle_message(mock_message)

        if should_parse_successfully:
            assert result is True
            # Verify data was stored
            stored_data = message_handler.storage.stored_calls[-1]
            assert stored_data["token_name"] == expected_token
            assert "entry_cap" in stored_data
            assert "peak_cap" in stored_data
            assert "x_gain" in stored_data
        else:
            assert result is False

    @pytest.mark.asyncio
    async def test_parser_error_handling(self, message_handler):
        """Test graceful handling of parser errors."""
        mock_message = Mock()
        mock_message.text = "🚀 Entry: 45K MC Peak: 180K MC (4x)"
        mock_message.chat_id = -1001234567890
        mock_message.id = 12345

        # Mock parser to raise exception
        with patch("src.listener.parse_crypto_call") as mock_parser:
            mock_parser.side_effect = ValueError("Parser error")

            result = await message_handler.handle_message(mock_message)

            # Should handle error gracefully
            assert result is False
            # Storage should not be called
            assert len(message_handler.storage.stored_calls) == 0

    @pytest.mark.asyncio
    async def test_parser_returns_none(self, message_handler):
        """Test handling when parser returns None."""
        mock_message = Mock()
        mock_message.text = "Unparseable message"
        mock_message.chat_id = -1001234567890
        mock_message.id = 12345

        # Mock parser to return None
        with patch("src.listener.parse_crypto_call") as mock_parser:
            mock_parser.return_value = None

            result = await message_handler.handle_message(mock_message)

            assert result is False
            assert len(message_handler.storage.stored_calls) == 0


class TestStorageIntegration:
    """Test storage integration with enhanced error handling."""

    @pytest.fixture
    def channel_configs(self) -> List[ChannelConfig]:
        """Test channel configurations."""
        return [
            ChannelConfig(
                channel_id=-1001234567890, channel_name="test_channel", is_active=True
            )
        ]

    @pytest.mark.asyncio
    async def test_storage_success(self, channel_configs):
        """Test successful storage of crypto call data."""
        mock_storage = MockStorage()
        message_handler = MessageHandler(channel_configs, mock_storage)

        mock_message = Mock()
        mock_message.text = "🚀 Entry: 45K MC Peak: 180K MC (4x)"
        mock_message.chat_id = -1001234567890
        mock_message.id = 12345

        result = await message_handler.handle_message(mock_message)

        assert result is True
        assert len(mock_storage.stored_calls) == 1

        stored_data = mock_storage.stored_calls[0]
        assert "token_name" in stored_data
        assert "entry_cap" in stored_data
        assert "peak_cap" in stored_data
        assert "x_gain" in stored_data
        assert "message_id" in stored_data
        assert "channel_id" in stored_data

    @pytest.mark.asyncio
    async def test_storage_failure_handling(self, channel_configs):
        """Test graceful handling of storage failures."""
        # Create storage that will fail
        mock_storage = MockStorage(should_fail=True)
        message_handler = MessageHandler(channel_configs, mock_storage)

        mock_message = Mock()
        mock_message.text = "🚀 Entry: 45K MC Peak: 180K MC (4x)"
        mock_message.chat_id = -1001234567890
        mock_message.id = 12345

        result = await message_handler.handle_message(mock_message)

        # Should handle storage failure gracefully
        assert result is False
        # No data should be stored due to failure
        assert len(mock_storage.stored_calls) == 0

    @pytest.mark.asyncio
    async def test_storage_data_format(self, channel_configs):
        """Test that data is formatted correctly for storage."""
        mock_storage = MockStorage()
        message_handler = MessageHandler(channel_configs, mock_storage)

        mock_message = Mock()
        mock_message.text = "🚀 $TOKEN Entry: 50K MC Peak: 250K MC (5x VIP)"
        mock_message.chat_id = -1001234567890
        mock_message.id = 12345

        result = await message_handler.handle_message(mock_message)

        assert result is True
        stored_data = mock_storage.stored_calls[0]

        # Verify all required fields are present
        required_fields = [
            "token_name",
            "entry_cap",
            "peak_cap",
            "x_gain",
            "vip_x",
            "message_id",
            "channel_id",
            "channel_name",
            "timestamp",
        ]
        for field in required_fields:
            assert field in stored_data

        # Verify data types
        assert isinstance(stored_data["entry_cap"], float)
        assert isinstance(stored_data["peak_cap"], float)
        assert isinstance(stored_data["x_gain"], float)
        assert isinstance(stored_data["message_id"], int)
        assert isinstance(stored_data["channel_id"], int)

    @pytest.mark.asyncio
    async def test_multiple_storage_calls(self, channel_configs):
        """Test handling multiple storage calls."""
        mock_storage = MockStorage()
        message_handler = MessageHandler(channel_configs, mock_storage)

        messages = [
            "🚀 Entry: 45K MC Peak: 180K MC (4x)",
            "⚡️ $TOKEN Entry: 50K MC Peak: 250K MC (5x)",
            "CA: 0x123 Entry: 100K MC Peak: 400K MC (4x)",
        ]

        for i, message_text in enumerate(messages):
            mock_message = Mock()
            mock_message.text = message_text
            mock_message.chat_id = -1001234567890
            mock_message.id = 12345 + i

            result = await message_handler.handle_message(mock_message)
            assert result is True

        assert len(mock_storage.stored_calls) == 3

        # Verify each message was stored correctly
        for i, stored_data in enumerate(mock_storage.stored_calls):
            assert stored_data["message_id"] == 12345 + i


class TestIntegrationErrorRecovery:
    """Test error recovery and resilience in integration scenarios."""

    @pytest.fixture
    def channel_configs(self) -> List[ChannelConfig]:
        """Test channel configurations."""
        return [
            ChannelConfig(
                channel_id=-1001234567890, channel_name="test_channel", is_active=True
            )
        ]

    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self, channel_configs):
        """Test recovery from partial failures."""

        # Storage that fails on first call, succeeds on second
        class FlakeyStorage(MockStorage):
            def __init__(self):
                super().__init__()
                self.call_count = 0

            def append_row(self, data: Dict[str, Any]) -> None:
                self.call_count += 1
                if self.call_count == 1:
                    raise Exception("First call fails")
                super().append_row(data)

        flakey_storage = FlakeyStorage()
        message_handler = MessageHandler(channel_configs, flakey_storage)

        # First message should fail
        mock_message1 = Mock()
        mock_message1.text = "🚀 Entry: 45K MC Peak: 180K MC (4x)"
        mock_message1.chat_id = -1001234567890
        mock_message1.id = 12345

        result1 = await message_handler.handle_message(mock_message1)
        assert result1 is False

        # Second message should succeed
        mock_message2 = Mock()
        mock_message2.text = "⚡️ Entry: 50K MC Peak: 250K MC (5x)"
        mock_message2.chat_id = -1001234567890
        mock_message2.id = 12346

        result2 = await message_handler.handle_message(mock_message2)
        assert result2 is True
        assert len(flakey_storage.stored_calls) == 1

    @pytest.mark.asyncio
    async def test_invalid_message_object(self, channel_configs):
        """Test handling of invalid message objects."""
        mock_storage = MockStorage()
        message_handler = MessageHandler(channel_configs, mock_storage)

        # Test with None message
        result = await message_handler.handle_message(None)
        assert result is False

        # Test with message missing attributes
        incomplete_message = Mock()
        # Missing required attributes

        try:
            result = await message_handler.handle_message(incomplete_message)
            assert result is False
        except AttributeError:
            # This is acceptable - the handler should be robust
            pass
