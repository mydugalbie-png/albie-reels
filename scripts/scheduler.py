"""APScheduler based daily runner for Albie Reels."""
from __future__ import annotations

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from agents.orchestrator import Orchestrator
from utils.config import settings
from db.session import init_db


async def job():
    logger.info("Scheduled job fired at {}", datetime.now())
    orch = Orchestrator()
    result = await orch.execute_run()
    logger.info("Job result: {}", {k: result.get(k) for k in ("run_id", "status", "error")})


def main():
    asyncio.get_event_loop().run_until_complete(init_db())

    tz = ZoneInfo(settings.timezone)
    scheduler = AsyncIOScheduler(timezone=tz)

    for t in settings.schedule_times:
        hour, minute = map(int, t.split(":"))
        trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)
        scheduler.add_job(job, trigger, id=f"albie_run_{t}", replace_existing=True)
        logger.info("Scheduled run at {:02d}:{:02d} {}", hour, minute, settings.timezone)

    scheduler.start()
    logger.success("Albie Reels scheduler running. Press Ctrl+C to exit.")
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    main()
