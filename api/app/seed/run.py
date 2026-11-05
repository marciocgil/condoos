"""Load the fictitious seed into the database (owner role). Idempotent."""

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.models import ManagementCompany
from app.db.session import get_admin_engine, sessionmaker_for
from app.seed.data import build_seed

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
    return True


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    loaded = await load_seed(get_admin_engine())
    logger.info("seed %s", "loaded" if loaded else "already present, skipped")


if __name__ == "__main__":
    asyncio.run(main())
