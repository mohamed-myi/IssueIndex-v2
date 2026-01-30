import secrets
from enum import Enum
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from gim_backend.api.dependencies import get_db, get_http_client
from gim_backend.core.audit import AuditEvent, log_audit_event
from gim_backend.core.config import get_settings
from gim_backend.core.cookies import (
    clear_session_cookie,
    create_login_flow_cookie,
    create_session_cookie,
)
from gim_backend.core.oauth import (
    GITHUB_PROFILE_SCOPES,
    EmailNotVerifiedError,
    InvalidCodeError,
    NoEmailError,
    OAuthProvider,
    OAuthStateError,
    exchange_code_for_token,
    fetch_user_profile,
    get_authorization_url,
    get_profile_authorization_url,
)
from gim_backend.middleware.auth import get_current_session, get_current_user, require_fingerprint
from gim_backend.middleware.context import RequestContext, get_request_context
from gim_backend.middleware.rate_limit import check_auth_rate_limit
from gim_backend.services.linked_account_service import (
    get_active_linked_account,
    list_linked_accounts,
    mark_revoked,
    store_linked_account,
)
from gim_backend.services.session_service import (
    ExistingAccountError,
    ProviderConflictError,
    SessionListResponse,
    UserNotFoundError,
    count_sessions,
    create_session,
    delete_user_cascade,
    get_session_by_id,
    invalidate_all_sessions,
    invalidate_session,
    link_provider,
    list_sessions,
    upsert_user,
)

router = APIRouter()



STATE_COOKIE_NAME = "oauth_state"
STATE_COOKIE_MAX_AGE = 300


class AuthIntent(str, Enum):
    LOGIN = "login"
    LINK = "link"
    CONNECT = "connect"


def _get_state_cookie_params(settings) -> dict:
    is_production = settings.environment == "production"
    return {
        "httponly": True,
        "secure": is_production,
        "samesite": "lax",
        "max_age": STATE_COOKIE_MAX_AGE,
        "path": "/",
    }


def _build_error_redirect(error_code: str, provider: str | None = None) -> str:
    settings = get_settings()
    params = {"error": error_code}
    if provider:
        params["provider"] = provider
    return f"{settings.frontend_base_url}/login?{urlencode(params)}"


@router.get("/init", status_code=204)
async def init_login_flow() -> Response:
    """Sets X-Login-Flow-ID cookie for rate limiting compound key"""
    flow_id = secrets.token_urlsafe(16)
    response = Response(status_code=204)
    create_login_flow_cookie(response, flow_id)
    return response


@router.get("/login/{provider}")
async def login(
    provider: str,
    request: Request,
    remember_me: bool = Query(default=False),
    _: None = Depends(check_auth_rate_limit),
) -> RedirectResponse:
    try:
        oauth_provider = OAuthProvider(provider)
    except ValueError:
        return RedirectResponse(
            url=_build_error_redirect("invalid_provider"),
            status_code=302,
        )

    settings = get_settings()
    # State format: "intent:token:remember_me"
    state_token = secrets.token_urlsafe(32)
    state_value = f"{AuthIntent.LOGIN.value}:{state_token}:{1 if remember_me else 0}"

    # Redirect to frontend callback page to pick up fingerprint
    redirect_uri = f"{settings.frontend_base_url}/auth/callback/{provider}"
    auth_url = get_authorization_url(oauth_provider, redirect_uri, state_value)
    response = RedirectResponse(url=auth_url, status_code=302)

    response.set_cookie(
        key=STATE_COOKIE_NAME,
        value=state_token, # Store only the secret token in cookie
        **_get_state_cookie_params(settings),
    )

    return response


