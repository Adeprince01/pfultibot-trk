"""Tests for the message parser module."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from unittest.mock import Mock

import pytest

from src.parser import parse_crypto_call


class TestParseCryptoCall:
    """Test cases for parsing crypto call messages."""

    @pytest.mark.parametrize(
        "message,expected",
        [
            # Standard format with CA
            (
                "🚀 CA: 0x123abc Entry: 45K MC Peak: 180K MC (4x)",
                {
                    "token_name": None,
                    "entry_cap": 45000.0,
                    "peak_cap": 180000.0,
                    "x_gain": 4.0,
                    "vip_x": None,
                },
            ),
            # Format with token name and VIP
            (
                "⚡️ $TOKEN Entry 50k Peak 250k (5x VIP)",
                {
                    "token_name": "TOKEN",
                    "entry_cap": 50000.0,
                    "peak_cap": 250000.0,
                    "x_gain": 5.0,
                    "vip_x": 5.0,
                },
            ),
            # Different formatting variations
            (
                "🔥 $DOGE Entry: 100K MC Peak: 500K MC (5.2x)",
                {
                    "token_name": "DOGE",
                    "entry_cap": 100000.0,
                    "peak_cap": 500000.0,
                    "x_gain": 5.2,
                    "vip_x": None,
                },
            ),
            # Million format
            (
                "💎 Entry 1.5M Peak 7.5M (5x VIP)",
                {
                    "token_name": None,
                    "entry_cap": 1500000.0,
                    "peak_cap": 7500000.0,
                    "x_gain": 5.0,
                    "vip_x": 5.0,
                },
            ),
        ],
    )
    def test_parse_crypto_call_success(self, message: str, expected: dict) -> None:
        """Test successful parsing of crypto call messages.

        Args:
            message: The input message to parse.
            expected: The expected parsed result.
        """
        result = parse_crypto_call(message)
        assert result == expected

    @pytest.mark.parametrize(
        "message",
        [
            "",  # Empty string
            "Just some random text",  # No crypto call pattern
            "Entry: 50k but no peak",  # Missing peak
            "Peak: 100k but no entry",  # Missing entry
            "Entry: abc Peak: def (5x)",  # Invalid numbers
        ],
    )
    def test_parse_crypto_call_invalid_input(self, message: str) -> None:
        """Test parsing with invalid input returns None.

        Args:
            message: Invalid input message.
        """
        result = parse_crypto_call(message)
        assert result is None

    def test_parse_crypto_call_none_input(self) -> None:
        """Test parsing with None input returns None."""
        result = parse_crypto_call(None)
        assert result is None

    def test_parse_crypto_call_whitespace_handling(self) -> None:
        """Test parsing handles extra whitespace correctly."""
        message = "  🚀  Entry:  50k   Peak:  200k  (4x)  "
        expected = {
            "token_name": None,
            "entry_cap": 50000.0,
            "peak_cap": 200000.0,
            "x_gain": 4.0,
            "vip_x": None,
        }
        result = parse_crypto_call(message)
        assert result == expected
