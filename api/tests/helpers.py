import re
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from app.auth.mailer import MemoryMailer
from app.db.models import Condominium
from app.db.session import sessionmaker_for


async def condo_id(admin_engine: AsyncEngine, slug: str) -> uuid.UUID:
    async with sessionmaker_for(admin_engine)() as s:
        cid = await s.scalar(select(Condominium.id).where(Condominium.slug == slug))
    assert cid is not None
    return cid


TOKEN_RE = re.compile(r"token=([A-Za-z0-9_\-]+)")


async def login(client: httpx.AsyncClient, mailer: MemoryMailer, email: str) -> None:
    mailer.sent.clear()
    r = await client.post("/auth/magic-link", json={"email": email})
    assert r.status_code == 202
    assert mailer.sent, f"no e-mail sent to {email}"
    match = TOKEN_RE.search(mailer.sent[-1].body)
    assert match
    r = await client.post("/auth/verify", json={"token": match.group(1)})
    assert r.status_code == 200, r.text


SINDICA_ACACIAS = "ana.sindica@acacias.example.com"
CONSELHEIRO_ACACIAS = "bruno.conselho@acacias.example.com"
SINDICA_MIRANTE = "carla.sindica@mirante.example.com"
GERENTE = "diego.gerente@atlantida.example.com"
ANALISTA = "elisa.analista@atlantida.example.com"
ADMIN_CONDOOS = "fabio.admin@condoos.example.com"  # CondoOS admin: both condominiums
REVISORA = "gabriela.revisora@condoos.example.com"  # CondoOS reviewer: Mirante do Vale only


def jpeg_bytes(tag: str = "") -> bytes:
    """A small real JPEG (triage opens and saves images again, D95). ``tag`` changes the
    pixels so two calls with different tags are different files."""
    import io

    from PIL import Image

    shade = sum(tag.encode()) % 200 + 30
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), (shade, shade, shade)).save(buf, format="JPEG")
    return buf.getvalue()
