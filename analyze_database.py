#!/usr/bin/env python3
"""Enhanced database analyzer for crypto call tracking with message linking."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add new import for analytics
from src.metrics import (
    extract_crypto_calls_data,
    generate_comprehensive_report,
    calculate_win_rates,
    calculate_performance_stats,
    calculate_channel_performance,
    cleanse_crypto_calls_data,
    get_data_quality_report,
)


def _safe_parse_timestamp(ts: str) -> datetime:
    """Parse timestamp string in either ISO-8601 or standard format.

    Args:
        ts: Timestamp string in various formats

    Returns:
        Parsed datetime object (always timezone-naive for comparison)

    Raises:
        ValueError: If timestamp cannot be parsed in any known format
    """
    # Try ISO-8601 format first (includes 'T' and microseconds)
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        # Convert to naive datetime for comparison
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except ValueError:
        pass

    # Try standard format without 'T'
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass

    # Try format with timezone
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S%z")
        # Convert to naive datetime for comparison
        return dt.replace(tzinfo=None)
    except ValueError:
        pass

    # If all else fails, raise with helpful message
    raise ValueError(f"Cannot parse timestamp: {ts}")


def get_database_path() -> Optional[Path]:
    """Find the appropriate database file to use."""
    possible_paths = [
        Path("crypto_calls_production.db"),
        Path("test_crypto_calls.db"),
        Path("crypto_calls.db"),
        Path("message_analysis.db"),
    ]

    for db_path in possible_paths:
        if db_path.exists():
            return db_path

    return None


def view_linked_messages() -> None:
    """View linked messages and their relationships."""
    db_path = get_database_path()
    if not db_path:
        print("❌ No database files found!")
        print("Run the monitor script first to collect data.")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        print(f"🔗 LINKED MESSAGE ANALYSIS")
        print(f"📊 Database: {db_path}")
        print("=" * 80)

        # Get all crypto calls with linking information
        cursor = conn.execute(
            """
            SELECT 
                cc.id,
                cc.token_name,
                cc.entry_cap,
                cc.peak_cap,
                cc.x_gain,
                cc.vip_x,
                cc.timestamp,
                cc.message_id,
                cc.channel_name,
                cc.linked_crypto_call_id,
                cc.created_at,
                -- Get original message details if this is a linked message
                orig.token_name as orig_token_name,
                orig.entry_cap as orig_entry_cap,
                orig.message_id as orig_message_id
            FROM crypto_calls cc
            LEFT JOIN crypto_calls orig ON cc.linked_crypto_call_id = orig.id
            ORDER BY cc.created_at DESC
        """
        )

        records = cursor.fetchall()

        if not records:
            print("📊 No crypto calls found in database yet.")
            return

        print(f"📈 Found {len(records)} total calls")

        # Group messages by token/linked chains
        discovery_calls = [r for r in records if not r["linked_crypto_call_id"]]
        update_calls = [r for r in records if r["linked_crypto_call_id"]]

        print(f"🎯 Discovery calls: {len(discovery_calls)}")
        print(f"📊 Update calls: {len(update_calls)}")
        print()

        # Show each discovery with its updates
        for i, discovery in enumerate(discovery_calls, 1):
            print(f"🏷️  TOKEN CHAIN #{i}")
            print("=" * 60)

            # Show discovery message
            print(f"🎯 DISCOVERY CALL (ID: {discovery['id']})")
            print(f"   Token: {discovery['token_name'] or 'Unknown'}")
            print(
                f"   Entry Cap: ${discovery['entry_cap']:,.0f}"
                if discovery["entry_cap"]
                else "   Entry Cap: N/A"
            )
            print(
                f"   Initial Gain: {discovery['x_gain']}x"
                if discovery["x_gain"]
                else "   Initial Gain: N/A"
            )
            if discovery["vip_x"]:
                print(f"   VIP: {discovery['vip_x']}x")
            print(f"   Message ID: {discovery['message_id']}")
            print(f"   Time: {discovery['timestamp']}")
            print()

            # Find and show updates for this discovery
            related_updates = [
                u for u in update_calls if u["linked_crypto_call_id"] == discovery["id"]
            ]

            if related_updates:
                print(f"📊 UPDATES ({len(related_updates)} total):")
                # Sort updates by actual timestamp, not just created_at
                updates = sorted(
                    related_updates, key=lambda x: _safe_parse_timestamp(x["timestamp"])
                )

                for j, update in enumerate(updates, 1):
                    print(f"   #{j}. Update (ID: {update['id']})")
                    print(
                        f"       Token: {update['token_name'] or 'Inherited from discovery'}"
                    )
                    print(
                        f"       Peak Cap: ${update['peak_cap']:,.0f}"
                        if update["peak_cap"]
                        else "       Peak Cap: N/A"
                    )
                    print(
                        f"       Gain: {update['x_gain']}x"
                        if update["x_gain"]
                        else "       Gain: N/A"
                    )
                    if update["vip_x"]:
                        print(f"       VIP: {update['vip_x']}x")
                    print(f"       Message ID: {update['message_id']}")
                    print(f"       Time: {update['timestamp']}")
                    print(
                        f"       → Linked to Discovery ID: {update['linked_crypto_call_id']}"
                    )
                    print()

                # Show token summary
                all_gains: list[float] = []
                # Start with discovery gain if it exists
                if discovery["x_gain"]:
                    all_gains.append(discovery["x_gain"])

                # Add gains from chronologically sorted updates
                for update in updates:
                    if update["x_gain"] and update["x_gain"] not in all_gains:
                        all_gains.append(update["x_gain"])

                if all_gains:
                    print(f"📈 TOKEN SUMMARY:")
                    print(f"   Total Updates: {len(related_updates)}")
                    print(f"   Best Performance: {max(all_gains)}x")
                    print(f"   Latest Performance: {all_gains[-1]}x")
                    print(
                        f"   Gain Progression: {' → '.join(f'{g:.1f}x' for g in all_gains)}"
                    )
            else:
                print(f"📊 No updates found for this discovery")

            print("=" * 60)
            print()

        # Show orphaned updates (updates without discoveries)
        orphaned = [
            u
            for u in update_calls
            if not any(d["id"] == u["linked_crypto_call_id"] for d in discovery_calls)
        ]
        if orphaned:
            print(f"⚠️  ORPHANED UPDATES ({len(orphaned)}):")
            for update in orphaned:
                print(
                    f"   Update ID {update['id']} → Links to missing Discovery ID {update['linked_crypto_call_id']}"
                )

        conn.close()

    except Exception as e:
        print(f"❌ Error reading database: {e}")
        import traceback

        traceback.print_exc()


def view_raw_message_text() -> None:
    """View the full text of raw messages stored in the database."""
    db_path = get_database_path()
    if not db_path:
        print("❌ No database files found!")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        print(f"📝 RAW MESSAGE TEXT VIEWER")
        print(f"📊 Database: {db_path}")
        print("=" * 80)

        # Check if raw_messages table exists
        cursor = conn.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='raw_messages'
        """
        )

        if not cursor.fetchone():
            print("❌ No raw_messages table found!")
            print("This means messages are only stored in parsed format.")
            return

        # Get raw messages with reply relationships
        cursor = conn.execute(
            """
            SELECT 
                rm.message_id,
                rm.channel_name,
                rm.message_text,
                rm.message_date,
                rm.reply_to_message_id,
                rm.is_classified,
                rm.classification_result,
                -- Join with crypto_calls to see if it was parsed
                cc.id as crypto_call_id,
                cc.token_name as parsed_token,
                cc.x_gain as parsed_gain
            FROM raw_messages rm
            LEFT JOIN crypto_calls cc ON rm.message_id = cc.message_id
            ORDER BY rm.message_date DESC
            LIMIT 20
        """
        )

        messages = cursor.fetchall()

        if not messages:
            print("📊 No raw messages found in database.")
            return

        print(f"📨 Found {len(messages)} recent messages")
        print()

        for i, msg in enumerate(messages, 1):
            print(f"📬 MESSAGE #{i}")
            print(f"   ID: {msg['message_id']}")
            print(f"   Channel: {msg['channel_name']}")
            print(f"   Date: {msg['message_date']}")

            if msg["reply_to_message_id"]:
                print(f"   🔗 Replies to: {msg['reply_to_message_id']}")

            if msg["crypto_call_id"]:
                print(f"   ✅ Parsed as: {msg['parsed_token']} ({msg['parsed_gain']}x)")
            else:
                print(f"   ❌ Not parsed")

            print(f"   📝 FULL TEXT:")
            print(f"   {'-' * 60}")
            # Show full message text with proper formatting
            text_lines = msg["message_text"].split("\n")
            for line in text_lines:
                print(f"   {line}")
            print(f"   {'-' * 60}")
            print()

        # Show reply relationships
        print(f"🔗 REPLY RELATIONSHIPS:")
        cursor = conn.execute(
            """
            SELECT 
                rm1.message_id as reply_id,
                rm1.reply_to_message_id as original_id,
                rm2.message_text as original_text
            FROM raw_messages rm1
            LEFT JOIN raw_messages rm2 ON rm1.reply_to_message_id = rm2.message_id
            WHERE rm1.reply_to_message_id IS NOT NULL
            ORDER BY rm1.message_date DESC
            LIMIT 10
        """
        )

        replies = cursor.fetchall()
        for reply in replies:
            print(f"   Message {reply['reply_id']} → Replies to {reply['original_id']}")
            if reply["original_text"]:
                preview = (
                    reply["original_text"][:100] + "..."
                    if len(reply["original_text"]) > 100
                    else reply["original_text"]
                )
                print(f"      Original: {preview}")

        conn.close()

    except Exception as e:
        print(f"❌ Error reading raw messages: {e}")
        import traceback

        traceback.print_exc()


