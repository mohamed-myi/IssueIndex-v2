"""Integration tests for the /auth/connect/* profile OAuth flow.

Tests the GitHub profile connect flow which stores OAuth tokens in linked_accounts
for background API access (different from the login flow which discards tokens).
"""
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from gim_backend.api.routes.auth import CONNECT_STATE_COOKIE_NAME
from gim_backend.core.oauth import OAuthToken, UserProfile
from gim_backend.main import app
from gim_backend.middleware.rate_limit import reset_rate_limiter, reset_rate_limiter_instance


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Reset rate limiter before each test to prevent 429 errors."""
    reset_rate_limiter()
    reset_rate_limiter_instance()
    yield
    reset_rate_limiter()


@pytest.fixture
def client():
    """Sync test client for redirect tests."""
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def mock_authenticated_session():
    """Mock an authenticated session for connect flow tests."""
    with patch("gim_backend.api.routes.auth.get_current_session") as mock_session, \
         patch("gim_backend.api.routes.auth.get_current_user") as mock_user:

        session = MagicMock()
        session.id = uuid4()
        session.user_id = uuid4()
        mock_session.return_value = session

        user = MagicMock()
        user.id = session.user_id
        user.email = "test@example.com"
        mock_user.return_value = user

        yield {"session": session, "user": user}


class TestConnectGitHubEndpoint:
    """Tests for GET /auth/connect/github"""

    def test_connect_redirects_to_github_with_profile_scopes(self, client, mock_authenticated_session):
        """Verify connect uses profile scopes (includes repo) not login scopes."""
        response = client.get("/auth/connect/github")

        assert response.status_code == 302
        location = response.headers["location"]
        assert "github.com/login/oauth/authorize" in location
        assert "repo" in location  # Profile scope includes repo access

    def test_connect_sets_state_cookie(self, client, mock_authenticated_session):
        """Verify state cookie is set for CSRF protection."""
        response = client.get("/auth/connect/github")

        assert CONNECT_STATE_COOKIE_NAME in response.cookies
        cookie = response.cookies[CONNECT_STATE_COOKIE_NAME]
        assert len(cookie) >= 32

    def test_connect_requires_authentication(self, client):
        """Verify connect redirects unauthenticated users to login."""
        with patch("gim_backend.api.routes.auth.get_current_session") as mock_session:
            mock_session.side_effect = Exception("Not authenticated")

            response = client.get("/auth/connect/github")

            assert response.status_code == 302
            location = response.headers["location"]
            assert "error=not_authenticated" in location


class TestConnectGitHubCallbackEndpoint:
    """Tests for GET /auth/connect/callback/github"""

    def test_callback_rejects_missing_state(self, client, mock_authenticated_session):
        """Verify redirect with csrf_failed when state missing."""
        response = client.get(
            "/auth/connect/callback/github",
            params={"code": "test_code"},
        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "error=csrf_failed" in location

    def test_callback_rejects_mismatched_state(self, client, mock_authenticated_session):
        """Verify redirect with csrf_failed when state mismatches cookie."""
        client.cookies.set(CONNECT_STATE_COOKIE_NAME, "stored_state_123456789012345678")

        response = client.get(
            "/auth/connect/callback/github",
            params={"code": "test_code", "state": "different_state_901234567890123"},
        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "error=csrf_failed" in location

    def test_callback_handles_consent_denied(self, client, mock_authenticated_session):
        """Verify redirect when user denies OAuth consent."""
        response = client.get(
            "/auth/connect/callback/github",
            params={"error": "access_denied"},
        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "error=consent_denied" in location

    def test_callback_requires_authentication(self, client):
        """Verify callback redirects unauthenticated users."""
        with patch("gim_backend.api.routes.auth.get_current_session") as mock_session:
            mock_session.side_effect = Exception("Not authenticated")

            response = client.get(
                "/auth/connect/callback/github",
                params={"code": "test_code", "state": "test_state"},
            )

            assert response.status_code == 302
            location = response.headers["location"]
            assert "error=not_authenticated" in location


class TestConnectCallbackSuccessFlow:
    """Tests for successful connect callback with mocked dependencies."""

    @pytest.fixture
    def mock_connect_flow(self, mock_authenticated_session):
        """Mock all OAuth and storage dependencies for success flow."""
        with patch("gim_backend.api.routes.auth.exchange_code_for_token") as mock_exchange, \
             patch("gim_backend.api.routes.auth.fetch_user_profile") as mock_profile, \
             patch("gim_backend.api.routes.auth.store_linked_account") as mock_store, \
             patch("gim_backend.api.routes.auth.get_db") as mock_db, \
             patch("gim_backend.api.routes.auth.get_http_client") as mock_client:

            mock_exchange.return_value = OAuthToken(
                access_token="gho_test_token_for_profile",
                token_type="bearer",
                scope="read:user,repo",
                refresh_token=None,
            )
            mock_profile.return_value = UserProfile(
                email="test@example.com",
                provider_id="MDQ6VXNlcjEyMzQ1Njc=",
                avatar_url="https://example.com/avatar.png",
                is_verified=True,
                username="testuser",
            )

            mock_linked_account = MagicMock()
            mock_linked_account.id = uuid4()
            mock_store.return_value = mock_linked_account

            async def mock_db_gen():
                yield MagicMock()
            async def mock_client_gen():
                yield MagicMock()

            mock_db.return_value = mock_db_gen()
            mock_client.return_value = mock_client_gen()

            yield {
                "exchange": mock_exchange,
                "profile": mock_profile,
                "store": mock_store,
                "session": mock_authenticated_session,
            }

    def test_callback_success_redirects_to_profile(self, client, mock_connect_flow):
        """Verify successful callback redirects to profile onboarding."""
        state = "validstate123456789012345678901234"
        client.cookies.set(CONNECT_STATE_COOKIE_NAME, state)

        response = client.get(
            "/auth/connect/callback/github",
            params={"code": "valid_code", "state": state},
        )

        assert response.status_code == 302
        location = response.headers["location"]
        assert "/profile/onboarding" in location
        assert "connected=github" in location

    def test_callback_success_stores_token(self, client, mock_connect_flow):
        """Verify token is stored in linked_accounts."""
        state = "validstate123456789012345678901234"
        client.cookies.set(CONNECT_STATE_COOKIE_NAME, state)

        client.get(
            "/auth/connect/callback/github",
            params={"code": "valid_code", "state": state},
        )

        mock_connect_flow["store"].assert_called_once()
        call_kwargs = mock_connect_flow["store"].call_args.kwargs

        assert call_kwargs["provider"] == "github"
        assert call_kwargs["access_token"] == "gho_test_token_for_profile"
        assert "repo" in call_kwargs["scopes"] or "read:user" in call_kwargs["scopes"]

    def test_callback_success_clears_state_cookie(self, client, mock_connect_flow):
        """State cookie must be cleared to prevent replay attacks."""
        state = "validstate123456789012345678901234"
        client.cookies.set(CONNECT_STATE_COOKIE_NAME, state)

        response = client.get(
            "/auth/connect/callback/github",
            params={"code": "valid_code", "state": state},
        )

        state_cookie = response.cookies.get(CONNECT_STATE_COOKIE_NAME)
        assert state_cookie == "" or state_cookie is None, \
            "State cookie must be cleared after callback to prevent replay"


class TestDisconnectGitHubEndpoint:
    """Tests for DELETE /auth/connect/github"""

    def test_disconnect_requires_authentication(self, client):
        """Verify disconnect returns 401 for unauthenticated users."""
        with patch("gim_backend.api.routes.auth.get_current_session") as mock_session:
            mock_session.side_effect = Exception("Not authenticated")

            response = client.delete("/auth/connect/github")

            assert response.status_code == 401

    def test_disconnect_returns_404_when_not_connected(self, client, mock_authenticated_session):
        """Verify 404 when no GitHub account is connected."""
        with patch("gim_backend.api.routes.auth.mark_revoked") as mock_revoke, \
             patch("gim_backend.api.routes.auth.get_db") as mock_db:

            mock_revoke.return_value = False  # No account found

            async def mock_db_gen():
                yield MagicMock()
            mock_db.return_value = mock_db_gen()

            response = client.delete("/auth/connect/github")

            assert response.status_code == 404

    def test_disconnect_success(self, client, mock_authenticated_session):
        """Verify successful disconnect returns confirmation."""
        with patch("gim_backend.api.routes.auth.mark_revoked") as mock_revoke, \
             patch("gim_backend.api.routes.auth.get_db") as mock_db:

            mock_revoke.return_value = True

            async def mock_db_gen():
                yield MagicMock()
            mock_db.return_value = mock_db_gen()

            response = client.delete("/auth/connect/github")

            assert response.status_code == 200
            data = response.json()
            assert data["disconnected"] is True
            assert data["provider"] == "github"


class TestConnectStatusEndpoint:
    """Tests for GET /auth/connect/status"""

    def test_status_requires_authentication(self, client):
        """Verify status returns 401 for unauthenticated users."""
        with patch("gim_backend.api.routes.auth.get_current_session") as mock_session:
            mock_session.side_effect = Exception("Not authenticated")

            response = client.get("/auth/connect/status")

            assert response.status_code == 401

    def test_status_returns_not_connected(self, client, mock_authenticated_session):
        """Verify status shows not connected when no account linked."""
        with patch("gim_backend.api.routes.auth.get_active_linked_account") as mock_get, \
             patch("gim_backend.api.routes.auth.get_db") as mock_db:

            mock_get.return_value = None

            async def mock_db_gen():
                yield MagicMock()
            mock_db.return_value = mock_db_gen()

            response = client.get("/auth/connect/status")

            assert response.status_code == 200
            data = response.json()
            assert data["github"]["connected"] is False
            assert data["github"]["username"] is None

    def test_status_returns_connected(self, client, mock_authenticated_session):
        """Verify status shows connected with account details."""
        with patch("gim_backend.api.routes.auth.get_active_linked_account") as mock_get, \
             patch("gim_backend.api.routes.auth.get_db") as mock_db:

            mock_account = MagicMock()
            mock_account.provider_user_id = "testuser"
            mock_account.created_at = datetime.now(UTC)
            mock_get.return_value = mock_account

            async def mock_db_gen():
                yield MagicMock()
            mock_db.return_value = mock_db_gen()

            response = client.get("/auth/connect/status")

            assert response.status_code == 200
            data = response.json()
            assert data["github"]["connected"] is True
            assert data["github"]["username"] == "testuser"
            assert data["github"]["connected_at"] is not None