@router.get("/callback/{provider}")
async def callback(
    provider: str,
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    fingerprint_hash: str = Depends(require_fingerprint),
    ctx: RequestContext = Depends(get_request_context),
    db: AsyncSession = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_http_client),
    _: None = Depends(check_auth_rate_limit),
) -> RedirectResponse:
    settings = get_settings()

    if error:
        # Default error handling - could be improved by parsing state even on error
        # to know where to redirect, but for security fail-safe to login
        return RedirectResponse(
            url=_build_error_redirect("consent_denied"),
            status_code=302,
        )

    try:
        oauth_provider = OAuthProvider(provider)
    except ValueError:
        return RedirectResponse(
            url=_build_error_redirect("invalid_provider"),
            status_code=302,
        )

    if not state or not code:
         return RedirectResponse(
            url=_build_error_redirect("missing_code"),
            status_code=302,
        )

    # Parse state: "intent:token:extra"
    try:
        state_parts = state.split(":", 2)
        intent = state_parts[0]
        state_token = state_parts[1]
        extra = state_parts[2] if len(state_parts) > 2 else None
    except Exception:
         return RedirectResponse(
            url=_build_error_redirect("csrf_failed"),
            status_code=302,
        )

    # Verify CSRF token from cookie
    stored_token = request.cookies.get(STATE_COOKIE_NAME)

    if not stored_token or stored_token != state_token:
        # Determine redirect based on intent if possible, else default to login error
        if intent == AuthIntent.LINK.value:
             return RedirectResponse(url=_build_settings_redirect("csrf_failed"), status_code=302)
        if intent == AuthIntent.CONNECT.value:
             return RedirectResponse(url=_build_profile_redirect("csrf_failed"), status_code=302)

        return RedirectResponse(
            url=_build_error_redirect("csrf_failed"),
            status_code=302,
        )

    # Unified Redirect URI - Matches frontend callback URL
    redirect_uri = f"{settings.frontend_base_url}/auth/callback/{provider}"

    # Dispatch Logic
    if intent == AuthIntent.LOGIN.value:
        remember_me = extra == "1"
        return await _handle_login_callback(
            code, redirect_uri, oauth_provider, remember_me,
            fingerprint_hash, ctx, db, client, request, settings
        )

    elif intent == AuthIntent.LINK.value:
        return await _handle_link_callback(
            code, redirect_uri, oauth_provider,
            ctx, db, client, request
        )

    elif intent == AuthIntent.CONNECT.value:
        return await _handle_connect_callback(
            code, redirect_uri, oauth_provider,
            ctx, db, client, request
        )

    return RedirectResponse(url=_build_error_redirect("invalid_request"), status_code=302)





def _build_settings_redirect(error_code: str | None = None) -> str:
    settings = get_settings()
    base = f"{settings.frontend_base_url}/settings/accounts"
    if error_code:
        return f"{base}?{urlencode({'error': error_code})}"
    return base


@router.get("/link/{provider}")
async def link(
    provider: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_auth_rate_limit),
) -> RedirectResponse:
    """Initiates OAuth flow to link additional provider to authenticated user"""
    try:
        oauth_provider = OAuthProvider(provider)
    except ValueError:
        return RedirectResponse(
            url=_build_settings_redirect("invalid_provider"),
            status_code=302,
        )

    ctx = await get_request_context(request)

    try:
        _ = await get_current_session(request, ctx, db)
    except Exception:
        return RedirectResponse(
            url=_build_error_redirect("not_authenticated"),
            status_code=302,
        )

    settings = get_settings()

    # State format: "intent:token"
    state_token = secrets.token_urlsafe(32)
    state_value = f"{AuthIntent.LINK.value}:{state_token}"

    # Callback to frontend
    redirect_uri = f"{settings.frontend_base_url}/auth/callback/{provider}"

    auth_url = get_authorization_url(oauth_provider, redirect_uri, state_value)
    response = RedirectResponse(url=auth_url, status_code=302)

    response.set_cookie(
        key=STATE_COOKIE_NAME,
        value=state_token,
        **_get_state_cookie_params(settings),
    )

    return response