def view_database_stats() -> None:
    """Show comprehensive database statistics."""
    db_path = get_database_path()
    if not db_path:
        print("❌ No database files found!")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        print(f"📊 COMPREHENSIVE DATABASE STATISTICS")
        print(f"📁 Database: {db_path}")
        print("=" * 80)

        # Check tables
        cursor = conn.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """
        )
        tables = [row["name"] for row in cursor.fetchall()]
        print(f"🗄️  Tables: {', '.join(tables)}")
        print()

        # Crypto calls stats
        if "crypto_calls" in tables:
            print("🚀 CRYPTO CALLS TABLE:")

            # Show table structure
            cursor = conn.execute("PRAGMA table_info(crypto_calls)")
            columns = cursor.fetchall()
            print("   Columns:")
            for col in columns:
                print(f"      {col[1]} ({col[2]})")
            print()

            cursor = conn.execute("SELECT COUNT(*) as total FROM crypto_calls")
            total_calls = cursor.fetchone()["total"]

            cursor = conn.execute(
                """
                SELECT COUNT(*) as linked 
                FROM crypto_calls 
                WHERE linked_crypto_call_id IS NOT NULL
            """
            )
            linked_calls = cursor.fetchone()["linked"]

            print(f"   Records:")
            print(f"      Total: {total_calls}")
            print(f"      Discoveries: {total_calls - linked_calls}")
            print(f"      Updates: {linked_calls}")
            if total_calls > 0:
                print(f"      Linking Rate: {(linked_calls/total_calls*100):.1f}%")
            print()

        # Raw messages stats
        if "raw_messages" in tables:
            print("📨 RAW MESSAGES TABLE:")

            # Show table structure
            cursor = conn.execute("PRAGMA table_info(raw_messages)")
            columns = cursor.fetchall()
            print("   Columns:")
            for col in columns:
                print(f"      {col[1]} ({col[2]})")
            print()

            cursor = conn.execute("SELECT COUNT(*) as total FROM raw_messages")
            total_raw = cursor.fetchone()["total"]

            cursor = conn.execute(
                """
                SELECT COUNT(*) as with_replies 
                FROM raw_messages 
                WHERE reply_to_message_id IS NOT NULL
            """
            )
            with_replies = cursor.fetchone()["with_replies"]

            print(f"   Records:")
            print(f"      Total: {total_raw}")
            print(f"      With Replies: {with_replies}")
            if total_raw > 0:
                print(f"      Reply Rate: {(with_replies/total_raw*100):.1f}%")
            print()

        # Performance stats
        if "crypto_calls" in tables:
            cursor = conn.execute(
                """
                SELECT 
                    AVG(x_gain) as avg_gain,
                    MAX(x_gain) as max_gain,
                    MIN(x_gain) as min_gain,
                    COUNT(CASE WHEN x_gain > 2 THEN 1 END) as profitable_calls,
                    COUNT(CASE WHEN x_gain IS NOT NULL THEN 1 END) as calls_with_gains
                FROM crypto_calls
            """
            )
            perf = cursor.fetchone()

            if perf["calls_with_gains"] > 0:
                print(f"📈 PERFORMANCE STATS:")
                print(f"      Calls with Gains: {perf['calls_with_gains']}")
                print(f"      Average Gain: {perf['avg_gain']:.2f}x")
                print(f"      Best Gain: {perf['max_gain']}x")
                print(f"      Worst Gain: {perf['min_gain']}x")
                print(f"      Profitable Calls (>2x): {perf['profitable_calls']}")
                print()

        conn.close()

    except Exception as e:
        print(f"❌ Error reading database stats: {e}")


def test_linking_integrity() -> None:
    """Test the integrity of message linking."""
    db_path = get_database_path()
    if not db_path:
        print("❌ No database files found!")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        print(f"🔬 TESTING LINKING INTEGRITY")
        print(f"📊 Database: {db_path}")
        print("=" * 80)

        # Test 1: Check for broken links
        cursor = conn.execute(
            """
            SELECT cc1.id, cc1.message_id, cc1.linked_crypto_call_id
            FROM crypto_calls cc1
            LEFT JOIN crypto_calls cc2 ON cc1.linked_crypto_call_id = cc2.id
            WHERE cc1.linked_crypto_call_id IS NOT NULL 
            AND cc2.id IS NULL
        """
        )
        broken_links = cursor.fetchall()

        print(f"🔗 BROKEN LINKS TEST:")
        if broken_links:
            print(f"   ❌ Found {len(broken_links)} broken links:")
            for link in broken_links:
                print(
                    f"      Call ID {link['id']} → Links to missing ID {link['linked_crypto_call_id']}"
                )
        else:
            print(f"   ✅ No broken links found!")
        print()

        # Test 2: Check reply relationships if raw_messages exists
        cursor = conn.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='raw_messages'
        """
        )

        if cursor.fetchone():
            print(f"📨 RAW MESSAGE LINKING TEST:")

            # Check if crypto calls have corresponding raw messages
            cursor = conn.execute(
                """
                SELECT cc.message_id as call_msg_id, rm.message_id as raw_msg_id
                FROM crypto_calls cc
                LEFT JOIN raw_messages rm ON cc.message_id = rm.message_id
                WHERE rm.message_id IS NULL
            """
            )
            missing_raw = cursor.fetchall()

            if missing_raw:
                print(f"   ⚠️  {len(missing_raw)} crypto calls without raw messages")
            else:
                print(f"   ✅ All crypto calls have raw messages")

            # Check reply chains
            cursor = conn.execute(
                """
                SELECT 
                    cc.id as call_id,
                    cc.message_id as call_msg_id,
                    cc.linked_crypto_call_id as linked_to_id,
                    rm.reply_to_message_id as raw_reply_to,
                    cc2.message_id as original_msg_id
                FROM crypto_calls cc
                JOIN raw_messages rm ON cc.message_id = rm.message_id
                LEFT JOIN crypto_calls cc2 ON cc.linked_crypto_call_id = cc2.id
                WHERE cc.linked_crypto_call_id IS NOT NULL
                AND rm.reply_to_message_id != cc2.message_id
            """
            )
            mismatched_replies = cursor.fetchall()

            if mismatched_replies:
                print(f"   ⚠️  {len(mismatched_replies)} mismatched reply relationships")
                for mm in mismatched_replies[:5]:  # Show first 5
                    print(
                        f"      Call {mm['call_id']}: Raw reply to {mm['raw_reply_to']} ≠ Linked to {mm['original_msg_id']}"
                    )
            else:
                print(f"   ✅ All reply relationships match properly")
        print()

        # Test 3: Token name inheritance
        cursor = conn.execute(
            """
            SELECT 
                cc1.id, cc1.token_name as update_token,
                cc2.token_name as discovery_token
            FROM crypto_calls cc1
            JOIN crypto_calls cc2 ON cc1.linked_crypto_call_id = cc2.id
            WHERE cc1.token_name IS NULL AND cc2.token_name IS NOT NULL
        """
        )
        missing_inheritance = cursor.fetchall()

        print(f"🏷️  TOKEN NAME INHERITANCE TEST:")
        if missing_inheritance:
            print(
                f"   ⚠️  {len(missing_inheritance)} updates missing inherited token names"
            )
        else:
            print(f"   ✅ Token name inheritance working properly")
        print()

        conn.close()

    except Exception as e:
        print(f"❌ Error testing linking integrity: {e}")


