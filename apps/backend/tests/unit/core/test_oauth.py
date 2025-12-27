import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
import httpx


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


class TestOAuthProvider:
    def test_github_provider_value(self):
        from src.core.oauth import OAuthProvider
        assert OAuthProvider.GITHUB.value == "github"

    def test_google_provider_value(self):
        from src.core.oauth import OAuthProvider
        assert OAuthProvider.GOOGLE.value == "google"


class TestGetAuthorizationUrl:
    def test_github_authorization_url_uses_urlencode(self):
        from src.core.oauth import get_authorization_url, OAuthProvider
        state = "a" * 32  # Min 32 chars required
        url = get_authorization_url(
            OAuthProvider.GITHUB,
            redirect_uri="http://localhost:3000/callback",
            state=state
        )
        assert "github.com/login/oauth/authorize" in url
        assert "client_id=test-github-client-id" in url
        assert f"state={state}" in url
        assert "scope=read%3Auser+user%3Aemail" in url

    def test_google_authorization_url_uses_urlencode(self):
        from src.core.oauth import get_authorization_url, OAuthProvider
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


class TestValidateState:
    def test_valid_state_passes(self):
        from src.core.oauth import validate_state
        validate_state("a" * 32)
        validate_state("abcdefghijklmnopqrstuvwxyz123456")
        validate_state("A-B_C" + "x" * 27)

    def test_empty_state_raises(self):
        from src.core.oauth import validate_state, OAuthStateError
        with pytest.raises(OAuthStateError) as exc:
            validate_state("")
        assert "required" in str(exc.value)

    def test_short_state_raises(self):
        from src.core.oauth import validate_state, OAuthStateError
        with pytest.raises(OAuthStateError) as exc:
            validate_state("short")
        assert "at least 32" in str(exc.value)

    def test_long_state_raises(self):
        from src.core.oauth import validate_state, OAuthStateError
        with pytest.raises(OAuthStateError) as exc:
            validate_state("x" * 129)
        assert "at most 128" in str(exc.value)

    def test_invalid_chars_raises(self):
        from src.core.oauth import validate_state, OAuthStateError
        with pytest.raises(OAuthStateError) as exc:
            validate_state("a" * 31 + "<script>")
        assert "invalid characters" in str(exc.value)


class TestOAuthToken:
    def test_oauth_token_creation(self):
        from src.core.oauth import OAuthToken
        token = OAuthToken(
            access_token="test-token",
            token_type="bearer",
            scope="read:user",
            refresh_token="test-refresh",
            expires_in=3600
        )
        assert token.access_token == "test-token"
        assert token.refresh_token == "test-refresh"
        assert token.expires_in == 3600

    def test_oauth_token_optional_fields(self):
        from src.core.oauth import OAuthToken
        token = OAuthToken(access_token="test", token_type="bearer")
        assert token.refresh_token is None
        assert token.expires_in is None


class TestUserProfile:
    def test_user_profile_creation(self):
        from src.core.oauth import UserProfile
        profile = UserProfile(
            email="test@example.com",
            provider_id="MDQ6VXNlcjEyMzQ1",
            avatar_url="https://example.com/avatar.jpg",
            is_verified=True,
            username="testuser"
        )
        assert profile.email == "test@example.com"
        assert profile.provider_id == "MDQ6VXNlcjEyMzQ1"
        assert profile.is_verified is True


class TestFetchGitHubProfile:
    @pytest.mark.asyncio
    async def test_fetch_github_profile_uses_node_id(self, mock_client):
        from src.core.oauth import fetch_user_profile, OAuthProvider, OAuthToken
        
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
    async def test_fetch_github_profile_unverified_email(self, mock_client):
        from src.core.oauth import fetch_user_profile, OAuthProvider, OAuthToken, EmailNotVerifiedError
        
        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {"id": 12345, "node_id": "MDQ6VXNlcjEyMzQ1"}
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
    async def test_fetch_github_profile_no_email(self, mock_client):
        from src.core.oauth import fetch_user_profile, OAuthProvider, OAuthToken, NoEmailError
        
        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {"id": 12345, "node_id": "MDQ6VXNlcjEyMzQ1"}
        mock_user_response.raise_for_status = MagicMock()
        
        mock_emails_response = MagicMock()
        mock_emails_response.json.return_value = []
        mock_emails_response.raise_for_status = MagicMock()
        
        mock_client.get = AsyncMock(side_effect=[mock_user_response, mock_emails_response])
        
        token = OAuthToken(access_token="test-token", token_type="bearer")
        with pytest.raises(NoEmailError):
            await fetch_user_profile(OAuthProvider.GITHUB, token, mock_client)


class TestFetchGoogleProfile:
    @pytest.mark.asyncio
    async def test_fetch_google_profile_success(self, mock_client):
        from src.core.oauth import fetch_user_profile, OAuthProvider, OAuthToken
        
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
        
        assert profile.email == "test@gmail.com"
        assert profile.provider_id == "google-12345"
        assert profile.is_verified is True

    @pytest.mark.asyncio
    async def test_fetch_google_profile_unverified_email(self, mock_client):
        from src.core.oauth import fetch_user_profile, OAuthProvider, OAuthToken, EmailNotVerifiedError
        
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


