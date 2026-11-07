"""Job worker: python -m app.worker"""

import asyncio
import contextlib
import logging
import signal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.actions import DISPATCH_JOB, dispatch_job
from app.chat.search import INDEX_JOB, index_job
from app.config import get_settings
from app.core.jobs import Handler, run_one
from app.core.retention import RETENTION_JOB, purge_job
from app.data_issues import SCAN_JOB, scan_job
from app.db.session import get_worker_engine, sessionmaker_for
from app.enrichment.indices import refresh_indices_job
from app.enrichment.suppliers import enrich_job
from app.extraction.pipeline import process_document
from app.findings.explain import explain_job
from app.ingestion.documents import PROCESS_JOB
from app.ingestion.email import FolderEmailProvider, poll_provider
from app.matching.bank import match_bank_job
from app.matching.documents import match_document_job
from app.policy import job_paused
from app.rules.engine import evaluate_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("condoos.worker")


async def _ping(_: AsyncSession, payload: dict[str, Any]) -> None:
    logger.info("ping job received keys=%s", sorted(payload))


# Pipeline handlers (ingestion, extraction, enrichment, matching, rules...) are registered
# here as each milestone lands.
HANDLERS: dict[str, Handler] = {
    "ping": _ping,
    PROCESS_JOB: process_document,
    "document.match": match_document_job,
    "bank.match": match_bank_job,
    "supplier.enrich": enrich_job,
    "indices.refresh": refresh_indices_job,
    "rules.evaluate": evaluate_job,
    "finding.explain": explain_job,
    INDEX_JOB: index_job,
    RETENTION_JOB: purge_job,
    DISPATCH_JOB: dispatch_job,
    SCAN_JOB: scan_job,
}


async def _schedule_daily(maker: Any) -> None:
    """Once a day (deduplicated by date): refresh price indices from the Banco Central and
    apply the document retention policy."""
    from datetime import date

    from app.core.jobs import enqueue

    async with maker() as session, session.begin():
        await enqueue(
            session,
            "indices.refresh",
            {"months": 24},
            dedupe_key=f"indices:{date.today().isoformat()}",
        )
        await enqueue(
            session,
            RETENTION_JOB,
            {},
            dedupe_key=f"retention:{date.today().isoformat()}",
        )
        # Data conflicts of every condominium (D95), in case a change bypassed the pipeline.
        await enqueue(session, SCAN_JOB, {}, dedupe_key=f"data-issues:{date.today().isoformat()}")


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
        await _schedule_daily(maker)
        if provider is not None and loop.time() >= next_email_poll:
            next_email_poll = loop.time() + settings.inbound_email_poll_seconds
            try:
                accepted = await poll_provider(maker, provider)
                if accepted:
                    logger.info("inbound email accepted=%s", accepted)
            except Exception:
                logger.exception("inbound email poll failed")
        try:
            worked = await run_one(maker, HANDLERS, job_paused)
        except Exception:
            logger.exception("worker loop error")
            worked = False
        if not worked:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_interval_seconds)
    logger.info("worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
