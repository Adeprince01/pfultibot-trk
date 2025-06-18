"""SQLite storage implementation for crypto call data."""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class SQLiteStorage:
    """SQLite-based storage implementation for crypto call data.

    This class provides persistent storage using SQLite database with proper
    error handling and resource management.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize SQLite storage with database path.

        Args:
            db_path: Path to the SQLite database file.

        Raises:
            Exception: If database initialization fails.
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database and create tables if they don't exist.

        Raises:
            Exception: If database or table creation fails.
        """
        try:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._connection.row_factory = sqlite3.Row

            # Create crypto_calls table
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS crypto_calls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_name TEXT,
                    entry_cap REAL,
                    peak_cap REAL,
                    x_gain REAL,
                    vip_x REAL,
                    timestamp TEXT,
                    message_id INTEGER,
                    channel_name TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Create raw_messages table for storing ALL messages before classification
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS raw_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    channel_name TEXT,
                    message_text TEXT,
                    message_date DATETIME,
                    is_classified BOOLEAN DEFAULT FALSE,
                    classification_result TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(message_id, channel_id)
                )
            """
            )

            self._connection.commit()

            logger.info(f"SQLite database initialized at {self.db_path}")

        except sqlite3.Error as e:
            logger.error(f"Failed to initialize SQLite database: {e}")
            raise

    def append_row(self, data: Dict[str, Any]) -> None:
        """Append a new row of crypto call data to the database.

        Args:
            data: Dictionary containing crypto call data to store.
                 Expected keys: token_name, entry_cap, peak_cap, x_gain,
                 vip_x, timestamp, message_id, channel_name

        Raises:
            ValueError: If data is None or not a dictionary.
            Exception: If database insertion fails.
        """
        if data is None:
            raise ValueError("Data cannot be None")

        if not isinstance(data, dict):
            raise TypeError("Data must be a dictionary")

        if not data:
            raise ValueError("Data dictionary cannot be empty")

        if not self._connection:
            raise Exception("Database connection is not available")

        try:
            # Extract values with None as default for missing keys
            values = (
                data.get("token_name"),
                data.get("entry_cap"),
                data.get("peak_cap"),
                data.get("x_gain"),
                data.get("vip_x"),
                data.get("timestamp"),
                data.get("message_id"),
                data.get("channel_name"),
            )

            self._connection.execute(
                """
                INSERT INTO crypto_calls 
                (token_name, entry_cap, peak_cap, x_gain, vip_x, timestamp, message_id, channel_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                values,
            )

            self._connection.commit()
            logger.debug(
                f"Inserted crypto call data for token: {data.get('token_name')}"
            )

        except sqlite3.Error as e:
            logger.error(f"Failed to insert data into SQLite: {e}")
            raise

    def get_records(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve records from the database.

        Args:
            limit: Maximum number of records to return. If None, returns all records.

        Returns:
            List of dictionaries containing stored crypto call data.

        Raises:
            Exception: If database query fails.
        """
        if not self._connection:
            raise Exception("Database connection is not available")

        try:
            query = """
                SELECT token_name, entry_cap, peak_cap, x_gain, vip_x, 
                       timestamp, message_id, channel_name
                FROM crypto_calls 
                ORDER BY created_at DESC
            """

            if limit is not None:
                query += f" LIMIT {limit}"

            cursor = self._connection.execute(query)
            rows = cursor.fetchall()

            # Convert sqlite3.Row objects to dictionaries
            records = []
            for row in rows:
                record = {
                    "token_name": row["token_name"],
                    "entry_cap": row["entry_cap"],
                    "peak_cap": row["peak_cap"],
                    "x_gain": row["x_gain"],
                    "vip_x": row["vip_x"],
                    "timestamp": row["timestamp"],
                    "message_id": row["message_id"],
                    "channel_name": row["channel_name"],
                }
                records.append(record)

            logger.debug(f"Retrieved {len(records)} records from SQLite")
            return records

        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve records from SQLite: {e}")
            raise

    def close(self) -> None:
        """Close database connection and cleanup resources.

        This method should be called when finished with the storage instance
        to properly clean up database connections.
        """
        if self._connection:
            try:
                self._connection.close()
                self._connection = None
                logger.debug("SQLite connection closed")
            except sqlite3.Error as e:
                logger.error(f"Error closing SQLite connection: {e}")
                # Don't re-raise as this is cleanup code

    def store_raw_message(self, message_data: Dict[str, Any]) -> None:
        """Store a raw message before classification.

        Args:
            message_data: Dictionary containing raw message data
                Expected keys: message_id, channel_id, channel_name, 
                message_text, message_date

        Raises:
            Exception: If storage operation fails.
        """
        if not self._connection:
            raise Exception("Database connection is not available")

        try:
            self._connection.execute(
                """
                INSERT OR REPLACE INTO raw_messages 
                (message_id, channel_id, channel_name, message_text, message_date)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    message_data["message_id"],
                    message_data["channel_id"],
                    message_data["channel_name"],
                    message_data["message_text"],
                    message_data["message_date"],
                ),
            )
            self._connection.commit()

            logger.debug(f"Stored raw message {message_data['message_id']} from channel {message_data['channel_id']}")

        except sqlite3.Error as e:
            logger.error(f"Failed to store raw message to SQLite: {e}")
            raise

    def get_raw_messages(
        self, 
        limit: Optional[int] = None, 
        channel_id: Optional[int] = None,
        unclassified_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Retrieve raw messages from storage.

        Args:
            limit: Maximum number of records to return
            channel_id: Filter by specific channel ID
            unclassified_only: Only return messages that haven't been classified

        Returns:
            List of dictionaries containing raw message data

        Raises:
            Exception: If retrieval operation fails.
        """
        if not self._connection:
            raise Exception("Database connection is not available")

        try:
            query = """
                SELECT message_id, channel_id, channel_name, message_text, 
                       message_date, is_classified, classification_result, created_at
                FROM raw_messages 
                WHERE 1=1
            """
            params = []

            if channel_id is not None:
                query += " AND channel_id = ?"
                params.append(channel_id)

            if unclassified_only:
                query += " AND is_classified = FALSE"

            query += " ORDER BY created_at DESC"

            if limit is not None:
                query += " LIMIT ?"
                params.append(limit)

            cursor = self._connection.execute(query, params)
            rows = cursor.fetchall()

            # Convert sqlite3.Row objects to dictionaries
            records = []
            for row in rows:
                record = {
                    "message_id": row["message_id"],
                    "channel_id": row["channel_id"],
                    "channel_name": row["channel_name"],
                    "message_text": row["message_text"],
                    "message_date": row["message_date"],
                    "is_classified": bool(row["is_classified"]),
                    "classification_result": row["classification_result"],
                    "created_at": row["created_at"],
                }
                records.append(record)

            logger.debug(f"Retrieved {len(records)} raw messages from SQLite")
            return records

        except sqlite3.Error as e:
            logger.error(f"Failed to retrieve raw messages from SQLite: {e}")
            raise
