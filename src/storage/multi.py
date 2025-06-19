"""Multi-storage implementation for simultaneous storage across multiple backends."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .excel import ExcelStorage
from .sheet import GoogleSheetsStorage
from .sqlite import SQLiteStorage

logger = logging.getLogger(__name__)


class MultiStorage:
    """Multi-backend storage implementation that writes to multiple storage systems.

    This class coordinates data storage across SQLite, Google Sheets, and Excel
    simultaneously, providing redundancy and multiple export formats.
    """

    def __init__(
        self,
        sqlite_path: Path,
        excel_path: Optional[Path] = None,
        sheet_id: Optional[str] = None,
        credentials_path: Optional[Path] = None,
    ) -> None:
        """Initialize multi-storage with specified backends.

        Args:
            sqlite_path: Path to SQLite database file (required).
            excel_path: Path to Excel file (optional).
            sheet_id: Google Sheets ID (optional).
            credentials_path: Path to Google service account credentials (required if sheet_id provided).

        Raises:
            ValueError: If sheet_id is provided without credentials_path.
            Exception: If any storage backend initialization fails.
        """
        self.sqlite_path = sqlite_path
        self.excel_path = excel_path
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        
        # Validate Google Sheets configuration
        if sheet_id and not credentials_path:
            raise ValueError("credentials_path is required when sheet_id is provided")
        
        # Initialize storage backends
        self._init_storage_backends()
        
        # Track which backends are active
        self.active_backends = []
        if self.sqlite_storage:
            self.active_backends.append("SQLite")
        if self.excel_storage:
            self.active_backends.append("Excel")
        if self.sheets_storage:
            self.active_backends.append("Google Sheets")
        
        logger.info(f"MultiStorage initialized with backends: {', '.join(self.active_backends)}")

    def _init_storage_backends(self) -> None:
        """Initialize all requested storage backends.

        Raises:
            Exception: If SQLite initialization fails (SQLite is required).
        """
        # SQLite is always required
        try:
            self.sqlite_storage = SQLiteStorage(self.sqlite_path)
            logger.info(f"SQLite storage initialized: {self.sqlite_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite storage: {e}")
            raise

        # Excel is optional
        self.excel_storage = None
        if self.excel_path:
            try:
                self.excel_storage = ExcelStorage(self.excel_path)
                logger.info(f"Excel storage initialized: {self.excel_path}")
            except Exception as e:
                logger.warning(f"Failed to initialize Excel storage: {e}")

        # Google Sheets is optional
        self.sheets_storage = None
        if self.sheet_id and self.credentials_path:
            try:
                self.sheets_storage = GoogleSheetsStorage(
                    sheet_id=self.sheet_id,
                    credentials_path=self.credentials_path
                )
                logger.info(f"Google Sheets storage initialized: {self.sheet_id}")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Sheets storage: {e}")

    def append_row(self, data: Dict[str, Any]) -> None:
        """Append data to all active storage backends.

        Args:
            data: Dictionary containing crypto call data to store.
                 Expected keys: token_name, entry_cap, peak_cap, x_gain,
                 vip_x, timestamp, message_id, channel_name

        Raises:
            ValueError: If data is invalid.
            Exception: If all storage operations fail.
        """
        if data is None:
            raise ValueError("Data cannot be None")

        if not isinstance(data, dict):
            raise TypeError("Data must be a dictionary")

        if not data:
            raise ValueError("Data dictionary cannot be empty")

        success_count = 0
        errors = []

        # Try SQLite first (primary storage)
        try:
            self.sqlite_storage.append_row(data)
            success_count += 1
            logger.debug("Data stored to SQLite successfully")
        except Exception as e:
            error_msg = f"SQLite storage failed: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        # Try Excel storage
        if self.excel_storage:
            try:
                self.excel_storage.append_row(data)
                success_count += 1
                logger.debug("Data stored to Excel successfully")
            except Exception as e:
                error_msg = f"Excel storage failed: {e}"
                logger.warning(error_msg)
                errors.append(error_msg)

        # Try Google Sheets storage
        if self.sheets_storage:
            try:
                self.sheets_storage.append_row(data)
                success_count += 1
                logger.debug("Data stored to Google Sheets successfully")
            except Exception as e:
                error_msg = f"Google Sheets storage failed: {e}"
                logger.warning(error_msg)
                errors.append(error_msg)

        # Log results
        token = data.get('token_name', 'Unknown')
        logger.info(f"Data for {token} stored to {success_count}/{len(self.active_backends)} backends")

        # If all storage operations failed, raise an exception
        if success_count == 0:
            raise Exception(f"All storage operations failed: {'; '.join(errors)}")

    def get_records(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve records from primary storage (SQLite).

        Args:
            limit: Maximum number of records to return. If None, returns all records.

        Returns:
            List of dictionaries containing stored crypto call data.

        Raises:
            Exception: If retrieval operation fails.
        """
        try:
            records = self.sqlite_storage.get_records(limit)
            logger.debug(f"Retrieved {len(records)} records from SQLite")
            return records
        except Exception as e:
            logger.error(f"Failed to retrieve records from SQLite: {e}")
            raise

    def get_backend_status(self) -> Dict[str, bool]:
        """Get the status of all storage backends.

        Returns:
            Dictionary with backend names as keys and availability as boolean values.
        """
        status = {
            "sqlite": self.sqlite_storage is not None,
            "excel": self.excel_storage is not None,
            "sheets": self.sheets_storage is not None,
        }
        return status

    def store_raw_message(self, message_data: Dict[str, Any]) -> None:
        """Store a raw message before classification (SQLite only).

        Args:
            message_data: Dictionary containing raw message data
                Expected keys: message_id, channel_id, channel_name, 
                message_text, message_date, reply_to_message_id

        Raises:
            Exception: If SQLite storage operation fails.
        """
        if message_data is None:
            raise ValueError("Message data cannot be None")

        if not isinstance(message_data, dict):
            raise TypeError("Message data must be a dictionary")

        if not message_data:
            raise ValueError("Message data dictionary cannot be empty")

        # Only store raw messages in SQLite (primary storage)
        try:
            if self.sqlite_storage:
                self.sqlite_storage.store_raw_message(message_data)
                logger.debug(f"Raw message {message_data.get('message_id')} stored to SQLite")
            else:
                logger.warning("Cannot store raw message: SQLite storage not available")
        except Exception as e:
            logger.error(f"Failed to store raw message: {e}")
            raise

    def get_raw_messages(
        self, 
        limit: Optional[int] = None, 
        channel_id: Optional[int] = None,
        unclassified_only: bool = False
    ) -> List[Dict[str, Any]]:
        """Retrieve raw messages from primary storage (SQLite only).

        Args:
            limit: Maximum number of records to return
            channel_id: Filter by specific channel ID
            unclassified_only: Only return messages that haven't been classified

        Returns:
            List of dictionaries containing raw message data

        Raises:
            Exception: If retrieval operation fails.
        """
        try:
            if self.sqlite_storage:
                records = self.sqlite_storage.get_raw_messages(limit, channel_id, unclassified_only)
                logger.debug(f"Retrieved {len(records)} raw messages from SQLite")
                return records
            else:
                logger.warning("Cannot retrieve raw messages: SQLite storage not available")
                return []
        except Exception as e:
            logger.error(f"Failed to retrieve raw messages: {e}")
            raise

    def close(self) -> None:
        """Close all storage backends and cleanup resources.

        This method should be called when finished with the storage instance
        to properly clean up resources (connections, file handles, etc.).
        """
        logger.info("Closing all storage backends...")

        # Close SQLite
        if self.sqlite_storage:
            try:
                self.sqlite_storage.close()
                logger.debug("SQLite storage closed")
            except Exception as e:
                logger.error(f"Error closing SQLite storage: {e}")

        # Close Excel
        if self.excel_storage:
            try:
                self.excel_storage.close()
                logger.debug("Excel storage closed")
            except Exception as e:
                logger.error(f"Error closing Excel storage: {e}")

        # Close Google Sheets
        if self.sheets_storage:
            try:
                self.sheets_storage.close()
                logger.debug("Google Sheets storage closed")
            except Exception as e:
                logger.error(f"Error closing Google Sheets storage: {e}")

        logger.info("All storage backends closed") 