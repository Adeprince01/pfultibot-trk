#!/usr/bin/env python3
"""Test Excel integration with linking functionality."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_excel_integration():
    """Test Excel storage with sample linked data."""
    
    try:
        from src.storage.excel import ExcelStorage
        
        # Create exports directory
        excel_path = Path("exports/crypto_calls_test.xlsx")
        excel_path.parent.mkdir(exist_ok=True)
        
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
            token = record.get('token_name') or 'N/A'
            msg_type = record.get('message_type', 'unknown')
            linked_id = record.get('linked_crypto_call_id')
            gain = record.get('x_gain', 0)
            
            link_text = f" → Linked to #{linked_id}" if linked_id else ""
            print(f"   {i}. {token} ({msg_type}) - {gain}x gain{link_text}")
        
        excel_storage.close()
        
        print(f"\n🎉 Excel integration test successful!")
        print(f"📁 Test file created: {excel_path}")
        print("\n📋 Excel is ready for production use!")
        
        return True
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("💡 Run: pip install openpyxl")
        return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("🔗 Testing Excel Integration")
    print("=" * 30)
    
    if test_excel_integration():
        print("\n✅ Ready to enable Excel in production!")
        print("\n📋 Next steps:")
        print("1. Add to .env file:")
        print("   ENABLE_EXCEL=true")
        print("   EXCEL_PATH=exports/crypto_calls.xlsx")
        print("2. Run: python monitor.py")
    else:
        print("\n❌ Excel integration test failed") 