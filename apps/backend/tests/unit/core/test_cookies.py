

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from fastapi import Response

from gim_backend.core.cookies import (
    LOGIN_FLOW_COOKIE_NAME,
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    create_login_flow_cookie,
    create_session_cookie,
)


def parse_set_cookie(response: Response, cookie_name: str) -> dict:

    raw = ""
    for key, value in response.raw_headers:
        if key.decode().lower() == "set-cookie" and value.decode().startswith(f"{cookie_name}="):
            raw = value.decode()
            break

    if not raw:
        return {}

    parts = raw.split("; ")
    value = parts[0].split("=", 1)[1].strip('"')

    result = {
        "value": value,
        "httponly": False,
        "secure": False,
        "samesite": "",
        "path": "",
        "max-age": "",
        "expires": "",
        "domain": "",
    }

    for part in parts[1:]:
        lower = part.lower()
        if lower == "httponly":
            result["httponly"] = True
        elif lower == "secure":
            result["secure"] = True
        elif lower.startswith("samesite="):
            result["samesite"] = part.split("=", 1)[1]
        elif lower.startswith("path="):
            result["path"] = part.split("=", 1)[1]
        elif lower.startswith("max-age="):
            result["max-age"] = part.split("=", 1)[1]
        elif lower.startswith("expires="):
            result["expires"] = part.split("=", 1)[1]
        elif lower.startswith("domain="):
            result["domain"] = part.split("=", 1)[1]

    return result


class TestSessionCookieSecurityAttributes:

    def test_httponly_always_set(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_session_cookie(response, "test-session-id")

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)


            assert attrs["httponly"] is True, "HttpOnly MUST be True to prevent XSS"
            get_settings.cache_clear()

    def test_samesite_lax_in_development(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_session_cookie(response, "test-session-id")

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)

            assert attrs["samesite"].lower() == "lax", f"SameSite must be 'lax', got '{attrs['samesite']}'"
            get_settings.cache_clear()

    def test_samesite_lax_in_production(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "COOKIE_DOMAIN": ".issueindex.dev"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_session_cookie(response, "test-session-id")

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)

            assert attrs["samesite"].lower() == "lax", (
                f"SameSite must be 'lax' in production, got '{attrs['samesite']}'"
            )
            get_settings.cache_clear()

    def test_secure_true_in_production(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_session_cookie(response, "test-session-id")

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)

            assert attrs["secure"] is True, "Secure MUST be True in production to prevent HTTP leakage"
            get_settings.cache_clear()

    def test_secure_false_in_development(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_session_cookie(response, "test-session-id")

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)


            assert attrs["secure"] in (False, ""), "Secure should be False in development for localhost testing"
            get_settings.cache_clear()

    def test_path_is_root(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_session_cookie(response, "test-session-id")

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)

            assert attrs["path"] == "/", "Path must be '/' for site-wide access"
            get_settings.cache_clear()


class TestSessionCookieDomain:

    def test_domain_set_when_configured(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "COOKIE_DOMAIN": ".issueindex.dev"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_session_cookie(response, "test-session-id")

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)

            assert attrs["domain"] == ".issueindex.dev", f"Domain must be '.issueindex.dev', got '{attrs['domain']}'"
            get_settings.cache_clear()

    def test_no_domain_when_empty(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "COOKIE_DOMAIN": ""}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_session_cookie(response, "test-session-id")

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)

            assert attrs["domain"] == "", f"Domain should be empty for dev, got '{attrs['domain']}'"
            get_settings.cache_clear()

    def test_clear_cookie_includes_domain(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "COOKIE_DOMAIN": ".issueindex.dev"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            clear_session_cookie(response)

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)

            assert attrs["domain"] == ".issueindex.dev", (
                "clear_session_cookie must include domain to match creation attributes"
            )
            get_settings.cache_clear()


class TestSessionCookieExpiration:

    def test_expires_set_when_provided(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            expires_at = datetime.now(UTC) + timedelta(days=7)
            create_session_cookie(response, "test-session-id", expires_at=expires_at)

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)


            assert attrs["expires"], "expires should be set when expires_at provided"
            get_settings.cache_clear()

    def test_session_cookie_when_no_expires(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_session_cookie(response, "test-session-id", expires_at=None)

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)


            assert not attrs["expires"], "Session cookie should not have expires"
            assert not attrs["max-age"], "Session cookie should not have max-age"
            get_settings.cache_clear()


class TestClearSessionCookie:

    def test_clear_uses_same_security_attributes(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            clear_session_cookie(response)

            attrs = parse_set_cookie(response, SESSION_COOKIE_NAME)


            assert attrs["httponly"] is True
            assert attrs["samesite"].lower() == "lax"
            assert attrs["secure"] is True
            assert attrs["path"] == "/"
            get_settings.cache_clear()


class TestLoginFlowCookie:

    def test_max_age_is_300_seconds(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_login_flow_cookie(response, "flow-123")

            attrs = parse_set_cookie(response, LOGIN_FLOW_COOKIE_NAME)


            assert attrs["max-age"] == "300", f"max-age must be exactly 300, got {attrs['max-age']}"
            get_settings.cache_clear()

    def test_httponly_protects_flow_id(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_login_flow_cookie(response, "flow-123")

            attrs = parse_set_cookie(response, LOGIN_FLOW_COOKIE_NAME)

            assert attrs["httponly"] is True
            get_settings.cache_clear()

    def test_login_flow_cookie_includes_domain(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "COOKIE_DOMAIN": ".issueindex.dev"}):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            response = Response()
            create_login_flow_cookie(response, "flow-123")

            attrs = parse_set_cookie(response, LOGIN_FLOW_COOKIE_NAME)

            assert attrs["domain"] == ".issueindex.dev"
            get_settings.cache_clear()


