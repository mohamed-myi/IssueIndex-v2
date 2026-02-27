

import os
from unittest.mock import patch

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


class TestInsecureSecretValidation:

    def test_empty_secret_fails_in_any_environment(self):
        from gim_backend.core.security import InsecureSecretError

        with patch.dict(
            os.environ,
            {
                "FINGERPRINT_SECRET": "",
                "ENVIRONMENT": "development",
            },
        ):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            from gim_backend.core.security import hash_fingerprint

            with pytest.raises(InsecureSecretError) as exc:
                hash_fingerprint("test-fingerprint")

            assert "must be set" in str(exc.value)
            get_settings.cache_clear()

    def test_weak_secret_raises_in_production(self):
        from gim_backend.core.security import InsecureSecretError

        with patch.dict(
            os.environ,
            {
                "FINGERPRINT_SECRET": "a-random-string",
                "ENVIRONMENT": "production",
            },
        ):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            from gim_backend.core.security import hash_fingerprint

            with pytest.raises(InsecureSecretError) as exc:
                hash_fingerprint("test-fingerprint")

            assert "weak" in str(exc.value).lower()
            get_settings.cache_clear()

    def test_weak_secret_allowed_in_development(self):
        with patch.dict(
            os.environ,
            {
                "FINGERPRINT_SECRET": "a-random-string",
                "ENVIRONMENT": "development",
            },
        ):
            from gim_backend.core.config import get_settings

            get_settings.cache_clear()

            from gim_backend.core.security import hash_fingerprint

            result = hash_fingerprint("test-fingerprint")
            assert len(result) == 64

            get_settings.cache_clear()


class TestHashConsistency:

    def test_hash_produces_consistent_output(self):
        from gim_backend.core.security import hash_fingerprint

        fp = "test-fingerprint-value"
        hash1 = hash_fingerprint(fp)
        hash2 = hash_fingerprint(fp)

        assert hash1 == hash2
        assert len(hash1) == 64
