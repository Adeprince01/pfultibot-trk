"""Test suite for backfill_unparsed_messages.py script."""

import sqlite3

# Add project root to path for imports
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from backfill_unparsed_messages import BackfillProcessor, get_database_path
from src.storage.sqlite import SQLiteStorage


@pytest.fixture
def temp_db():
    """Create a temporary test database with sample data."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_path = Path(temp_file.name)
    temp_file.close()

    # Initialize database with tables
    storage = SQLiteStorage(db_path)

    # Add sample raw messages
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Sample discovery message (already processed)
    discovery_message_id = 12345
    conn.execute(
        """
        INSERT INTO raw_messages 
        (message_id, channel_id, channel_name, message_text, message_date, is_classified, classification_result)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            discovery_message_id,
            -1002380293749,
            "Pumpfun Ultimate Alert",
            "Bean Cabal (CABAL)\n944XTHEz... Entry: 45.9K MC",
            (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
            True,
            "parsed",
        ),
    )

    # Add corresponding crypto call for discovery
    conn.execute(
        """
        INSERT INTO crypto_calls 
        (token_name, entry_cap, peak_cap, x_gain, message_type, message_id, channel_name, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            "CABAL",
            45900.0,
            45900.0,
            1.0,
            "discovery",
            discovery_message_id,
            "Pumpfun Ultimate Alert",
            (datetime.now() - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )

    # Sample unparsed update message (reply to discovery)
    conn.execute(
        """
        INSERT INTO raw_messages 
        (message_id, channel_id, channel_name, message_text, message_date, reply_to_message_id, is_classified)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            12346,
            -1002380293749,
            "Pumpfun Ultimate Alert",
            "🚀 **3.6x(4.6x from VIP)** `|` 💹`From` **45.9K** ↗️ **165.2K** `within` **8m**",
            (datetime.now() - timedelta(minutes=22)).strftime("%Y-%m-%d %H:%M:%S"),
            discovery_message_id,
            False,
        ),
    )

    # Sample unparsed message without reply (needs heuristic linking)
    conn.execute(
        """
        INSERT INTO raw_messages 
        (message_id, channel_id, channel_name, message_text, message_date, is_classified)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            12347,
            -1002380293749,
            "Pumpfun Ultimate Alert",
            "🌕 **5.2x** `|` 💹`From` **45.9K** ↗️ **238.7K** `within` **15m**",
            (datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"),
            False,
        ),
    )

    # Sample unparsable message
    conn.execute(
        """
        INSERT INTO raw_messages 
        (message_id, channel_id, channel_name, message_text, message_date, is_classified)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            12348,
            -1002380293749,
            "Pumpfun Ultimate Alert",
            "Just random text that can't be parsed",
            (datetime.now() - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S"),
            False,
        ),
    )

    conn.commit()
    conn.close()
    storage.close()

    yield db_path

    # Cleanup
    db_path.unlink()


