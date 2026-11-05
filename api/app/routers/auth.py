from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth.mailer import Mailer, get_mailer
from app.auth.service import consume_magic_link, request_magic_link, revoke_session
from app.config import get_settings
from app.core.audit import record_audit
from app.db.session import DbSession
from app.routers.schemas import MagicLinkRequest, MessageOut, VerifyRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/magic-link", status_code=status.HTTP_202_ACCEPTED)
async def magic_link(
    body: MagicLinkRequest,
    session: DbSession,
    mailer: Mailer = Depends(get_mailer),
) -> MessageOut:
    await request_magic_link(session, body.email, mailer)
    return MessageOut(message="Se o e-mail estiver cadastrado, enviaremos um link de acesso.")


@router.post("/verify")
async def verify(body: VerifyRequest, response: Response, session: DbSession) -> MessageOut:
    created = await consume_magic_link(session, body.token)
    if created is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Link inválido ou expirado. Peça um novo link."
        )
    s = get_settings()
    response.set_cookie(
        s.session_cookie_name,
        created.raw_token,
        max_age=s.session_ttl_days * 86400,
        httponly=True,
        secure=s.session_cookie_secure,
        samesite="lax",
        path="/",
    )
    return MessageOut(message="Acesso liberado.")


@router.post("/logout")
async def logout(request: Request, response: Response, session: DbSession) -> MessageOut:
    s = get_settings()
    raw = request.cookies.get(s.session_cookie_name)
    if raw:
        user_id = await revoke_session(session, raw)
        if user_id:
            await record_audit(
                session,
                action="auth.logout",
                object_type="app_user",
                object_id=user_id,
                actor_user_id=user_id,
            )
    response.delete_cookie(s.session_cookie_name, path="/")
    return MessageOut(message="Sessão encerrada.")
