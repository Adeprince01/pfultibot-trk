"""Storage module for persisting crypto call data.

This module provides an abstract storage protocol and concrete implementations
for different storage backends (SQLite, Excel, Google Sheets).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol


class StorageProtocol(Protocol):
    """Abstract protocol for storage implementations.

    This protocol defines the interface that all storage backends must implement
    to ensure consistent behavior across different storage options.
    """

    def append_row(self, data: Dict[str, Any]) -> None:
        """Append a new row of data to storage.

        Args:
            data: Dictionary containing the crypto call data to store.
                 Expected keys: token_name, entry_cap, peak_cap, x_gain,
                 vip_x, timestamp, message_id, channel_name

        Raises:
            ValueError: If data is invalid or missing required fields.
            Exception: If storage operation fails.
        """
        ...

    def get_records(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve records from storage.

        Args:
            limit: Maximum number of records to return. If None, returns all records.

        Returns:
            List of dictionaries containing stored crypto call data.

        Raises:
            Exception: If retrieval operation fails.
        """
        ...

    def close(self) -> None:
        """Close storage connection and cleanup resources.

        This method should be called when finished with the storage instance
        to properly clean up any resources (connections, file handles, etc.).
        """
        ...


from .excel import ExcelStorage
from .multi import MultiStorage
from .sheet import GoogleSheetsStorage
from .sqlite import SQLiteStorage

__all__ = ["StorageProtocol", "SQLiteStorage", "ExcelStorage", "GoogleSheetsStorage", "MultiStorage"]
