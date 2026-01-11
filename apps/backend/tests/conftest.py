import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env.local from project root before setting any defaults.
# This ensures integration tests use the real DATABASE_URL.
project_root = Path(__file__).resolve().parent.parent.parent.parent
env_local_path = project_root / ".env.local"
try:
    load_dotenv(env_local_path)
except PermissionError:
    # CI may deny access to local secret files.
    # Tests fall back to defaults below.
    pass
load_dotenv(project_root / ".env")

if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Add database package source to path for models imports
database_src = project_root / "packages" / "database" / "src"
if str(database_src) not in sys.path:
    sys.path.insert(0, str(database_src))
os.environ.setdefault("FINGERPRINT_SECRET", "test_fingerprint_secret_for_testing_only_32chars")
os.environ.setdefault("JWT_SECRET_KEY", "test_jwt_secret_key_for_testing")
os.environ.setdefault("GITHUB_CLIENT_ID", "test_github_client_id")
os.environ.setdefault("GITHUB_CLIENT_SECRET", "test_github_client_secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test_google_client_id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test_google_client_secret")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ["REDIS_URL"] = ""  # Force in-memory rate limiting for tests

import pytest

@pytest.fixture(autouse=True)
async def reset_global_state():
    """
    Ensure global singletons are reset between tests to prevent:
    1. 'Event loop is closed' errors (from stale Redis clients)
    2. State leakage between tests
    """
    from src.core.redis import reset_redis_for_testing, close_redis
    from src.middleware.rate_limit import reset_rate_limiter, reset_rate_limiter_instance
    
    # Clean before
    reset_redis_for_testing()
    reset_rate_limiter_instance()
    
    yield
    
    # Clean after
    await close_redis()
    reset_redis_for_testing()
    reset_rate_limiter()
    reset_rate_limiter_instance()
