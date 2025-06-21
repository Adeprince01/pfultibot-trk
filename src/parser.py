"""Message parser for extracting structured data from crypto call messages."""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


def parse_crypto_call(
    message: Optional[str],
) -> Optional[Dict[str, Union[str, float, None]]]:
    """Parse a crypto call message and extract structured data.

    Extracts token name, entry market cap, peak market cap, and gain multiplier
    from Telegram crypto call messages. Also supports coin discovery/analysis posts.

    Args:
        message: The raw message text to parse. Can be None.

    Returns:
        A dictionary containing parsed data with keys:
        - token_name: Token symbol (str) or None if not found
        - entry_cap: Entry market cap as float (or current cap for discovery posts)
        - peak_cap: Peak market cap as float (same as entry_cap for discovery posts)
        - x_gain: Gain multiplier as float (1.0 for discovery posts)
        - vip_x: VIP gain multiplier as float or None if not VIP
        - message_type: 'discovery', 'update', or 'other'
        - contract_address: Token contract address if found

        Returns None if message is invalid or cannot be parsed.

    Examples:
        >>> parse_crypto_call("🚀 CA: 0x123 Entry: 45K MC Peak: 180K MC (4x)")
        {
            'token_name': None,
            'entry_cap': 45000.0,
            'peak_cap': 180000.0,
            'x_gain': 4.0,
            'vip_x': None,
            'message_type': 'update',
            'contract_address': None
        }

        >>> parse_crypto_call("Bean Cabal (CABAL)\\n944XTHEz...")
        {
            'token_name': 'CABAL',
            'entry_cap': 45900.0,
            'peak_cap': 45900.0,
            'x_gain': 1.0,
            'vip_x': None,
            'message_type': 'discovery',
            'contract_address': '944XTHEz...'
        }
    """
    if not message or not isinstance(message, str):
        return None

    # Clean up whitespace
    message = message.strip()
    if not message:
        return None

    try:
        # First, check for update messages (price movements)
        update_result = _parse_update_message(message)
        if update_result:
            return update_result

        # Then check for discovery messages
        discovery_result = _parse_discovery_message(message)
        if discovery_result:
            return discovery_result

        # Check for bonding messages
        if "bonded" in message.lower():
            return {
                "token_name": None,
                "entry_cap": None,
                "peak_cap": None,
                "x_gain": None,
                "vip_x": None,
                "message_type": "bonding",
                "contract_address": None,
            }

        # Fallback to original format: "Entry: 45K MC Peak: 180K MC (4x)"
        fallback_result = _parse_fallback_format(message)
        if fallback_result:
            return fallback_result

        return None

    except (ValueError, AttributeError) as e:
        logger.debug(f"Failed to parse message: {message[:50]}... Error: {e}")
        return None


