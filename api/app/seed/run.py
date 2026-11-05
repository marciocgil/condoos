"""Load the fictitious seed into the database (owner role). Idempotent."""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import ManagementCompany
from app.db.session import get_admin_engine, sessionmaker_for
from app.seed.data import build_seed
from app.seed.documents import seed_documents

logger = logging.getLogger("condoos.seed")


async def load_seed(engine: AsyncEngine) -> bool:
    """Insert the seed. Returns False when it was already loaded."""
    seed = build_seed()
    async with sessionmaker_for(engine)() as session, session.begin():
        exists = await session.scalar(
            select(ManagementCompany.id).where(ManagementCompany.cnpj == seed.company_cnpj)
        )
        if exists is not None:
            return False
        for phase in seed.objects:
            session.add_all(phase)
            await session.flush()
        await seed_documents(session)
    return True


async def evaluate_seed(engine: AsyncEngine) -> int:
    """Run the audit rules over the seed's open month, as on 05/11/2026 (deterministic)."""
    from datetime import date

    from app.db.models import Condominium
    from app.rules.engine import evaluate
    from app.seed.data import LAST_MONTH

    created = 0
    async with sessionmaker_for(engine)() as session, session.begin():
        for condo_id in await session.scalars(select(Condominium.id)):
            summary = await evaluate(session, condo_id, LAST_MONTH, date(2026, 11, 5))
            created += summary.created
    return created


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    engine = get_admin_engine()
    loaded = await load_seed(engine)
    logger.info("seed %s", "loaded" if loaded else "already present, skipped")
    if loaded:
        logger.info("seed findings created=%s", await evaluate_seed(engine))


if __name__ == "__main__":
    asyncio.run(main())
