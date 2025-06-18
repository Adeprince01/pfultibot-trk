"""Application orchestrator for the Telegram Crypto Call Tracker."""

from __future__ import annotations

import asyncio
import logging

# from .listener import run_listener  # TODO: Implement in Task 2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


def main() -> None:  # noqa: D401
    """Run the Telegram listener in an asyncio event loop."""
    logger.info("Starting Telegram Crypto Call Tracker …")
    # asyncio.run(run_listener())  # TODO: Implement in Task 2
    logger.info("Task 1 complete: Basic TelegramListener class ready!")


if __name__ == "__main__":
    main()
