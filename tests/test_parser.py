#!/usr/bin/env python3
"""Test parser with actual message formats"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.parser import parse_crypto_call

# Test with actual messages we captured
test_messages = [
    # Discovery call (what we want to capture)
    """[killer featherless cock (KFC)](https://solscan.io/token/8K4VbtJ6cWVxUfxK1DoFP9g2H1V4cWFF2RrQTqEwpump)
8K4VbtJ6cWVxUfxK1DoFP9g2H1V4cWFF2RrQTqEwpump

Cap: 45.1K | ⌛️ 1h:29m""",
    # Price update (should parse but not what we focus on)
    "🎉 **2.1x(3.6x from VIP)** | 💹From **46.0K** ↗️ **94.7K** within **17m**",
    # Another price update
    "🎉 **2.7x(4.7x from VIP)** | 💹From **46.0K** ↗️ **125.0K** within **19m**",
]

print("🧪 PARSER TEST WITH REAL MESSAGES")
print("=" * 50)

for i, message in enumerate(test_messages, 1):
    print(f"\n📝 TEST {i}:")
    print("Message:", repr(message[:80] + "..." if len(message) > 80 else message))

    result = parse_crypto_call(message)

    if result:
        print("✅ PARSED:")
        for key, value in result.items():
            print(f"  {key}: {value}")
    else:
        print("❌ FAILED TO PARSE")
