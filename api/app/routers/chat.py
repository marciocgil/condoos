"""Chat "Pergunte ao CondoOS" for one condominium (spec §10). Read-only by construction."""

import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth.deps import require
from app.auth.rbac import CondoAccess, Permission
from app.chat.agent import ChatUnavailable
from app.chat.service import answer, history
from app.chat.tools import ScreenContext
from app.db.session import DbSession, set_tenant_scope
from app.launch.readiness import chat_available

router = APIRouter(prefix="/condominiums/{condominium_id}/chat", tags=["chat"])

CanView = Annotated[CondoAccess, Depends(require(Permission.VIEW))]


class ScreenIn(BaseModel):
    screen: Literal[
        "resumo", "achados", "achado", "contratos", "historico", "carteira", "outra"
    ] = "resumo"
    finding_id: uuid.UUID | None = None
    competence: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")


class ChatIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    screen: ScreenIn = ScreenIn()


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[dict[str, Any]]
    suggested_action: dict[str, Any] | None
    created_at: str


def _screen(s: ScreenIn) -> ScreenContext:
    comp = None
    if s.competence:
        comp = date(int(s.competence[:4]), int(s.competence[5:7]), 1)
    return ScreenContext(screen=s.screen, finding_id=s.finding_id, competence=comp)


@router.get("/status")
async def chat_status(condominium_id: uuid.UUID, access: CanView) -> dict[str, bool]:
    """Whether the chat can answer now (LB-085, D108): the "Pergunte" button only shows
    when it does. Without a model (``replay``/``off``) every question would get a 503."""
    return {"available": chat_available()}


@router.get("")
async def get_history(
    condominium_id: uuid.UUID, access: CanView, db: DbSession
) -> list[ChatMessageOut]:
    return [
        ChatMessageOut(
            id=m.id,
            role=m.role,
            content=m.content,
            citations=m.citations,
            suggested_action=m.suggested_action,
            created_at=m.created_at.isoformat(),
        )
        for m in await history(db, access)
    ]


@router.post("")
async def ask(
    condominium_id: uuid.UUID, body: ChatIn, access: CanView, db: DbSession
) -> ChatMessageOut:
    # The whole turn sees only this condominium, even for a manager with many (RLS).
    await set_tenant_scope(db, [access.condominium_id])
    try:
        out = await answer(db, access, body.question, _screen(body.screen))
    except ChatUnavailable as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    return ChatMessageOut(
        id=uuid.UUID(out.message_id),
        role="assistant",
        content=out.content,
        citations=out.citations,
        suggested_action=out.suggested_action,
        created_at=out.created_at,
    )
