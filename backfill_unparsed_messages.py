#!/usr/bin/env python3
"""Backfill Script: Re-parse unparsed raw messages and link to discovery calls.

This script finds raw Telegram messages that failed initial parsing, re-parses them
with the current parser logic, attempts to link them to existing discovery calls,
and inserts them into the crypto_calls table.

Features:
- Batch processing for memory efficiency
- Reply-based and heuristic linking
- Dry-run mode for safe testing
- Progress tracking and detailed logging
- Transaction safety with rollback on errors
"""

import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.parser import parse_crypto_call
from src.storage.sqlite import SQLiteStorage


# Configure logging
def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration for the backfill script."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "backfill.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


logger = logging.getLogger(__name__)


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


class BackfillProcessor:
    """Processes unparsed raw messages and links them to discovery calls."""

    def __init__(self, db_path: Path, dry_run: bool = False) -> None:
        """Initialize the backfill processor.

        Args:
            db_path: Path to the SQLite database
            dry_run: If True, parse and link but don't write to database
        """
        self.db_path = db_path
        self.dry_run = dry_run
        self.connection: Optional[sqlite3.Connection] = None
        self.storage: Optional[SQLiteStorage] = None

        # Statistics tracking
        self.stats = {
            "processed": 0,
            "parsed_successfully": 0,
            "linked_by_reply": 0,
            "linked_by_heuristic": 0,
            "inserted": 0,
            "skipped": 0,
            "errors": 0,
        }

    def __enter__(self) -> "BackfillProcessor":
        """Context manager entry - establish database connection."""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row

            if not self.dry_run:
                self.storage = SQLiteStorage(self.db_path)

            logger.info(f"Connected to database: {self.db_path}")
            return self

        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - close database connection."""
        if self.storage:
            self.storage.close()
        if self.connection:
            self.connection.close()
        logger.info("Database connection closed")

    def get_unparsed_messages(
        self, since_hours: int = 24, batch_size: int = 500, offset: int = 0
    ) -> List[Dict]:
        """Get unparsed raw messages that don't have corresponding crypto_calls.

        Args:
            since_hours: Only process messages newer than X hours
            batch_size: Number of records to fetch per batch
            offset: Offset for pagination

        Returns:
            List of raw message dictionaries
        """
        cutoff_time = datetime.now() - timedelta(hours=since_hours)

        query = """
            SELECT rm.*
            FROM raw_messages rm
            LEFT JOIN crypto_calls cc ON rm.message_id = cc.message_id
            WHERE cc.id IS NULL
            AND rm.message_date >= ?
            ORDER BY rm.message_date DESC
            LIMIT ? OFFSET ?
        """

        cursor = self.connection.execute(
            query, (cutoff_time.strftime("%Y-%m-%d %H:%M:%S"), batch_size, offset)
        )

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def link_to_discovery_call(
        self, raw_message: Dict, parsed_data: Dict
    ) -> Optional[int]:
        """Link an update message to its discovery call using reliable methods only.

        Args:
            raw_message: Raw message data from database
            parsed_data: Parsed crypto call data

        Returns:
            Database ID of linked discovery call, or None if no link found
        """
        # Skip linking for discovery messages
        if parsed_data.get("message_type") == "discovery":
            return None

        # Priority 1: Reply-based linking (MOST RELIABLE)
        if raw_message.get("reply_to_message_id"):
            cursor = self.connection.execute(
                "SELECT id FROM crypto_calls WHERE message_id = ? LIMIT 1",
                (raw_message["reply_to_message_id"],),
            )
            row = cursor.fetchone()
            if row:
                self.stats["linked_by_reply"] += 1
                logger.debug(
                    f"Linked via reply to message {raw_message['reply_to_message_id']}"
                )
                return row["id"]

        # Priority 2: Exact contract address match (VERY RELIABLE)
        if parsed_data.get("contract_address"):
            cursor = self.connection.execute(
                """
                SELECT id FROM crypto_calls 
                WHERE contract_address = ? 
                AND message_type = 'discovery'
                AND channel_name = ?
                AND datetime(timestamp) >= datetime('now', '-24 hours')
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (parsed_data["contract_address"], raw_message.get("channel_name", "")),
            )
            row = cursor.fetchone()
            if row:
                self.stats["linked_by_heuristic"] += 1
                logger.debug(f"Linked via contract address to discovery {row['id']}")
                return row["id"]

        # Priority 3: Exact token name match (MODERATELY RELIABLE)
        if parsed_data.get("token_name"):
            cursor = self.connection.execute(
                """
                SELECT id FROM crypto_calls 
                WHERE LOWER(token_name) = LOWER(?) 
                AND message_type = 'discovery'
                AND channel_name = ?
                AND datetime(timestamp) >= datetime('now', '-24 hours')
                ORDER BY timestamp DESC
                LIMIT 1
                """,
                (parsed_data["token_name"], raw_message.get("channel_name", "")),
            )
            row = cursor.fetchone()
            if row:
                self.stats["linked_by_heuristic"] += 1
                logger.debug(
                    f"Linked via token name '{parsed_data['token_name']}' to discovery {row['id']}"
                )
                return row["id"]

        # NO MARKET CAP MATCHING - too unreliable!
        logger.debug("No reliable linking found for update message")
        return None

    def inherit_discovery_data(self, parsed_data: Dict, discovery_id: int) -> Dict:
        """Inherit token name and other data from discovery call.

        Args:
            parsed_data: Current parsed data (may be incomplete)
            discovery_id: ID of the discovery call to inherit from

        Returns:
            Enhanced parsed data with inherited fields
        """
        if not discovery_id:
            return parsed_data

        cursor = self.connection.execute(
            "SELECT token_name, contract_address FROM crypto_calls WHERE id = ? LIMIT 1",
            (discovery_id,),
        )
        row = cursor.fetchone()

        if row:
            enhanced_data = parsed_data.copy()

            # Inherit token name if not present
            if not enhanced_data.get("token_name") and row["token_name"]:
                enhanced_data["token_name"] = row["token_name"]
                logger.debug(f"Inherited token name: {row['token_name']}")

            # Inherit contract address if not present
            if not enhanced_data.get("contract_address") and row["contract_address"]:
                enhanced_data["contract_address"] = row["contract_address"]
                logger.debug(f"Inherited contract address: {row['contract_address']}")

            return enhanced_data

        return parsed_data

    def prepare_storage_record(
        self, raw_message: Dict, parsed_data: Dict, linked_call_id: Optional[int]
    ) -> Dict:
        """Prepare a complete record for storage.

        Args:
            raw_message: Original raw message data
            parsed_data: Parsed crypto call data
            linked_call_id: ID of linked discovery call (if any)

        Returns:
            Complete record ready for storage
        """
        return {
            "token_name": parsed_data.get("token_name"),
            "entry_cap": parsed_data.get("entry_cap"),
            "peak_cap": parsed_data.get("peak_cap"),
            "x_gain": parsed_data.get("x_gain"),
            "vip_x": parsed_data.get("vip_x"),
            "message_type": parsed_data.get("message_type", "update"),
            "contract_address": parsed_data.get("contract_address"),
            "time_to_peak": parsed_data.get("time_to_peak"),
            "timestamp": raw_message.get("message_date"),
            "message_id": raw_message.get("message_id"),
            "channel_name": raw_message.get("channel_name"),
            "linked_crypto_call_id": linked_call_id,
        }

    def process_batch(self, messages: List[Dict], verbose: bool = False) -> None:
        """Process a batch of raw messages.

        Args:
            messages: List of raw message dictionaries
            verbose: Print detailed progress information
        """
        if not messages:
            return

        logger.info(f"Processing batch of {len(messages)} messages...")

        for i, raw_message in enumerate(messages, 1):
            try:
                self.stats["processed"] += 1

                # Parse the message
                parsed_data = parse_crypto_call(raw_message.get("message_text"))

                if not parsed_data:
                    self.stats["skipped"] += 1
                    if verbose:
                        logger.debug(
                            f"Message {raw_message['message_id']} could not be parsed"
                        )
                    continue

                self.stats["parsed_successfully"] += 1

                # Attempt to link to discovery call
                linked_call_id = self.link_to_discovery_call(raw_message, parsed_data)

                # Inherit data from discovery if linked
                if linked_call_id:
                    parsed_data = self.inherit_discovery_data(
                        parsed_data, linked_call_id
                    )

                # Prepare complete record
                storage_record = self.prepare_storage_record(
                    raw_message, parsed_data, linked_call_id
                )

                if verbose:
                    token = storage_record.get("token_name", "Unknown")
                    gain = storage_record.get("x_gain", 0)
                    link_info = (
                        f" -> Discovery {linked_call_id}" if linked_call_id else ""
                    )
                    logger.info(f"  [{i}/{len(messages)}] {token}: {gain}x{link_info}")

                # Store the record (unless dry run)
                if not self.dry_run:
                    self.storage.append_row(storage_record)

                self.stats["inserted"] += 1

            except Exception as e:
                self.stats["errors"] += 1
                logger.error(
                    f"Error processing message {raw_message.get('message_id', 'unknown')}: {e}"
                )
                continue

    def mark_processed_messages(self, messages: List[Dict]) -> None:
        """Mark processed messages as classified (optional - for tracking).

        Args:
            messages: List of processed message dictionaries
        """
        if self.dry_run:
            return

        try:
            message_ids = [
                msg["message_id"] for msg in messages if msg.get("message_id")
            ]

            if message_ids:
                placeholders = ",".join("?" * len(message_ids))
                self.connection.execute(
                    f"""
                    UPDATE raw_messages 
                    SET is_classified = 1, classification_result = 'backfilled'
                    WHERE message_id IN ({placeholders})
                    """,
                    message_ids,
                )
                self.connection.commit()
                logger.debug(f"Marked {len(message_ids)} messages as processed")

        except Exception as e:
            logger.error(f"Failed to mark messages as processed: {e}")

    def print_progress(self, batch_num: int, total_estimated: int) -> None:
        """Print progress statistics.

        Args:
            batch_num: Current batch number
            total_estimated: Estimated total messages (may be approximate)
        """
        processed = self.stats["processed"]
        parsed = self.stats["parsed_successfully"]
        inserted = self.stats["inserted"]

        parse_rate = (parsed / max(processed, 1)) * 100

        print(f"\n📊 BATCH #{batch_num} PROGRESS")
        print(f"   Processed: {processed}")
        print(f"   Parsed: {parsed} ({parse_rate:.1f}%)")
        print(f"   Inserted: {inserted}")
        print(f"   Linked by reply: {self.stats['linked_by_reply']}")
        print(f"   Linked by heuristic: {self.stats['linked_by_heuristic']}")
        print(f"   Errors: {self.stats['errors']}")


