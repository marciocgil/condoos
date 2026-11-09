"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.routers import (
    actions,
    agenda,
    approvals,
    auth,
    briefing,
    cases,
    chat,
    compliance,
    condominiums,
    data_issues,
    delegations,
    documents,
    findings,
    inbound,
    launch,
    me,
    opportunities,
    platform,
    portfolio,
    queue,
    registry,
    reports,
    review_policy,
    settings,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("condoos")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.environment != "test" and settings.storage_backend == "s3":
        from app.storage.s3 import ensure_bucket

        try:
            ensure_bucket()
        except Exception:  # storage may start after the API; uploads will retry
            logger.warning("object storage not reachable at startup")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="CondoOS API", version="0.1.0", lifespan=lifespan)
    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(condominiums.router)
    app.include_router(documents.router)
    app.include_router(queue.router)
    app.include_router(findings.router)
    app.include_router(portfolio.router)
    app.include_router(settings.router)
    app.include_router(chat.router)
    app.include_router(reports.router)
    app.include_router(approvals.router)
    app.include_router(registry.router)
    app.include_router(agenda.router)
    app.include_router(platform.router)
    app.include_router(review_policy.router)
    app.include_router(cases.router)
    app.include_router(opportunities.router)
    app.include_router(briefing.router)
    app.include_router(actions.router)
    app.include_router(launch.router)
    app.include_router(data_issues.router)
    app.include_router(delegations.router)
    app.include_router(inbound.router)
    app.include_router(compliance.router)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
