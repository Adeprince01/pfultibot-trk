#!/usr/bin/env python3
"""Telegram authentication script for first-time setup.

This script handles the initial authentication with Telegram API.
Run this once before using the main integration test.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from telethon import TelegramClient
from src.settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
)
logger = logging.getLogger(__name__)


async def authenticate_telegram() -> None:
    """Authenticate with Telegram API for the first time."""
    print("🔐 TELEGRAM AUTHENTICATION SETUP")
    print("=" * 50)
    
    try:
        print(f"Using API ID: {settings.api_id}")
        print(f"Session file: {settings.tg_session}.session")
        
        # Create Telegram client
        client = TelegramClient(settings.tg_session, settings.api_id, settings.api_hash)
        
        print("\n📱 Connecting to Telegram...")
        await client.connect()
        
        if not await client.is_user_authorized():
            print("\n🔢 Please enter your phone number (with country code):")
            print("Example: +1234567890")
            phone = input("Phone: ").strip()
            
            if not phone:
                print("❌ Phone number is required!")
                return
            
            print(f"\n📤 Sending verification code to {phone}...")
            await client.send_code_request(phone)
            
            print("\n🔑 Enter the verification code you received:")
            code = input("Code: ").strip()
            
            if not code:
                print("❌ Verification code is required!")
                return
            
            print("\n✅ Signing in...")
            try:
                await client.sign_in(phone, code)
                print("🎉 Successfully authenticated!")
                
                # Test by getting user info
                me = await client.get_me()
                print(f"👤 Logged in as: {me.first_name} {me.last_name or ''}")
                print(f"📱 Phone: {me.phone}")
                
            except Exception as e:
                if "two-step verification" in str(e).lower():
                    print("\n🔐 Two-step verification enabled. Enter your password:")
                    password = input("Password: ").strip()
                    await client.sign_in(password=password)
                    print("🎉 Successfully authenticated with 2FA!")
                else:
                    raise
        else:
            # Already authenticated
            me = await client.get_me()
            print(f"✅ Already authenticated as: {me.first_name} {me.last_name or ''}")
        
        print(f"\n💾 Session saved as: {settings.tg_session}.session")
        print("🚀 You can now run the integration test!")
        
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        print(f"❌ Authentication failed: {e}")
        
        if "api_id" in str(e).lower() or "api_hash" in str(e).lower():
            print("\n🔧 Check your .env file contains valid:")
            print("   API_ID=your_api_id")
            print("   API_HASH=your_api_hash")
            print("\n📖 Get credentials from: https://my.telegram.org/apps")
    
    finally:
        if 'client' in locals():
            try:
                await client.disconnect()
                print("📱 Disconnected from Telegram")
            except:
                pass


def main() -> None:
    """Main function."""
    print("🤖 Telegram Authentication Setup")
    print("This will authenticate your Telegram session for the crypto tracker.")
    print()
    
    try:
        asyncio.run(authenticate_telegram())
    except KeyboardInterrupt:
        print("\n👋 Authentication cancelled by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"❌ Fatal error: {e}")


if __name__ == "__main__":
    main() 