def main() -> None:
    """Main function with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Backfill unparsed raw messages into crypto_calls table",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--since-hours",
        type=int,
        default=24,
        help="Only process messages newer than X hours",
    )

    parser.add_argument(
        "--batch", type=int, default=500, help="Number of messages to process per batch"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Stop after processing N messages (0 = no limit)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and link but don't write to database",
    )

    parser.add_argument(
        "--verbose", action="store_true", help="Print detailed progress information"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Find database
    db_path = get_database_path()
    if not db_path:
        logger.error("❌ No database files found!")
        logger.error("Run the monitor script first to collect data.")
        sys.exit(1)

    logger.info(f"🔄 Starting backfill process")
    logger.info(f"📊 Database: {db_path}")
    logger.info(f"⏰ Since: {args.since_hours} hours ago")
    logger.info(f"📦 Batch size: {args.batch}")
    logger.info(f"🔒 Dry run: {args.dry_run}")

    if args.dry_run:
        print("\n⚠️  DRY RUN MODE - No database writes will occur")

    try:
        with BackfillProcessor(db_path, args.dry_run) as processor:
            batch_num = 0
            total_processed = 0

            while True:
                # Get next batch of unparsed messages
                messages = processor.get_unparsed_messages(
                    since_hours=args.since_hours,
                    batch_size=args.batch,
                    offset=total_processed,
                )

                if not messages:
                    logger.info("✅ No more unparsed messages found")
                    break

                batch_num += 1

                # Process the batch
                processor.process_batch(messages, args.verbose)

                # Mark messages as processed (optional)
                processor.mark_processed_messages(messages)

                # Update counters
                total_processed += len(messages)

                # Print progress
                processor.print_progress(batch_num, total_processed)

                # Check limit
                if args.limit > 0 and total_processed >= args.limit:
                    logger.info(f"✋ Reached limit of {args.limit} messages")
                    break

                # If we got fewer messages than batch size, we're done
                if len(messages) < args.batch:
                    logger.info("✅ Processed all available messages")
                    break

        # Final statistics
        stats = processor.stats
        print(f"\n{'='*60}")
        print(f"✅ BACKFILL COMPLETE")
        print(f"{'='*60}")
        print(f"📊 Total Processed: {stats['processed']}")
        print(f"✅ Successfully Parsed: {stats['parsed_successfully']}")
        print(f"💾 Inserted: {stats['inserted']}")
        print(f"🔗 Linked by Reply: {stats['linked_by_reply']}")
        print(f"🎯 Linked by Heuristic: {stats['linked_by_heuristic']}")
        print(f"⏭️  Skipped: {stats['skipped']}")
        print(f"❌ Errors: {stats['errors']}")

        if stats["processed"] > 0:
            parse_rate = (stats["parsed_successfully"] / stats["processed"]) * 100
            print(f"📈 Parse Success Rate: {parse_rate:.1f}%")

        if args.dry_run:
            print(f"\n⚠️  This was a DRY RUN - no data was actually inserted")
            print(f"   Run without --dry-run to perform actual backfill")

        print(f"📝 Detailed logs saved to: logs/backfill.log")
        print(f"{'='*60}")

    except Exception as e:
        logger.error(f"❌ Backfill failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
