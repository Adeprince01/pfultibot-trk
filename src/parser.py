"""Message parser for extracting structured data from crypto call messages."""

import logging
import re
from typing import Dict, Optional, Union, List, Tuple
from datetime import datetime, timedelta

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
                "contract_address": None
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
    vip_pattern = r"[🎉🔥🌕⚡️🚀🌙]\s*\*?\*?([0-9]+(?:\.[0-9]+)?)x\s*\(([0-9]+(?:\.[0-9]+)?)x\s*from\s*VIP\)\*?\*?\s*[`|]*\s*💹[`]*From[`]*\s*\*?\*?([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\*?\*?\s*↗️\s*\*?\*?([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\*?\*?\s*[`]*within[`]*\s*(.+?)(?:\s|$)"
    
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
            "time_to_peak": time_to_peak
        }
    
    # Pattern for regular update messages (no VIP)
    # 🎉 2.6x | 💹From 43.7K ↗️ 115.0K within 8m
    regular_pattern = r"[🎉🔥🌕⚡️🚀🌙]\s*\*?\*?([0-9]+(?:\.[0-9]+)?)x\*?\*?\s*[`|]*\s*💹[`]*From[`]*\s*\*?\*?([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\*?\*?\s*↗️\s*\*?\*?([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\*?\*?\s*[`]*within[`]*\s*(.+?)(?:\s|$)"
    
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
            "time_to_peak": time_to_peak
        }
    
    return None


def _parse_discovery_message(message: str) -> Optional[Dict[str, Union[str, float, None]]]:
    """Parse discovery messages like 'Bean Cabal (CABAL) 944XTHEz... Cap: 43.7K'"""
    
    # Pattern for discovery messages: [token name (symbol)] or token name (symbol)
    # Followed by contract address and Cap: value
    discovery_pattern = r"(?:\[(.+?)\s*\(([^)]+)\)\]|^(.+?)\s*\(([^)]+)\))\s*(?:https?://[^\s]*/)?\s*([A-Za-z0-9]{20,})\s*.*?[`]*Cap:?[`]*\s*\*?\*?([0-9]+(?:\.[0-9]+)?)\s*([KMB]?)\*?\*?"
    
    discovery_match = re.search(discovery_pattern, message, re.IGNORECASE | re.DOTALL)
    
    if discovery_match:
        # Extract token name and symbol
        if discovery_match.group(1):  # Bracketed format
            coin_name = discovery_match.group(1).strip()
            token_symbol = discovery_match.group(2).strip().upper()
        else:  # Non-bracketed format
            coin_name = discovery_match.group(3).strip()
            token_symbol = discovery_match.group(4).strip().upper()
            
        contract_address = discovery_match.group(5)
        
        cap_value = float(discovery_match.group(6))
        cap_unit = discovery_match.group(7)
        current_cap = _convert_to_number(cap_value, cap_unit)
        
        # For discovery posts, entry_cap = peak_cap = current_cap, x_gain = 1.0
        return {
            "token_name": token_symbol,
            "entry_cap": current_cap,
            "peak_cap": current_cap,
            "x_gain": 1.0,
            "vip_x": None,
            "message_type": "discovery",
            "contract_address": contract_address
        }
    
    return None


def _parse_fallback_format(message: str) -> Optional[Dict[str, Union[str, float, None]]]:
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
        "contract_address": None
    }


def link_messages_to_calls(messages: List[Dict]) -> List[Dict]:
    """Link update messages to their original discovery calls.
    
    Args:
        messages: List of parsed message dictionaries, sorted by timestamp
        
    Returns:
        List of messages with additional 'linked_to_call_id' field
    """
    # Track active discovery calls (discovery messages that haven't been "completed")
    active_calls = {}  # entry_cap -> discovery_message_info
    
    linked_messages = []
    
    for msg in messages:
        msg = msg.copy()  # Don't modify original
        
        if msg.get('message_type') == 'discovery':
            # New discovery call - add to active calls
            entry_cap = msg.get('entry_cap')
            if entry_cap:
                active_calls[entry_cap] = {
                    'id': msg.get('id'),
                    'token_name': msg.get('token_name'),
                    'contract_address': msg.get('contract_address'),
                    'timestamp': msg.get('timestamp')
                }
            msg['linked_to_call_id'] = None  # Discovery calls don't link to anything
            
        elif msg.get('message_type') == 'update':
            # Update message - try to link to discovery call
            entry_cap = msg.get('entry_cap')
            linked_call_id = None
            
            if entry_cap:
                # Look for exact match first
                if entry_cap in active_calls:
                    linked_call_id = active_calls[entry_cap]['id']
                else:
                    # Look for close matches (within 5% tolerance for rounding differences)
                    tolerance = 0.05
                    for active_cap, call_info in active_calls.items():
                        if abs(entry_cap - active_cap) / active_cap <= tolerance:
                            linked_call_id = call_info['id']
                            break
            
            msg['linked_to_call_id'] = linked_call_id
            
        else:
            # Other message types (bonding, etc.)
            msg['linked_to_call_id'] = None
            
        linked_messages.append(msg)
    
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
