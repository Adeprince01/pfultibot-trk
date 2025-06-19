"""Tests for the multi-storage implementation."""

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.storage.multi import MultiStorage


class TestMultiStorage:
    """Test cases for multi-storage implementation."""

    @pytest.fixture
    def temp_sqlite_path(self) -> Path:
        """Create a temporary SQLite database file path for testing.

        Returns:
            Path to a temporary database file.
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_file.close()
        path = Path(temp_file.name)
        path.unlink()  # Remove the file so SQLite can create it fresh
        yield path
        # Cleanup after test
        if path.exists():
            try:
                path.unlink()
            except (PermissionError, OSError):
                pass

    @pytest.fixture
    def temp_excel_path(self) -> Path:
        """Create a temporary Excel file path for testing.

        Returns:
            Path to a temporary Excel file.
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        temp_file.close()
        path = Path(temp_file.name)
        path.unlink()  # Remove the file so Excel can create it fresh
        yield path
        # Cleanup after test
        if path.exists():
            try:
                path.unlink()
            except (PermissionError, OSError):
                pass

    @pytest.fixture
    def temp_credentials_path(self) -> Path:
        """Create a temporary credentials file for testing.

        Returns:
            Path to a temporary credentials file.
        """
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".json", mode="w")
        # Create minimal valid JSON credentials file
        temp_file.write('{"type": "service_account", "client_email": "test@test.com"}')
        temp_file.close()
        path = Path(temp_file.name)
        yield path
        # Cleanup after test
        if path.exists():
            try:
                path.unlink()
            except (PermissionError, OSError):
                pass

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

    def test_multistorage_sqlite_only(
        self, temp_sqlite_path: Path, sample_call_data: Dict[str, Any]
    ) -> None:
        """Test MultiStorage with only SQLite backend."""
        storage = MultiStorage(sqlite_path=temp_sqlite_path)

        # Verify SQLite backend is active
        status = storage.get_backend_status()
        assert status["sqlite"] is True
        assert status["excel"] is False
        assert status["sheets"] is False

        # Test append and retrieve
        storage.append_row(sample_call_data)
        records = storage.get_records()
        assert len(records) == 1
        assert records[0]["token_name"] == "SOLANA"

        storage.close()

    def test_multistorage_sqlite_and_excel(
        self,
        temp_sqlite_path: Path,
        temp_excel_path: Path,
        sample_call_data: Dict[str, Any],
    ) -> None:
        """Test MultiStorage with SQLite and Excel backends."""
        storage = MultiStorage(sqlite_path=temp_sqlite_path, excel_path=temp_excel_path)

        # Verify both backends are active
        status = storage.get_backend_status()
        assert status["sqlite"] is True
        assert status["excel"] is True
        assert status["sheets"] is False

        # Test append
        storage.append_row(sample_call_data)

        # Verify data in SQLite
        records = storage.get_records()
        assert len(records) == 1
        assert records[0]["token_name"] == "SOLANA"

        # Verify Excel file exists
        assert temp_excel_path.exists()

        storage.close()

    @patch("src.storage.multi.GoogleSheetsStorage")
    def test_multistorage_all_backends(
        self,
        mock_sheets_class,
        temp_sqlite_path: Path,
        temp_excel_path: Path,
        temp_credentials_path: Path,
        sample_call_data: Dict[str, Any],
    ) -> None:
        """Test MultiStorage with all three backends."""
        # Mock Google Sheets storage
        mock_sheets_instance = Mock()
        mock_sheets_class.return_value = mock_sheets_instance

        storage = MultiStorage(
            sqlite_path=temp_sqlite_path,
            excel_path=temp_excel_path,
            sheet_id="test_sheet_id",
            credentials_path=temp_credentials_path,
        )

        # Verify all backends are active
        status = storage.get_backend_status()
        assert status["sqlite"] is True
        assert status["excel"] is True
        assert status["sheets"] is True

        # Test append
        storage.append_row(sample_call_data)

        # Verify Google Sheets was called
        mock_sheets_instance.append_row.assert_called_once_with(sample_call_data)

        storage.close()

    def test_multistorage_invalid_sheets_config(self, temp_sqlite_path: Path) -> None:
        """Test MultiStorage with invalid Google Sheets configuration."""
        with pytest.raises(ValueError, match="credentials_path is required"):
            MultiStorage(sqlite_path=temp_sqlite_path, sheet_id="test_sheet_id")

    @patch("src.storage.multi.ExcelStorage")
    def test_multistorage_excel_init_failure(
        self, mock_excel_class, temp_sqlite_path: Path, temp_excel_path: Path
    ) -> None:
        """Test MultiStorage handles Excel initialization failure gracefully."""
        # Mock Excel to fail during initialization
        mock_excel_class.side_effect = Exception("Excel init failed")

        storage = MultiStorage(sqlite_path=temp_sqlite_path, excel_path=temp_excel_path)

        # Verify SQLite works but Excel is disabled
        status = storage.get_backend_status()
        assert status["sqlite"] is True
        assert status["excel"] is False

        storage.close()

    @patch("src.storage.multi.GoogleSheetsStorage")
    def test_multistorage_sheets_init_failure(
        self,
        mock_sheets_class,
        temp_sqlite_path: Path,
        temp_credentials_path: Path,
    ) -> None:
        """Test MultiStorage handles Google Sheets initialization failure gracefully."""
        # Mock Google Sheets to fail during initialization
        mock_sheets_class.side_effect = Exception("Sheets init failed")

        storage = MultiStorage(
            sqlite_path=temp_sqlite_path,
            sheet_id="test_sheet_id",
            credentials_path=temp_credentials_path,
        )

        # Verify SQLite works but Sheets is disabled
        status = storage.get_backend_status()
        assert status["sqlite"] is True
        assert status["sheets"] is False

        storage.close()

    @patch("src.storage.multi.ExcelStorage")
    @patch("src.storage.multi.GoogleSheetsStorage")
    def test_multistorage_partial_storage_failure(
        self,
        mock_sheets_class,
        mock_excel_class,
        temp_sqlite_path: Path,
        sample_call_data: Dict[str, Any],
    ) -> None:
        """Test MultiStorage handles partial storage failures."""
        # Setup mocks
        mock_excel_instance = Mock()
        mock_excel_instance.append_row.side_effect = Exception("Excel write failed")
        mock_excel_class.return_value = mock_excel_instance

        mock_sheets_instance = Mock()
        mock_sheets_class.return_value = mock_sheets_instance

        storage = MultiStorage(
            sqlite_path=temp_sqlite_path,
            excel_path=Path("dummy.xlsx"),
            sheet_id="test_sheet_id",
            credentials_path=Path("dummy.json"),
        )

        # This should succeed despite Excel failure (SQLite and Sheets work)
        storage.append_row(sample_call_data)

        # Verify SQLite has the data
        records = storage.get_records()
        assert len(records) == 1

        storage.close()

    def test_multistorage_all_storage_failure(
        self, temp_sqlite_path: Path, sample_call_data: Dict[str, Any]
    ) -> None:
        """Test MultiStorage raises exception when all storage backends fail."""
        storage = MultiStorage(sqlite_path=temp_sqlite_path)

        # Force SQLite to fail by closing the connection
        storage.sqlite_storage.close()

        # This should raise an exception since all backends failed
        with pytest.raises(Exception, match="All storage operations failed"):
            storage.append_row(sample_call_data)

    @pytest.mark.parametrize(
        "invalid_data",
        [
            None,  # None data
            "not_a_dict",  # String instead of dict
            [],  # List instead of dict
            {},  # Empty dict
        ],
    )
    def test_multistorage_invalid_data(
        self, temp_sqlite_path: Path, invalid_data: Any
    ) -> None:
        """Test MultiStorage with invalid data types."""
        storage = MultiStorage(sqlite_path=temp_sqlite_path)

        with pytest.raises((ValueError, TypeError)):
            storage.append_row(invalid_data)

        storage.close()

    def test_multistorage_get_records_limit(
        self, temp_sqlite_path: Path, sample_call_data: Dict[str, Any]
    ) -> None:
        """Test MultiStorage get_records with limit parameter."""
        storage = MultiStorage(sqlite_path=temp_sqlite_path)

        # Insert multiple records
        for i in range(5):
            data = sample_call_data.copy()
            data["token_name"] = f"TOKEN{i}"
            storage.append_row(data)

        # Test limit
        records = storage.get_records(limit=3)
        assert len(records) == 3

        storage.close()

    def test_multistorage_close_all_backends(
        self, temp_sqlite_path: Path, temp_excel_path: Path
    ) -> None:
        """Test MultiStorage properly closes all backends."""
        storage = MultiStorage(sqlite_path=temp_sqlite_path, excel_path=temp_excel_path)

        # Verify storage is functional
        assert storage.sqlite_storage is not None
        assert storage.excel_storage is not None

        # Close storage
        storage.close()

        # Note: We can't easily test that connections are closed without
        # accessing private attributes, but the close() method should
        # not raise exceptions
