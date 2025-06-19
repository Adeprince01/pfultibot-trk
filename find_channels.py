#!/usr/bin/env python3
"""Channel finder script to locate @pfultimate and other channels.

This script helps find the correct channel IDs for monitoring.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from telethon import TelegramClient
from telethon.tl.types import Channel, Chat

from src.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def find_channels() -> None:
    """Find channels, especially @pfultimate."""
    print("🔍 TELEGRAM CHANNEL FINDER")
    print("=" * 50)

    client = TelegramClient(settings.tg_session, settings.api_id, settings.api_hash)

    try:
        print("📱 Connecting to Telegram...")
        await client.connect()

        if not await client.is_user_authorized():
            print("❌ Not authenticated! Run authenticate_telegram.py first")
            return

        me = await client.get_me()
        print(f"✅ Connected as: {me.first_name} {me.last_name or ''}")

        print("\n🔍 Searching for @pfultimate...")

        # Method 1: Direct search by username
        try:
            entity = await client.get_entity("@pfultimate")
            print(f"✅ Found @pfultimate!")
            print(f"   Channel ID: {entity.id}")
            print(f"   Title: {entity.title}")
            print(f"   Username: @{entity.username}")
            print(
                f"   Participants: {entity.participants_count if hasattr(entity, 'participants_count') else 'Unknown'}"
            )

            # Test if we can access it
            try:
                # Try to get recent messages
                messages = await client.get_messages(entity, limit=1)
                print(f"   ✅ Access confirmed - Can read messages")

                if messages:
                    msg = messages[0]
                    print(
                        f"   📨 Latest message preview: {msg.text[:100] if msg.text else 'Media/Empty'}..."
                    )

            except Exception as e:
                print(f"   ⚠️  Limited access: {e}")

        except Exception as e:
            print(f"❌ Could not find @pfultimate directly: {e}")
            print("   Make sure you're subscribed to the channel!")

        print("\n📋 Listing your accessible channels and groups:")
        print("-" * 50)

        # Get all dialogs (channels, groups, chats)
        dialogs = await client.get_dialogs()

        channels = []
        groups = []

        for dialog in dialogs:
            entity = dialog.entity

            if isinstance(entity, Channel):
                if entity.broadcast:  # It's a channel
                    channels.append(
                        {
                            "id": entity.id,
                            "title": entity.title,
                            "username": (
                                f"@{entity.username}"
                                if entity.username
                                else "No username"
                            ),
                            "participants": getattr(
                                entity, "participants_count", "Unknown"
                            ),
                        }
                    )
                else:  # It's a supergroup
                    groups.append(
                        {
                            "id": entity.id,
                            "title": entity.title,
                            "username": (
                                f"@{entity.username}"
                                if entity.username
                                else "No username"
                            ),
                            "participants": getattr(
                                entity, "participants_count", "Unknown"
                            ),
                        }
                    )

        # Display channels
        if channels:
            print(f"\n📢 CHANNELS ({len(channels)} found):")
            for i, ch in enumerate(channels[:10], 1):  # Show first 10
                print(f"   {i}. {ch['title']}")
                print(f"      ID: {ch['id']}")
                print(f"      Username: {ch['username']}")
                print(f"      Participants: {ch['participants']}")
                print()

        # Display groups
        if groups:
            print(f"\n👥 SUPERGROUPS ({len(groups)} found):")
            for i, gr in enumerate(groups[:10], 1):  # Show first 10
                print(f"   {i}. {gr['title']}")
                print(f"      ID: {gr['id']}")
                print(f"      Username: {gr['username']}")
                print(f"      Participants: {gr['participants']}")
                print()

        # Search for channels with "pf" or "ultimate" in name
        print("\n🎯 CHANNELS WITH 'PF' OR 'ULTIMATE' IN NAME:")
        print("-" * 50)

        matching_channels = []
        for ch in channels:
            title_lower = ch["title"].lower()
            username_lower = ch["username"].lower()

            if any(
                keyword in title_lower or keyword in username_lower
                for keyword in ["pf", "ultimate", "crypto", "pump"]
            ):
                matching_channels.append(ch)
                print(f"✨ {ch['title']}")
                print(f"   ID: {ch['id']}")
                print(f"   Username: {ch['username']}")
                print()

        if not matching_channels:
            print("   No matching channels found.")
            print("   Make sure you're subscribed to @pfultimate!")

        print("\n" + "=" * 50)
        print("🔧 TO UPDATE YOUR INTEGRATION TEST:")
        print("1. Copy the channel ID from above")
        print("2. Edit test_integration.py")
        print("3. Replace -1001234567890 with the real channel ID")
        print("4. Run the integration test again!")

    except Exception as e:
        logger.error(f"Error finding channels: {e}")
        print(f"❌ Error: {e}")

    finally:
        await client.disconnect()
        print("📱 Disconnected from Telegram")


def main() -> None:
    """Main function."""
    print("🤖 Telegram Channel Finder")
    print("This will help you find the @pfultimate channel ID.")
    print()

    try:
        asyncio.run(find_channels())
    except KeyboardInterrupt:
        print("\n👋 Search cancelled by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"❌ Fatal error: {e}")


if __name__ == "__main__":
    main()
