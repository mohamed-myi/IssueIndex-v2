import hashlib
import hmac
import secrets
from uuid import uuid4

from .config import get_settings


class InsecureSecretError(Exception):
    pass


# todo: expand weak secrets list
WEAK_SECRETS = {
    "a-random-string",
    "test-fingerprint-secret",
    "change-me",
    "development",
}


def hash_fingerprint(raw_value: str) -> str:
    """HMAC SHA256; raises InsecureSecretError if secret empty or weak in production"""
    settings = get_settings()
    secret = settings.fingerprint_secret

    if not secret:
        raise InsecureSecretError("FINGERPRINT_SECRET must be set")

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
    return str(uuid4())


def generate_login_flow_id() -> str:
    """16 byte token for rate limiting auth flows"""
    return secrets.token_urlsafe(16)

