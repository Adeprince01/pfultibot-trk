#!/usr/bin/env python3
"""Test script to verify parser fixes for token name extraction."""

import sys

sys.path.append("src")

from parser import parse_crypto_call


def test_parser_fixes():
    """Test the updated parser with real message samples."""

    print("🧪 Testing Parser Fix #1: Token Name Extraction")
    print("=" * 60)

    # Test case 1: Name Every Coin
    test1 = r"""[Name Every Coin (NameEvery)](https://solscan.io/token/7QKwX6oBAcXiBixRzWjq9Aei2Hdp2RUgrJ3XqyjQpump)
`7QKwX6oBAcXiBixRzWjq9Aei2Hdp2RUgrJ3XqyjQpump`

`Cap:` **42.4K** | ⌛️ 29m"""

    # Test case 2: GOOTS
    test2 = r"""[GOOTS (GOOTS)](https://solscan.io/token/8sicdrZzAYbJnLdebj1193L3oRRvSKXL7p7uXGCepump)
`8sicdrZzAYbJnLdebj1193L3oRRvSKXL7p7uXGCepump`

`Cap:` **42.0K** | ⌛️ 9m"""

    # Test case 3: Infinite Frontrooms
    test3 = r"""[Infinite Frontrooms (INF)](https://solscan.io/token/3o6ZCQ8o3dzoW1wbtux5SdRBedmrySLxCmF3ZsmJpump)
`3o6ZCQ8o3dzoW1wbtux5SdRBedmrySLxCmF3ZsmJpump`

`Cap:` **41.9K** | ⌛️ 13m"""

    test_cases = [
        ("Name Every Coin", test1, "Name Every Coin (NameEvery)"),
        ("GOOTS", test2, "GOOTS (GOOTS)"),
        ("Infinite Frontrooms", test3, "Infinite Frontrooms (INF)"),
    ]

    success_count = 0

    for name, message, expected_token in test_cases:
        print(f"\n📝 Testing: {name}")
        print(f"Expected: {expected_token}")

        result = parse_crypto_call(message)

        if result:
            token_name = result.get("token_name")
            print(f"Extracted: {token_name}")
            print(f"Message Type: {result.get('message_type')}")
            print(
                f"Cap: ${result.get('entry_cap'):,.0f}"
                if result.get("entry_cap")
                else "Cap: N/A"
            )

            if token_name == expected_token:
                print("✅ SUCCESS: Token name matches expected!")
                success_count += 1
            else:
                print("❌ FAILED: Token name doesn't match expected")
        else:
            print("❌ FAILED: Parser returned None")

        print("-" * 40)

    print(f"\n📊 FINAL RESULTS:")
    print(f"✅ Successful: {success_count}/{len(test_cases)}")
    print(f"❌ Failed: {len(test_cases) - success_count}/{len(test_cases)}")

    if success_count == len(test_cases):
        print("\n🎉 ALL TESTS PASSED! Parser fix is working!")
        print("Ready to move to Fix #2: Message Linking Logic")
    else:
        print("\n⚠️ SOME TESTS FAILED! Parser needs more work.")

    return success_count == len(test_cases)


if __name__ == "__main__":
    test_parser_fixes()