class TestBackfillProcessor:
    """Test the BackfillProcessor class."""

    def test_processor_context_manager(self, temp_db):
        """Test the context manager functionality."""
        with BackfillProcessor(temp_db, dry_run=True) as processor:
            assert processor.connection is not None
            assert processor.storage is None  # dry_run mode
            assert processor.stats["processed"] == 0

    def test_get_unparsed_messages(self, temp_db):
        """Test fetching unparsed messages."""
        with BackfillProcessor(temp_db, dry_run=True) as processor:
            messages = processor.get_unparsed_messages(since_hours=1, batch_size=10)

            # Should get 3 unparsed messages (excluding the discovery which is already processed)
            assert len(messages) == 3

            # Check message IDs
            message_ids = [msg["message_id"] for msg in messages]
            assert 12346 in message_ids  # Reply message
            assert 12347 in message_ids  # Heuristic message
            assert 12348 in message_ids  # Unparsable message

    def test_link_to_discovery_call_by_reply(self, temp_db):
        """Test linking update to discovery via reply."""
        with BackfillProcessor(temp_db, dry_run=True) as processor:
            # Get the reply message
            messages = processor.get_unparsed_messages(since_hours=1)
            reply_message = next(msg for msg in messages if msg["message_id"] == 12346)

            # Mock parsed data
            parsed_data = {
                "message_type": "update",
                "x_gain": 3.6,
                "vip_x": 4.6,
                "entry_cap": 45900.0,
                "peak_cap": 165200.0,
            }

            # Should link via reply
            linked_id = processor.link_to_discovery_call(reply_message, parsed_data)
            assert linked_id is not None
            assert processor.stats["linked_by_reply"] == 1

    def test_link_to_discovery_call_by_heuristic(self, temp_db):
        """Test linking update to discovery via heuristic matching."""
        with BackfillProcessor(
            temp_db, dry_run=False
        ) as processor:  # Need storage for heuristic
            # Get the heuristic message (no reply)
            messages = processor.get_unparsed_messages(since_hours=1)
            heuristic_message = next(
                msg for msg in messages if msg["message_id"] == 12347
            )

            # Mock parsed data with entry_cap that should match
            parsed_data = {
                "message_type": "update",
                "x_gain": 5.2,
                "entry_cap": 45900.0,  # Should match discovery entry cap
                "peak_cap": 238700.0,
            }

            # Should link via heuristic (entry cap match)
            linked_id = processor.link_to_discovery_call(heuristic_message, parsed_data)
            assert linked_id is not None
            assert processor.stats["linked_by_heuristic"] == 1

    def test_inherit_discovery_data(self, temp_db):
        """Test inheriting token name from discovery call."""
        with BackfillProcessor(temp_db, dry_run=True) as processor:
            # Mock parsed data without token name
            parsed_data = {
                "message_type": "update",
                "x_gain": 3.6,
                "entry_cap": None,
                "peak_cap": 165200.0,
            }

            # Get discovery call ID
            cursor = processor.connection.execute(
                "SELECT id FROM crypto_calls WHERE message_type = 'discovery' LIMIT 1"
            )
            discovery_id = cursor.fetchone()["id"]

            # Inherit data
            enhanced_data = processor.inherit_discovery_data(parsed_data, discovery_id)

            # Should have inherited token name
            assert enhanced_data["token_name"] == "CABAL"
            assert enhanced_data["x_gain"] == 3.6  # Original data preserved

    def test_prepare_storage_record(self, temp_db):
        """Test preparing a complete storage record."""
        with BackfillProcessor(temp_db, dry_run=True) as processor:
            raw_message = {
                "message_id": 12346,
                "message_date": "2024-01-01 12:00:00",
                "channel_name": "Test Channel",
            }

            parsed_data = {
                "token_name": "CABAL",
                "x_gain": 3.6,
                "vip_x": 4.6,
                "entry_cap": 45900.0,
                "peak_cap": 165200.0,
                "message_type": "update",
            }

            linked_call_id = 1

            record = processor.prepare_storage_record(
                raw_message, parsed_data, linked_call_id
            )

            # Verify all fields are present
            assert record["token_name"] == "CABAL"
            assert record["x_gain"] == 3.6
            assert record["vip_x"] == 4.6
            assert record["message_id"] == 12346
            assert record["linked_crypto_call_id"] == 1
            assert record["message_type"] == "update"

    @patch("backfill_unparsed_messages.parse_crypto_call")
    def test_process_batch_success(self, mock_parse, temp_db):
        """Test processing a batch of messages successfully."""
        # Mock the parser to return valid data
        mock_parse.return_value = {
            "token_name": None,
            "x_gain": 3.6,
            "vip_x": 4.6,
            "entry_cap": 45900.0,
            "peak_cap": 165200.0,
            "message_type": "update",
        }

        with BackfillProcessor(temp_db, dry_run=True) as processor:
            messages = processor.get_unparsed_messages(since_hours=1, batch_size=1)

            processor.process_batch(messages, verbose=True)

            # Check statistics
            assert processor.stats["processed"] == 1
            assert processor.stats["parsed_successfully"] == 1
            assert processor.stats["inserted"] == 1
            assert processor.stats["errors"] == 0

    @patch("backfill_unparsed_messages.parse_crypto_call")
    def test_process_batch_parse_failure(self, mock_parse, temp_db):
        """Test processing batch with unparsable messages."""
        # Mock parser to return None (parse failure)
        mock_parse.return_value = None

        with BackfillProcessor(temp_db, dry_run=True) as processor:
            messages = processor.get_unparsed_messages(since_hours=1, batch_size=1)

            processor.process_batch(messages, verbose=True)

            # Should skip unparsable messages
            assert processor.stats["processed"] == 1
            assert processor.stats["parsed_successfully"] == 0
            assert processor.stats["skipped"] == 1
            assert processor.stats["inserted"] == 0


class TestDatabasePath:
    """Test database path detection."""

    @patch("backfill_unparsed_messages.Path.exists")
    def test_get_database_path_found(self, mock_exists):
        """Test finding an existing database."""
        # Mock the first database path as existing
        mock_exists.side_effect = lambda: True

        result = get_database_path()
        assert result == Path("crypto_calls_production.db")

    @patch("backfill_unparsed_messages.Path.exists")
    def test_get_database_path_not_found(self, mock_exists):
        """Test when no database is found."""
        # Mock all paths as non-existing
        mock_exists.return_value = False

        result = get_database_path()
        assert result is None


@pytest.mark.integration
class TestBackfillIntegration:
    """Integration tests for the full backfill process."""

    def test_full_backfill_dry_run(self, temp_db):
        """Test complete backfill process in dry-run mode."""
        with BackfillProcessor(temp_db, dry_run=True) as processor:
            # Get all unparsed messages
            total_processed = 0
            batch_num = 0

            while True:
                messages = processor.get_unparsed_messages(
                    since_hours=1, batch_size=2, offset=total_processed
                )

                if not messages:
                    break

                batch_num += 1
                processor.process_batch(messages)
                total_processed += len(messages)

                if len(messages) < 2:
                    break

            # Should have processed all unparsed messages
            assert total_processed == 3
            assert processor.stats["processed"] == 3

            # At least some should be parsable
            assert processor.stats["parsed_successfully"] >= 2

    def test_real_backfill_with_storage(self, temp_db):
        """Test actual backfill with database writes."""
        # Count initial crypto_calls
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT COUNT(*) FROM crypto_calls")
        initial_count = cursor.fetchone()[0]
        conn.close()

        with BackfillProcessor(temp_db, dry_run=False) as processor:
            messages = processor.get_unparsed_messages(since_hours=1, batch_size=10)
            processor.process_batch(messages)

        # Check that new records were added
        conn = sqlite3.connect(temp_db)
        cursor = conn.execute("SELECT COUNT(*) FROM crypto_calls")
        final_count = cursor.fetchone()[0]
        conn.close()

        # Should have added at least the parsable messages
        assert final_count > initial_count