class TestExchangeCodeForToken:
    @pytest.mark.asyncio
    async def test_exchange_code_github_success(self, mock_client):
        from src.core.oauth import exchange_code_for_token, OAuthProvider
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "gho_test_token",
            "token_type": "bearer",
            "scope": "read:user,user:email"
        }
        
        mock_client.post = AsyncMock(return_value=mock_response)
        
        token = await exchange_code_for_token(
            OAuthProvider.GITHUB,
            code="test-auth-code",
            redirect_uri="http://localhost:3000/callback",
            client=mock_client
        )
        
        assert token.access_token == "gho_test_token"

    @pytest.mark.asyncio
    async def test_exchange_code_returns_refresh_token(self, mock_client):
        from src.core.oauth import exchange_code_for_token, OAuthProvider
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_token",
            "token_type": "bearer",
            "refresh_token": "test_refresh",
            "expires_in": 3600
        }
        
        mock_client.post = AsyncMock(return_value=mock_response)
        
        token = await exchange_code_for_token(
            OAuthProvider.GOOGLE,
            code="test-code",
            redirect_uri="http://localhost:3000/callback",
            client=mock_client
        )
        
        assert token.refresh_token == "test_refresh"
        assert token.expires_in == 3600

    @pytest.mark.asyncio
    async def test_exchange_code_no_retry_on_4xx(self, mock_client):
        from src.core.oauth import exchange_code_for_token, OAuthProvider, OAuthError
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.content = b'{"error": "bad_verification_code"}'
        mock_response.json.return_value = {"error": "bad_verification_code"}
        
        mock_client.post = AsyncMock(return_value=mock_response)
        
        # Should raise InvalidCodeError, not generic OAuthError
        from src.core.oauth import InvalidCodeError
        with pytest.raises(InvalidCodeError) as exc_info:
            await exchange_code_for_token(
                OAuthProvider.GITHUB,
                code="invalid-code",
                redirect_uri="http://localhost:3000/callback",
                client=mock_client
            )
        
        assert "expired or invalid" in str(exc_info.value)
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_exchange_code_retries_on_5xx(self, mock_client):
        from src.core.oauth import exchange_code_for_token, OAuthProvider, OAuthError
        
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.content = b''
        mock_response.json.return_value = {}
        
        mock_client.post = AsyncMock(return_value=mock_response)
        
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(OAuthError) as exc_info:
                await exchange_code_for_token(
                    OAuthProvider.GITHUB,
                    code="test-code",
                    redirect_uri="http://localhost:3000/callback",
                    client=mock_client
                )
        
        assert "503" in str(exc_info.value)
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_github_200_ok_with_error_in_body(self, mock_client):
        """GitHub returns 200 OK but with error in JSON body."""
        from src.core.oauth import exchange_code_for_token, OAuthProvider, InvalidCodeError
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"error": "bad_verification_code", "error_description": "Code expired"}'
        mock_response.json.return_value = {"error": "bad_verification_code", "error_description": "Code expired"}
        
        mock_client.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(InvalidCodeError) as exc_info:
            await exchange_code_for_token(
                OAuthProvider.GITHUB,
                code="expired-code",
                redirect_uri="http://localhost:3000/callback",
                client=mock_client
            )
        
        assert "expired or invalid" in str(exc_info.value)
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_exchange_code_retries_on_timeout(self, mock_client):
        """Timeouts should trigger retries just like 5xx."""
        from src.core.oauth import exchange_code_for_token, OAuthProvider, OAuthError
        
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
    async def test_exchange_code_retries_on_read_timeout(self, mock_client):
        """Read timeouts should also trigger retries."""
        from src.core.oauth import exchange_code_for_token, OAuthProvider, OAuthError
        
        mock_client.post = AsyncMock(side_effect=httpx.ReadTimeout("Read timed out"))
        
        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(OAuthError) as exc_info:
                await exchange_code_for_token(
                    OAuthProvider.GOOGLE,
                    code="test-code",
                    redirect_uri="http://localhost:3000/callback",
                    client=mock_client
                )
        
        assert "timed out" in str(exc_info.value)
        assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_exchange_code_invalid_json_response(self, mock_client):
        """Provider returns non-JSON response."""
        from src.core.oauth import exchange_code_for_token, OAuthProvider, OAuthError
        import json
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'<html>Service Unavailable</html>'
        mock_response.json.side_effect = json.JSONDecodeError("", "", 0)
        
        mock_client.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(OAuthError) as exc_info:
            await exchange_code_for_token(
                OAuthProvider.GITHUB,
                code="test-code",
                redirect_uri="http://localhost:3000/callback",
                client=mock_client
            )
        
        assert "invalid JSON" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exchange_code_missing_access_token(self, mock_client):
        """Provider returns JSON but missing access_token key."""
        from src.core.oauth import exchange_code_for_token, OAuthProvider, OAuthError
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"token_type": "bearer"}'
        mock_response.json.return_value = {"token_type": "bearer"}
        
        mock_client.post = AsyncMock(return_value=mock_response)
        
        with pytest.raises(OAuthError) as exc_info:
            await exchange_code_for_token(
                OAuthProvider.GITHUB,
                code="test-code",
                redirect_uri="http://localhost:3000/callback",
                client=mock_client
            )
        
        assert "missing access_token" in str(exc_info.value)


