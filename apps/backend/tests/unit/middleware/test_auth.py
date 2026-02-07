"""
Auth Middleware Tests - Risk-Based Session Validation

This module tests the core authentication and session management logic:
- Session validation with risk assessment
- Cookie synchronization for rolling window sessions
- Fingerprint requirement for login flows
"""
import os
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock environment variables for all tests."""
    with patch.dict(os.environ, {
        "FINGERPRINT_SECRET": "test-fingerprint-secret-key-for-testing",
        "JWT_SECRET_KEY": "test-jwt-secret-key",
        "SESSION_REMEMBER_ME_DAYS": "7",
        "SESSION_DEFAULT_HOURS": "24",
    }):
        from gim_backend.core.config import get_settings
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()


@pytest.fixture
def mock_request():
    """Creates a mock FastAPI Request."""
    request = MagicMock()
    request.headers = {}
    request.cookies = {}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.state = MagicMock()
    return request


@pytest.fixture
def valid_ctx():
    """Creates a valid RequestContext with fingerprint and metadata."""
    from gim_backend.middleware.context import RequestContext
    return RequestContext(
        fingerprint_raw="test-fingerprint",
        fingerprint_hash="a" * 64,
        ip_address="127.0.0.1",
        user_agent="Test Browser",
        login_flow_id=None,
        os_family="Mac OS X",
        ua_family="Chrome",
        asn="AS15169",
        country_code="US",
    )




@pytest.fixture
def mock_db():
    """Creates a mock AsyncSession."""
    db = MagicMock(spec=AsyncSession)
    db.get = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def mock_session():
    """Creates a mock session with soft binding metadata."""
    session = MagicMock()
    session.id = uuid4()
    session.user_id = uuid4()
    session.fingerprint = "a" * 64
    session.os_family = "Mac OS X"
    session.ua_family = "Chrome"
    session.asn = "AS15169"
    session.country_code = "US"
    session.deviation_logged_at = None
    return session


class TestFingerprintGating:
    """
    Tests for require_fingerprint dependency.

    Security: Enforces JavaScript requirement to prevent headless/bot attacks.
    """

    @pytest.mark.parametrize("fingerprint_hash,expected_status", [
        (None, 400),
        ("", 400),
        ("a" * 64, "PASS"),
    ])
    def test_fingerprint_requirements(self, fingerprint_hash, expected_status):
        """Validates fingerprint gating with various inputs."""
        from fastapi import HTTPException

        from gim_backend.middleware.auth import require_fingerprint
        from gim_backend.middleware.context import RequestContext

        ctx = RequestContext(
            fingerprint_raw="raw-value" if fingerprint_hash else None,
            fingerprint_hash=fingerprint_hash if fingerprint_hash else None,
            ip_address="127.0.0.1",
            user_agent="Test",
            login_flow_id=None,
            os_family=None,
            ua_family=None,
            asn=None,
            country_code=None,
        )

        if expected_status == "PASS":
            result = require_fingerprint(ctx)
            assert result == fingerprint_hash
        else:
            with pytest.raises(HTTPException) as exc:
                require_fingerprint(ctx)
            assert exc.value.status_code == expected_status


class TestSessionValidation:
    """Core session validation tests."""

    async def test_returns_401_if_cookie_missing(self, mock_request, valid_ctx, mock_db):
        """No session cookie = not authenticated."""
        from fastapi import HTTPException

        from gim_backend.middleware.auth import get_current_session

        mock_request.cookies = {}

        with pytest.raises(HTTPException) as exc:
            await get_current_session(mock_request, valid_ctx, mock_db)

        assert exc.value.status_code == 401

    async def test_returns_401_if_session_not_found(self, mock_request, valid_ctx, mock_db):
        """Session ID not in database = invalid session."""
        from fastapi import HTTPException

        from gim_backend.core.cookies import SESSION_COOKIE_NAME
        from gim_backend.middleware.auth import get_current_session

        mock_request.cookies = {SESSION_COOKIE_NAME: str(uuid4())}

        with patch("gim_backend.middleware.auth.get_session_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc:
                await get_current_session(mock_request, valid_ctx, mock_db)

            assert exc.value.status_code == 401


class TestRiskBasedValidation:
    """
    Risk-based session validation tests.

    Replaces hard fingerprint blocking with soft metadata binding.
    """

    async def test_low_risk_allows_request(self, mock_request, valid_ctx, mock_db, mock_session):
        """Matching metadata = low risk score; request allowed."""
        from gim_backend.core.cookies import SESSION_COOKIE_NAME
        from gim_backend.middleware.auth import get_current_session

        mock_request.cookies = {SESSION_COOKIE_NAME: str(mock_session.id)}

        with patch("gim_backend.middleware.auth.get_session_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_session

            result = await get_current_session(mock_request, valid_ctx, mock_db)
            assert result == mock_session

    async def test_country_change_kills_session(self, mock_request, mock_db, mock_session):
        """Country mismatch = 0.8 risk score = session killed."""
        from fastapi import HTTPException

        from gim_backend.core.cookies import SESSION_COOKIE_NAME
        from gim_backend.middleware.auth import get_current_session
        from gim_backend.middleware.context import RequestContext

        ctx = RequestContext(
            fingerprint_raw="test",
            fingerprint_hash="a" * 64,
            ip_address="1.2.3.4",
            user_agent="Test",
            login_flow_id=None,
            os_family="Mac OS X",
            ua_family="Chrome",
            asn="AS15169",
            country_code="RU",  # Different country
        )

        mock_request.cookies = {SESSION_COOKIE_NAME: str(mock_session.id)}

        with patch("gim_backend.middleware.auth.get_session_by_id", new_callable=AsyncMock) as mock_get, \
             patch("gim_backend.middleware.auth.invalidate_session", new_callable=AsyncMock) as mock_invalidate, \
             patch("gim_backend.middleware.auth.log_audit_event"):
            mock_get.return_value = mock_session

            with pytest.raises(HTTPException) as exc:
                await get_current_session(mock_request, ctx, mock_db)

            assert exc.value.status_code == 401
            assert "reauthentication" in exc.value.detail.lower()
            mock_invalidate.assert_called_once()

    async def test_medium_risk_logs_deviation(self, mock_request, mock_db, mock_session):
        """OS mismatch + UA mismatch = 0.5 risk; allows but logs."""
        from gim_backend.core.cookies import SESSION_COOKIE_NAME
        from gim_backend.middleware.auth import get_current_session
        from gim_backend.middleware.context import RequestContext

        ctx = RequestContext(
            fingerprint_raw="test",
            fingerprint_hash="a" * 64,
            ip_address="127.0.0.1",
            user_agent="Test",
            login_flow_id=None,
            os_family="Windows",  # Different OS (+0.3)
            ua_family="Firefox",  # Different UA (+0.2)
            asn="AS15169",
            country_code="US",
        )

        mock_request.cookies = {SESSION_COOKIE_NAME: str(mock_session.id)}

        with patch("gim_backend.middleware.auth.get_session_by_id", new_callable=AsyncMock) as mock_get, \
             patch("gim_backend.middleware.auth._log_and_update_deviation", new_callable=AsyncMock) as mock_log:
            mock_get.return_value = mock_session

            result = await get_current_session(mock_request, ctx, mock_db)

            assert result == mock_session
            mock_log.assert_called_once()


class TestMaliciousInput:
    """Malformed/malicious cookie input handling."""

    @pytest.mark.parametrize("malicious_cookie", [
        "not-a-uuid",
        "../../etc/passwd",
        "' OR '1'='1",
        "a" * 10000,
        "\x00\x00\x00\x00",
        "<script>alert(1)</script>",
        "12345678-1234-1234-1234-1234567890ab; DROP TABLE sessions;--",
    ])
    async def test_malformed_input_returns_401(self, mock_request, valid_ctx, mock_db, malicious_cookie):
        """All malicious cookie values should safely return 401 before DB query."""
        from fastapi import HTTPException

        from gim_backend.core.cookies import SESSION_COOKIE_NAME
        from gim_backend.middleware.auth import get_current_session

        mock_request.cookies = {SESSION_COOKIE_NAME: malicious_cookie}

        with pytest.raises(HTTPException) as exc:
            await get_current_session(mock_request, valid_ctx, mock_db)

        assert exc.value.status_code == 401


class TestCookieSyncMiddleware:
    """Cookie synchronization middleware tests."""

    async def test_injects_cookie_on_success_response(self):
        """Cookie injected when session refreshed and response is success."""
        from gim_backend.middleware.auth import session_cookie_sync_middleware

        mock_request = MagicMock()
        mock_request.state = MagicMock()
        mock_request.state.session_expires_at = datetime.now(UTC) + timedelta(days=7)
        mock_request.state.session_id = str(uuid4())

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("gim_backend.middleware.auth.create_session_cookie") as mock_cookie:
            await session_cookie_sync_middleware(mock_request, mock_call_next)

            mock_cookie.assert_called_once()

    @pytest.mark.parametrize("status_code", [302, 307])
    async def test_injects_cookie_on_redirect_responses(self, status_code):
        """Cookie must be injected on redirect responses for OAuth flow."""
        from gim_backend.middleware.auth import session_cookie_sync_middleware

        mock_request = MagicMock()
        mock_request.state = MagicMock()
        mock_request.state.session_expires_at = datetime.now(UTC) + timedelta(days=7)
        mock_request.state.session_id = str(uuid4())

        mock_response = MagicMock()
        mock_response.status_code = status_code
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("gim_backend.middleware.auth.create_session_cookie") as mock_cookie:
            await session_cookie_sync_middleware(mock_request, mock_call_next)

            mock_cookie.assert_called_once()

    async def test_does_not_inject_cookie_on_error_response(self):
        """No cookie injection on error (prevents session fixation on failure)."""
        from gim_backend.middleware.auth import session_cookie_sync_middleware

        mock_request = MagicMock()
        mock_request.state = MagicMock()
        mock_request.state.session_expires_at = datetime.now(UTC) + timedelta(days=7)
        mock_request.state.session_id = str(uuid4())

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("gim_backend.middleware.auth.create_session_cookie") as mock_cookie:
            await session_cookie_sync_middleware(mock_request, mock_call_next)

            mock_cookie.assert_not_called()


class TestDependencyWiring:
    """
    Regression tests for FastAPI dependency injection wiring.

    Validates that auth functions use Depends(get_db) rather than placeholder
    lambdas. This class of bug is invisible to unit tests that call functions
    directly and to integration tests that override require_auth entirely.
    """

    @pytest.mark.parametrize("func_name", [
        "get_current_session",
        "get_current_user",
        "require_auth",
    ])
    def test_db_parameter_uses_get_db(self, func_name):
        """Each auth function must use Depends(get_db) for its db parameter."""
        import inspect

        from gim_backend.api.dependencies import get_db
        from gim_backend.middleware import auth

        func = getattr(auth, func_name)
        sig = inspect.signature(func)
        db_param = sig.parameters.get("db")

        assert db_param is not None, f"{func_name} is missing a db parameter"

        depends_obj = db_param.default
        assert hasattr(depends_obj, "dependency"), (
            f"{func_name}.db default is not a Depends(); got {type(depends_obj)}"
        )
        assert depends_obj.dependency is get_db, (
            f"{func_name}.db must use Depends(get_db), not a placeholder lambda"
        )