def _parse_update_message(message: str) -> Optional[Dict[str, Union[str, float, None]]]:
    """Parse price update messages like '🎉 2.6x | 💹From 43.7K ↗️ 115.0K within 8m'"""

    # Pattern for update messages with both regular and VIP multipliers
    # 🔥 5.4x(6.6x from VIP) | 💹From 43.6K ↗️ 234.1K within 5d
    vip_pattern = r"[🎉🔥🌕⚡️🚀🌙]\s*\*?\*?([0-9]+(?:\.[0-9]+)?)x\s*\(([0-9]+(?:\.[0-9]+)?)x\s*from\s*VIP\)\*?\*?\s*[`|]*\s*💹[`]*From[`]*\s*\*?\*?([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\*?\*?\s*↗️\s*\*?\*?([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\*?\*?\s*[`]*within[`]*\s*(.+?)(?::?\s|$)"

    vip_match = re.search(vip_pattern, message, re.IGNORECASE | re.DOTALL)
    if vip_match:
        x_gain = float(vip_match.group(1))
        vip_x = float(vip_match.group(2))

        entry_value = float(vip_match.group(3))
        entry_unit = vip_match.group(4)
        entry_cap = _convert_to_number(entry_value, entry_unit)

        peak_value = float(vip_match.group(5))
        peak_unit = vip_match.group(6)
        peak_cap = _convert_to_number(peak_value, peak_unit)

        time_to_peak = vip_match.group(7).strip()

        return {
            "token_name": None,  # Updates don't contain token name
            "entry_cap": entry_cap,
            "peak_cap": peak_cap,
            "x_gain": x_gain,
            "vip_x": vip_x,
            "message_type": "update",
            "contract_address": None,
            "time_to_peak": time_to_peak,
        }

    # Pattern for regular update messages (no VIP)
    # 🎉 2.6x | 💹From 43.7K ↗️ 115.0K within 8m
    regular_pattern = (
        r"[🎉🔥🌕⚡️🚀🌙]\s*\*?\*?([0-9]+(?:\.[0-9]+)?)x"
        r"\s*\(([0-9]+(?:\.[0-9]+)?)x\s*from\s*VIP\)\*?\*?"
        r"\s*[`|]*\s*💹[`]*From[`]*\s*\*?\*?([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\*?\*?"
        r"\s*↗️\s*\*?\*?([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\*?\*?"
        r"\s*[`]*within[`]*\s*(.+?)(?::?\s|$)"
    )

    regular_match = re.search(regular_pattern, message, re.IGNORECASE | re.DOTALL)
    if regular_match:
        x_gain = float(regular_match.group(1))

        entry_value = float(regular_match.group(2))
        entry_unit = regular_match.group(3)
        entry_cap = _convert_to_number(entry_value, entry_unit)

        peak_value = float(regular_match.group(4))
        peak_unit = regular_match.group(5)
        peak_cap = _convert_to_number(peak_value, peak_unit)

        time_to_peak = regular_match.group(6).strip()

        return {
            "token_name": None,  # Updates don't contain token name
            "entry_cap": entry_cap,
            "peak_cap": peak_cap,
            "x_gain": x_gain,
            "vip_x": None,
            "message_type": "update",
            "contract_address": None,
            "time_to_peak": time_to_peak,
        }

    return None


def _parse_discovery_message(
    message: str,
) -> Optional[Dict[str, Union[str, float, None]]]:
    """Parse discovery messages with the new markdown link format."""

    # This new pattern correctly handles the `[Token Name](URL)` format and
    # uses named capture groups for clarity and robustness.
    # It looks for the token name, contract address, and market cap.
    discovery_pattern = re.compile(
        r"\[(?P<token_name>[^\]]+)\]"  # Group "token_name": Captures the full token name inside brackets.
        r"\(https?://[^\)]+\)"  # Matches the (URL) part, which we don't need to capture.
        r".*?"  # Non-greedily matches characters between the URL and address.
        r"`(?P<contract_address>[A-Za-z0-9]{30,})`"  # Group "contract_address": Captures the address from within backticks.
        r".*?"  # Non-greedily matches characters between the address and the cap.
        r"Cap:`\s*\**(?P<cap_value>[0-9]+(?:\.[0-9]+)?)\s*(?P<cap_unit>[KMB]?)\**",  # Named groups for cap value and unit.
        re.DOTALL | re.IGNORECASE,
    )

    match = discovery_pattern.search(message)

    if match:
        data = match.groupdict()

        current_cap = _convert_to_number(float(data["cap_value"]), data.get("cap_unit"))

        # For discovery posts, entry_cap and peak_cap are the same, and x_gain is 1.0.
        return {
            "token_name": data["token_name"].strip(),
            "entry_cap": current_cap,
            "peak_cap": current_cap,
            "x_gain": 1.0,
            "vip_x": None,
            "message_type": "discovery",
            "contract_address": data["contract_address"].strip(),
        }

    logger.debug("Message did not match the primary discovery pattern.")
    return None