def fix_token_inheritance() -> None:
    """Fix token name inheritance for existing records in the database."""
    db_path = get_database_path()
    if not db_path:
        print("❌ No database files found!")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        print(f"🔧 FIXING TOKEN NAME INHERITANCE")
        print(f"📊 Database: {db_path}")
        print("=" * 80)

        # Find update records that are linked but missing token names
        cursor = conn.execute(
            """
            SELECT 
                cc1.id as update_id,
                cc1.message_id as update_msg_id,
                cc1.token_name as update_token,
                cc1.linked_crypto_call_id as linked_to_id,
                cc2.token_name as discovery_token
            FROM crypto_calls cc1
            JOIN crypto_calls cc2 ON cc1.linked_crypto_call_id = cc2.id
            WHERE cc1.linked_crypto_call_id IS NOT NULL 
            AND (cc1.token_name IS NULL OR cc1.token_name = 'Unknown')
            AND cc2.token_name IS NOT NULL 
            AND cc2.token_name != 'Unknown'
        """
        )

        records_to_fix = cursor.fetchall()

        if not records_to_fix:
            print("✅ No records need token name inheritance fixes!")
            return

        print(
            f"🔍 Found {len(records_to_fix)} records that need token name inheritance"
        )
        print()

        # Show what will be fixed
        for record in records_to_fix:
            print(f"   Update ID {record['update_id']} (msg {record['update_msg_id']})")
            print(f"      Current token: {record['update_token'] or 'NULL'}")
            print(
                f"      Will inherit: '{record['discovery_token']}' from discovery ID {record['linked_to_id']}"
            )
            print()

        # Ask for confirmation
        response = input(f"Fix {len(records_to_fix)} records? (y/N): ").strip().lower()
        if response != "y":
            print("❌ Operation cancelled")
            return

        # Apply the fixes
        fixed_count = 0
        for record in records_to_fix:
            try:
                cursor = conn.execute(
                    """
                    UPDATE crypto_calls 
                    SET token_name = ? 
                    WHERE id = ?
                """,
                    (record["discovery_token"], record["update_id"]),
                )

                if cursor.rowcount > 0:
                    fixed_count += 1
                    print(
                        f"✅ Fixed record ID {record['update_id']}: inherited '{record['discovery_token']}'"
                    )

            except Exception as e:
                print(f"❌ Failed to fix record ID {record['update_id']}: {e}")

        # Commit the changes
        conn.commit()
        print()
        print(f"🎉 Successfully fixed {fixed_count}/{len(records_to_fix)} records!")

        conn.close()

    except Exception as e:
        print(f"❌ Error fixing token inheritance: {e}")
        import traceback

        traceback.print_exc()


