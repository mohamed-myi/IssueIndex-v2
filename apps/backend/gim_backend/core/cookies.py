from datetime import datetime

from fastapi import Response

from .config import get_settings

SESSION_COOKIE_NAME = "session_id"


def create_session_cookie(
    response: Response,
    session_id: str,
    expires_at: datetime | None = None,
) -> None:
    """Creates session cookie. If expires_at is None, expires on browser close."""
    settings = get_settings()
    is_production = settings.environment == "production"

    # Production uses cross-origin requests, requiring SameSite=None and Secure=True.
    # Local dev uses localhost, so Lax is sufficient.
    samesite_policy = "none" if is_production else "lax"

    cookie_params = {
        "key": SESSION_COOKIE_NAME,
        "value": session_id,
        "httponly": True,
        "samesite": samesite_policy,
        "secure": is_production,
        "path": "/",
    }

    if expires_at is not None:
        cookie_params["expires"] = int(expires_at.timestamp())

    response.set_cookie(**cookie_params)


def clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    is_production = settings.environment == "production"
    samesite_policy = "none" if is_production else "lax"

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        samesite=samesite_policy,
        secure=is_production,
        path="/",
    )


LOGIN_FLOW_COOKIE_NAME = "login_flow_id"
LOGIN_FLOW_COOKIE_MAX_AGE = 300


def create_login_flow_cookie(response, flow_id: str) -> None:
    settings = get_settings()
    is_production = settings.environment == "production"
    # Production uses cross-origin requests, requiring SameSite=None + Secure.
    samesite_policy = "none" if is_production else "lax"

    response.set_cookie(
        key=LOGIN_FLOW_COOKIE_NAME,
        value=flow_id,
        httponly=True,
        samesite=samesite_policy,
        secure=is_production,
        path="/",
        max_age=LOGIN_FLOW_COOKIE_MAX_AGE,
    )


def clear_login_flow_cookie(response) -> None:
    settings = get_settings()
    is_production = settings.environment == "production"
    samesite_policy = "none" if is_production else "lax"

    response.delete_cookie(
        key=LOGIN_FLOW_COOKIE_NAME,
        httponly=True,
        samesite=samesite_policy,
        secure=is_production,
        path="/",
    )
