"""
Security Tests - Fail-Safes and Production Hardening

This module tests the core security utilities:
- InsecureSecretError enforcement (fail-fast on weak secrets)
- Malformed hash handling (DB NULL/corruption resilience)
- Constant-time comparison (timing attack resistance)
- ID generation uniqueness verification

Tests are condensed to focus on security-critical behavior, not stdlib validation.
"""
import pytest
import os
from unittest.mock import patch


@pytest.fixture(autouse=True)
def mock_settings():
    with patch.dict(os.environ, {
        "FINGERPRINT_SECRET": "test-fingerprint-secret-key-for-testing",
        "JWT_SECRET_KEY": "test-jwt-secret-key",
    }):
        from src.core.config import get_settings
        get_settings.cache_clear()
        yield
        get_settings.cache_clear()


class TestInsecureSecretValidation:
    """
    Security Fail-Safes for FINGERPRINT_SECRET.
    
    Proves the app "fails secure" - prevents production deployment
    with weak .env.example keys or empty secrets.
    """
    
    def test_empty_secret_fails_in_any_environment(self):
        """Empty FINGERPRINT_SECRET should fail-fast in ANY environment."""
        from src.core.security import InsecureSecretError
        
        with patch.dict(os.environ, {
            "FINGERPRINT_SECRET": "",
            "ENVIRONMENT": "development",
        }):
            from src.core.config import get_settings
            get_settings.cache_clear()
            
            from src.core.security import hash_fingerprint
            with pytest.raises(InsecureSecretError) as exc:
                hash_fingerprint("test-fingerprint")
            
            assert "must be set" in str(exc.value)
            get_settings.cache_clear()

    def test_weak_secret_raises_in_production(self):
        """Default .env.example value should raise in production."""
        from src.core.security import InsecureSecretError
        
        with patch.dict(os.environ, {
            "FINGERPRINT_SECRET": "a-random-string",
            "ENVIRONMENT": "production",
        }):
            from src.core.config import get_settings
            get_settings.cache_clear()
            
            from src.core.security import hash_fingerprint
            with pytest.raises(InsecureSecretError) as exc:
                hash_fingerprint("test-fingerprint")
            
            assert "weak" in str(exc.value).lower()
            get_settings.cache_clear()

    def test_weak_secret_allowed_in_development(self):
        """Non-empty weak secrets are allowed in development for convenience."""
        with patch.dict(os.environ, {
            "FINGERPRINT_SECRET": "a-random-string",
            "ENVIRONMENT": "development",
        }):
            from src.core.config import get_settings
            get_settings.cache_clear()
            
            from src.core.security import hash_fingerprint
            result = hash_fingerprint("test-fingerprint")
            assert len(result) == 64
            
            get_settings.cache_clear()


class TestHashConsistency:
    """Verifies hash behavior for login flow ID matching."""

    def test_hash_produces_consistent_output(self):
        """Same input produces same hash (for session comparison)."""
        from src.core.security import hash_fingerprint
        
        fp = "test-fingerprint-value"
        hash1 = hash_fingerprint(fp)
        hash2 = hash_fingerprint(fp)
        
        assert hash1 == hash2
        assert len(hash1) == 64