@router.get("/sessions", response_model=SessionListResponse)
async def get_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> SessionListResponse:
    """Returns all active sessions for authenticated user"""
    ctx = await get_request_context(request)

    try:
        session = await get_current_session(request, ctx, db)
        user = await get_current_user(session, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    sessions = await list_sessions(db, user.id, session.id)

    return SessionListResponse(
        sessions=sessions,
        count=len(sessions),
    )


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revokes a specific session; must belong to authenticated user"""
    ctx = await get_request_context(request)

    try:
        current_session = await get_current_session(request, ctx, db)
        user = await get_current_user(current_session, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        target_session_id = UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    target_session = await get_session_by_id(db, target_session_id)

    if target_session is None or target_session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    is_current = target_session_id == current_session.id

    await invalidate_session(db, target_session_id)

    log_audit_event(
        AuditEvent.SESSION_REVOKED,
        user_id=user.id,
        session_id=target_session_id,
        ip_address=request.client.host if request.client else None,
        metadata={"was_current": is_current},
    )

    response_data = {"revoked": True, "was_current": is_current}

    if is_current:
        response = JSONResponse(content=response_data)
        clear_session_cookie(response)
        return response

    return response_data


@router.delete("/sessions")
async def revoke_all_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revokes all sessions except current"""
    ctx = await get_request_context(request)

    try:
        current_session = await get_current_session(request, ctx, db)
        user = await get_current_user(current_session, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    revoked_count = await invalidate_all_sessions(
        db, user.id, except_session_id=current_session.id
    )

    return {"revoked_count": revoked_count}


@router.post("/logout")
async def logout(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Invalidates current session; always returns success even if session expired"""
    session_id_str = request.cookies.get("session_id")
    session_uuid = None

    if session_id_str:
        try:
            session_uuid = UUID(session_id_str)
            await invalidate_session(db, session_uuid)
        except ValueError:
            pass

    log_audit_event(
        AuditEvent.LOGOUT,
        session_id=session_uuid,
        ip_address=request.client.host if request.client else None,
    )

    response = JSONResponse(content={"logged_out": True})
    clear_session_cookie(response)
    return response


@router.post("/logout/all")
async def logout_all(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Invalidates all sessions including current"""
    ctx = await get_request_context(request)

    try:
        current_session = await get_current_session(request, ctx, db)
        user = await get_current_user(current_session, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    revoked_count = await invalidate_all_sessions(db, user.id, except_session_id=None)

    log_audit_event(
        AuditEvent.LOGOUT_ALL,
        user_id=user.id,
        session_id=current_session.id,
        ip_address=request.client.host if request.client else None,
        metadata={"revoked_count": revoked_count},
    )

    response = JSONResponse(content={"revoked_count": revoked_count, "logged_out": True})
    clear_session_cookie(response)
    return response


# Stores OAuth tokens for background API access



def _build_profile_redirect(error_code: str | None = None, success: bool = False) -> str:
    """Builds redirect URL to profile onboarding page"""
    settings = get_settings()
    base = f"{settings.frontend_base_url}/profile/onboarding"
    if error_code:
        return f"{base}?{urlencode({'error': error_code})}"
    if success:
        return f"{base}?{urlencode({'connected': 'github'})}"
    return base


@router.get("/connect/github")
async def connect_github(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(check_auth_rate_limit),
) -> RedirectResponse:
    """
    Initiates GitHub OAuth flow for profile data access.
    Uses different scopes than login (includes repo access for activity data).
    Requires authenticated session.
    """
    ctx = await get_request_context(request)

    try:
        session = await get_current_session(request, ctx, db)
        _ = await get_current_user(session, db)
    except Exception:
        return RedirectResponse(
            url=_build_error_redirect("not_authenticated"),
            status_code=302,
        )

    settings = get_settings()

    # "intent:token"
    state_token = secrets.token_urlsafe(32)
    state_value = f"{AuthIntent.CONNECT.value}:{state_token}"

    # Note: connect/github is specific, but it routes through generalized callback
    # The callback will see Intent=CONNECT and Provider=GITHUB
    redirect_uri = f"{settings.frontend_base_url}/auth/callback/github"

    auth_url = get_profile_authorization_url(OAuthProvider.GITHUB, redirect_uri, state_value)

    response = RedirectResponse(url=auth_url, status_code=302)

    response.set_cookie(
        key=STATE_COOKIE_NAME,
        value=state_token,
        **_get_state_cookie_params(settings),
    )

    return response





@router.delete("/connect/github")
async def disconnect_github(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Disconnects GitHub from profile (marks linked_account as revoked).
    Does NOT delete historical profile data; marks it as stale for recommendations.
    """
    ctx = await get_request_context(request)

    try:
        session = await get_current_session(request, ctx, db)
        user = await get_current_user(session, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    was_revoked = await mark_revoked(db, user.id, "github")

    if not was_revoked:
        raise HTTPException(status_code=404, detail="No connected GitHub account found")

    log_audit_event(
        AuditEvent.ACCOUNT_LINKED,
        user_id=user.id,
        session_id=session.id,
        ip_address=ctx.ip_address,
        provider="github",
        metadata={"action": "disconnect_profile"},
    )

    return {"disconnected": True, "provider": "github"}


@router.get("/connect/status")
async def get_connect_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns status of connected accounts for profile features"""
    ctx = await get_request_context(request)

    try:
        session = await get_current_session(request, ctx, db)
        user = await get_current_user(session, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    github_account = await get_active_linked_account(db, user.id, "github")

    return {
        "github": {
            "connected": github_account is not None,
            "username": github_account.provider_user_id if github_account else None,
            "connected_at": github_account.created_at.isoformat() if github_account else None,
        }
    }


@router.get("/me")
async def get_current_user_info(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns current user info for navbar and settings pages"""
    ctx = await get_request_context(request)

    try:
        session = await get_current_session(request, ctx, db)
        user = await get_current_user(session, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "id": str(user.id),
        "email": user.email,
        "github_username": user.github_username,
        "google_id": user.google_id,
        "created_at": user.created_at.isoformat(),
        "created_via": user.created_via,
    }


@router.get("/linked-accounts")
async def get_linked_accounts_list(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lists all connected OAuth providers for settings page"""
    ctx = await get_request_context(request)

    try:
        session = await get_current_session(request, ctx, db)
        user = await get_current_user(session, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    accounts = await list_linked_accounts(db, user.id)

    return {
        "accounts": [
            {
                "provider": account.provider,
                "connected": True,
                "username": account.provider_user_id,
                "connected_at": account.created_at.isoformat(),
                "scopes": account.scopes or [],
            }
            for account in accounts
        ]
    }


@router.get("/sessions/count")
async def get_sessions_count(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Returns count of active sessions for user"""
    ctx = await get_request_context(request)

    try:
        session = await get_current_session(request, ctx, db)
        user = await get_current_user(session, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    count = await count_sessions(db, user.id)

    return {"count": count}


@router.delete("/account")
async def delete_account(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """GDPR-compliant full account deletion with cascade"""
    ctx = await get_request_context(request)

    try:
        session = await get_current_session(request, ctx, db)
        user = await get_current_user(session, db)
    except Exception:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_id = user.id

    try:
        result = await delete_user_cascade(db, user_id)
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")

    log_audit_event(
        AuditEvent.LOGOUT_ALL,
        user_id=user_id,
        session_id=session.id,
        ip_address=ctx.ip_address,
        metadata={
            "action": "account_deleted",
            "tables_affected": result.tables_affected,
            "total_rows": result.total_rows,
        },
    )

    response = JSONResponse(content={
        "deleted": True,
        "message": "Account and all data permanently deleted",
    })
    clear_session_cookie(response)
    return response


async def _handle_login_callback(
    code: str,
    redirect_uri: str,
    oauth_provider: OAuthProvider,
    remember_me: bool,
    fingerprint_hash: str,
    ctx: RequestContext,
    db: AsyncSession,
    client: httpx.AsyncClient,
    request: Request,
    settings
) -> RedirectResponse:
    try:
        token = await exchange_code_for_token(
            oauth_provider, code, redirect_uri, client
        )
        profile = await fetch_user_profile(oauth_provider, token, client)
        user = await upsert_user(db, profile, oauth_provider)

        session, expires_at = await create_session(
            db=db,
            user_id=user.id,
            fingerprint_hash=fingerprint_hash,
            remember_me=remember_me,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
            os_family=ctx.os_family,
            ua_family=ctx.ua_family,
            asn=ctx.asn,
            country_code=ctx.country_code,
        )

        log_audit_event(
            AuditEvent.LOGIN_SUCCESS,
            user_id=user.id,
            session_id=session.id,
            ip_address=ctx.ip_address,
            user_agent=ctx.user_agent,
            provider=oauth_provider.value,
        )

        response = RedirectResponse(
            url=f"{settings.frontend_base_url}/dashboard",
            status_code=302,
        )
        response.delete_cookie(key=STATE_COOKIE_NAME, path="/")
        create_session_cookie(response, str(session.id), expires_at)

        return response

    except InvalidCodeError:
        log_audit_event(AuditEvent.LOGIN_FAILED, ip_address=ctx.ip_address, provider=oauth_provider.value, metadata={"reason": "code_expired"})
        return RedirectResponse(url=_build_error_redirect("code_expired"), status_code=302)
    except EmailNotVerifiedError:
        log_audit_event(AuditEvent.LOGIN_FAILED, ip_address=ctx.ip_address, provider=oauth_provider.value, metadata={"reason": "email_not_verified"})
        return RedirectResponse(url=_build_error_redirect("email_not_verified", oauth_provider.value), status_code=302)
    except NoEmailError:
        log_audit_event(AuditEvent.LOGIN_FAILED, ip_address=ctx.ip_address, provider=oauth_provider.value, metadata={"reason": "no_email"})
        return RedirectResponse(url=_build_error_redirect("no_email", oauth_provider.value), status_code=302)
    except ExistingAccountError as e:
        log_audit_event(AuditEvent.LOGIN_FAILED, ip_address=ctx.ip_address, provider=oauth_provider.value, metadata={"reason": "existing_account", "original_provider": e.original_provider})
        return RedirectResponse(url=_build_error_redirect("existing_account", e.original_provider), status_code=302)
    except OAuthStateError:
         return RedirectResponse(url=_build_error_redirect("csrf_failed"), status_code=302)


async def _handle_link_callback(
    code: str,
    redirect_uri: str,
    oauth_provider: OAuthProvider,
    ctx: RequestContext,
    db: AsyncSession,
    client: httpx.AsyncClient,
    request: Request
) -> RedirectResponse:
    try:
        session = await get_current_session(request, ctx, db)
        user = await get_current_user(session, db)
    except Exception:
        return RedirectResponse(url=_build_error_redirect("not_authenticated"), status_code=302)

    try:
        token = await exchange_code_for_token(
            oauth_provider, code, redirect_uri, client
        )
        profile = await fetch_user_profile(oauth_provider, token, client)
        await link_provider(db, user, profile, oauth_provider)

        log_audit_event(
            AuditEvent.ACCOUNT_LINKED,
            user_id=user.id,
            session_id=session.id,
            ip_address=ctx.ip_address,
            provider=oauth_provider.value,
        )

        response = RedirectResponse(url=_build_settings_redirect(), status_code=302)
        response.delete_cookie(key=STATE_COOKIE_NAME, path="/") # Consuming unified cookie
        return response

    except InvalidCodeError:
        return RedirectResponse(url=_build_settings_redirect("code_expired"), status_code=302)
    except EmailNotVerifiedError:
        return RedirectResponse(url=_build_settings_redirect("email_not_verified"), status_code=302)
    except NoEmailError:
        return RedirectResponse(url=_build_settings_redirect("no_email"), status_code=302)
    except ProviderConflictError:
        return RedirectResponse(url=_build_settings_redirect("provider_conflict"), status_code=302)


async def _handle_connect_callback(
    code: str,
    redirect_uri: str,
    oauth_provider: OAuthProvider,
    ctx: RequestContext,
    db: AsyncSession,
    client: httpx.AsyncClient,
    request: Request
) -> RedirectResponse:
    try:
        session = await get_current_session(request, ctx, db)
        user = await get_current_user(session, db)
    except Exception:
        return RedirectResponse(url=_build_error_redirect("not_authenticated"), status_code=302)

    try:
        token = await exchange_code_for_token(
            oauth_provider, code, redirect_uri, client
        )
        profile = await fetch_user_profile(oauth_provider, token, client)

        # Parse scopes from token response
        scopes = token.scope.split(",") if token.scope else GITHUB_PROFILE_SCOPES.split(" ")

        await store_linked_account(
            db=db,
            user_id=user.id,
            provider="github",
            provider_user_id=profile.provider_id,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            scopes=scopes,
            expires_at=None,
        )

        log_audit_event(
            AuditEvent.ACCOUNT_LINKED,
            user_id=user.id,
            session_id=session.id,
            ip_address=ctx.ip_address,
            provider="github",
            metadata={"action": "connect_profile", "scopes": scopes},
        )

        response = RedirectResponse(url=_build_profile_redirect(success=True), status_code=302)
        response.delete_cookie(key=STATE_COOKIE_NAME, path="/") # Consuming unified cookie
        return response

    except InvalidCodeError:
        log_audit_event(AuditEvent.ACCOUNT_LINKED, user_id=user.id, ip_address=ctx.ip_address, provider="github", metadata={"action": "connect_failed", "reason": "code_expired"})
        return RedirectResponse(url=_build_profile_redirect("code_expired"), status_code=302)
    except EmailNotVerifiedError:
        return RedirectResponse(url=_build_profile_redirect("email_not_verified"), status_code=302)
    except NoEmailError:
        return RedirectResponse(url=_build_profile_redirect("no_email"), status_code=302)

