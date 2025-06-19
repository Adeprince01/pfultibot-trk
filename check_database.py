#!/usr/bin/env python3
"""Script to check the database for raw messages and crypto calls."""

import sqlite3
from pathlib import Path

def check_database():
    """Check the database for raw messages and crypto calls."""
    db_path = Path('crypto_calls_production.db')
    
    if not db_path.exists():
        print("❌ Database not found: crypto_calls_production.db")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    print("🔍 DATABASE CHECK")
    print("=" * 50)
    
    # Check raw messages
    print("\n📝 LATEST RAW MESSAGES:")
    print("-" * 30)
    cursor = conn.execute('''
        SELECT message_id, message_text, reply_to_message_id 
        FROM raw_messages 
        ORDER BY created_at DESC 
        LIMIT 10
    ''')
    
    for i, row in enumerate(cursor.fetchall(), 1):
        text = row[1][:80] + '...' if row[1] and len(row[1]) > 80 else row[1]
        reply_status = f"Reply to: {row[2]}" if row[2] else "Original message"
        print(f"{i:2d}. ID:{row[0]} | {reply_status}")
        print(f"    Text: {text}")
        print()
    
    # Check crypto calls with linking info
    print("\n🎯 LATEST CRYPTO CALLS:")
    print("-" * 30)
    cursor = conn.execute('''
        SELECT message_id, token_name, message_type, linked_crypto_call_id, x_gain, vip_x
        FROM crypto_calls 
        ORDER BY created_at DESC 
        LIMIT 10
    ''')
    
    for i, row in enumerate(cursor.fetchall(), 1):
        link_status = f"Linked to call #{row[3]}" if row[3] else "Original call"
        gains = f"{row[4]}x" if row[4] else "N/A"
        vip_gains = f" (VIP: {row[5]}x)" if row[5] else ""
        print(f"{i:2d}. Msg:{row[0]} | Token: {row[1] or 'Unknown'} | Type: {row[2] or 'N/A'}")
        print(f"    Gains: {gains}{vip_gains} | {link_status}")
        print()
    
    # Check linking statistics
    print("\n📊 LINKING STATISTICS:")
    print("-" * 30)
    
    # Total calls
    cursor = conn.execute('SELECT COUNT(*) FROM crypto_calls')
    total_calls = cursor.fetchone()[0]
    
    # Discovery calls
    cursor = conn.execute("SELECT COUNT(*) FROM crypto_calls WHERE message_type = 'discovery'")
    discovery_calls = cursor.fetchone()[0]
    
    # Update calls
    cursor = conn.execute("SELECT COUNT(*) FROM crypto_calls WHERE message_type = 'update'")
    update_calls = cursor.fetchone()[0]
    
    # Linked calls
    cursor = conn.execute('SELECT COUNT(*) FROM crypto_calls WHERE linked_crypto_call_id IS NOT NULL')
    linked_calls = cursor.fetchone()[0]
    
    # Calls with token names
    cursor = conn.execute('SELECT COUNT(*) FROM crypto_calls WHERE token_name IS NOT NULL AND token_name != ""')
    named_calls = cursor.fetchone()[0]
    
    print(f"Total calls: {total_calls}")
    print(f"Discovery calls: {discovery_calls}")
    print(f"Update calls: {update_calls}")
    print(f"Linked calls: {linked_calls}")
    print(f"Calls with token names: {named_calls}")
    
    if total_calls > 0:
        link_rate = (linked_calls / total_calls) * 100
        name_rate = (named_calls / total_calls) * 100
        print(f"Linking rate: {link_rate:.1f}%")
        print(f"Token naming rate: {name_rate:.1f}%")
    
    conn.close()
    print("\n✅ Database check completed!")

if __name__ == "__main__":
    check_database() 