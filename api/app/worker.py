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
from app.extraction.pipeline import process_document
from app.ingestion.documents import PROCESS_JOB
from app.ingestion.email import FolderEmailProvider, poll_provider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("condoos.worker")


async def _ping(_: AsyncSession, payload: dict[str, Any]) -> None:
    logger.info("ping job received keys=%s", sorted(payload))


# Pipeline handlers (ingestion, extraction, enrichment, matching, rules...) are registered
# here as each milestone lands.
HANDLERS: dict[str, Handler] = {
    "ping": _ping,
    PROCESS_JOB: process_document,
}


async def main() -> None:
    settings = get_settings()
    maker = sessionmaker_for(get_worker_engine())
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    logger.info("worker started")
    provider = (
        FolderEmailProvider(settings.inbound_email_dir) if settings.inbound_email_dir else None
    )
    next_email_poll = 0.0
    while not stop.is_set():
        if provider is not None and loop.time() >= next_email_poll:
            next_email_poll = loop.time() + settings.inbound_email_poll_seconds
            try:
                accepted = await poll_provider(maker, provider)
                if accepted:
                    logger.info("inbound email accepted=%s", accepted)
            except Exception:
                logger.exception("inbound email poll failed")
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
