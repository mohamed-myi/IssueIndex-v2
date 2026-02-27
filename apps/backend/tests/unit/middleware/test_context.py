import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_settings():
    with patch.dict(
        os.environ,
        {
            "FINGERPRINT_SECRET": "test-fingerprint-secret-key-for-testing",
            "JWT_SECRET_KEY": "test-jwt-secret-key",
        },
    ):
        from gim_backend.core.config import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()


class TestRequestContextExtraction:

    async def test_extracts_fingerprint_header(self):
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"X-Device-Fingerprint": "test-fingerprint-value"}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.fingerprint_raw == "test-fingerprint-value"
        assert ctx.fingerprint_hash is not None


    async def test_extracts_user_agent(self):
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"User-Agent": "Mozilla/5.0 Test Browser"}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.user_agent == "Mozilla/5.0 Test Browser"

    async def test_extracts_login_flow_id_cookie(self):
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {"login_flow_id": "flow-123-abc"}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.login_flow_id == "flow-123-abc"

    async def test_handles_missing_all_optional_headers(self):
        from gim_backend.middleware.context import get_request_context

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

    async def test_hashes_fingerprint_correctly(self):
        from gim_backend.core.security import hash_fingerprint
        from gim_backend.middleware.context import get_request_context

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
        from gim_backend.core.config import get_settings
        from gim_backend.middleware.context import get_request_context

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
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"X-Device-Fingerprint": ""}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.fingerprint_raw == ""
        assert ctx.fingerprint_hash is None


class TestIPExtraction:

    @pytest.mark.parametrize(
        "headers,client_host,expected_ip",
        [
            ({"X-Forwarded-For": "spoofed_by_attacker, real_client_ip"}, "10.0.0.1", "real_client_ip"),
            ({"X-Forwarded-For": "203.0.113.195"}, "10.0.0.1", "203.0.113.195"),
            ({}, "192.168.1.1", "192.168.1.1"),
            ({}, None, "0.0.0.0"),
            ({"X-Forwarded-For": "2001:db8::1"}, "127.0.0.1", "2001:db8::1"),
            ({"X-Forwarded-For": "   "}, "192.168.1.1", "192.168.1.1"),
        ],
    )
    async def test_ip_extraction_logic(self, headers, client_host, expected_ip):
        from gim_backend.middleware.context import get_request_context

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
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"

        ctx = await get_request_context(request)

        assert ctx.ip_address == "2001:0db8:85a3:0000:0000:8a2e:0370:7334"


class TestCookieExtraction:

    async def test_login_flow_id_with_multiple_cookies(self):
        from gim_backend.middleware.context import get_request_context

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
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {"login_flow_id": ""}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.login_flow_id == ""


class TestUserAgentParsing:

    async def test_parses_chrome_on_mac(self):
        from gim_backend.middleware.context import get_request_context

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
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
        }
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.os_family == "iOS"


    async def test_handles_missing_user_agent(self):
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.os_family is None
        assert ctx.ua_family is None


class TestGCPHeaderExtraction:

    async def test_extracts_appengine_country(self):
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"X-AppEngine-Country": "us"}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.country_code == "US"

    async def test_extracts_cloudflare_country(self):
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"CF-IPCountry": "GB"}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.country_code == "GB"

    async def test_extracts_asn(self):
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {"X-GCP-ASN": "AS15169"}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.asn == "AS15169"

    async def test_handles_missing_gcp_headers(self):
        from gim_backend.middleware.context import get_request_context

        request = MagicMock()
        request.headers = {}
        request.cookies = {}
        request.client = MagicMock()
        request.client.host = "127.0.0.1"

        ctx = await get_request_context(request)

        assert ctx.asn is None
        assert ctx.country_code is None
