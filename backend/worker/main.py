import argparse
import asyncio
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings
from worker.sync_exhibitions import result_dict, sync_exhibitions

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


TOKYO = ZoneInfo("Asia/Tokyo")


def next_run(now: datetime) -> datetime:
    candidate = now.replace(hour=settings.exhibition_sync_hour, minute=0, second=0, microsecond=0)
    return candidate if candidate > now else candidate + timedelta(days=1)


async def run_once(*, dry_run: bool) -> None:
    result = await sync_exhibitions(dry_run=dry_run)
    logger.info("Exhibition sync complete: %s", json.dumps(result_dict(result), ensure_ascii=False))


async def serve() -> None:
    while True:
        now = datetime.now(TOKYO)
        scheduled = next_run(now)
        logger.info("Next exhibition sync: %s", scheduled.isoformat())
        await asyncio.sleep((scheduled - now).total_seconds())
        try:
            await run_once(dry_run=False)
        except Exception:
            logger.exception("Exhibition sync failed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily Tokyo exhibition importer")
    parser.add_argument("--once", action="store_true", help="Run immediately and exit")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and match without database writes")
    args = parser.parse_args()
    if args.dry_run and not args.once:
        parser.error("--dry-run requires --once")
    asyncio.run(run_once(dry_run=args.dry_run) if args.once else serve())


if __name__ == "__main__":
    main()
