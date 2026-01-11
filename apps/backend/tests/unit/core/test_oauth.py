"""
OAuth Tests - Security-Critical Tests Only

This module tests the OAuth authentication layer:
- Provider URL generation
- State validation (CSRF protection)
- Token exchange resiliency (retries, error handling)
- Email verification enforcement
- GitHub-specific quirks (200 OK with error body)

Tests are condensed to avoid redundancy while maintaining full security coverage.
"""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture(autouse=True)
def mock_settings():
    with patch.dict(os.environ, {
        "GITHUB_CLIENT_ID": "test-github-client-id",
        "GITHUB_CLIENT_SECRET": "test-github-client-secret",
        "GOOGLE_CLIENT_ID": "test-google-client-id",
        "GOOGLE_CLIENT_SECRET": "test-google-client-secret",
        "FINGERPRINT_SECRET": "test-fingerprint-secret",
    }):
        from src.core.config import get_settings
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()


@pytest.fixture
def mock_client():
    """Provides a mock httpx.AsyncClient for dependency injection."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


class TestAuthorizationUrlGeneration:
    """
    URL generation tests for each OAuth provider.

    Ensures client_id and scopes are correctly injected.
    """

    def test_github_login_url_uses_login_scopes(self):
        from src.core.oauth import OAuthProvider, get_authorization_url
        state = "a" * 32
        url = get_authorization_url(
            OAuthProvider.GITHUB,
            redirect_uri="http://localhost:3000/callback",
            state=state
        )
        assert "github.com/login/oauth/authorize" in url
        assert "client_id=test-github-client-id" in url
        assert f"state={state}" in url
        assert "scope=read%3Auser+user%3Aemail" in url  # Login scopes (no repo)

    def test_google_authorization_url(self):
        from src.core.oauth import OAuthProvider, get_authorization_url
        state = "b" * 32
        url = get_authorization_url(
            OAuthProvider.GOOGLE,
            redirect_uri="http://localhost:3000/callback",
            state=state
        )
        assert "accounts.google.com/o/oauth2/v2/auth" in url
        assert "client_id=test-google-client-id" in url
        assert f"state={state}" in url
        assert "response_type=code" in url

    def test_github_profile_url_uses_profile_scopes(self):
        """Profile connect flow uses different scopes (includes repo access)."""
        from src.core.oauth import OAuthProvider, get_profile_authorization_url
        state = "c" * 32
        url = get_profile_authorization_url(
            OAuthProvider.GITHUB,
            redirect_uri="http://localhost:3000/connect/callback",
            state=state
        )
        assert "github.com/login/oauth/authorize" in url
        assert "client_id=test-github-client-id" in url
        assert f"state={state}" in url
        assert "repo" in url  # Profile scopes include repo

    def test_profile_url_rejects_unsupported_provider(self):
        """Google profile connect is not supported (login already has sufficient scopes)."""
        from src.core.oauth import OAuthProvider, get_profile_authorization_url
        state = "d" * 32

        with pytest.raises(ValueError) as exc:
            get_profile_authorization_url(
                OAuthProvider.GOOGLE,
                redirect_uri="http://localhost:3000/connect/callback",
                state=state
            )

        assert "not supported" in str(exc.value).lower()


class TestStateValidation:
    """
    State parameter validation (CSRF protection).

    Condensed to essential boundary cases only.
    """

    @pytest.mark.parametrize("state,should_pass", [
        ("a" * 32, True),                # Min length boundary (exactly 32)
        ("x" * 128, True),               # Max length boundary (exactly 128)
        ("a" * 31, False),               # Just under min (31)
        ("a" * 31 + "<script>", False),  # XSS/invalid chars
    ])
    def test_state_boundaries(self, state, should_pass):
        from src.core.oauth import OAuthStateError, validate_state

        if should_pass:
            validate_state(state)  # Should not raise
        else:
            with pytest.raises(OAuthStateError):
                validate_state(state)


class TestTokenExchangeResiliency:
    """
    Token exchange tests focusing on retry behavior and error handling.

    Critical for handling network blips and provider issues during login.
    """

    @pytest.mark.asyncio
    async def test_successful_exchange(self, mock_client):
        from src.core.oauth import OAuthProvider, exchange_code_for_token

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "gho_test_token",
            "token_type": "bearer",
            "scope": "read:user,user:email",
            "refresh_token": "test_refresh",
            "expires_in": 3600
        }
        mock_client.post = AsyncMock(return_value=mock_response)

        token = await exchange_code_for_token(
            OAuthProvider.GITHUB,
            code="test-auth-code",
            redirect_uri="http://localhost:3000/callback",
            client=mock_client
        )

        assert token.access_token == "gho_test_token"
        assert token.refresh_token == "test_refresh"

    @pytest.mark.asyncio
    async def test_retries_on_5xx(self, mock_client):
        """5xx errors should trigger retries before failing."""
        from src.core.oauth import OAuthError, OAuthProvider, exchange_code_for_token

        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.content = b''
        mock_response.json.return_value = {}
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(OAuthError):
                await exchange_code_for_token(
                    OAuthProvider.GITHUB,
                    code="test-code",
                    redirect_uri="http://localhost:3000/callback",
                    client=mock_client
                )

        assert mock_client.post.call_count == 3  # 3 attempts

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self, mock_client):
        """Timeouts should trigger retries (cold start handling)."""
        from src.core.oauth import OAuthError, OAuthProvider, exchange_code_for_token

        mock_client.post = AsyncMock(side_effect=httpx.ConnectTimeout("Connection timed out"))

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(OAuthError) as exc_info:
                await exchange_code_for_token(
                    OAuthProvider.GITHUB,
                    code="test-code",
                    redirect_uri="http://localhost:3000/callback",
                    client=mock_client
                )

        assert "timed out" in str(exc_info.value)
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self, mock_client):
        """4xx errors should NOT retry (wasted rate limit)."""
        from src.core.oauth import InvalidCodeError, OAuthProvider, exchange_code_for_token

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.content = b'{"error": "bad_verification_code"}'
        mock_response.json.return_value = {"error": "bad_verification_code"}
        mock_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(InvalidCodeError):
            await exchange_code_for_token(
                OAuthProvider.GITHUB,
                code="invalid-code",
                redirect_uri="http://localhost:3000/callback",
                client=mock_client
            )

        assert mock_client.post.call_count == 1  # No retries


class TestGitHubQuirks:
    """
    GitHub-specific edge cases.

    GitHub returns 200 OK even when token exchange fails,
    requiring inspection of the response body for errors.
    """

    @pytest.mark.asyncio
    async def test_200_ok_with_error_in_body(self, mock_client):
        """CRITICAL: GitHub returns 200 but body contains error."""
        from src.core.oauth import InvalidCodeError, OAuthProvider, exchange_code_for_token

        mock_response = MagicMock()
        mock_response.status_code = 200  # Looks successful!
        mock_response.content = b'{"error": "bad_verification_code", "error_description": "Code expired"}'
        mock_response.json.return_value = {"error": "bad_verification_code", "error_description": "Code expired"}
        mock_client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(InvalidCodeError):
            await exchange_code_for_token(
                OAuthProvider.GITHUB,
                code="expired-code",
                redirect_uri="http://localhost:3000/callback",
                client=mock_client
            )

        assert mock_client.post.call_count == 1  # No retry on 200

    @pytest.mark.asyncio
    async def test_email_selection_primary_not_first(self, mock_client):
        """Primary verified email is not first in the list."""
        from src.core.oauth import OAuthProvider, OAuthToken, fetch_user_profile

        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {"node_id": "MDQ6VXNlcjEyMzQ1", "login": "testuser"}
        mock_user_response.raise_for_status = MagicMock()

        mock_emails_response = MagicMock()
        mock_emails_response.json.return_value = [
            {"email": "secondary@example.com", "primary": False, "verified": True},
            {"email": "unverified@example.com", "primary": False, "verified": False},
            {"email": "primary@example.com", "primary": True, "verified": True},
        ]
        mock_emails_response.raise_for_status = MagicMock()

        mock_client.get = AsyncMock(side_effect=[mock_user_response, mock_emails_response])

        token = OAuthToken(access_token="test-token", token_type="bearer")
        profile = await fetch_user_profile(OAuthProvider.GITHUB, token, mock_client)

        assert profile.email == "primary@example.com"


class TestEmailVerificationGating:
    """
    Email verification enforcement.

    Prevents "shadow account" creation where users could spoof emails.
    """

    @pytest.mark.asyncio
    async def test_github_unverified_email_rejected(self, mock_client):
        from src.core.oauth import EmailNotVerifiedError, OAuthProvider, OAuthToken, fetch_user_profile

        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {"node_id": "MDQ6VXNlcjEyMzQ1"}
        mock_user_response.raise_for_status = MagicMock()

        mock_emails_response = MagicMock()
        mock_emails_response.json.return_value = [
            {"email": "test@example.com", "primary": True, "verified": False}
        ]
        mock_emails_response.raise_for_status = MagicMock()

        mock_client.get = AsyncMock(side_effect=[mock_user_response, mock_emails_response])

        token = OAuthToken(access_token="test-token", token_type="bearer")
        with pytest.raises(EmailNotVerifiedError):
            await fetch_user_profile(OAuthProvider.GITHUB, token, mock_client)

    @pytest.mark.asyncio
    async def test_google_unverified_email_rejected(self, mock_client):
        from src.core.oauth import EmailNotVerifiedError, OAuthProvider, OAuthToken, fetch_user_profile

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "google-12345",
            "email": "test@gmail.com",
            "verified_email": False
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        token = OAuthToken(access_token="test-token", token_type="bearer")
        with pytest.raises(EmailNotVerifiedError):
            await fetch_user_profile(OAuthProvider.GOOGLE, token, mock_client)

    @pytest.mark.asyncio
    async def test_github_no_emails_rejected(self, mock_client):
        from src.core.oauth import NoEmailError, OAuthProvider, OAuthToken, fetch_user_profile

        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {"node_id": "MDQ6VXNlcjEyMzQ1"}
        mock_user_response.raise_for_status = MagicMock()

        mock_emails_response = MagicMock()
        mock_emails_response.json.return_value = []  # Empty list
        mock_emails_response.raise_for_status = MagicMock()

        mock_client.get = AsyncMock(side_effect=[mock_user_response, mock_emails_response])

        token = OAuthToken(access_token="test-token", token_type="bearer")
        with pytest.raises(NoEmailError):
            await fetch_user_profile(OAuthProvider.GITHUB, token, mock_client)


class TestProfileFetching:
    """Profile fetching success cases for both providers."""

    @pytest.mark.asyncio
    async def test_github_profile_uses_node_id(self, mock_client):
        """GitHub uses node_id as provider_id (stable identifier)."""
        from src.core.oauth import OAuthProvider, OAuthToken, fetch_user_profile

        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {
            "id": 12345,
            "node_id": "MDQ6VXNlcjEyMzQ1",
            "login": "testuser",
            "avatar_url": "https://github.com/avatar.jpg"
        }
        mock_user_response.raise_for_status = MagicMock()

        mock_emails_response = MagicMock()
        mock_emails_response.json.return_value = [
            {"email": "test@example.com", "primary": True, "verified": True}
        ]
        mock_emails_response.raise_for_status = MagicMock()

        mock_client.get = AsyncMock(side_effect=[mock_user_response, mock_emails_response])

        token = OAuthToken(access_token="test-token", token_type="bearer")
        profile = await fetch_user_profile(OAuthProvider.GITHUB, token, mock_client)

        assert profile.provider_id == "MDQ6VXNlcjEyMzQ1"
        assert profile.email == "test@example.com"
        assert profile.username == "testuser"

    @pytest.mark.asyncio
    async def test_google_profile_success(self, mock_client):
        from src.core.oauth import OAuthProvider, OAuthToken, fetch_user_profile

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "google-12345",
            "email": "test@gmail.com",
            "verified_email": True,
            "picture": "https://google.com/avatar.jpg"
        }
        mock_response.raise_for_status = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        token = OAuthToken(access_token="test-token", token_type="bearer")
        profile = await fetch_user_profile(OAuthProvider.GOOGLE, token, mock_client)

        assert profile.provider_id == "google-12345"
        assert profile.email == "test@gmail.com"
        assert profile.is_verified is True