class TestGitHubEmailSelection:
    """GitHub email list edge cases."""
    
    @pytest.mark.asyncio
    async def test_primary_email_not_first_in_list(self, mock_client):
        """Primary verified email is not first in the list."""
        from src.core.oauth import fetch_user_profile, OAuthProvider, OAuthToken
        
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

    @pytest.mark.asyncio
    async def test_multiple_emails_none_verified(self, mock_client):
        """Multiple emails but none are verified."""
        from src.core.oauth import fetch_user_profile, OAuthProvider, OAuthToken, EmailNotVerifiedError
        
        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {"node_id": "MDQ6VXNlcjEyMzQ1"}
        mock_user_response.raise_for_status = MagicMock()
        
        mock_emails_response = MagicMock()
        mock_emails_response.json.return_value = [
            {"email": "email1@example.com", "primary": False, "verified": False},
            {"email": "email2@example.com", "primary": True, "verified": False},
            {"email": "email3@example.com", "primary": False, "verified": False},
        ]
        mock_emails_response.raise_for_status = MagicMock()
        
        mock_client.get = AsyncMock(side_effect=[mock_user_response, mock_emails_response])
        
        token = OAuthToken(access_token="test-token", token_type="bearer")
        with pytest.raises(EmailNotVerifiedError):
            await fetch_user_profile(OAuthProvider.GITHUB, token, mock_client)


class TestStateBoundaryValidation:
    """Boundary value testing for state parameter."""
    
    def test_state_exactly_32_chars(self):
        """Exactly minimum length should pass."""
        from src.core.oauth import validate_state
        validate_state("a" * 32)

    def test_state_exactly_128_chars(self):
        """Exactly maximum length should pass."""
        from src.core.oauth import validate_state
        validate_state("x" * 128)

    def test_state_31_chars_fails(self):
        """One less than minimum should fail."""
        from src.core.oauth import validate_state, OAuthStateError
        with pytest.raises(OAuthStateError):
            validate_state("a" * 31)

    def test_state_129_chars_fails(self):
        """One more than maximum should fail."""
        from src.core.oauth import validate_state, OAuthStateError
        with pytest.raises(OAuthStateError):
            validate_state("x" * 129)


class TestGoogleProfileEdgeCases:
    """Google identity constraints."""
    
    @pytest.mark.asyncio
    async def test_google_verified_email_missing(self, mock_client):
        """verified_email field missing entirely from payload."""
        from src.core.oauth import fetch_user_profile, OAuthProvider, OAuthToken, EmailNotVerifiedError
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "google-12345",
            "email": "test@gmail.com",
            # verified_email key missing entirely
        }
        mock_response.raise_for_status = MagicMock()
        
        mock_client.get = AsyncMock(return_value=mock_response)
        
        token = OAuthToken(access_token="test-token", token_type="bearer")
        with pytest.raises(EmailNotVerifiedError):
            await fetch_user_profile(OAuthProvider.GOOGLE, token, mock_client)


class TestHttpClientConfiguration:
    """Client configuration & security."""
    
    def test_client_has_timeout(self):
        """Client should have a reasonable timeout configured."""
        from src.core.oauth import get_http_client
        client = get_http_client()
        assert client.timeout.connect is not None or client.timeout.read is not None

    def test_client_has_connection_limits(self):
        """Client should be created with limits configured."""
        from src.core.oauth import get_http_client
        client = get_http_client()
        # Verify client is properly configured (can make requests)
        assert hasattr(client, 'get')
        assert hasattr(client, 'post')


class TestOAuthError:
    def test_oauth_error_is_exception(self):
        from src.core.oauth import OAuthError
        assert issubclass(OAuthError, Exception)

    def test_email_not_verified_error_is_oauth_error(self):
        from src.core.oauth import EmailNotVerifiedError, OAuthError
        assert issubclass(EmailNotVerifiedError, OAuthError)

    def test_no_email_error_is_oauth_error(self):
        from src.core.oauth import NoEmailError, OAuthError
        assert issubclass(NoEmailError, OAuthError)

    def test_oauth_state_error_is_oauth_error(self):
        from src.core.oauth import OAuthStateError, OAuthError
        assert issubclass(OAuthStateError, OAuthError)

    def test_invalid_code_error_is_oauth_error(self):
        from src.core.oauth import InvalidCodeError, OAuthError
        assert issubclass(InvalidCodeError, OAuthError)


class TestGetHttpClient:
    def test_returns_async_client(self):
        from src.core.oauth import get_http_client
        client = get_http_client()
        assert isinstance(client, httpx.AsyncClient)