def run_comprehensive_analytics() -> None:
    """Run comprehensive analytics using the new metrics functions."""
    db_path = get_database_path()
    if not db_path:
        print("❌ No database files found!")
        print("Run the monitor script first to collect data.")
        return

    try:
        print(f"📊 COMPREHENSIVE ANALYTICS")
        print(f"📁 Database: {db_path}")
        print("=" * 80)

        # Extract data
        print("🔄 Extracting crypto calls data...")
        df = extract_crypto_calls_data(db_path=db_path)
        
        if df.empty:
            print("❌ No crypto calls data found in database.")
            print("Run the monitor and let it collect some data first.")
            return

        print(f"✅ Loaded {len(df)} crypto calls")
        print()

        # Generate comprehensive report
        print("🧮 Calculating analytics...")
        report = generate_comprehensive_report(df)
        
        # Display results
        print("📈 OVERALL PERFORMANCE")
        print("-" * 40)
        overview = report["overview"]
        print(f"Total Calls: {overview['total_calls']}")
        print(f"Valid Calls (with x_gain): {overview['valid_calls']}")
        if overview['avg_x_gain']:
            print(f"Average X-Gain: {overview['avg_x_gain']:.2f}x")
            print(f"Median X-Gain: {overview['median_x_gain']:.2f}x")
            print(f"Max X-Gain: {overview['max_x_gain']:.2f}x")
            print(f"Min X-Gain: {overview['min_x_gain']:.2f}x")
            print(f"Standard Deviation: {overview['std_x_gain']:.2f}")
        print()

        # Win rates
        print("🎯 WIN RATES")
        print("-" * 40)
        win_rates = report["win_rates"]
        print(f"2x or better: {win_rates['win_rate_2x']:.1%}")
        print(f"3x or better: {win_rates['win_rate_3x']:.1%}")
        print(f"5x or better: {win_rates['win_rate_5x']:.1%}")
        print(f"10x or better: {win_rates['win_rate_10x']:.1%}")
        print()

        # Channel performance
        print("📺 CHANNEL PERFORMANCE")
        print("-" * 40)
        channel_perf = report["channel_performance"]
        if channel_perf:
            for channel in channel_perf:
                print(f"Channel: {channel['channel_name']}")
                print(f"  Calls: {channel['total_calls']} | Avg Gain: {channel.get('avg_x_gain', 0):.2f}x")
                print(f"  Win Rate (2x): {channel.get('win_rate_2x', 0):.1%} | Win Rate (5x): {channel.get('win_rate_5x', 0):.1%}")
                print()
        else:
            print("No channel data available")

        # Message type performance
        print("📝 MESSAGE TYPE PERFORMANCE")
        print("-" * 40)
        msg_type_perf = report["message_type_performance"]
        if msg_type_perf:
            for msg_type in msg_type_perf:
                print(f"Type: {msg_type['message_type']}")
                print(f"  Calls: {msg_type['total_calls']} | Avg Gain: {msg_type.get('avg_x_gain', 0):.2f}x")
                print(f"  Win Rate (2x): {msg_type.get('win_rate_2x', 0):.1%}")
                print()
        else:
            print("No message type data available")

        # Linking analysis
        print("🔗 MESSAGE LINKING ANALYSIS")
        print("-" * 40)
        linking = report["linking_analysis"]
        print(f"Total Calls: {linking['total_calls']}")
        print(f"Discovery Calls: {linking['discovery_calls']}")
        print(f"Update Calls: {linking['update_calls']}")
        print(f"Successfully Linked: {linking['linked_calls']}")
        print(f"Linking Success Rate: {linking['linking_rate']:.1%}")
        print()

        # Data quality
        print("🔍 DATA QUALITY")
        print("-" * 40)
        quality = report["data_quality"]
        print(f"Total Records: {quality['total_records']}")
        print(f"Missing X-Gain: {quality['missing_x_gain']}")
        print(f"Missing Entry Cap: {quality['missing_entry_cap']}")
        print(f"Missing Peak Cap: {quality['missing_peak_cap']}")
        print(f"Missing Timestamps: {quality['missing_timestamps']}")
        print()

        # Time-based performance (if available)
        time_perf = report.get("time_based_performance", {})
        if time_perf.get("daily_performance"):
            print("📅 DAILY PERFORMANCE")
            print("-" * 40)
            for day, stats in time_perf["daily_performance"].items():
                if stats.get('total_calls', 0) > 0:
                    print(f"{day.capitalize()}: {stats['total_calls']} calls | Avg: {stats.get('avg_x_gain', 0):.2f}x | 2x Rate: {stats.get('win_rate_2x', 0):.1%}")
            print()

        # Save detailed report
        import json
        from pathlib import Path
        
        # Ensure reports directory exists
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        report_file = reports_dir / f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"💾 Detailed report saved to: {report_file}")

    except Exception as e:
        print(f"❌ Error during analytics: {e}")
        import traceback
        traceback.print_exc()


