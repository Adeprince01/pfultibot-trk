#!/usr/bin/env python3
"""Database viewer to see parsed crypto calls."""

import sqlite3
from datetime import datetime
from pathlib import Path


def view_database() -> None:
    """View all parsed crypto calls from the database."""
    # Check both test and production databases
    test_db = Path("test_crypto_calls.db")
    prod_db = Path("crypto_calls_production.db")
    
    if prod_db.exists():
        db_path = prod_db
        print("📊 Using production database")
    elif test_db.exists():
        db_path = test_db
        print("📊 Using test database")
    else:
        print("❌ No database files found!")
        print("Run the crypto monitor or integration test first.")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Get all records
        cursor = conn.execute("""
            SELECT token_name, entry_cap, peak_cap, x_gain, vip_x, 
                   timestamp, message_id, channel_name, created_at
            FROM crypto_calls 
            ORDER BY created_at DESC
        """)
        
        records = cursor.fetchall()
        
        if not records:
            print("📊 No crypto calls found in database yet.")
            print("The listener might not have detected any calls, or messages didn't match the parser.")
            return
        
        print(f"📊 CRYPTO CALLS DATABASE - {len(records)} records found")
        print("=" * 80)
        
        for i, record in enumerate(records, 1):
            print(f"\n🚀 CALL #{i}")
            print(f"   Token: {record['token_name'] or 'N/A'}")
            print(f"   Entry Cap: ${record['entry_cap']:,.0f}" if record['entry_cap'] else "   Entry Cap: N/A")
            print(f"   Peak Cap: ${record['peak_cap']:,.0f}" if record['peak_cap'] else "   Peak Cap: N/A")
            print(f"   Gain: {record['x_gain']}x" if record['x_gain'] else "   Gain: N/A")
            
            if record['vip_x']:
                print(f"   VIP: {record['vip_x']}x")
            
            print(f"   Channel: {record['channel_name']}")
            print(f"   Message ID: {record['message_id']}")
            print(f"   Timestamp: {record['timestamp']}")
            print(f"   Stored: {record['created_at']}")
        
        # Show summary
        print(f"\n📈 SUMMARY:")
        print(f"   Total Calls: {len(records)}")
        
        gains = [r['x_gain'] for r in records if r['x_gain']]
        if gains:
            print(f"   Average Gain: {sum(gains)/len(gains):.2f}x")
            print(f"   Max Gain: {max(gains)}x")
        
        vip_calls = sum(1 for r in records if r['vip_x'])
        print(f"   VIP Calls: {vip_calls}")
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")
    
    finally:
        if 'conn' in locals():
            conn.close()


def view_raw_messages() -> None:
    """Show raw database structure for debugging."""
    db_path = Path("test_crypto_calls.db")
    
    if not db_path.exists():
        print("❌ Database file not found!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        
        # Show table structure
        cursor = conn.execute("PRAGMA table_info(crypto_calls)")
        columns = cursor.fetchall()
        
        print("🗄️  DATABASE STRUCTURE:")
        for col in columns:
            print(f"   {col[1]} ({col[2]})")
        
        # Count total records
        cursor = conn.execute("SELECT COUNT(*) FROM crypto_calls")
        count = cursor.fetchone()[0]
        print(f"\n📊 Total records: {count}")
        
        if count > 0:
            # Show sample raw data
            cursor = conn.execute("SELECT * FROM crypto_calls LIMIT 3")
            raw_records = cursor.fetchall()
            
            print(f"\n📄 SAMPLE RAW DATA:")
            for i, record in enumerate(raw_records, 1):
                print(f"   Record {i}: {record}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        if 'conn' in locals():
            conn.close()


def main() -> None:
    """Main function with menu."""
    print("🔍 Crypto Calls Database Viewer")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. View parsed crypto calls")
        print("2. View raw database info")
        print("3. Exit")
        
        choice = input("\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            view_database()
        elif choice == "2":
            view_raw_messages()
        elif choice == "3":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice")
        
        if choice in ["1", "2"]:
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    main() 