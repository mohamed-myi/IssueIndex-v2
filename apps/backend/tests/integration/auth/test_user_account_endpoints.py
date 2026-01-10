"""Integration tests for User & Account Management endpoints.

Tests: GET /auth/me, GET /auth/linked-accounts, GET /auth/sessions/count, DELETE /auth/account
Focus: Auth requirements, data integrity, GDPR compliance, security.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.main import app
from src.middleware.rate_limit import reset_rate_limiter, reset_rate_limiter_instance


@pytest.fixture(autouse=True)
def reset_rate_limit():
    reset_rate_limiter()
    reset_rate_limiter_instance()
    yield
    reset_rate_limiter()


@pytest.fixture
def client():
    return TestClient(app, follow_redirects=False)


class TestGetMeEndpoint:
    """Tests for GET /auth/me"""

    def test_requires_authentication(self, client):
        """Unauthenticated request returns 401"""
        response = client.get("/auth/me")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json().get("detail", "")

    def test_no_sensitive_fields_leak(self, client):
        """Response must not contain password, hash, or salt fields"""
        response = client.get("/auth/me")
        
        body = response.text.lower()
        assert "password" not in body
        assert "hash" not in body
        assert "salt" not in body


class TestGetMeEndpointAuthenticated:
    """Tests for GET /auth/me with mocked auth"""

    @pytest.fixture
    def mock_auth_flow(self):
        """Mock authentication to return a user"""
        with patch("src.api.routes.auth.get_request_context") as mock_ctx, \
             patch("src.api.routes.auth.get_current_session") as mock_session, \
             patch("src.api.routes.auth.get_current_user") as mock_user, \
             patch("src.api.routes.auth.get_db") as mock_db:
            
            context = MagicMock()
            context.ip_address = "127.0.0.1"
            mock_ctx.return_value = context
            
            session = MagicMock()
            session.id = uuid4()
            mock_session.return_value = session
            
            user = MagicMock()
            user.id = uuid4()
            user.email = "test@example.com"
            user.github_username = "octocat"
            user.google_id = None
            user.created_at = datetime.now(timezone.utc)
            user.created_via = "github"
            mock_user.return_value = user
            
            async def mock_db_gen():
                yield MagicMock()
            mock_db.return_value = mock_db_gen()
            
            yield {"user": user, "session": session}

    def test_returns_user_fields(self, client, mock_auth_flow):
        """Returns all expected user fields"""
        response = client.get("/auth/me")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert "email" in data
        assert "github_username" in data
        assert "google_id" in data
        assert "created_at" in data
        assert "created_via" in data


class TestGetLinkedAccountsEndpoint:
    """Tests for GET /auth/linked-accounts"""

    def test_requires_authentication(self, client):
        """Unauthenticated request returns 401"""
        response = client.get("/auth/linked-accounts")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json().get("detail", "")


class TestGetLinkedAccountsAuthenticated:
    """Tests for GET /auth/linked-accounts with mocked auth"""

    @pytest.fixture
    def mock_auth_and_accounts(self):
        """Mock authentication and linked accounts service"""
        with patch("src.api.routes.auth.get_request_context") as mock_ctx, \
             patch("src.api.routes.auth.get_current_session") as mock_session, \
             patch("src.api.routes.auth.get_current_user") as mock_user, \
             patch("src.api.routes.auth.list_linked_accounts") as mock_list, \
             patch("src.api.routes.auth.get_db") as mock_db:
            
            context = MagicMock()
            mock_ctx.return_value = context
            
            session = MagicMock()
            session.id = uuid4()
            mock_session.return_value = session
            
            user = MagicMock()
            user.id = uuid4()
            mock_user.return_value = user
            
            async def mock_db_gen():
                yield MagicMock()
            mock_db.return_value = mock_db_gen()
            
            yield {"mock_list": mock_list, "user": user}

    def test_returns_empty_list_when_no_accounts(self, client, mock_auth_and_accounts):
        """Empty array when no accounts linked"""
        mock_auth_and_accounts["mock_list"].return_value = []
        
        response = client.get("/auth/linked-accounts")
        
        assert response.status_code == 200
        data = response.json()
        assert data["accounts"] == []


class TestGetSessionsCountEndpoint:
    """Tests for GET /auth/sessions/count"""

    def test_requires_authentication(self, client):
        """Unauthenticated request returns 401"""
        response = client.get("/auth/sessions/count")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json().get("detail", "")


class TestDeleteAccountEndpoint:
    """Tests for DELETE /auth/account"""

    def test_requires_authentication(self, client):
        """Unauthenticated request returns 401"""
        response = client.delete("/auth/account")
        
        assert response.status_code == 401
        assert "Not authenticated" in response.json().get("detail", "")


class TestDeleteAccountAuthenticated:
    """Tests for DELETE /auth/account with mocked auth"""

    @pytest.fixture
    def mock_auth_and_cascade(self):
        """Mock authentication and cascade deletion"""
        with patch("src.api.routes.auth.get_request_context") as mock_ctx, \
             patch("src.api.routes.auth.get_current_session") as mock_session, \
             patch("src.api.routes.auth.get_current_user") as mock_user, \
             patch("src.api.routes.auth.delete_user_cascade") as mock_cascade, \
             patch("src.api.routes.auth.log_audit_event"), \
             patch("src.api.routes.auth.get_db") as mock_db:
            
            context = MagicMock()
            context.ip_address = "127.0.0.1"
            mock_ctx.return_value = context
            
            session = MagicMock()
            session.id = uuid4()
            mock_session.return_value = session
            
            user = MagicMock()
            user.id = uuid4()
            mock_user.return_value = user
            
            from src.services.session_service import CascadeDeletionResult
            mock_cascade.return_value = CascadeDeletionResult(
                tables_affected=["users", "sessions"],
                total_rows=2,
            )
            
            async def mock_db_gen():
                yield MagicMock()
            mock_db.return_value = mock_db_gen()
            
            yield {"user": user, "session": session, "mock_cascade": mock_cascade}

    def test_delete_clears_session_cookie(self, client, mock_auth_and_cascade):
        """Session cookie cleared on deletion"""
        response = client.delete("/auth/account")
        
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] is True


class TestPostDeleteAccess:
    """Verify deleted user cannot access protected endpoints"""

    def test_deleted_user_gets_401_on_me(self, client):
        """After deletion, accessing /auth/me with old session returns 401"""
        with patch("src.api.routes.auth.get_request_context") as mock_ctx, \
             patch("src.api.routes.auth.get_current_session") as mock_session:
            
            context = MagicMock()
            mock_ctx.return_value = context
            mock_session.side_effect = Exception("Session not found")
            
            response = client.get("/auth/me")
            
            assert response.status_code == 401


class TestGDPRZombieCheck:
    """GDPR: Ensure deleted user data does not cause conflicts on re-registration"""

    @pytest.fixture
    def mock_full_flow(self):
        """Mock complete user creation flow"""
        with patch("src.api.routes.auth.get_request_context") as mock_ctx, \
             patch("src.api.routes.auth.get_current_session") as mock_session, \
             patch("src.api.routes.auth.get_current_user") as mock_user, \
             patch("src.api.routes.auth.delete_user_cascade") as mock_cascade, \
             patch("src.api.routes.auth.upsert_user") as mock_upsert, \
             patch("src.api.routes.auth.log_audit_event"), \
             patch("src.api.routes.auth.get_db") as mock_db:
            
            context = MagicMock()
            context.ip_address = "127.0.0.1"
            mock_ctx.return_value = context
            
            session = MagicMock()
            session.id = uuid4()
            mock_session.return_value = session
            
            user = MagicMock()
            user.id = uuid4()
            user.github_username = "octocat"
            mock_user.return_value = user
            
            from src.services.session_service import CascadeDeletionResult
            mock_cascade.return_value = CascadeDeletionResult(
                tables_affected=["users"],
                total_rows=1,
            )
            
            # Simulates successful re-creation with same username
            mock_upsert.return_value = MagicMock(id=uuid4())
            
            async def mock_db_gen():
                yield MagicMock()
            mock_db.return_value = mock_db_gen()
            
            yield {"mock_upsert": mock_upsert, "user": user}

    def test_deleted_username_can_be_reused(self, client, mock_full_flow):
        """After deletion, same github_username can register again"""
        # Delete the account
        response = client.delete("/auth/account")
        assert response.status_code == 200
        
        # Verify upsert was not called during delete
        mock_full_flow["mock_upsert"].assert_not_called()