def _parse_fallback_format(
    message: str,
) -> Optional[Dict[str, Union[str, float, None]]]:
    """Parse fallback format: 'Entry: 45K MC Peak: 180K MC (4x)'"""

    # Extract token name (optional)
    token_name = None
    token_match = re.search(r"\$([A-Z][A-Z0-9]*)", message, re.IGNORECASE)
    if token_match:
        token_name = token_match.group(1).upper()

    # Extract entry market cap
    entry_pattern = r"Entry:?\s*([0-9]+(?:\.[0-9]+)?)\s*([KMB])?"
    entry_match = re.search(entry_pattern, message, re.IGNORECASE)
    if not entry_match:
        return None

    entry_value = float(entry_match.group(1))
    entry_unit = entry_match.group(2)
    entry_cap = _convert_to_number(entry_value, entry_unit)

    # Extract peak market cap
    peak_pattern = r"Peak:?\s*([0-9]+(?:\.[0-9]+)?)\s*([KMB])?"
    peak_match = re.search(peak_pattern, message, re.IGNORECASE)
    if not peak_match:
        return None

    peak_value = float(peak_match.group(1))
    peak_unit = peak_match.group(2)
    peak_cap = _convert_to_number(peak_value, peak_unit)

    # Extract gain multiplier
    gain_pattern = r"\(([0-9]+(?:\.[0-9]+)?)x"
    gain_match = re.search(gain_pattern, message, re.IGNORECASE)
    if not gain_match:
        return None

    x_gain = float(gain_match.group(1))

    # Check if it's a VIP call
    vip_x = None
    if re.search(r"vip", message, re.IGNORECASE):
        vip_x = x_gain

    return {
        "token_name": token_name,
        "entry_cap": entry_cap,
        "peak_cap": peak_cap,
        "x_gain": x_gain,
        "vip_x": vip_x,
        "message_type": "update",
        "contract_address": None,
    }


def link_messages_to_calls(messages: List[Dict]) -> List[Dict]:
    """Link update messages to their original discovery calls using reply_to_message_id.

    This function iterates through a list of raw message data, creating a
    map of message IDs to messages. It then links 'update' type messages
    back to their corresponding 'discovery' calls if the update is a direct
    reply to the discovery.

    Args:
        messages: A list of dictionaries, where each dictionary represents
                  a raw message from the database, including 'message_id',
                  'reply_to_message_id', and a 'parsed_data' dictionary
                  containing the message_type.

    Returns:
        The same list of messages, with an added 'linked_to_call_id'
        field in the 'parsed_data' dictionary for linked updates.
    """
    # Create a lookup map for message_id -> message
    message_map = {msg["message_id"]: msg for msg in messages}

    linked_messages = []
    for msg in messages:
        # Ensure we don't modify the original dict
        updated_msg = msg.copy()

        # We only need to link messages that are updates and are replies
        reply_to_id = updated_msg.get("reply_to_message_id")

        parsed_data = updated_msg.get("parsed_data")
        if not parsed_data:
            linked_messages.append(updated_msg)
            continue

        # Ensure parsed_data is a mutable dictionary
        parsed_data = parsed_data.copy()
        updated_msg["parsed_data"] = parsed_data

        if parsed_data.get("message_type") == "update" and reply_to_id:
            # Find the original message this was a reply to
            original_message = message_map.get(reply_to_id)

            if original_message:
                original_parsed_data = original_message.get("parsed_data")
                # Check if the original message was a discovery call
                if (
                    original_parsed_data
                    and original_parsed_data.get("message_type") == "discovery"
                ):
                    # Link found! Use the database ID of the original message.
                    parsed_data["linked_to_call_id"] = original_message.get("id")
                else:
                    parsed_data["linked_to_call_id"] = None
            else:
                # Reply to a message not in the current batch
                parsed_data["linked_to_call_id"] = None
        else:
            # Not an update message or not a reply
            parsed_data["linked_to_call_id"] = None

        linked_messages.append(updated_msg)

    return linked_messages


def _convert_to_number(value: float, unit: Optional[str]) -> float:
    """Convert a value with unit suffix to a number.

    Args:
        value: The numeric value.
        unit: The unit suffix ('K', 'M', 'B') or None.

    Returns:
        The converted number as float.

    Examples:
        >>> _convert_to_number(45.0, 'K')
        45000.0
        >>> _convert_to_number(1.5, 'M')
        1500000.0
    """
    if not unit:
        return value

    unit = unit.upper()
    multipliers = {
        "K": 1_000,
        "M": 1_000_000,
        "B": 1_000_000_000,
    }

    return value * multipliers.get(unit, 1)
