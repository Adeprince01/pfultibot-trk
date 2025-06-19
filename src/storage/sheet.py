"""Google Sheets storage implementation for crypto call data."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import gspread
    from gspread import Worksheet
except ImportError:
    raise ImportError(
        "gspread is required for Google Sheets storage. Install with: pip install gspread google-auth"
    )

logger = logging.getLogger(__name__)


class GoogleSheetsStorage:
    """Google Sheets-based storage implementation for crypto call data.

    This class provides persistent storage using Google Sheets with proper
    error handling and API management.
    """

    def __init__(
        self,
        sheet_id: str,
        credentials_path: Path,
        worksheet_name: str = "crypto_calls",
    ) -> None:
        """Initialize Google Sheets storage.

        Args:
            sheet_id: Google Sheets ID from the URL.
            credentials_path: Path to Google service account credentials JSON.
            worksheet_name: Name of the worksheet to use.

        Raises:
            Exception: If Google Sheets initialization fails.
        """
        self.sheet_id = sheet_id
        self.credentials_path = credentials_path
        self.worksheet_name = worksheet_name
        self._client: Optional[gspread.Client] = None
        self._worksheet: Optional[Worksheet] = None
        self._is_closed = False
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Google Sheets client and worksheet.

        Raises:
            Exception: If client initialization fails.
        """
        try:
            # Initialize gspread client with service account
            self._client = gspread.service_account(filename=self.credentials_path)

            # Open the sheet and get worksheet
            sheet = self._client.open_by_key(self.sheet_id)

            try:
                # Try to get existing worksheet
                self._worksheet = sheet.worksheet(self.worksheet_name)
            except gspread.WorksheetNotFound:
                # Create worksheet if it doesn't exist
                self._worksheet = sheet.add_worksheet(
                    title=self.worksheet_name, rows=1000, cols=12
                )
                self._create_headers()

            logger.info(f"Google Sheets client initialized for sheet: {self.sheet_id}")

        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")
            raise

    def _create_headers(self) -> None:
        """Create column headers in the worksheet."""
        if not self._worksheet:
            raise Exception("Worksheet is not available")

        headers = [
            "token_name",
            "entry_cap",
            "peak_cap",
            "x_gain",
            "vip_x",
            "message_type",
            "contract_address",
            "time_to_peak",
            "linked_crypto_call_id",
            "timestamp",
            "message_id",
            "channel_name",
        ]

        try:
            # Check if headers already exist
            if self._worksheet.row_count == 0 or not self._worksheet.row_values(1):
                self._worksheet.append_row(headers)
                logger.debug("Created headers in Google Sheets")
        except Exception as e:
            logger.error(f"Failed to create headers: {e}")
            raise

    def append_row(self, data: Dict[str, Any]) -> None:
        """Append a new row of crypto call data to Google Sheets.

        Args:
            data: Dictionary containing crypto call data to store.
                 Expected keys: token_name, entry_cap, peak_cap, x_gain,
                 vip_x, message_type, contract_address, time_to_peak,
                 linked_crypto_call_id, timestamp, message_id, channel_name

        Raises:
            ValueError: If data is None or not a dictionary.
            Exception: If Google Sheets API operation fails.
        """
        if self._is_closed:
            raise Exception("Google Sheets storage is closed")

        if data is None:
            raise ValueError("Data cannot be None")

        if not isinstance(data, dict):
            raise TypeError("Data must be a dictionary")

        if not data:
            raise ValueError("Data dictionary cannot be empty")

        if not self._worksheet:
            raise Exception("Google Sheets worksheet is not available")

        try:
            # Column order matches headers
            columns = [
                "token_name",
                "entry_cap",
                "peak_cap",
                "x_gain",
                "vip_x",
                "message_type",
                "contract_address",
                "time_to_peak",
                "linked_crypto_call_id",
                "timestamp",
                "message_id",
                "channel_name",
            ]

            # Build row data, converting None to empty string for string fields
            row_data: List[Any] = []
            for key in columns:
                value = data.get(key)
                # Convert None to empty string for string fields
                if value is None and key in ["token_name", "message_type", "contract_address", "time_to_peak"]:
                    row_data.append("")
                else:
                    row_data.append(value)

            # Append row to Google Sheets
            self._worksheet.append_row(row_data)
            logger.debug(
                f"Inserted crypto call data for token: {data.get('token_name')}"
            )

        except Exception as e:
            logger.error(f"Failed to insert data into Google Sheets: {e}")
            raise

    def get_records(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve records from Google Sheets.

        Args:
            limit: Maximum number of records to return. If None, returns all records.

        Returns:
            List of dictionaries containing stored crypto call data.

        Raises:
            Exception: If Google Sheets API operation fails.
        """
        if self._is_closed:
            raise Exception("Google Sheets storage is closed")

        if not self._worksheet:
            raise Exception("Google Sheets worksheet is not available")

        try:
            # Get all records from the worksheet
            all_records = self._worksheet.get_all_records()

            # Apply limit if specified
            if limit is not None:
                records = all_records[:limit]
            else:
                records = all_records

            logger.debug(f"Retrieved {len(records)} records from Google Sheets")
            return records

        except Exception as e:
            logger.error(f"Failed to retrieve records from Google Sheets: {e}")
            raise

    def close(self) -> None:
        """Close Google Sheets client and cleanup resources.

        This method should be called when finished with the storage instance
        to properly clean up API connections.
        """
        if not self._is_closed:
            try:
                # Google Sheets client doesn't require explicit closing
                # but we can clean up references
                self._client = None
                self._worksheet = None
                self._is_closed = True
                logger.debug("Google Sheets client closed")
            except Exception as e:
                logger.error(f"Error closing Google Sheets client: {e}")
                # Don't re-raise as this is cleanup code


def append_row(data: Dict[str, Any]) -> None:
    """Legacy function for backwards compatibility.

    Args:
        data: Parsed and enriched call data.
    """
    logger.debug("[Sheets] append_row called with data=%s", data)
