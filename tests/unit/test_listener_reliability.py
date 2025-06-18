"""Tests for Listener Module Phase 3: Reliability Features.

These tests focus on connection reliability, network failure handling,
automatic retry mechanisms, and enhanced channel configuration.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, call
from typing import Dict, Any, List, Optional

from telethon.errors import FloodWaitError, AuthKeyError, RPCError
from src.listener import TelegramListener, ChannelConfig, MessageHandler


class TestReconnectionLogic:
    """Test automatic reconnection and connection recovery."""
    
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
    async def test_auto_reconnect_on_connection_loss(self, listener):
        """Test automatic reconnection when connection is lost."""
        mock_client = AsyncMock()
        listener.client = mock_client
        listener.is_connected = True
        
        # Simulate connection loss
        mock_client.is_user_authorized.side_effect = [False, True]  # Lost, then recovered
        mock_client.connect.return_value = None
        
        # Should attempt to reconnect
        result = await listener.auto_reconnect()
        
        assert result is True
        assert mock_client.connect.call_count == 1
        
    @pytest.mark.asyncio
    async def test_auto_reconnect_with_retry_limit(self, listener):
        """Test reconnection with maximum retry attempts."""
        mock_client = AsyncMock()
        listener.client = mock_client
        listener.is_connected = False
        
        # Simulate persistent connection failure  
        mock_client.connect.side_effect = RPCError(None, "Network error")
        
        # Should try multiple times then give up
        result = await listener.auto_reconnect(max_retries=3)
        
        assert result is False
        assert mock_client.connect.call_count == 3
        
    @pytest.mark.asyncio
    async def test_reconnect_with_exponential_backoff(self, listener):
        """Test reconnection uses exponential backoff delays."""
        mock_client = AsyncMock()
        listener.client = mock_client
        listener.is_connected = False
        
        # Mock connection to fail first 2 times, succeed on 3rd
        mock_client.connect.side_effect = [
            RPCError(None, "Network error"),
            RPCError(None, "Network error"), 
            None  # Success
        ]
        mock_client.is_user_authorized.return_value = True
        
        with patch('asyncio.sleep') as mock_sleep:
            result = await listener.auto_reconnect(max_retries=3)
            
            assert result is True
            # Should use exponential backoff: 1s, 2s delays
            expected_calls = [call(1), call(2)]
            mock_sleep.assert_has_calls(expected_calls)


class TestNetworkFailureHandling:
    """Test handling of various network failures and errors."""
    
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
    
    @pytest.mark.parametrize(
        "exception_type,should_retry,expected_delay",
        [
            (RPCError, True, 1),
            (FloodWaitError(None, 30), True, 30),
            (AuthKeyError, False, 0),
            (Exception, True, 1),
        ]
    )
    @pytest.mark.asyncio
    async def test_handle_network_errors(
        self, listener, exception_type, should_retry, expected_delay
    ):
        """Test handling of different network error types."""
        mock_client = AsyncMock()
        listener.client = mock_client
        
        if isinstance(exception_type, FloodWaitError):
            mock_client.connect.side_effect = exception_type
        else:
            mock_client.connect.side_effect = exception_type(None, "Test error")
        
        with patch('asyncio.sleep') as mock_sleep:
            result = await listener.handle_connection_error(exception_type)
            
            if should_retry:
                if expected_delay > 1:
                    mock_sleep.assert_called_with(expected_delay)
                assert result['should_retry'] is True
            else:
                assert result['should_retry'] is False
                
    @pytest.mark.asyncio
    async def test_graceful_degradation_on_network_failure(self, listener):
        """Test system continues operating during network issues."""
        # Setup listener with message handler
        channel_configs = [ChannelConfig(-123, "test", True)]
        mock_storage = Mock()
        listener.setup_message_handler(channel_configs, mock_storage)
        
        # Simulate network failure during message processing
        mock_client = AsyncMock()
        listener.client = mock_client
        listener.is_connected = True
        
        # Should not crash, should log error and continue
        with patch.object(listener, 'auto_reconnect') as mock_reconnect:
            mock_reconnect.return_value = True
            
            await listener.handle_network_failure()
            
            mock_reconnect.assert_called_once()


class TestAutomaticRetryMechanisms:
    """Test retry logic for failed operations."""
    
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
    async def test_retry_failed_message_processing(self, listener):
        """Test retry mechanism for failed message processing."""
        channel_configs = [ChannelConfig(-123, "test", True)]
        mock_storage = Mock()
        mock_storage.append_row.side_effect = [
            Exception("Storage error"),  # First attempt fails
            None  # Second attempt succeeds
        ]
        
        message_handler = MessageHandler(channel_configs, mock_storage)
        
        # Mock message
        mock_message = Mock()
        mock_message.text = "🚀 Entry: 45K MC Peak: 180K MC (4x)"
        mock_message.chat_id = -123
        mock_message.id = 12345
        
        with patch('src.listener.parse_crypto_call') as mock_parse:
            mock_parse.return_value = {
                "token_name": None,
                "entry_cap": 45000.0,
                "peak_cap": 180000.0,
                "x_gain": 4.0,
                "vip_x": None,
            }
            
            # Should retry and eventually succeed
            result = await message_handler.handle_message_with_retry(mock_message, max_retries=2)
            
            assert result is True
            assert mock_storage.append_row.call_count == 2
            
    @pytest.mark.asyncio
    async def test_retry_with_jitter(self, listener):
        """Test retry mechanism includes jitter to avoid thundering herd."""
        with patch('asyncio.sleep') as mock_sleep, \
             patch('random.uniform') as mock_random:
            
            mock_random.return_value = 0.5  # 50% jitter
            
            # Create a function that fails twice then succeeds
            call_count = [0]
            def failing_func():
                call_count[0] += 1
                if call_count[0] < 3:
                    raise Exception("Temporary failure")
                return "success"
            
            await listener.retry_with_backoff(failing_func, max_retries=3)
            
            # Should include random jitter in delays
            assert mock_sleep.call_count >= 1
            mock_random.assert_called()


class TestEnhancedChannelConfiguration:
    """Test enhanced channel configuration and management."""
    
    @pytest.mark.parametrize(
        "config_data,expected_valid",
        [
            ({
                "channel_id": -123,
                "channel_name": "test",
                "is_active": True,
                "retry_count": 3,
                "timeout": 30,
                "priority": "high"
            }, True),
            ({
                "channel_id": -123,
                "channel_name": "test",
                "retry_count": -1  # Invalid retry count
            }, False),
            ({
                "channel_id": "invalid",  # Invalid ID type
                "channel_name": "test",
            }, False),
        ]
    )
    def test_enhanced_channel_config_validation(self, config_data, expected_valid):
        """Test validation of enhanced channel configuration."""
        if expected_valid:
            config = ChannelConfig.from_dict(config_data)
            assert config.channel_id == config_data["channel_id"]
            assert config.channel_name == config_data["channel_name"]
            if "retry_count" in config_data:
                assert config.retry_count == config_data["retry_count"]
        else:
            with pytest.raises((ValueError, TypeError)):
                ChannelConfig.from_dict(config_data)
                
    def test_channel_specific_settings(self):
        """Test channel-specific configuration options."""
        config = ChannelConfig(
            channel_id=-123,
            channel_name="high_priority_channel",
            is_active=True,
            retry_count=5,
            timeout=60,
            priority="high",
            rate_limit=10
        )
        
        assert config.retry_count == 5
        assert config.timeout == 60
        assert config.priority == "high"
        assert config.rate_limit == 10
        
    def test_channel_priority_ordering(self):
        """Test channels can be ordered by priority."""
        channels = [
            ChannelConfig(-1, "low", True, priority="low"),
            ChannelConfig(-2, "high", True, priority="high"),
            ChannelConfig(-3, "medium", True, priority="medium"),
        ]
        
        sorted_channels = ChannelConfig.sort_by_priority(channels)
        
        priorities = [ch.priority for ch in sorted_channels]
        assert priorities == ["high", "medium", "low"]


class TestMultiChannelMonitoring:
    """Test enhanced multi-channel monitoring capabilities."""
    
    @pytest.fixture
    def channel_configs(self):
        """Multiple channel configurations for testing."""
        return [
            ChannelConfig(-1, "channel1", True, priority="high", rate_limit=5),
            ChannelConfig(-2, "channel2", True, priority="medium", rate_limit=10),
            ChannelConfig(-3, "channel3", False, priority="low", rate_limit=15),
        ]
    
    @pytest.fixture
    def mock_storage(self):
        """Mock storage for testing."""
        return Mock()
    
    @pytest.fixture
    def message_handler(self, channel_configs, mock_storage):
        """Message handler with multiple channels."""
        return MessageHandler(channel_configs, mock_storage)
    
    def test_active_channel_filtering(self, message_handler):
        """Test filtering of only active channels."""
        active_channels = message_handler.get_active_channels()
        
        assert len(active_channels) == 2  # Only 2 are active
        channel_ids = [ch.channel_id for ch in active_channels]
        assert -1 in channel_ids
        assert -2 in channel_ids
        assert -3 not in channel_ids  # Inactive
        
    def test_priority_based_processing(self, message_handler):
        """Test messages processed based on channel priority."""
        # Create messages from different priority channels
        high_priority_msg = Mock()
        high_priority_msg.chat_id = -1  # High priority channel
        high_priority_msg.id = 1
        
        medium_priority_msg = Mock()
        medium_priority_msg.chat_id = -2  # Medium priority channel
        medium_priority_msg.id = 2
        
        # High priority should be processed first
        processing_order = message_handler.get_processing_order([
            medium_priority_msg, high_priority_msg
        ])
        
        assert processing_order[0].chat_id == -1  # High priority first
        assert processing_order[1].chat_id == -2  # Medium priority second
        
    @pytest.mark.asyncio
    async def test_rate_limiting_per_channel(self, message_handler):
        """Test rate limiting applied per channel."""
        # Mock rate limiter
        with patch.object(message_handler, 'apply_rate_limit') as mock_rate_limit:
            mock_rate_limit.return_value = True
            
            mock_message = Mock()
            mock_message.chat_id = -1
            mock_message.id = 123
            mock_message.text = "🚀 Entry: 45K MC Peak: 180K MC (4x)"
            
            await message_handler.handle_message(mock_message)
            
            # Should apply rate limiting for channel -1
            mock_rate_limit.assert_called_with(-1)
            
    def test_channel_health_monitoring(self, message_handler):
        """Test monitoring of channel health and statistics."""
        # Simulate message processing
        message_handler.record_channel_stats(-1, success=True, processing_time=0.1)
        message_handler.record_channel_stats(-1, success=False, processing_time=0.5)
        message_handler.record_channel_stats(-2, success=True, processing_time=0.2)
        
        stats_ch1 = message_handler.get_channel_stats(-1)
        stats_ch2 = message_handler.get_channel_stats(-2)
        
        # Channel -1: 1 success, 1 failure = 50% success rate
        assert stats_ch1['successful_messages'] == 1
        assert stats_ch1['failed_messages'] == 1
        assert stats_ch1['average_processing_time'] == 0.3  # (0.1 + 0.5) / 2
        
        # Channel -2: 1 success, 0 failures = 100% success rate  
        assert stats_ch2['successful_messages'] == 1
        assert stats_ch2['failed_messages'] == 0


class TestReliabilityIntegration:
    """Test integration of all reliability features working together."""
    
    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        mock_settings = Mock()
        mock_settings.api_id = 12345
        mock_settings.api_hash = "test_hash"
        mock_settings.tg_session = "test_session" 
        return mock_settings
    
    @pytest.fixture
    def listener_with_reliability(self, mock_settings):
        """Listener with all reliability features enabled."""
        listener = TelegramListener(mock_settings)
        
        # Configure with multiple channels
        channels = [
            ChannelConfig(-1, "priority_channel", True, priority="high", retry_count=3),
            ChannelConfig(-2, "normal_channel", True, priority="medium", retry_count=2),
        ]
        mock_storage = Mock()
        listener.setup_message_handler(channels, mock_storage)
        
        return listener
    
    @pytest.mark.asyncio
    async def test_end_to_end_reliability(self, listener_with_reliability):
        """Test complete reliability scenario: network failure → reconnect → retry → success."""
        listener = listener_with_reliability
        mock_client = AsyncMock()
        listener.client = mock_client
        
        # Mock the client.on() decorator to work properly
        def mock_on_decorator(event_type):
            def decorator(func):
                return func  # Just return the function unchanged
            return decorator
        
        mock_client.on = mock_on_decorator
        mock_client.remove_event_handler = AsyncMock()
        mock_client.run_until_disconnected = AsyncMock()
        
        # Simulate initial connection success
        mock_client.is_user_authorized.return_value = True
        listener.is_connected = True
        
        # Test the complete reliability flow
        with patch.object(listener, 'auto_reconnect') as mock_reconnect, \
             patch('asyncio.sleep'):
            
            mock_reconnect.return_value = True
            
            # Should handle network failure and recover
            result = await listener.run_with_reliability()
            
            assert result is True
            
    @pytest.mark.asyncio 
    async def test_graceful_shutdown_with_pending_operations(self, listener_with_reliability):
        """Test graceful shutdown doesn't lose pending operations."""
        listener = listener_with_reliability
        
        # Simulate pending operations
        pending_messages = [Mock(), Mock(), Mock()]
        listener.message_handler.pending_messages = pending_messages
        
        # Should complete pending operations before shutdown
        await listener.shutdown_gracefully(timeout=30)
        
        # All pending messages should be processed
        assert len(listener.message_handler.pending_messages) == 0 