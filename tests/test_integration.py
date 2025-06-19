#!/usr/bin/env python3
"""Integration test script for Telegram Crypto Call Tracker.

This script demonstrates the complete flow:
1. Connect to Telegram
2. Parse crypto call messages
3. Store data in SQLite
4. Display results

Run with: python test_integration.py
Requires: .env file with API_ID, API_HASH, and TG_SESSION variables
"""

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.listener import ChannelConfig, MessageHandler, TelegramListener
from src.parser import parse_crypto_call
from src.settings import settings
from src.storage.sqlite import SQLiteStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


class IntegrationTestDisplay:
    """Display and store test results."""

    def __init__(self) -> None:
        """Initialize test display."""
        self.calls: List[Dict[str, any]] = []
        db_path = Path("test_crypto_calls.db")
        self.db_storage = SQLiteStorage(db_path)
        logger.info(f"Test storage initialized at {db_path}")

    def process_call(self, message: str, channel: str = "Test") -> None:
        """Process a crypto call message."""
        print(f"\n📨 Processing: {message[:60]}...")

        parsed_data = parse_crypto_call(message)

        if parsed_data:
            # Add metadata
            parsed_data.update(
                {
                    "timestamp": datetime.now().isoformat(),
                    "message_id": len(self.calls) + 1000,
                    "channel_name": channel,
                }
            )

            self.calls.append(parsed_data)

            # Display result
            print("✅ CRYPTO CALL DETECTED!")
            print(f"   Token: {parsed_data.get('token_name', 'N/A')}")
            print(f"   Entry: ${parsed_data.get('entry_cap', 0):,.0f}")
            print(f"   Peak: ${parsed_data.get('peak_cap', 0):,.0f}")
            print(f"   Gain: {parsed_data.get('x_gain', 0)}x")
            if parsed_data.get("vip_x"):
                print(f"   VIP: {parsed_data.get('vip_x')}x")

            # Save to database
            try:
                self.db_storage.append_row(parsed_data)
                print("   💾 Saved to database")
            except Exception as e:
                print(f"   ❌ DB Error: {e}")
        else:
            print("❌ Not a crypto call")

    def show_summary(self) -> None:
        """Display summary of results."""
        if not self.calls:
            print("\n📊 No crypto calls processed.")
            return

        print(f"\n📊 SUMMARY - {len(self.calls)} calls processed:")
        print("-" * 40)

        total_gain = sum(call.get("x_gain", 0) for call in self.calls)
        avg_gain = total_gain / len(self.calls)
        max_gain = max(call.get("x_gain", 0) for call in self.calls)
        vip_count = sum(1 for call in self.calls if call.get("vip_x"))

        print(f"Average Gain: {avg_gain:.2f}x")
        print(f"Maximum Gain: {max_gain}x")
        print(f"VIP Calls: {vip_count}")

        # Show database contents
        try:
            db_records = self.db_storage.get_records(limit=10)
            print(f"\n💾 Database has {len(db_records)} total records")
        except Exception as e:
            print(f"❌ Database error: {e}")

    def close(self) -> None:
        """Close storage."""
        self.db_storage.close()


def test_parser_samples() -> None:
    """Test parser with sample messages."""
    print("🧪 TESTING CRYPTO CALL PARSER")
    print("=" * 50)

    display = IntegrationTestDisplay()

    # Test messages (mix of real and invalid)
    test_messages = [
        "🚀 $PEPE Entry: 45K MC Peak: 180K MC (4x) LFG!!!",
        "⚡️ Entry 50k Peak 250k (5x VIP 💎) INSANE PUMP",
        "$SHIB Entry: 100K MC Peak: 800K MC (8x) 🚀🚀🚀",
        "Entry 25k MC Peak 200k MC (8x VIP) MOON SHOT!",
        "📈 Entry: 75K Peak: 600K (8x) MASSIVE GAINS",
        "Regular message - not a crypto call",
        "Entry without peak - incomplete",
        "",
        None,
    ]

    for message in test_messages:
        if message is not None:
            display.process_call(message)
        else:
            print("\n📨 Processing: None...")
            print("❌ Invalid message")

    display.show_summary()
    display.close()


async def test_telegram_connection() -> None:
    """Test actual Telegram connection and message handling."""
    print("📡 TESTING TELEGRAM CONNECTION")
    print("=" * 50)

    # Validate settings
    try:
        from src.settings import settings

        print(f"API ID: {settings.api_id}")
        print(f"Session: {settings.tg_session}")
        print("✅ Settings loaded successfully")
    except Exception as e:
        print(f"❌ Settings error: {e}")
        print("\n🔧 TO SET UP TELEGRAM CONNECTION:")
        print("1. Create a .env file in the project root")
        print("2. Add your Telegram API credentials:")
        print("   API_ID=your_api_id")
        print("   API_HASH=your_api_hash")
        print("   TG_SESSION=pf_session")
        print("\n📖 Get API credentials from: https://my.telegram.org/apps")
        return

    # Initialize storage
    storage = IntegrationTestDisplay()

    # Configure test channels with real @pfultimate channel ID
    test_channels = [
        ChannelConfig(
            channel_id=-1002380293749,  # Real @pfultimate channel ID
            channel_name="Pumpfun Ultimate Alert",
            keywords=["Entry", "Peak", "x", "MC", "CA:", "$"],
            priority="high",
        )
    ]

    print("📢 CHANNEL CONFIGURATION:")
    for channel in test_channels:
        print(f"   • {channel.channel_name} (ID: {channel.channel_id})")
    print("\n💡 To get real channel IDs:")
    print("   1. Forward a message from target channel to @userinfobot")
    print("   2. Update the channel_id values above")

    # Initialize Telegram listener
    listener = TelegramListener(settings)

    try:
        # Connect to Telegram
        print("Connecting to Telegram...")
        connected = await listener.connect()

        if not connected:
            print("❌ Failed to connect to Telegram")
            return

        print("✅ Connected to Telegram successfully!")

        # Setup message handler
        listener.setup_message_handler(test_channels, storage)

        print("\n🎧 Listening for messages... (Press Ctrl+C to stop)")
        print(
            "📝 This will run until manually stopped - perfect for long-term monitoring!"
        )

        # Start listening (no timeout - run until stopped)
        listening_task = asyncio.create_task(listener.start_listening())

        try:
            # Run indefinitely until interrupted
            await listener.run_until_disconnected()
        except KeyboardInterrupt:
            print("\n🛑 Interrupted by user")

        # Stop listening
        await listener.stop_listening()

    except Exception as e:
        logger.error(f"Error during Telegram test: {e}")
        print(f"❌ Telegram test failed: {e}")

    finally:
        # Cleanup
        await listener.disconnect()
        storage.show_summary()
        storage.close()


async def main() -> None:
    """Main test function with interactive menu."""
    print("🤖 Telegram Crypto Call Tracker - Integration Test")
    print("=" * 55)

    while True:
        print("\nSelect test mode:")
        print("1. Test parser only (safe, no network)")
        print("2. Test Telegram connection (requires .env credentials)")
        print("3. Exit")

        try:
            choice = input("\nEnter choice (1-3): ").strip()

            if choice == "1":
                print("\n" + "=" * 50)
                test_parser_samples()
                print("\n✅ Parser test completed!")

            elif choice == "2":
                print("\n" + "=" * 50)
                await test_telegram_connection()
                print("\n✅ Telegram test completed!")

            elif choice == "3":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1-3.")

        except KeyboardInterrupt:
            print("\n\n👋 Interrupted by user. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            print(f"❌ Error: {e}")

        input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"❌ Fatal error: {e}")
