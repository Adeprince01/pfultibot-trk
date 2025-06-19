#!/usr/bin/env python3
"""Quick script to check raw messages in the database."""

import sqlite3
from datetime import datetime


def check_raw_messages():
    """Check raw messages in the database."""
    try:
        conn = sqlite3.connect("crypto_calls_production.db")
        conn.row_factory = sqlite3.Row

        print("🔍 RAW MESSAGES DATABASE CHECK")
        print("=" * 50)

        # Check if raw_messages table exists
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='raw_messages'"
        )
        if not cursor.fetchone():
            print("❌ raw_messages table doesn't exist!")
            return

        # Count total raw messages
        cursor = conn.execute("SELECT COUNT(*) FROM raw_messages")
        total_count = cursor.fetchone()[0]
        print(f"📊 Total raw messages: {total_count}")

        if total_count == 0:
            print("❌ No raw messages found - listener is not storing raw messages!")
            return

        # Show recent raw messages
        print("\n📨 Recent Raw Messages (last 10):")
        print("-" * 50)

        cursor = conn.execute(
            """
            SELECT message_id, channel_id, channel_name, message_text, 
                   message_date, reply_to_message_id, is_classified, created_at
            FROM raw_messages 
            ORDER BY created_at DESC 
            LIMIT 10
        """
        )

        for i, row in enumerate(cursor.fetchall(), 1):
            msg_text = (
                row["message_text"][:100] + "..."
                if len(row["message_text"]) > 100
                else row["message_text"]
            )
            reply_info = (
                f" (Reply to: {row['reply_to_message_id']})"
                if row["reply_to_message_id"]
                else ""
            )
            classified = "✅" if row["is_classified"] else "❌"

            print(f"{i:2d}. Message {row['message_id']}{reply_info}")
            print(f"    Channel: {row['channel_name']} ({row['channel_id']})")
            print(f"    Date: {row['message_date']}")
            print(f"    Classified: {classified}")
            print(f"    Text: {msg_text}")
            print()

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if "conn" in locals():
            conn.close()


if __name__ == "__main__":
    check_raw_messages()
