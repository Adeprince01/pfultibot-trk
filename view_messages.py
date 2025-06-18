#!/usr/bin/env python3
"""View collected messages from the database"""

import sqlite3
from datetime import datetime
import sys
from pathlib import Path

# Add src to path for parser testing
sys.path.insert(0, str(Path(__file__).parent / "src"))

def view_messages(db_path="message_analysis.db", limit=10, test_fixes=True):
    """View messages from the database."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Get basic stats
        cursor = conn.execute("SELECT COUNT(*) as total FROM messages")
        total = cursor.fetchone()["total"]
        
        print(f"📊 DATABASE OVERVIEW")
        print(f"=" * 50)
        print(f"Total Messages: {total}")
        print(f"Database: {db_path}")
        print()
        
        # Get message type stats
        cursor = conn.execute("""
            SELECT 
                SUM(looks_like_discovery) as discoveries,
                SUM(looks_like_update) as updates, 
                SUM(looks_like_result) as results,
                SUM(parser_success) as parsed
            FROM messages
        """)
        stats = cursor.fetchone()
        
        print(f"📈 MESSAGE TYPES (Original Classification)")
        print(f"Discovery calls: {stats['discoveries']}")
        print(f"Update messages: {stats['updates']}")
        print(f"Result messages: {stats['results']}")
        print(f"Successfully parsed: {stats['parsed']}")
        print()

        # Test parser fixes if requested
        if test_fixes:
            print(f"🔧 TESTING PARSER FIXES")
            print(f"=" * 50)
            
            try:
                from src.parser import parse_crypto_call
                
                # Get all messages for testing
                cursor = conn.execute("""
                    SELECT message_id, message_text, 
                           looks_like_discovery, looks_like_update, parser_success
                    FROM messages 
                    ORDER BY message_id DESC
                """)
                
                all_messages = cursor.fetchall()
                new_successes = 0
                
                for row in all_messages:
                    parser_result = parse_crypto_call(row["message_text"])
                    if parser_result:
                        new_successes += 1
                
                old_success_rate = (stats['parsed'] / max(total, 1)) * 100
                new_success_rate = (new_successes / max(total, 1)) * 100
                
                print(f"Parser Success: {stats['parsed']}/{total} → {new_successes}/{total}")
                print(f"Success Rate: {old_success_rate:.1f}% → {new_success_rate:.1f}%")
                
                if new_success_rate >= 80:
                    print("🎉 EXCELLENT: Parser fixes working!")
                elif new_success_rate > old_success_rate:
                    print("🔄 IMPROVED: Parser fixes helping")
                else:
                    print("❌ NO IMPROVEMENT: Fixes need more work")
                print()
                
            except ImportError:
                print("⚠️ Cannot test fixes - parser import failed")
                print()
        
        # Show recent messages
        print(f"📝 RECENT MESSAGES (Last {limit})")
        print(f"=" * 70)
        
        cursor = conn.execute("""
            SELECT 
                message_id, message_text, message_date,
                looks_like_discovery, looks_like_update, looks_like_result,
                parser_success, parsed_token_name, parsed_x_gain
            FROM messages 
            ORDER BY message_id DESC 
            LIMIT ?
        """, (limit,))
        
        for i, row in enumerate(cursor.fetchall(), 1):
            # Determine message type
            msg_type = "DISCOVERY" if row["looks_like_discovery"] else \
                      "UPDATE" if row["looks_like_update"] else \
                      "RESULT" if row["looks_like_result"] else "OTHER"
            
            parse_status = "✅" if row["parser_success"] else "❌"
            
            print(f"\n{i}. MESSAGE #{row['message_id']} | {msg_type} | {parse_status}")
            print(f"Text: {row['message_text']}")
            
            if row["parser_success"]:
                token = row["parsed_token_name"] or "Unknown"
                gain = row["parsed_x_gain"] or 0
                print(f"Parsed: {token} | {gain}x gain")
                
            print(f"Time: {row['message_date']}")
            print("-" * 70)
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error reading database: {e}")

if __name__ == "__main__":
    view_messages() 