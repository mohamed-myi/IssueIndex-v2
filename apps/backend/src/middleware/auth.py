from datetime import datetime, timezone
from uuid import UUID

from fastapi import Request, HTTPException, Depends
from starlette.responses import Response
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.cookies import SESSION_COOKIE_NAME, create_session_cookie
from src.core.audit import AuditEvent, log_audit_event
from models.identity import User, Session
from src.services.session_service import get_session_by_id, refresh_session, invalidate_session
from src.services.risk_assessment import assess_session_risk, RiskResult
from src.middleware.context import RequestContext, get_request_context


async def _log_and_update_deviation(
    db: AsyncSession,
    session: Session,
    risk: RiskResult,
    ctx: RequestContext,
) -> None:
    """Logs deviation to audit trail and updates throttle timestamp"""
    log_audit_event(
        AuditEvent.SESSION_DEVIATION,
        user_id=session.user_id,
        session_id=session.id,
        ip_address=ctx.ip_address,
        user_agent=ctx.user_agent,
        metadata={
            "risk_score": risk.score,
            "factors": risk.factors,
        },
    )
    
    session.deviation_logged_at = datetime.now(timezone.utc)
    await db.commit()


async def get_current_session(
    request: Request,
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(lambda: None),
) -> Session:
    """Validates session and performs risk assessment; rejects high-risk requests"""
    session_id_str = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id_str:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        session_uuid = UUID(session_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid session format")
    
    session = await get_session_by_id(db, session_uuid)
    
    if session is None:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    
    # Risk-based session validation (replaces hard fingerprint blocking)
    risk = assess_session_risk(session, ctx)
    
    if risk.should_reauthenticate:
        log_audit_event(
            AuditEvent.SESSION_KILLED,
            user_id=session.user_id,
            session_id=session.id,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
            metadata={
                "risk_score": risk.score,
                "factors": risk.factors,
            },
        )
        await invalidate_session(db, session.id)
        raise HTTPException(status_code=401, detail="Session requires reauthentication")
    
    if risk.should_log:
        await _log_and_update_deviation(db, session, risk, ctx)
    
    return session


async def get_current_user(
    session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(lambda: None),
) -> User:
    user = await db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def require_auth(
    request: Request,
    session: Session = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(lambda: None),
) -> tuple[User, Session]:
    """Stores new expires_at in request state for response middleware"""
    new_expires = await refresh_session(db, session)
    if new_expires:
        request.state.session_expires_at = new_expires
        request.state.session_id = str(session.id)
    
    return user, session


def require_fingerprint(
    ctx: RequestContext = Depends(get_request_context),
) -> str:
    """Returns 400 if X_Device_Fingerprint header missing"""
    if not ctx.fingerprint_hash:
        raise HTTPException(
            status_code=400,
            detail="Please enable JavaScript to sign in."
        )
    return ctx.fingerprint_hash


async def session_cookie_sync_middleware(request: Request, call_next) -> Response:
    """Injects updated session cookie if refresh_session updated expires_at"""
    response = await call_next(request)
    
    if response.status_code < 400:
        if hasattr(request.state, "session_expires_at") and hasattr(request.state, "session_id"):
            create_session_cookie(
                response,
                request.state.session_id,
                request.state.session_expires_at
            )
    
    return response

