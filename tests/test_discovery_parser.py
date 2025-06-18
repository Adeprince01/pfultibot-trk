#!/usr/bin/env python3
"""Test the parser with the actual coin discovery message."""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.parser import parse_crypto_call

# Your actual message from @pfultimate
test_message = """undervalued coin (undervalue) (https://solscan.io/token/4GhCcer65iXJMruyoQA4XiXDP2hk34AGy48pogYXpump)
4GhCcer65iXJMruyoQA4XiXDP2hk34AGy48pogYXpump

Cap: 45.9K | ⌛️ 38m | Search on 𝕏 (https://x.com/search?f=live&q=(undervalue%20OR%204GhCcer65iXJMruyoQA4XiXDP2hk34AGy48pogYXpump%20OR%20url:4GhCcer65iXJMruyoQA4XiXDP2hk34AGy48pogYXpump)&src=typed_query)
Vol: 202.6K | 🅑 1682 | 🅢 1353 
Bonding Curve:  94.47%
Dev:✅ (sold)
 ├Made: 2
 └Dex Paid: ❌ | CTO: ❌
 └𝕏 (https://x.com/i/communities/1934955225842163776)
Buyers 
 ├🐁Insiders: 5
 └🌟KOLs: 2"""

def main():
    print("🧪 Testing Parser with Coin Discovery Message")
    print("=" * 50)
    
    print("📝 Original Message:")
    print(test_message[:200] + "..." if len(test_message) > 200 else test_message)
    print()
    
    print("🔍 Parser Result:")
    result = parse_crypto_call(test_message)
    
    if result:
        print("✅ SUCCESS! Parser detected the message:")
        print(f"   Token: {result['token_name']}")
        print(f"   Market Cap: ${result['entry_cap']:,.0f}")
        print(f"   Gain: {result['x_gain']}x")
        print(f"   VIP: {result['vip_x']}")
        print()
        print("🎯 This message will now be captured by the monitor!")
    else:
        print("❌ FAILED! Parser could not detect the message.")
        print("   The parser needs further adjustment.")
    
    print("=" * 50)

if __name__ == "__main__":
    main() 