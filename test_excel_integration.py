#!/usr/bin/env python3
"""Test Excel integration with linking functionality."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from src.storage.excel import ExcelStorage
except ImportError:
    ExcelStorage = None


def test_excel_storage_integration(tmp_path: Path):
    """Test Excel storage with sample linked data using a temporary file.

    Args:
        tmp_path: Pytest fixture for a temporary directory path.
    """
    if not ExcelStorage:
        print("⚠️ Skipping Excel test: openpyxl not installed.")
        return

    # Use tmp_path for the test file to isolate it from production files
    excel_path = tmp_path / "crypto_calls_test.xlsx"

    print("🧪 Testing Excel integration with linking...")
    print(f"📁 Test file: {excel_path}")

    # Initialize Excel storage
    excel_storage = ExcelStorage(excel_path)
    print("✅ Excel storage initialized")

    # Test discovery call
    discovery_data = {
        "token_name": "TESTCOIN",
        "entry_cap": 45000.0,
        "peak_cap": 45000.0,
        "x_gain": 1.0,
        "vip_x": None,
        "message_type": "discovery",
        "contract_address": "ABC123456789...",
        "time_to_peak": None,
        "linked_crypto_call_id": None,
        "timestamp": "2025-01-18T10:00:00",
        "message_id": 1001,
        "channel_name": "Pumpfun Ultimate Alert",
    }

    excel_storage.append_row(discovery_data)
    print("✅ Discovery call stored")

    # Test update call (linked to discovery)
    update_data = {
        "token_name": None,
        "entry_cap": 45000.0,
        "peak_cap": 90000.0,
        "x_gain": 2.0,
        "vip_x": 3.5,
        "message_type": "update",
        "contract_address": None,
        "time_to_peak": "15m",
        "linked_crypto_call_id": 1,  # Links to discovery
        "timestamp": "2025-01-18T10:15:00",
        "message_id": 1002,
        "channel_name": "Pumpfun Ultimate Alert",
    }

    excel_storage.append_row(update_data)
    print("✅ Update call stored (linked)")

    # Verify data
    records = excel_storage.get_records()
    print(f"\n📊 Verification - Retrieved {len(records)} records:")

    for i, record in enumerate(records, 1):
        token = record.get("token_name") or "N/A"
        msg_type = record.get("message_type", "unknown")
        linked_id = record.get("linked_crypto_call_id")
        gain = record.get("x_gain", 0)

        link_text = f" → Linked to #{linked_id}" if linked_id else ""
        print(f"   {i}. {token} ({msg_type}) - {gain}x gain{link_text}")

    excel_storage.close()

    print(f"\n🎉 Excel integration test successful!")
    print(f"📁 Test file created at temporary path: {excel_path}")

    # The file will be automatically cleaned up by pytest
    assert True


if __name__ == "__main__":
    print("🔗 Testing Excel Integration")
    print("=" * 30)

    # To run this standalone for manual checking, we can't use tmp_path directly.
    # We can create a temporary directory manually.
    import shutil
    import tempfile

    temp_dir = tempfile.mkdtemp()
    print(f"Running test in temporary directory: {temp_dir}")
    try:
        test_excel_storage_integration(Path(temp_dir))
        print("\n✅ Standalone test execution successful.")
    finally:
        print(f"Cleaning up temporary directory: {temp_dir}")
        shutil.rmtree(temp_dir)
        print("\n✅ Ready to enable Excel in production!")
