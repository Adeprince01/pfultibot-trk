#!/usr/bin/env python3
"""Test message filtering logic"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.listener import ChannelConfig, MessageHandler
from src.storage.sqlite import SQLiteStorage


# Mock storage for testing
class MockStorage:
    def append_row(self, data):
        pass

    def get_records(self):
        return []

    def close(self):
        pass


# Test messages
test_messages = [
    # Discovery call (what we want to capture)
    """[killer featherless cock (KFC)](https://solscan.io/token/8K4VbtJ6cWVxUfxK1DoFP9g2H1V4cWFF2RrQTqEwpump)
8K4VbtJ6cWVxUfxK1DoFP9g2H1V4cWFF2RrQTqEwpump

Cap: 45.1K | ⌛️ 1h:29m""",
    # Price update messages
    "🎉 **2.1x(3.6x from VIP)** | 💹From **46.0K** ↗️ **94.7K** within **17m**",
    "🎉 **2.7x(4.7x from VIP)** | 💹From **46.0K** ↗️ **125.0K** within **19m**",
]

# Create handler
channels = [ChannelConfig(channel_id=-1002380293749, channel_name="Test")]
handler = MessageHandler(channels, MockStorage())

print("🔍 MESSAGE FILTER TEST")
print("=" * 50)

for i, message in enumerate(test_messages, 1):
    print(f"\n📝 MESSAGE {i}:")
    print("Text:", repr(message[:60] + "..." if len(message) > 60 else message))

    is_crypto_call = handler.is_crypto_call_message(message)

    if is_crypto_call:
        print("✅ FILTER: Would process (crypto call detected)")
    else:
        print("❌ FILTER: Would ignore (not detected as crypto call)")

    # Show what keywords it's looking for
    message_lower = message.lower()
    has_entry = "entry" in message_lower
    has_peak = "peak" in message_lower
    has_cap = "cap" in message_lower

    print(f"   Keywords: entry={has_entry}, peak={has_peak}, cap={has_cap}")
