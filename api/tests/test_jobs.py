import asyncio
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.jobs import Handler, backoff_seconds, claim_next, enqueue, run_one
from app.core.time import utcnow
from app.db.enums import JobStatus
from app.db.models import Job
from app.db.session import sessionmaker_for


async def _clear(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(update(Job).values(status=JobStatus.DONE.value))


async def _get(engine: AsyncEngine, job_id: uuid.UUID) -> Job:
    async with sessionmaker_for(engine)() as s:
        job = await s.get(Job, job_id)
    assert job is not None
    return job


async def test_enqueue_is_idempotent_with_dedupe_key(worker_engine: AsyncEngine) -> None:
    key = f"doc:{uuid.uuid4()}:extract"
    async with sessionmaker_for(worker_engine)() as s, s.begin():
        first = await enqueue(s, "ping", {}, dedupe_key=key)
        second = await enqueue(s, "ping", {}, dedupe_key=key)
    assert first is not None
    assert second is None


async def test_concurrent_workers_never_claim_the_same_job(worker_engine: AsyncEngine) -> None:
    await _clear(worker_engine)
    maker = sessionmaker_for(worker_engine)
    async with maker() as s, s.begin():
        for _ in range(2):
            await enqueue(s, "ping", {})

    async with maker() as s1, s1.begin(), maker() as s2, s2.begin():
        a = await claim_next(s1)
        b = await claim_next(s2)  # first row is locked: SKIP LOCKED moves on
        c = await claim_next(s2)
        assert a is not None and b is not None
        assert a.id != b.id
        assert c is None


async def test_job_succeeds(worker_engine: AsyncEngine) -> None:
    await _clear(worker_engine)
    seen: list[dict[str, Any]] = []

    async def handler(_: AsyncSession, payload: dict[str, Any]) -> None:
        seen.append(payload)

    async with sessionmaker_for(worker_engine)() as s, s.begin():
        job_id = await enqueue(s, "t", {"n": 1})
    assert job_id
    assert await run_one(sessionmaker_for(worker_engine), {"t": handler})
    assert seen == [{"n": 1}]
    assert (await _get(worker_engine, job_id)).status == JobStatus.DONE.value
    assert not await run_one(sessionmaker_for(worker_engine), {"t": handler})


async def test_failing_job_retries_with_backoff_then_fails(worker_engine: AsyncEngine) -> None:
    await _clear(worker_engine)

    async def boom(_: AsyncSession, __: dict[str, Any]) -> None:
        raise ValueError("falha simulada")

    handlers: dict[str, Handler] = {"boom": boom}
    maker = sessionmaker_for(worker_engine)
    async with maker() as s, s.begin():
        job_id = await enqueue(s, "boom", {}, max_attempts=2)
    assert job_id

    assert await run_one(maker, handlers)
    job = await _get(worker_engine, job_id)
    assert job.status == JobStatus.QUEUED.value
    assert job.attempts == 1
    assert job.run_after > utcnow() + timedelta(seconds=backoff_seconds(1) - 2)
    assert job.last_error and "falha simulada" in job.last_error

    assert not await run_one(maker, handlers)  # not ready yet (backoff)
    async with maker() as s, s.begin():
        await s.execute(update(Job).where(Job.id == job_id).values(run_after=utcnow()))
    assert await run_one(maker, handlers)
    assert (await _get(worker_engine, job_id)).status == JobStatus.FAILED.value


async def test_stale_running_job_is_recovered(worker_engine: AsyncEngine) -> None:
    await _clear(worker_engine)
    maker = sessionmaker_for(worker_engine)
    async with maker() as s, s.begin():
        job_id = await enqueue(s, "ping", {})
        await s.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status=JobStatus.RUNNING.value, locked_at=utcnow() - timedelta(hours=1))
        )
    async with maker() as s, s.begin():
        job = await claim_next(s)
        assert job is not None and job.id == job_id


async def test_unknown_job_type_fails_without_crashing(worker_engine: AsyncEngine) -> None:
    await _clear(worker_engine)
    maker = sessionmaker_for(worker_engine)
    async with maker() as s, s.begin():
        job_id = await enqueue(s, "does-not-exist", {})
    assert job_id
    assert await run_one(maker, {})
    assert (await _get(worker_engine, job_id)).status == JobStatus.FAILED.value


def test_backoff_is_capped() -> None:
    assert backoff_seconds(1) == 10
    assert backoff_seconds(30) == 3600


async def test_parallel_run_one_processes_each_job_once(worker_engine: AsyncEngine) -> None:
    await _clear(worker_engine)
    maker = sessionmaker_for(worker_engine)
    counter: dict[str, int] = {}

    async def handler(_: AsyncSession, payload: dict[str, Any]) -> None:
        counter[payload["k"]] = counter.get(payload["k"], 0) + 1
        await asyncio.sleep(0.01)

    async with maker() as s, s.begin():
        for i in range(10):
            await enqueue(s, "count", {"k": str(i)})
    handlers: dict[str, Handler] = {"count": handler}
    for _ in range(4):
        await asyncio.gather(*(run_one(maker, handlers) for _ in range(4)))
    assert counter == {str(i): 1 for i in range(10)}
    async with maker() as s:
        remaining = await s.scalars(select(Job).where(Job.status == JobStatus.QUEUED.value))
        assert remaining.all() == []
