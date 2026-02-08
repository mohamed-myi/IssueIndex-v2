from datetime import datetime

from fastapi import Response

from .config import get_settings

SESSION_COOKIE_NAME = "session_id"


def _cookie_domain_or_none() -> str | None:
    """Returns the cookie domain if configured, None otherwise.
    Empty string in config means host-only cookie (local dev).
    """
    domain = get_settings().cookie_domain
    return domain if domain else None


def create_session_cookie(
    response: Response,
    session_id: str,
    expires_at: datetime | None = None,
) -> None:
    """Creates session cookie. If expires_at is None, expires on browser close."""
    settings = get_settings()
    is_production = settings.environment == "production"

    # SameSite=Lax is sufficient for same-site subdomain cookie sharing
    # Local dev also uses Lax (localhost).
    cookie_params: dict = {
        "key": SESSION_COOKIE_NAME,
        "value": session_id,
        "httponly": True,
        "samesite": "lax",
        "secure": is_production,
        "path": "/",
    }

    domain = _cookie_domain_or_none()
    if domain:
        cookie_params["domain"] = domain

    if expires_at is not None:
        cookie_params["expires"] = int(expires_at.timestamp())

    response.set_cookie(**cookie_params)


def clear_session_cookie(response: Response) -> None:
    """Clears session cookie. Must use identical attributes or browser won't delete it."""
    settings = get_settings()
    is_production = settings.environment == "production"

    kwargs: dict = {
        "key": SESSION_COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": is_production,
        "path": "/",
    }

    domain = _cookie_domain_or_none()
    if domain:
        kwargs["domain"] = domain

    response.delete_cookie(**kwargs)


LOGIN_FLOW_COOKIE_NAME = "login_flow_id"
LOGIN_FLOW_COOKIE_MAX_AGE = 300


def create_login_flow_cookie(response, flow_id: str) -> None:
    settings = get_settings()
    is_production = settings.environment == "production"

    kwargs: dict = {
        "key": LOGIN_FLOW_COOKIE_NAME,
        "value": flow_id,
        "httponly": True,
        "samesite": "lax",
        "secure": is_production,
        "path": "/",
        "max_age": LOGIN_FLOW_COOKIE_MAX_AGE,
    }

    domain = _cookie_domain_or_none()
    if domain:
        kwargs["domain"] = domain

    response.set_cookie(**kwargs)


def clear_login_flow_cookie(response) -> None:
    settings = get_settings()
    is_production = settings.environment == "production"

    kwargs: dict = {
        "key": LOGIN_FLOW_COOKIE_NAME,
        "httponly": True,
        "samesite": "lax",
        "secure": is_production,
        "path": "/",
    }

    domain = _cookie_domain_or_none()
    if domain:
        kwargs["domain"] = domain

    response.delete_cookie(**kwargs)
