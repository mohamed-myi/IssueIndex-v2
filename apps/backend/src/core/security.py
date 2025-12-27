import hmac
import hashlib
import secrets
from uuid import uuid4

from .config import get_settings


class InsecureSecretError(Exception):
    """Raised when security secret is empty or uses default development value."""
    pass


# Known weak secrets or common defaults (to be updated later)
WEAK_SECRETS = {
    "a-random-string",
    "test-fingerprint-secret",
    "change-me",
    "development",
}


def hash_fingerprint(raw_value: str) -> str:
    """
    HMAC-SHA256 hashes a device fingerprint.
    Raises InsecureSecretError if FINGERPRINT_SECRET is empty (any env) or weak (production).
    """
    settings = get_settings()
    secret = settings.fingerprint_secret
    
    if not secret:
        raise InsecureSecretError("FINGERPRINT_SECRET must be set")
    
    # Strict check for weak secrets in production only
    if settings.environment == "production" and secret in WEAK_SECRETS:
        raise InsecureSecretError(
            "Production environment detected with weak FINGERPRINT_SECRET"
        )
    
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_value.encode("utf-8"),
        digestmod=hashlib.sha256
    ).hexdigest()


def generate_session_id() -> str:
    """
    Generates a unique UUIDv4 for stateful session management.
    """
    return str(uuid4())


def compare_fingerprints(stored_hash: str, request_raw: str) -> bool:
    """
    O(1) comparison of fingerprints to prevent timing attacks.
    Returns False for malformed stored hashes (wrong length) to safely reject DB corruption.
    """
    # SHA256 hex digest is always 64 characters
    if not stored_hash or len(stored_hash) != 64:
        return False
    
    request_hash = hash_fingerprint(request_raw)
    return secrets.compare_digest(stored_hash, request_hash)


def generate_login_flow_id() -> str:
    """
    Secure 16-byte token for rate limiting auth flows by user/device.
    """
    return secrets.token_urlsafe(16)

