"""Tests for the storage module."""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.storage import StorageProtocol
from src.storage.excel import ExcelStorage
from src.storage.sheet import GoogleSheetsStorage
from src.storage.sqlite import SQLiteStorage


class TestStorageProtocol:
    """Test cases for the abstract storage protocol."""

    def test_storage_protocol_interface(self) -> None:
        """Test that StorageProtocol defines the required interface."""
        # This ensures our protocol has the expected methods
        assert hasattr(StorageProtocol, "append_row")
        assert hasattr(StorageProtocol, "get_records")
        assert hasattr(StorageProtocol, "close")


class TestSQLiteStorage:
    """Test cases for SQLite storage implementation."""

    @pytest.fixture
    def temp_db_path(self) -> Path:
        """Create a temporary database file path for testing.

        Returns:
            Path to a temporary database file.
        """
        # Create a temporary file and delete it so we have a clean path
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()
        path = Path(temp_file.name)
        # Remove the file so SQLite can create it fresh
        path.unlink()
        yield path
        # Cleanup after test - handle Windows file locking gracefully
        if path.exists():
            try:
                path.unlink()
            except (PermissionError, OSError):
                # On Windows, SQLite files might be locked briefly
                # This is acceptable for test cleanup
                pass

    @pytest.fixture
    def sqlite_storage(self, temp_db_path: Path) -> SQLiteStorage:
        """Create a SQLiteStorage instance with temporary database.

        Args:
            temp_db_path: Temporary database file path.

        Returns:
            SQLiteStorage instance for testing.
        """
        storage = SQLiteStorage(db_path=temp_db_path)
        yield storage
        storage.close()

    @pytest.fixture
    def sample_call_data(self) -> Dict[str, Any]:
        """Sample crypto call data for testing.

        Returns:
            Dictionary with sample parsed call data.
        """
        return {
            "token_name": "SOLANA",
            "entry_cap": 100000.0,
            "peak_cap": 1500000.0,
            "x_gain": 15.0,
            "vip_x": 15.0,
            "timestamp": "2024-01-15T10:30:00Z",
            "message_id": 12345,
            "channel_name": "test_channel",
        }

    def test_sqlite_storage_initialization(self, temp_db_path: Path) -> None:
        """Test SQLite storage initialization creates database and table."""
        storage = SQLiteStorage(db_path=temp_db_path)

        # Verify database file is created
        assert temp_db_path.exists()

        # Verify table structure
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='crypto_calls'
            """
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "crypto_calls"

        storage.close()

    def test_append_row_success(
        self, sqlite_storage: SQLiteStorage, sample_call_data: Dict[str, Any]
    ) -> None:
        """Test successful row insertion."""
        # Insert data
        sqlite_storage.append_row(sample_call_data)

        # Verify data was inserted
        records = sqlite_storage.get_records()
        assert len(records) == 1

        record = records[0]
        assert record["token_name"] == "SOLANA"
        assert record["entry_cap"] == 100000.0
        assert record["peak_cap"] == 1500000.0
        assert record["x_gain"] == 15.0
        assert record["vip_x"] == 15.0

    def test_append_multiple_rows(self, sqlite_storage: SQLiteStorage) -> None:
        """Test inserting multiple rows."""
        test_data = [
            {
                "token_name": "TOKEN1",
                "entry_cap": 50000.0,
                "peak_cap": 200000.0,
                "x_gain": 4.0,
                "vip_x": None,
                "timestamp": "2024-01-15T10:30:00Z",
            },
            {
                "token_name": "TOKEN2",
                "entry_cap": 75000.0,
                "peak_cap": 300000.0,
                "x_gain": 4.0,
                "vip_x": 4.0,
                "timestamp": "2024-01-15T11:30:00Z",
            },
        ]

        for data in test_data:
            sqlite_storage.append_row(data)

        records = sqlite_storage.get_records()
        assert len(records) == 2
        assert records[0]["token_name"] == "TOKEN1"
        assert records[1]["token_name"] == "TOKEN2"

    def test_append_row_with_none_values(self, sqlite_storage: SQLiteStorage) -> None:
        """Test inserting data with None values."""
        data = {
            "token_name": None,
            "entry_cap": 50000.0,
            "peak_cap": 200000.0,
            "x_gain": 4.0,
            "vip_x": None,
            "timestamp": "2024-01-15T10:30:00Z",
        }

        sqlite_storage.append_row(data)

        records = sqlite_storage.get_records()
        assert len(records) == 1
        assert records[0]["token_name"] is None
        assert records[0]["vip_x"] is None

    def test_get_records_empty_database(self, sqlite_storage: SQLiteStorage) -> None:
        """Test getting records from empty database."""
        records = sqlite_storage.get_records()
        assert records == []

    def test_get_records_with_limit(self, sqlite_storage: SQLiteStorage) -> None:
        """Test getting records with limit parameter."""
        # Insert 5 records
        for i in range(5):
            data = {
                "token_name": f"TOKEN{i}",
                "entry_cap": 50000.0 + i * 1000,
                "peak_cap": 200000.0 + i * 10000,
                "x_gain": 4.0,
                "vip_x": None,
                "timestamp": f"2024-01-15T10:3{i}:00Z",
            }
            sqlite_storage.append_row(data)

        # Test limit
        records = sqlite_storage.get_records(limit=3)
        assert len(records) == 3

    def test_append_row_database_error(self, sqlite_storage: SQLiteStorage) -> None:
        """Test handling of database errors during insertion."""
        # Close the storage to simulate database error
        sqlite_storage.close()

        with pytest.raises(Exception):  # Should raise an exception
            sqlite_storage.append_row({"invalid": "data"})

    def test_get_records_database_error(self, temp_db_path: Path) -> None:
        """Test handling of database errors during retrieval."""
        storage = SQLiteStorage(db_path=temp_db_path)
        storage.close()

        with pytest.raises(Exception):  # Should raise an exception
            storage.get_records()

    @pytest.mark.parametrize(
        "invalid_data",
        [
            None,  # None data
            "not_a_dict",  # String instead of dict
            [],  # List instead of dict
            {},  # Empty dict
        ],
    )
    def test_append_row_invalid_data(
        self, sqlite_storage: SQLiteStorage, invalid_data: Any
    ) -> None:
        """Test append_row with invalid data types.

        Args:
            sqlite_storage: SQLite storage instance.
            invalid_data: Invalid data to test with.
        """
        with pytest.raises((ValueError, TypeError)):
            sqlite_storage.append_row(invalid_data)

    def test_storage_implements_protocol(self, sqlite_storage: SQLiteStorage) -> None:
        """Test that SQLiteStorage implements StorageProtocol."""
        # This should not raise any typing errors
        storage_protocol: StorageProtocol = sqlite_storage
        assert hasattr(storage_protocol, "append_row")
        assert hasattr(storage_protocol, "get_records")
        assert hasattr(storage_protocol, "close")

    def test_close_cleanup(self, temp_db_path: Path) -> None:
        """Test that close() properly cleans up resources."""
        storage = SQLiteStorage(db_path=temp_db_path)

        # Insert some data
        storage.append_row(
            {
                "token_name": "TEST",
                "entry_cap": 50000.0,
                "peak_cap": 200000.0,
                "x_gain": 4.0,
                "vip_x": None,
            }
        )

        # Close storage
        storage.close()

        # Verify database file still exists and data is persisted
        assert temp_db_path.exists()

        # Create new storage instance and verify data
        new_storage = SQLiteStorage(db_path=temp_db_path)
        records = new_storage.get_records()
        assert len(records) == 1
        assert records[0]["token_name"] == "TEST"
        new_storage.close()

    def test_concurrent_access(self, temp_db_path: Path) -> None:
        """Test that multiple storage instances can access the same database."""
        storage1 = SQLiteStorage(db_path=temp_db_path)
        storage2 = SQLiteStorage(db_path=temp_db_path)

        # Insert data from first instance
        storage1.append_row(
            {
                "token_name": "STORAGE1",
                "entry_cap": 50000.0,
                "peak_cap": 200000.0,
                "x_gain": 4.0,
                "vip_x": None,
            }
        )

        # Insert data from second instance
        storage2.append_row(
            {
                "token_name": "STORAGE2",
                "entry_cap": 75000.0,
                "peak_cap": 300000.0,
                "x_gain": 4.0,
                "vip_x": None,
            }
        )

        # Both instances should see both records
        records1 = storage1.get_records()
        records2 = storage2.get_records()

        assert len(records1) == 2
        assert len(records2) == 2

        storage1.close()
        storage2.close()


class TestExcelStorage:
    """Test cases for Excel storage implementation."""

    @pytest.fixture
    def temp_excel_path(self) -> Path:
        """Create a temporary Excel file path for testing.

        Returns:
            Path to a temporary Excel file.
        """
        # Create a temporary file path
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        temp_file.close()
        path = Path(temp_file.name)
        # Remove the file so Excel storage can create it fresh
        path.unlink()
        yield path
        # Cleanup after test - handle Windows file locking gracefully
        if path.exists():
            try:
                path.unlink()
            except (PermissionError, OSError):
                # On Windows, Excel files might be locked briefly
                # This is acceptable for test cleanup
                pass

    @pytest.fixture
    def excel_storage(self, temp_excel_path: Path) -> ExcelStorage:
        """Create an ExcelStorage instance with temporary file.

        Args:
            temp_excel_path: Temporary Excel file path.

        Returns:
            ExcelStorage instance for testing.
        """
        storage = ExcelStorage(file_path=temp_excel_path)
        yield storage
        storage.close()

    @pytest.fixture
    def sample_call_data(self) -> Dict[str, Any]:
        """Sample crypto call data for testing.

        Returns:
            Dictionary with sample parsed call data.
        """
        return {
            "token_name": "SOLANA",
            "entry_cap": 100000.0,
            "peak_cap": 1500000.0,
            "x_gain": 15.0,
            "vip_x": 15.0,
            "timestamp": "2024-01-15T10:30:00Z",
            "message_id": 12345,
            "channel_name": "test_channel",
        }

    def test_excel_storage_initialization(self, temp_excel_path: Path) -> None:
        """Test Excel storage initialization creates file and headers."""
        storage = ExcelStorage(file_path=temp_excel_path)

        # Verify Excel file is created
        assert temp_excel_path.exists()

        storage.close()

    def test_append_row_success(
        self, excel_storage: ExcelStorage, sample_call_data: Dict[str, Any]
    ) -> None:
        """Test successful row insertion."""
        # Insert data
        excel_storage.append_row(sample_call_data)

        # Verify data was inserted
        records = excel_storage.get_records()
        assert len(records) == 1

        record = records[0]
        assert record["token_name"] == "SOLANA"
        assert record["entry_cap"] == 100000.0
        assert record["peak_cap"] == 1500000.0
        assert record["x_gain"] == 15.0
        assert record["vip_x"] == 15.0

    def test_append_multiple_rows(self, excel_storage: ExcelStorage) -> None:
        """Test inserting multiple rows."""
        test_data = [
            {
                "token_name": "TOKEN1",
                "entry_cap": 50000.0,
                "peak_cap": 200000.0,
                "x_gain": 4.0,
                "vip_x": None,
                "timestamp": "2024-01-15T10:30:00Z",
            },
            {
                "token_name": "TOKEN2",
                "entry_cap": 75000.0,
                "peak_cap": 300000.0,
                "x_gain": 4.0,
                "vip_x": 4.0,
                "timestamp": "2024-01-15T11:30:00Z",
            },
        ]

        for data in test_data:
            excel_storage.append_row(data)

        records = excel_storage.get_records()
        assert len(records) == 2
        assert records[0]["token_name"] == "TOKEN1"
        assert records[1]["token_name"] == "TOKEN2"

    def test_append_row_with_none_values(self, excel_storage: ExcelStorage) -> None:
        """Test inserting data with None values."""
        data = {
            "token_name": None,
            "entry_cap": 50000.0,
            "peak_cap": 200000.0,
            "x_gain": 4.0,
            "vip_x": None,
            "timestamp": "2024-01-15T10:30:00Z",
        }

        excel_storage.append_row(data)

        records = excel_storage.get_records()
        assert len(records) == 1
        assert records[0]["token_name"] is None
        assert records[0]["vip_x"] is None

    def test_get_records_empty_file(self, excel_storage: ExcelStorage) -> None:
        """Test getting records from empty Excel file."""
        records = excel_storage.get_records()
        assert records == []

    def test_get_records_with_limit(self, excel_storage: ExcelStorage) -> None:
        """Test getting records with limit parameter."""
        # Insert 5 records
        for i in range(5):
            data = {
                "token_name": f"TOKEN{i}",
                "entry_cap": 50000.0 + i * 1000,
                "peak_cap": 200000.0 + i * 10000,
                "x_gain": 4.0,
                "vip_x": None,
                "timestamp": f"2024-01-15T10:3{i}:00Z",
            }
            excel_storage.append_row(data)

        # Test limit
        records = excel_storage.get_records(limit=3)
        assert len(records) == 3

    def test_append_row_file_error(self, excel_storage: ExcelStorage) -> None:
        """Test handling of file errors during insertion."""
        # Close the storage to simulate file error
        excel_storage.close()

        with pytest.raises(Exception):  # Should raise an exception
            excel_storage.append_row({"invalid": "data"})

    def test_get_records_file_error(self, temp_excel_path: Path) -> None:
        """Test handling of file errors during retrieval."""
        storage = ExcelStorage(file_path=temp_excel_path)
        storage.close()

        with pytest.raises(Exception):  # Should raise an exception
            storage.get_records()

    @pytest.mark.parametrize(
        "invalid_data",
        [
            None,  # None data
            "not_a_dict",  # String instead of dict
            [],  # List instead of dict
            {},  # Empty dict
        ],
    )
    def test_append_row_invalid_data(
        self, excel_storage: ExcelStorage, invalid_data: Any
    ) -> None:
        """Test append_row with invalid data types.

        Args:
            excel_storage: Excel storage instance.
            invalid_data: Invalid data to test with.
        """
        with pytest.raises((ValueError, TypeError)):
            excel_storage.append_row(invalid_data)

    def test_storage_implements_protocol(self, excel_storage: ExcelStorage) -> None:
        """Test that ExcelStorage implements StorageProtocol."""
        # This should not raise any typing errors
        storage_protocol: StorageProtocol = excel_storage
        assert hasattr(storage_protocol, "append_row")
        assert hasattr(storage_protocol, "get_records")
        assert hasattr(storage_protocol, "close")

    def test_close_cleanup(self, temp_excel_path: Path) -> None:
        """Test that close() properly cleans up resources."""
        storage = ExcelStorage(file_path=temp_excel_path)

        # Insert some data
        storage.append_row(
            {
                "token_name": "TEST",
                "entry_cap": 50000.0,
                "peak_cap": 200000.0,
                "x_gain": 4.0,
                "vip_x": None,
            }
        )

        # Close storage
        storage.close()

        # Verify Excel file still exists and data is persisted
        assert temp_excel_path.exists()

        # Create new storage instance and verify data
        new_storage = ExcelStorage(file_path=temp_excel_path)
        records = new_storage.get_records()
        assert len(records) == 1
        assert records[0]["token_name"] == "TEST"
        new_storage.close()

    def test_concurrent_access(self, temp_excel_path: Path) -> None:
        """Test that multiple storage instances can access the same file."""
        storage1 = ExcelStorage(file_path=temp_excel_path)

        # Insert data from first instance
        storage1.append_row(
            {
                "token_name": "STORAGE1",
                "entry_cap": 50000.0,
                "peak_cap": 200000.0,
                "x_gain": 4.0,
                "vip_x": None,
            }
        )
        storage1.close()

        # Create second instance and add more data
        storage2 = ExcelStorage(file_path=temp_excel_path)
        storage2.append_row(
            {
                "token_name": "STORAGE2",
                "entry_cap": 75000.0,
                "peak_cap": 300000.0,
                "x_gain": 4.0,
                "vip_x": None,
            }
        )

        # Verify both records exist
        records = storage2.get_records()
        assert len(records) == 2

        storage2.close()


class TestGoogleSheetsStorage:
    """Test cases for Google Sheets storage implementation."""

    @pytest.fixture
    def mock_gspread_client(self):
        """Mock gspread client for testing without actual Google Sheets API."""
        with patch("src.storage.sheet.gspread") as mock_gspread:
            mock_gc = Mock()
            mock_sheet = Mock()
            mock_worksheet = Mock()

            # Setup mock chain
            mock_gspread.service_account.return_value = mock_gc
            mock_gc.open_by_key.return_value = mock_sheet
            mock_sheet.worksheet.return_value = mock_worksheet

            # Mock worksheet methods
            mock_worksheet.get_all_records.return_value = []
            mock_worksheet.append_row.return_value = None

            yield {
                "gspread": mock_gspread,
                "client": mock_gc,
                "sheet": mock_sheet,
                "worksheet": mock_worksheet,
            }

    @pytest.fixture
    def sheets_storage(self, mock_gspread_client):
        """Create a GoogleSheetsStorage instance with mocked dependencies.

        Returns:
            GoogleSheetsStorage instance for testing.
        """
        storage = GoogleSheetsStorage(
            sheet_id="test_sheet_id",
            credentials_path=Path("fake_creds.json"),
            worksheet_name="test_worksheet",
        )
        yield storage
        storage.close()

    @pytest.fixture
    def sample_call_data(self) -> Dict[str, Any]:
        """Sample crypto call data for testing.

        Returns:
            Dictionary with sample parsed call data.
        """
        return {
            "token_name": "SOLANA",
            "entry_cap": 100000.0,
            "peak_cap": 1500000.0,
            "x_gain": 15.0,
            "vip_x": 15.0,
            "timestamp": "2024-01-15T10:30:00Z",
            "message_id": 12345,
            "channel_name": "test_channel",
        }

    def test_sheets_storage_initialization(self, mock_gspread_client):
        """Test Google Sheets storage initialization."""
        storage = GoogleSheetsStorage(
            sheet_id="test_sheet_id",
            credentials_path=Path("fake_creds.json"),
            worksheet_name="test_worksheet",
        )

        # Verify gspread was called correctly
        mock_gspread_client["gspread"].service_account.assert_called_once()
        mock_gspread_client["client"].open_by_key.assert_called_once_with(
            "test_sheet_id"
        )
        mock_gspread_client["sheet"].worksheet.assert_called_once_with("test_worksheet")

        storage.close()

    def test_append_row_success(
        self,
        sheets_storage: GoogleSheetsStorage,
        sample_call_data: Dict[str, Any],
        mock_gspread_client,
    ) -> None:
        """Test successful row insertion."""
        # Insert data
        sheets_storage.append_row(sample_call_data)

        # Verify append_row was called on worksheet
        expected_row = [
            "SOLANA",  # token_name
            100000.0,  # entry_cap
            1500000.0,  # peak_cap
            15.0,  # x_gain
            15.0,  # vip_x
            "2024-01-15T10:30:00Z",  # timestamp
            12345,  # message_id
            "test_channel",  # channel_name
        ]
        mock_gspread_client["worksheet"].append_row.assert_called_once_with(
            expected_row
        )

    def test_append_multiple_rows(
        self, sheets_storage: GoogleSheetsStorage, mock_gspread_client
    ) -> None:
        """Test inserting multiple rows."""
        test_data = [
            {
                "token_name": "TOKEN1",
                "entry_cap": 50000.0,
                "peak_cap": 200000.0,
                "x_gain": 4.0,
                "vip_x": None,
                "timestamp": "2024-01-15T10:30:00Z",
            },
            {
                "token_name": "TOKEN2",
                "entry_cap": 75000.0,
                "peak_cap": 300000.0,
                "x_gain": 4.0,
                "vip_x": 4.0,
                "timestamp": "2024-01-15T11:30:00Z",
            },
        ]

        for data in test_data:
            sheets_storage.append_row(data)

        # Verify append_row was called twice
        assert mock_gspread_client["worksheet"].append_row.call_count == 2

    def test_append_row_with_none_values(
        self, sheets_storage: GoogleSheetsStorage, mock_gspread_client
    ) -> None:
        """Test inserting data with None values."""
        data = {
            "token_name": None,
            "entry_cap": 50000.0,
            "peak_cap": 200000.0,
            "x_gain": 4.0,
            "vip_x": None,
            "timestamp": "2024-01-15T10:30:00Z",
        }

        sheets_storage.append_row(data)

        # Verify None values are converted to empty strings
        expected_row = [
            "",  # token_name (None -> "")
            50000.0,  # entry_cap
            200000.0,  # peak_cap
            4.0,  # x_gain
            "",  # vip_x (None -> "")
            "2024-01-15T10:30:00Z",  # timestamp
            None,  # message_id
            None,  # channel_name
        ]
        mock_gspread_client["worksheet"].append_row.assert_called_once_with(
            expected_row
        )

    def test_get_records_success(
        self, sheets_storage: GoogleSheetsStorage, mock_gspread_client
    ) -> None:
        """Test successful record retrieval."""
        # Mock return data
        mock_records = [
            {
                "token_name": "SOLANA",
                "entry_cap": 100000.0,
                "peak_cap": 1500000.0,
                "x_gain": 15.0,
                "vip_x": 15.0,
                "timestamp": "2024-01-15T10:30:00Z",
                "message_id": 12345,
                "channel_name": "test_channel",
            }
        ]
        mock_gspread_client["worksheet"].get_all_records.return_value = mock_records

        records = sheets_storage.get_records()

        assert len(records) == 1
        assert records[0]["token_name"] == "SOLANA"
        mock_gspread_client["worksheet"].get_all_records.assert_called_once()

    def test_get_records_empty_sheet(
        self, sheets_storage: GoogleSheetsStorage, mock_gspread_client
    ) -> None:
        """Test getting records from empty sheet."""
        mock_gspread_client["worksheet"].get_all_records.return_value = []

        records = sheets_storage.get_records()
        assert records == []

    def test_get_records_with_limit(
        self, sheets_storage: GoogleSheetsStorage, mock_gspread_client
    ) -> None:
        """Test getting records with limit parameter."""
        # Mock 5 records
        mock_records = [
            {"token_name": f"TOKEN{i}", "entry_cap": 50000.0 + i * 1000}
            for i in range(5)
        ]
        mock_gspread_client["worksheet"].get_all_records.return_value = mock_records

        # Test limit
        records = sheets_storage.get_records(limit=3)
        assert len(records) == 3

    def test_append_row_api_error(
        self, sheets_storage: GoogleSheetsStorage, mock_gspread_client
    ) -> None:
        """Test handling of API errors during insertion."""
        # Simulate API error
        mock_gspread_client["worksheet"].append_row.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            sheets_storage.append_row({"token_name": "TEST"})

    def test_get_records_api_error(
        self, sheets_storage: GoogleSheetsStorage, mock_gspread_client
    ) -> None:
        """Test handling of API errors during retrieval."""
        # Simulate API error
        mock_gspread_client["worksheet"].get_all_records.side_effect = Exception(
            "API Error"
        )

        with pytest.raises(Exception):
            sheets_storage.get_records()

    @pytest.mark.parametrize(
        "invalid_data",
        [
            None,  # None data
            "not_a_dict",  # String instead of dict
            [],  # List instead of dict
            {},  # Empty dict
        ],
    )
    def test_append_row_invalid_data(
        self, sheets_storage: GoogleSheetsStorage, invalid_data: Any
    ) -> None:
        """Test append_row with invalid data types.

        Args:
            sheets_storage: Google Sheets storage instance.
            invalid_data: Invalid data to test with.
        """
        with pytest.raises((ValueError, TypeError)):
            sheets_storage.append_row(invalid_data)

    def test_storage_implements_protocol(
        self, sheets_storage: GoogleSheetsStorage
    ) -> None:
        """Test that GoogleSheetsStorage implements StorageProtocol."""
        # This should not raise any typing errors
        storage_protocol: StorageProtocol = sheets_storage
        assert hasattr(storage_protocol, "append_row")
        assert hasattr(storage_protocol, "get_records")
        assert hasattr(storage_protocol, "close")

    def test_close_cleanup(self, mock_gspread_client) -> None:
        """Test that close() properly cleans up resources."""
        storage = GoogleSheetsStorage(
            sheet_id="test_sheet_id",
            credentials_path=Path("fake_creds.json"),
            worksheet_name="test_worksheet",
        )

        # Close storage
        storage.close()

        # Verify cleanup was called (implementation dependent)