def run_data_cleansing_analysis() -> None:
    """Run data cleansing analysis and show before/after comparison."""
    db_path = get_database_path()
    if not db_path:
        print("❌ No database files found!")
        print("Run the monitor script first to collect data.")
        return

    try:
        print(f"🧹 DATA CLEANSING ANALYSIS")
        print(f"📁 Database: {db_path}")
        print("=" * 80)

        # Extract raw data
        print("🔄 Extracting raw crypto calls data...")
        raw_df = extract_crypto_calls_data(db_path=db_path)
        
        if raw_df.empty:
            print("❌ No crypto calls data found in database.")
            print("Run the monitor and let it collect some data first.")
            return

        print(f"✅ Loaded {len(raw_df)} raw records")
        print()

        # Generate data quality report for raw data
        print("📊 RAW DATA QUALITY REPORT")
        print("-" * 50)
        raw_quality = get_data_quality_report(raw_df)
        
        print(f"Total Records: {raw_quality['total_records']}")
        print()
        
        if raw_quality.get('missing_data'):
            print("❌ Missing Data:")
            for col, info in raw_quality['missing_data'].items():
                print(f"  {col}: {info['count']} records ({info['percentage']}%)")
            print()
        
        if raw_quality.get('outliers'):
            print("⚠️  Outliers Detected:")
            for col, info in raw_quality['outliers'].items():
                print(f"  {col}: {info['count']} outliers ({info['percentage']}%)")
                print(f"    Range: {info['min_outlier']:.2f} to {info['max_outlier']:.2f}")
            print()
        
        if raw_quality.get('duplicates'):
            print("🔄 Duplicates:")
            for col, count in raw_quality['duplicates'].items():
                print(f"  {col}: {count} duplicate records")
            print()

        # Apply data cleansing
        print("🧹 APPLYING DATA CLEANSING...")
        print("-" * 50)
        
        # Show cleansing options
        print("Cleansing Configuration:")
        print("  ✅ Drop rows missing both entry_cap and peak_cap")
        print("  ✅ Flag outliers (x_gain > 1000x)")
        print("  ✅ Convert timestamps to timezone-aware datetime")
        print("  ✅ Normalize token and channel names")
        print("  ✅ Calculate missing x_gain from caps")
        print()
        
        # Apply cleansing
        clean_df = cleanse_crypto_calls_data(
            raw_df,
            drop_missing_caps=True,
            handle_outliers=True,
            outlier_threshold=1000.0,
            normalize_names=True,
            convert_timestamps=True
        )
        
        print(f"✅ Cleansing complete: {len(raw_df)} → {len(clean_df)} records")
        print()

        # Generate data quality report for cleaned data
        print("📊 CLEANED DATA QUALITY REPORT")
        print("-" * 50)
        clean_quality = get_data_quality_report(clean_df)
        
        print(f"Total Records: {clean_quality['total_records']}")
        print()
        
        if clean_quality.get('missing_data'):
            print("❌ Remaining Missing Data:")
            for col, info in clean_quality['missing_data'].items():
                print(f"  {col}: {info['count']} records ({info['percentage']}%)")
            print()
        else:
            print("✅ No significant missing data remaining")
            print()
        
        if clean_quality.get('outliers'):
            print("⚠️  Remaining Outliers:")
            for col, info in clean_quality['outliers'].items():
                print(f"  {col}: {info['count']} outliers ({info['percentage']}%)")
            print()
        
        # Show cleansing impact
        print("📈 CLEANSING IMPACT")
        print("-" * 50)
        
        # Records retained
        retention_rate = (len(clean_df) / len(raw_df)) * 100
        print(f"Record Retention: {retention_rate:.1f}% ({len(clean_df)}/{len(raw_df)})")
        
        # Missing data improvement
        raw_missing_x_gain = raw_quality.get('missing_data', {}).get('x_gain', {}).get('count', 0)
        clean_missing_x_gain = clean_quality.get('missing_data', {}).get('x_gain', {}).get('count', 0)
        
        if raw_missing_x_gain > clean_missing_x_gain:
            recovered = raw_missing_x_gain - clean_missing_x_gain
            print(f"X-Gain Recovery: {recovered} values calculated from caps")
        
        # Show recommendations
        if clean_quality.get('recommendations'):
            print()
            print("💡 RECOMMENDATIONS:")
            for rec in clean_quality['recommendations']:
                print(f"  • {rec}")
        
        print()
        
        # Offer to show sample of cleaned data
        show_sample = input("Would you like to see a sample of cleaned data? (y/n): ").strip().lower()
        if show_sample == 'y':
            print()
            print("📋 SAMPLE CLEANED DATA")
            print("-" * 50)
            
            # Show first 5 records with key columns
            sample_cols = ['token_name', 'channel_name', 'message_type', 'entry_cap', 'peak_cap', 'x_gain', 'timestamp']
            available_cols = [col for col in sample_cols if col in clean_df.columns]
            
            sample_df = clean_df[available_cols].head(5)
            print(sample_df.to_string(index=False))
            print()
            
            # Show outliers if any
            if 'is_outlier' in clean_df.columns and clean_df['is_outlier'].any():
                print("⚠️  FLAGGED OUTLIERS:")
                outlier_df = clean_df[clean_df['is_outlier']][['token_name', 'x_gain', 'channel_name', 'timestamp']].head(3)
                print(outlier_df.to_string(index=False))
                print()

        # Save cleaned data option
        save_cleaned = input("Would you like to save the cleaned dataset to CSV? (y/n): ").strip().lower()
        if save_cleaned == 'y':
            from pathlib import Path
            
            # Ensure reports directory exists
            reports_dir = Path("reports")
            reports_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = reports_dir / f"cleaned_crypto_calls_{timestamp}.csv"
            clean_df.to_csv(filename, index=False)
            print(f"💾 Cleaned data saved to: {filename}")

    except Exception as e:
        print(f"❌ Error during data cleansing analysis: {e}")
        import traceback
        traceback.print_exc()


def main() -> None:
    """Main function with comprehensive analysis menu."""
    print("🔍 Crypto Call Database Analyzer")
    print("=" * 50)

    while True:
        print("\n🎯 Analysis Options:")
        print("1. 🔗 View Linked Messages & Token Chains")
        print("2. 📝 View Full Raw Message Text")
        print("3. 📊 Database Statistics & Structure")
        print("4. 🔬 Test Linking Integrity")
        print("5. 🔧 Fix Token Name Inheritance")
        print("6. 📈 Run Comprehensive Analytics")
        print("7. 🧹 Data Cleansing Analysis")
        print("8. 🚪 Exit")

        choice = input("\nEnter choice (1-8): ").strip()

        if choice == "1":
            view_linked_messages()
        elif choice == "2":
            view_raw_message_text()
        elif choice == "3":
            view_database_stats()
        elif choice == "4":
            test_linking_integrity()
        elif choice == "5":
            fix_token_inheritance()
        elif choice == "6":
            run_comprehensive_analytics()
        elif choice == "7":
            run_data_cleansing_analysis()
        elif choice == "8":
            print("👋 Analysis complete!")
            break
        else:
            print("❌ Invalid choice")

        if choice in ["1", "2", "3", "4", "5", "6", "7"]:
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()
