import asyncio
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from app.db.session import get_admin_engine, sessionmaker_for
from app.onboarding import OnboardingIn, onboard


async def run(spec: OnboardingIn) -> int:
    async with sessionmaker_for(get_admin_engine())() as session, session.begin():
        try:
            condo = await onboard(session, spec)
        except ValueError as exc:
            print(f"Não cadastrado: {exc}", file=sys.stderr)
            return 1
    print(f"Condomínio cadastrado: {condo.name} (id {condo.id}, slug {condo.slug})")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("uso: python -m app.onboarding <arquivo.json>", file=sys.stderr)
        return 2
    try:
        spec = OnboardingIn.model_validate(json.loads(Path(argv[1]).read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"Arquivo inválido: {exc}", file=sys.stderr)
        return 2
    return asyncio.run(run(spec))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
