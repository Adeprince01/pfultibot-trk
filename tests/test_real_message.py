#!/usr/bin/env python3
"""Test the exact real message from @pfultimate."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.parser import parse_crypto_call

def test_real_message():
    """Test the real message from @pfultimate."""
    
    # The exact message from user
    message = """craptocurrency (crapto) (https://solscan.io/token/7YdAFt1TdntrhS3sFUdKEnmJhDQ6z3EHcmuQrcfMpump)
7YdAFt1TdntrhS3sFUdKEnmJhDQ6z3EHcmuQrcfMpump

Cap: 45.8K | ⌛️ 15m | Search on 𝕏 (https://x.com/search?f=live&q=(crapto%20OR%207YdAFt1TdntrhS3sFUdKEnmJhDQ6z3EHcmuQrcfMpump%20OR%20url:7YdAFt1TdntrhS3sFUdKEnmJhDQ6z3EHcmuQrcfMpump)&src=typed_query)
Vol: 67.1K | 🅑 515 | 🅢 316 
Bonding Curve:  94.29%
Dev:✅ (sold)
 ├Made: 1
 └Dex Paid: ✅ | CTO: ❌
 └𝕏 (https://x.com/i/communities/1934972699983421590)
Buyers 
 ├🐁Insiders: 4
 └🌟KOLs: 0"""

    print("🧪 Testing REAL @pfultimate Message")
    print("=" * 50)
    print("📝 Message:")
    print(message[:150] + "..." if len(message) > 150 else message)
    print("\n" + "=" * 50)
    
    result = parse_crypto_call(message)
    
    print("🔍 Parser Result:")
    if result:
        print("✅ SUCCESS! Parser detected:")
        print(f"   Token: {result['token_name']}")
        print(f"   Market Cap: ${result['entry_cap']:,.0f}")
        print(f"   Gain: {result['x_gain']}x")
        print(f"   VIP: {result['vip_x']}")
        print("\n🎯 This message WILL be captured by the monitor!")
    else:
        print("❌ FAILED! Parser returned None")
        print("\n🔧 Debugging the regex patterns...")
        
        import re
        
        # Test the discovery pattern step by step
        print("\n1. Testing token name extraction:")
        token_pattern = r"(.+?)\s*\(([^)]+)\)"
        token_match = re.search(token_pattern, message)
        if token_match:
            print(f"   ✅ Found: '{token_match.group(1).strip()}' ({token_match.group(2)})")
        else:
            print("   ❌ No token pattern found")
        
        print("\n2. Testing cap extraction:")
        cap_pattern = r"Cap:\s*([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)"
        cap_match = re.search(cap_pattern, message, re.IGNORECASE)
        if cap_match:
            print(f"   ✅ Found cap: {cap_match.group(1)}{cap_match.group(2) or ''}")
        else:
            print("   ❌ No cap pattern found")
        
        print("\n3. Testing full discovery pattern:")
        discovery_pattern = r"(.+?)\s*\(([^)]+)\).*?Cap:\s*([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)"
        discovery_match = re.search(discovery_pattern, message, re.IGNORECASE | re.DOTALL)
        if discovery_match:
            print(f"   ✅ Full pattern works: {discovery_match.groups()}")
        else:
            print("   ❌ Full pattern failed")

if __name__ == "__main__":
    test_real_message() 