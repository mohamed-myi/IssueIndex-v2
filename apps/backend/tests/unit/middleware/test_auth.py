

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(autouse=True)
def mock_settings(settings_env_override):
    with settings_env_override(
        {
            "FINGERPRINT_SECRET": "test-fingerprint-secret-key-for-testing",
            "JWT_SECRET_KEY": "test-jwt-secret-key",
            "SESSION_REMEMBER_ME_DAYS": "7",
            "SESSION_DEFAULT_HOURS": "24",
        },
    ):
        yield


@pytest.fixture
def mock_request():
    request = MagicMock()
    request.headers = {}
    request.cookies = {}
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.state = MagicMock()
    return request


@pytest.fixture
def valid_ctx():
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
    db = MagicMock(spec=AsyncSession)
    db.get = AsyncMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def mock_session():
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

    @pytest.mark.parametrize(
        "fingerprint_hash,expected_status",
        [
            (None, 400),
            ("", 400),
            ("a" * 64, "PASS"),
        ],
    )
    def test_fingerprint_requirements(self, fingerprint_hash, expected_status):
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

    async def test_returns_401_if_cookie_missing(self, mock_request, valid_ctx, mock_db):
        from fastapi import HTTPException

        from gim_backend.middleware.auth import get_current_session

        mock_request.cookies = {}

        with pytest.raises(HTTPException) as exc:
            await get_current_session(mock_request, valid_ctx, mock_db)

        assert exc.value.status_code == 401

    async def test_returns_401_if_session_not_found(self, mock_request, valid_ctx, mock_db):
        from fastapi import HTTPException

        from gim_backend.core.cookies import SESSION_COOKIE_NAME
        from gim_backend.middleware.auth import get_current_session

        mock_request.cookies = {SESSION_COOKIE_NAME: str(uuid4())}

        with patch("gim_backend.middleware.auth.get_session_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None

            with pytest.raises(HTTPException) as exc:
                await get_current_session(mock_request, valid_ctx, mock_db)

            assert exc.value.status_code == 401


class TestRequireAuthenticatedUserSession:
    async def test_returns_user_and_session(self, mock_request, valid_ctx, mock_db, mock_session):
        from gim_backend.middleware.auth import require_authenticated_user_session

        mock_user = MagicMock()

        with (
            patch("gim_backend.middleware.auth.get_current_session", new_callable=AsyncMock) as mock_get_session,
            patch("gim_backend.middleware.auth.get_current_user", new_callable=AsyncMock) as mock_get_user,
        ):
            mock_get_session.return_value = mock_session
            mock_get_user.return_value = mock_user

            user, session = await require_authenticated_user_session(mock_request, mock_db, valid_ctx)

        assert user == mock_user
        assert session == mock_session

    async def test_normalizes_auth_failure_message(self, mock_request, valid_ctx, mock_db):
        from fastapi import HTTPException

        from gim_backend.middleware.auth import require_authenticated_user_session

        with patch("gim_backend.middleware.auth.get_current_session", new_callable=AsyncMock) as mock_get_session:
            mock_get_session.side_effect = HTTPException(
                status_code=401,
                detail="Session expired or invalid",
            )

            with pytest.raises(HTTPException) as exc:
                await require_authenticated_user_session(mock_request, mock_db, valid_ctx)

        assert exc.value.status_code == 401
        assert exc.value.detail == "Not authenticated"


class TestRiskBasedValidation:

    async def test_low_risk_allows_request(self, mock_request, valid_ctx, mock_db, mock_session):
        from gim_backend.core.cookies import SESSION_COOKIE_NAME
        from gim_backend.middleware.auth import get_current_session

        mock_request.cookies = {SESSION_COOKIE_NAME: str(mock_session.id)}

        with patch("gim_backend.middleware.auth.get_session_by_id", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_session

            result = await get_current_session(mock_request, valid_ctx, mock_db)
            assert result == mock_session

    async def test_country_change_kills_session(self, mock_request, mock_db, mock_session):
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
            country_code="RU",
        )

        mock_request.cookies = {SESSION_COOKIE_NAME: str(mock_session.id)}

        with (
            patch("gim_backend.middleware.auth.get_session_by_id", new_callable=AsyncMock) as mock_get,
            patch("gim_backend.middleware.auth.invalidate_session", new_callable=AsyncMock) as mock_invalidate,
            patch("gim_backend.middleware.auth.log_audit_event"),
        ):
            mock_get.return_value = mock_session

            with pytest.raises(HTTPException) as exc:
                await get_current_session(mock_request, ctx, mock_db)

            assert exc.value.status_code == 401
            assert "reauthentication" in exc.value.detail.lower()
            mock_invalidate.assert_called_once()

    async def test_medium_risk_logs_deviation(self, mock_request, mock_db, mock_session):
        from gim_backend.core.cookies import SESSION_COOKIE_NAME
        from gim_backend.middleware.auth import get_current_session
        from gim_backend.middleware.context import RequestContext

        ctx = RequestContext(
            fingerprint_raw="test",
            fingerprint_hash="a" * 64,
            ip_address="127.0.0.1",
            user_agent="Test",
            login_flow_id=None,
            os_family="Windows",
            ua_family="Firefox",
            asn="AS15169",
            country_code="US",
        )

        mock_request.cookies = {SESSION_COOKIE_NAME: str(mock_session.id)}

        with (
            patch("gim_backend.middleware.auth.get_session_by_id", new_callable=AsyncMock) as mock_get,
            patch("gim_backend.middleware.auth._log_and_update_deviation", new_callable=AsyncMock) as mock_log,
        ):
            mock_get.return_value = mock_session

            result = await get_current_session(mock_request, ctx, mock_db)

            assert result == mock_session
            mock_log.assert_called_once()


class TestMaliciousInput:

    @pytest.mark.parametrize(
        "malicious_cookie",
        [
            "not-a-uuid",
            "../../etc/passwd",
            "' OR '1'='1",
            "a" * 10000,
            "\x00\x00\x00\x00",
            "<script>alert(1)</script>",
            "12345678-1234-1234-1234-1234567890ab; DROP TABLE sessions;--",
        ],
    )
    async def test_malformed_input_returns_401(self, mock_request, valid_ctx, mock_db, malicious_cookie):
        from fastapi import HTTPException

        from gim_backend.core.cookies import SESSION_COOKIE_NAME
        from gim_backend.middleware.auth import get_current_session

        mock_request.cookies = {SESSION_COOKIE_NAME: malicious_cookie}

        with pytest.raises(HTTPException) as exc:
            await get_current_session(mock_request, valid_ctx, mock_db)

        assert exc.value.status_code == 401


class TestCookieSyncMiddleware:

    async def test_injects_cookie_on_success_response(self):
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

    @pytest.mark.parametrize(
        "func_name",
        [
            "get_current_session",
            "get_current_user",
            "require_auth",
        ],
    )
    def test_db_parameter_uses_get_db(self, func_name):
        import inspect

        from gim_backend.api.dependencies import get_db
        from gim_backend.middleware import auth

        func = getattr(auth, func_name)
        sig = inspect.signature(func)
        db_param = sig.parameters.get("db")

        assert db_param is not None, f"{func_name} is missing a db parameter"

        depends_obj = db_param.default
        assert hasattr(depends_obj, "dependency"), f"{func_name}.db default is not a Depends(); got {type(depends_obj)}"
        assert depends_obj.dependency is get_db, f"{func_name}.db must use Depends(get_db), not a placeholder lambda"
