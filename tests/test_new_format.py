#!/usr/bin/env python3
"""Test the new Pumpfun Ultimate Alert format from the user's image."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.parser import parse_crypto_call


def test_new_format():
    """Test the new message format from user's image."""

    # Recreate the message from the image
    message = """Pumpfun Ultimate Alert
this is peak (PEAK)
4GyYWMfZY8bMmWk73SmbrWUxK1aFKDQck5x6Equipump

Cap: 45.2K | 🏆 5d | Search on X
Vol: 67.5K | ⏰ 431 | 💰 283
Bonding Curve: 94.07%
Dev: ✅ (sold)
├─Made: 1
├─Dex Paid: ✅ | CTO: ❌
└─📊

Buyers
├─👥 Insiders: 12
└─⭐ KOLs: 2
TH: 178 (total) | Top 10: 25.2%
└─3.6|3.4|2.8|2.5|2.4|2.3|2.2|2.2|2|1.8

Early:
├─Sniper: 6 buy 11.4% with 3.9 SOL
├─Bundle: 0
├─Sum 🅱️: 26.8% | Sum 🅢: 27%
└─🟢🟢🟢🟢🟢🟢🟢🟢🟢🟢
└─🔴 Hold 0 | 🟡 Sold part 0 | 🟢 Sold 20"""

    print("🧪 Testing New Pumpfun Ultimate Alert Format")
    print("=" * 60)
    print("📝 Message:")
    print(message[:200] + "..." if len(message) > 200 else message)
    print("\n" + "=" * 60)

    result = parse_crypto_call(message)

    print("🔍 Parser Result:")
    if result:
        print("✅ SUCCESS! Parser detected:")
        for key, value in result.items():
            print(f"   {key}: {value}")
    else:
        print("❌ FAILED! Parser returned None")
        print("\n🔧 Let's debug step by step...")

        # Test each pattern individually
        import re

        print("\n1. Testing pfultimate result pattern (🎉):")
        pfultimate_pattern = r"🎉\s*([0-9]+(?:\.[0-9]+)?)x"
        if re.search(pfultimate_pattern, message):
            print("   ✅ Found pfultimate pattern")
        else:
            print("   ❌ No pfultimate pattern")

        print("\n2. Testing discovery pattern:")
        discovery_pattern = (
            r"(.+?)\s*\(([^)]+)\).*?Cap:\s*([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)"
        )
        match = re.search(discovery_pattern, message, re.IGNORECASE | re.DOTALL)
        if match:
            print(f"   ✅ Found discovery pattern: {match.groups()}")
        else:
            print("   ❌ No discovery pattern")

        print("\n3. Testing fallback pattern:")
        entry_pattern = r"Entry:?\s*([0-9]+(?:\.[0-9]+)?)\s*([KMB])?"
        if re.search(entry_pattern, message):
            print("   ✅ Found entry pattern")
        else:
            print("   ❌ No entry pattern")


if __name__ == "__main__":
    test_new_format()
