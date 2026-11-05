"""
Scheduled tasks for the auth module.

Run from cron or any scheduler:

    uv run python -m hr_minds.auth.tasks
"""

import asyncio
import logging
import sys

from hr_minds.auth.models import AccessToken
from hr_minds.settings.db import AsyncSessionLocal
from hr_minds.settings.logging import setup_logging

logger = logging.getLogger(__name__)


async def delete_expired_sessions() -> int:
    async with AsyncSessionLocal() as db:
        deleted = await AccessToken.delete_expired(db)
    logger.info("Removed expired access tokens", extra={"deleted": deleted})
    return deleted


def main() -> int:
    setup_logging()
    asyncio.run(delete_expired_sessions())
    return 0


if __name__ == "__main__":
    sys.exit(main())
