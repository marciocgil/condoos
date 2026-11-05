"""Postgres-backed job queue using SELECT ... FOR UPDATE SKIP LOCKED.

Each job type is handled by an idempotent coroutine. A job is claimed in one short
transaction and executed in another, so a slow handler never holds the row lock.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.time import utcnow
from app.db.enums import JobStatus
from app.db.models import Job

logger = logging.getLogger(__name__)

Handler = Callable[[AsyncSession, dict[str, Any]], Awaitable[None]]

STALE_AFTER = timedelta(minutes=15)
MAX_BACKOFF_SECONDS = 3600


async def enqueue(
    session: AsyncSession,
    job_type: str,
    payload: dict[str, Any],
    *,
    condominium_id: uuid.UUID | None = None,
    dedupe_key: str | None = None,
    run_after: datetime | None = None,
    max_attempts: int = 5,
) -> uuid.UUID | None:
    """Insert a job. Returns None when a job with the same dedupe_key already exists."""
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "job_type": job_type,
        "payload": payload,
        "condominium_id": condominium_id,
        "dedupe_key": dedupe_key,
        "max_attempts": max_attempts,
        "status": JobStatus.QUEUED.value,
        "attempts": 0,
    }
    if run_after is not None:
        values["run_after"] = run_after
    stmt = insert(Job).values(**values).on_conflict_do_nothing(index_elements=["dedupe_key"])
    result = await session.scalar(stmt.returning(Job.id))
    return result


async def claim_next(session: AsyncSession) -> Job | None:
    now = utcnow()
    job = await session.scalar(
        select(Job)
        .where(
            or_(
                (Job.status == JobStatus.QUEUED.value) & (Job.run_after <= now),
                # Recover jobs left "running" by a worker that died.
                (Job.status == JobStatus.RUNNING.value) & (Job.locked_at < now - STALE_AFTER),
            )
        )
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    job.status = JobStatus.RUNNING.value
    job.attempts += 1
    job.locked_at = now
    return job


def backoff_seconds(attempts: int) -> int:
    return int(min(2**attempts * 5, MAX_BACKOFF_SECONDS))


async def run_one(maker: async_sessionmaker[AsyncSession], handlers: dict[str, Handler]) -> bool:
    """Claim and execute one job. Returns False when the queue had nothing ready."""
    async with maker() as session, session.begin():
        job = await claim_next(session)
        if job is None:
            return False
        job_id, job_type, payload = job.id, job.job_type, dict(job.payload)
        attempts, max_attempts = job.attempts, job.max_attempts

    handler = handlers.get(job_type)
    error: str | None = None
    if handler is None:
        error = f"no handler for job type {job_type!r}"
    else:
        try:
            async with maker() as session, session.begin():
                await handler(session, payload)
        except Exception as exc:  # job failures must never kill the worker
            error = f"{type(exc).__name__}: {exc}"[:2000]

    async with maker() as session, session.begin():
        values: dict[str, Any]
        if error is None:
            values = {"status": JobStatus.DONE.value, "last_error": None}
            logger.info("job done id=%s type=%s", job_id, job_type)
        elif attempts >= max_attempts or handler is None:
            values = {"status": JobStatus.FAILED.value, "last_error": error}
            # Only ids in application logs; the error text stays in the database.
            logger.error("job failed id=%s type=%s attempts=%s", job_id, job_type, attempts)
        else:
            values = {
                "status": JobStatus.QUEUED.value,
                "last_error": error,
                "run_after": utcnow() + timedelta(seconds=backoff_seconds(attempts)),
            }
            logger.warning("job retry id=%s type=%s attempts=%s", job_id, job_type, attempts)
        await session.execute(update(Job).where(Job.id == job_id).values(locked_at=None, **values))
    return True
