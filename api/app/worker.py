"""Job worker: python -m app.worker"""

import asyncio
import contextlib
import logging
import signal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.jobs import Handler, run_one
from app.db.session import get_worker_engine, sessionmaker_for

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("condoos.worker")


async def _ping(_: AsyncSession, payload: dict[str, Any]) -> None:
    logger.info("ping job received keys=%s", sorted(payload))


# Pipeline handlers (ingestion, extraction, enrichment, matching, rules...) are registered
# here as each milestone lands.
HANDLERS: dict[str, Handler] = {
    "ping": _ping,
}


async def main() -> None:
    settings = get_settings()
    maker = sessionmaker_for(get_worker_engine())
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info("worker started")
    while not stop.is_set():
        try:
            worked = await run_one(maker, HANDLERS)
        except Exception:
            logger.exception("worker loop error")
            worked = False
        if not worked:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval_seconds)
    logger.info("worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
