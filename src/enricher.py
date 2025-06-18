"""Market data enrichment using Dexscreener API."""

from __future__ import annotations

import logging
from typing import Any, Dict

from .settings import settings  # noqa: F401  # imported for future use

logger = logging.getLogger(__name__)

DEX_API_BASE: str = "https://api.dexscreener.com/latest/dex/tokens"


async def enrich_with_price(data: Dict[str, Any]) -> Dict[str, Any]:
    """Return data enriched with live market information.

    This stub simply echoes the input data. Future implementations will fetch
    price and market-cap information from Dexscreener (or fallbacks) and merge
    it into the payload.

    Args:
        data: Parsed call dictionary from :pyfunc:`parser.parse_call`.

    Returns:
        The original data, currently unchanged.
    """
    logger.debug("enrich_with_price called with data=%s", data)
    # TODO: Implement HTTP request with caching and error handling
    return data
