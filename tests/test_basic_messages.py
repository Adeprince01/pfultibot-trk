#!/usr/bin/env python3
"""Basic Message Test - Capture ALL messages from @pfultimate

This script is for debugging - it captures ALL messages from the channel
to verify we can connect and receive messages before adding any logic.
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from telethon import TelegramClient, events

from src.settings import settings

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Channel to monitor
CHANNEL_ID = -1002380293749  # @pfultimate
message_count = 0


async def main():
    """Test basic message capture"""
    global message_count

    print("🔍 BASIC MESSAGE TEST")
    print("=" * 50)
    print(f"Channel: @pfultimate ({CHANNEL_ID})")
    print("Goal: Capture ALL messages (no filtering)")
    print("Press Ctrl+C to stop")
    print("=" * 50)

    # Create client
    client = TelegramClient(settings.tg_session, settings.api_id, settings.api_hash)

    try:
        # Connect
        print("Connecting to Telegram...")
        await client.connect()

        if not await client.is_user_authorized():
            print("❌ Not authorized! Run authenticate_telegram.py first")
            return

        print("✅ Connected and authorized")

        # Test channel access
        try:
            entity = await client.get_entity(CHANNEL_ID)
            print(f"✅ Found channel: {entity.title}")
        except Exception as e:
            print(f"❌ Cannot access channel {CHANNEL_ID}: {e}")
            return

        @client.on(events.NewMessage(chats=[CHANNEL_ID]))
        async def handler(event):
            global message_count
            message_count += 1

            message = event.message
            text = message.text or "(no text)"

            print(f"\n📨 MESSAGE #{message_count}")
            print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
            print(f"ID: {message.id}")
            print(f"Text: {text[:200]}{'...' if len(text) > 200 else ''}")
            print("-" * 40)

        print("🎧 Listening for messages...")
        print("(This will show ALL messages from the channel)")

        # Run until interrupted
        await client.run_until_disconnected()

    except KeyboardInterrupt:
        print(f"\n✅ Test stopped. Captured {message_count} messages")
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"Fatal error: {e}")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
