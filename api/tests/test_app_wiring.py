"""Guards on how routes are wired."""

from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

from app.db.session import get_db
from app.routers import auth, condominiums, me

ROUTERS = [auth.router, me.router, condominiums.router]


def _walk(dep: Dependant) -> list[Dependant]:
    out = [dep]
    for sub in dep.dependencies:
        out.extend(_walk(sub))
    return out


def test_db_session_commits_before_response_on_every_route() -> None:
    """get_db must be function-scoped so writes are committed before the client sees the
    response (otherwise a just-issued session cookie can hit the API before its row exists).
    """
    routes = [r for router in ROUTERS for r in router.routes if isinstance(r, APIRoute)]
    checked = 0
    for route in routes:
        for dep in _walk(route.dependant):
            if dep.call is get_db:
                assert dep.scope == "function", f"{route.path} uses get_db with scope={dep.scope}"
                checked += 1
    assert checked > 0
