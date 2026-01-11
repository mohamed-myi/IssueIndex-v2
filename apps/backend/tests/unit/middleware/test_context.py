import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock environment variables for all tests."""
    with patch.dict(os.environ, {
        "FINGERPRINT_SECRET": "test-fingerprint-secret-key-for-testing",
        "JWT_SECRET_KEY": "test-jwt-secret-key",
    }):
        from src.core.config import get_settings
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()


class TestRequestContextExtraction:
    """Tests for RequestContext dataclass and get_request_context dependency."""

    async def test_extracts_fingerprint_header(self):
        """Verify fingerprint is extracted from X-Device-Fingerprint header."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"X-Device-Fingerprint": "test-fingerprint-value"}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.fingerprint_raw == "test-fingerprint-value"
        assert ctx.fingerprint_hash is not None
        assert len(ctx.fingerprint_hash) == 64  # SHA256 hex length

    async def test_extracts_user_agent(self):
        """Verify User-Agent header is extracted."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"User-Agent": "Mozilla/5.0 Test Browser"}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.user_agent == "Mozilla/5.0 Test Browser"

    async def test_extracts_login_flow_id_cookie(self):
        """Verify login_flow_id cookie is extracted."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {"login_flow_id": "flow-123-abc"}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.login_flow_id == "flow-123-abc"

    async def test_handles_missing_all_optional_headers(self):
        """Verify graceful handling when all optional headers are missing."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.fingerprint_raw is None
        assert ctx.fingerprint_hash is None
        assert ctx.ip_address == "127.0.0.1"
        assert ctx.user_agent is None
        assert ctx.login_flow_id is None


class TestFingerprintIntegrity:
    """HMAC integrity tests for fingerprint hashing."""

    async def test_hashes_fingerprint_correctly(self):
        """Verify fingerprint is hashed using HMAC-SHA256."""
        from src.core.security import hash_fingerprint
        from src.middleware.context import get_request_context

        fingerprint_value = "unique-browser-fingerprint"
        expected_hash = hash_fingerprint(fingerprint_value)

        request = MagicMock()
        request.headers = {"X-Device-Fingerprint": fingerprint_value}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.fingerprint_hash == expected_hash

    async def test_fingerprint_hash_changes_with_different_secret(self):
        """Verify different secret produces different hash (salt verification)."""
        from src.core.config import get_settings
        from src.middleware.context import get_request_context

        fingerprint = "same-fingerprint"

        request = MagicMock()
        request.headers = {"X-Device-Fingerprint": fingerprint}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx1 = await get_request_context(request)
        hash1 = ctx1.fingerprint_hash

        with patch.dict(os.environ, {"FINGERPRINT_SECRET": "different-secret-key"}):
            get_settings.cache_clear()
            ctx2 = await get_request_context(request)
            hash2 = ctx2.fingerprint_hash
            get_settings.cache_clear()

        assert hash1 != hash2
        assert len(hash1) == len(hash2) == 64

    async def test_empty_string_fingerprint_treated_as_missing(self):
        """Empty string header results in no hash (falsy check)."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"X-Device-Fingerprint": ""}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.fingerprint_raw == ""
        assert ctx.fingerprint_hash is None


class TestIPExtraction:
    """
    IP extraction tests covering proxy chains, fallbacks, and IPv6.

    SECURITY: We extract the RIGHTMOST IP from X-Forwarded-For because
    Cloud Run appends the real client IP to the end. Attacker-spoofed IPs
    appear at the beginning and must be ignored.
    """

    @pytest.mark.parametrize("headers,client_host,expected_ip", [
        # SECURITY: RIGHTMOST IP extracted (Cloud Run appends real client IP)
        ({"X-Forwarded-For": "spoofed_by_attacker, real_client_ip"}, "10.0.0.1", "real_client_ip"),
        # Single proxy
        ({"X-Forwarded-For": "203.0.113.195"}, "10.0.0.1", "203.0.113.195"),
        # Direct IP (no proxy header)
        ({}, "192.168.1.1", "192.168.1.1"),
        # Total failure fallback (no client)
        ({}, None, "0.0.0.0"),
        # IPv6 support
        ({"X-Forwarded-For": "2001:db8::1"}, "127.0.0.1", "2001:db8::1"),
        # Empty/whitespace fallback
        ({"X-Forwarded-For": "   "}, "192.168.1.1", "192.168.1.1"),
    ])
    async def test_ip_extraction_logic(self, headers, client_host, expected_ip):
        """Parametrized test covering proxy chains, fallbacks, and IPv6."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = headers
        request.cookies = {}
        if client_host is None:
            request.client = None
        else:
            request.client = MagicMock()
            request.client.host = client_host

        ctx = await get_request_context(request)

        assert ctx.ip_address == expected_ip

    async def test_ipv6_from_client_host(self):
        """Verify IPv6 address from client.host is handled correctly."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

        ctx = await get_request_context(request)

        assert ctx.ip_address == "2001:0db8:85a3:0000:0000:8a2e:0370:7334"


class TestCookieExtraction:
    """Cookie extraction tests for login flow ID."""

    async def test_login_flow_id_with_multiple_cookies(self):
        """Ensure correct cookie is extracted when multiple cookies exist."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {
            "session_id": "abc123",
            "login_flow_id": "correct-flow-id",
            "_ga": "GA1.2.1234567890.1234567890",
            "other_cookie": "other_value",
        }
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.login_flow_id == "correct-flow-id"

    async def test_empty_login_flow_id_cookie(self):
        """Empty cookie value is preserved as empty string."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {"login_flow_id": ""}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.login_flow_id == ""


class TestUserAgentParsing:
    """Tests for OS and browser family extraction from User-Agent."""

    async def test_parses_chrome_on_mac(self):
        """Extracts Chrome and Mac OS from typical UA string."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0"
        }
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.os_family == "Mac OS X"
        assert ctx.ua_family == "Chrome"

    async def test_parses_safari_on_ios(self):
        """Extracts Safari and iOS from mobile UA string."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
        }
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.os_family == "iOS"
        assert "Safari" in ctx.ua_family  # ua-parser may return variants

    async def test_handles_missing_user_agent(self):
        """No User-Agent header results in None for os/ua family."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.os_family is None
        assert ctx.ua_family is None


class TestGCPHeaderExtraction:
    """Tests for ASN and country code extraction from GCP headers."""

    async def test_extracts_appengine_country(self):
        """Extracts country from X-AppEngine-Country header."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"X-AppEngine-Country": "us"}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.country_code == "US"

    async def test_extracts_cloudflare_country(self):
        """Extracts country from CF-IPCountry header."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"CF-IPCountry": "GB"}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.country_code == "GB"

    async def test_extracts_asn(self):
        """Extracts ASN from X-GCP-ASN header."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"X-GCP-ASN": "AS15169"}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.asn == "AS15169"

    async def test_handles_missing_gcp_headers(self):
        """No GCP headers results in None for asn/country."""
        from src.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.asn is None
        assert ctx.country_code is None

