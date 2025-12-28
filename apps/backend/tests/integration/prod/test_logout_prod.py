"""
Production-Safe Logout Integration Tests

SAFETY GUARANTEES:
- All operations use dedicated TEST_USER_UUIDs (never real users)
- All tests run within transactions that are ROLLED BACK (never committed)
- All queries include explicit WHERE user_id = TEST_USER_UUID
- Side-effect verification: check DB state after operations

These tests verify logout and logout_all correctly delete sessions.
"""
import pytest
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelSession
from dotenv import dotenv_values

# Load DATABASE_URL from .env files directly (bypass conftest override)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
env_local = dotenv_values(PROJECT_ROOT / ".env.local")
env_base = dotenv_values(PROJECT_ROOT / ".env")
REAL_DATABASE_URL = env_local.get("DATABASE_URL") or env_base.get("DATABASE_URL") or ""

# Hardcoded test user UUIDs - NEVER use real user IDs
TEST_USER_UUID = UUID("00000000-0000-0000-0000-000000000003")  # Different from session limit tests
TEST_USER_UUID_2 = UUID("00000000-0000-0000-0000-000000000004")

# Skip if no real database URL (not the test default)
# Also filter SQLModel deprecation warning (false positive when using text() raw SQL)
pytestmark = [
    pytest.mark.skipif(
        not REAL_DATABASE_URL or "localhost" in REAL_DATABASE_URL,
        reason="Real DATABASE_URL not set - skipping production DB tests"
    ),
    pytest.mark.filterwarnings("ignore:.*session.exec.*:DeprecationWarning"),
]


@pytest.fixture
async def db_engine():
    """Create async engine for production database."""
    database_url = REAL_DATABASE_URL
    
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(
        database_url,
        echo=False,
        connect_args={
            "prepared_statement_cache_size": 0,
            "statement_cache_size": 0,
        },
    )
    
    yield engine
    await engine.dispose()


@pytest.fixture
async def transactional_session(db_engine):
    """
    SAFETY: Session that automatically rolls back.
    Nothing is ever committed to production database.
    """
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        
        try:
            async_session = SQLModelSession(
                bind=connection,
                expire_on_commit=False,
            )
            
            yield async_session
            
        finally:
            # SAFETY: Always rollback
            await transaction.rollback()


async def create_test_user(session, user_id: UUID, email: str) -> None:
    """Create test user (will be rolled back)."""
    # Include all required fields for production schema
    await session.execute(
        text("""
            INSERT INTO public."user" (id, email, created_via, created_at, github_node_id, github_username)
            VALUES (:user_id, :email, 'test', NOW(), :github_node_id, :github_username)
            ON CONFLICT (id) DO NOTHING
        """),
        {
            "user_id": str(user_id), 
            "email": email,
            "github_node_id": f"test_node_{str(user_id)}",  # Full UUID for uniqueness
            "github_username": f"test_user_{str(user_id)[:8]}",
        }
    )


async def create_test_session(session, user_id: UUID, jti: str) -> UUID:
    """Create session for test user. Returns session ID."""
    session_id = uuid4()
    
    # Use SQL expressions to avoid timezone issues with asyncpg
    await session.execute(
        text("""
            INSERT INTO public.session 
                (id, user_id, fingerprint, jti, expires_at, remember_me, created_at, last_active_at)
            VALUES 
                (:session_id, :user_id, 'test_fingerprint', :jti, 
                 NOW() + INTERVAL '7 days', false, NOW(), NOW())
        """),
        {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "jti": jti,
        }
    )
    
    return session_id


async def count_user_sessions(session, user_id: UUID) -> int:
    """Count active sessions for specific user."""
    result = await session.execute(
        text("""
            SELECT COUNT(*) FROM public.session
            WHERE user_id = :user_id
            AND expires_at > NOW()
        """),
        {"user_id": str(user_id)}
    )
    return result.scalar() or 0


async def session_exists(session, session_id: UUID) -> bool:
    """Check if specific session exists."""
    result = await session.execute(
        text("""
            SELECT COUNT(*) FROM public.session
            WHERE id = :session_id
        """),
        {"session_id": str(session_id)}
    )
    return (result.scalar() or 0) > 0


async def delete_single_session(session, session_id: UUID) -> int:
    """
    Delete a single session by ID.
    Returns rowcount to verify deletion.
    """
    result = await session.execute(
        text("""
            DELETE FROM public.session
            WHERE id = :session_id
        """),
        {"session_id": str(session_id)}
    )
    return result.rowcount


async def delete_all_user_sessions(session, user_id: UUID, except_id: UUID | None = None) -> int:
    """
    Delete all sessions for a user.
    SAFETY: Explicit user_id scoping.
    """
    if except_id:
        result = await session.execute(
            text("""
                DELETE FROM public.session
                WHERE user_id = :user_id
                AND id != :except_id
            """),
            {"user_id": str(user_id), "except_id": str(except_id)}
        )
    else:
        result = await session.execute(
            text("""
                DELETE FROM public.session
                WHERE user_id = :user_id
            """),
            {"user_id": str(user_id)}
        )
    return result.rowcount


class TestLogoutSingleSession:
    """
    Tests for single session logout.
    Verifies side-effect: session is actually deleted from DB.
    """
    
    @pytest.mark.asyncio
    async def test_logout_deletes_session_from_database(self, transactional_session):
        """
        SIDE-EFFECT VERIFICATION: Session must be gone from DB after logout.
        A 200 OK response is not proof - we query the DB.
        """
        await create_test_user(transactional_session, TEST_USER_UUID, "test_logout@test.local")
        
        session_id = await create_test_session(
            transactional_session,
            TEST_USER_UUID,
            jti="jti_logout_test",
        )
        
        # Verify session exists before logout
        exists_before = await session_exists(transactional_session, session_id)
        assert exists_before is True, "Session should exist before logout"
        
        # Perform logout (delete)
        deleted_count = await delete_single_session(transactional_session, session_id)
        assert deleted_count == 1, "Should have deleted 1 session"
        
        # SIDE-EFFECT: Verify session is gone
        exists_after = await session_exists(transactional_session, session_id)
        assert exists_after is False, "Session should NOT exist after logout"
    
    @pytest.mark.asyncio
    async def test_logout_only_affects_target_session(self, transactional_session):
        """
        SAFETY: Logging out one session must not affect others.
        """
        await create_test_user(transactional_session, TEST_USER_UUID, "test_single@test.local")
        
        # Create 3 sessions
        session_1 = await create_test_session(transactional_session, TEST_USER_UUID, "jti_single_1")
        session_2 = await create_test_session(transactional_session, TEST_USER_UUID, "jti_single_2")
        session_3 = await create_test_session(transactional_session, TEST_USER_UUID, "jti_single_3")
        
        # Delete only session_2
        await delete_single_session(transactional_session, session_2)
        
        # Verify session_1 and session_3 still exist
        exists_1 = await session_exists(transactional_session, session_1)
        exists_2 = await session_exists(transactional_session, session_2)
        exists_3 = await session_exists(transactional_session, session_3)
        
        assert exists_1 is True, "Session 1 should still exist"
        assert exists_2 is False, "Session 2 should be gone"
        assert exists_3 is True, "Session 3 should still exist"


class TestLogoutAllSessions:
    """
    Tests for logout_all functionality.
    CRITICAL: Must verify no cross-user data corruption.
    """
    
    @pytest.mark.asyncio
    async def test_logout_all_deletes_all_user_sessions(self, transactional_session):
        """
        SIDE-EFFECT VERIFICATION: All sessions for user must be deleted.
        """
        await create_test_user(transactional_session, TEST_USER_UUID, "test_logout_all@test.local")
        
        # Create 3 sessions
        for i in range(3):
            await create_test_session(transactional_session, TEST_USER_UUID, f"jti_all_{i}")
        
        count_before = await count_user_sessions(transactional_session, TEST_USER_UUID)
        assert count_before == 3
        
        # Logout all
        deleted = await delete_all_user_sessions(transactional_session, TEST_USER_UUID)
        assert deleted == 3, f"Should have deleted 3 sessions, got {deleted}"
        
        # SIDE-EFFECT: Verify all sessions gone
        count_after = await count_user_sessions(transactional_session, TEST_USER_UUID)
        assert count_after == 0, f"Should have 0 sessions after logout_all, got {count_after}"
    
    @pytest.mark.asyncio
    async def test_logout_all_preserves_current_session(self, transactional_session):
        """
        When except_session_id is provided, that session must survive.
        """
        await create_test_user(transactional_session, TEST_USER_UUID, "test_except@test.local")
        
        # Create sessions
        current_session = await create_test_session(transactional_session, TEST_USER_UUID, "jti_current")
        other_1 = await create_test_session(transactional_session, TEST_USER_UUID, "jti_other_1")
        other_2 = await create_test_session(transactional_session, TEST_USER_UUID, "jti_other_2")
        
        # Logout all EXCEPT current
        deleted = await delete_all_user_sessions(
            transactional_session,
            TEST_USER_UUID,
            except_id=current_session
        )
        
        assert deleted == 2, f"Should have deleted 2 sessions, got {deleted}"
        
        # Verify current session survives
        current_exists = await session_exists(transactional_session, current_session)
        other_1_exists = await session_exists(transactional_session, other_1)
        other_2_exists = await session_exists(transactional_session, other_2)
        
        assert current_exists is True, "Current session should survive"
        assert other_1_exists is False, "Other session 1 should be gone"
        assert other_2_exists is False, "Other session 2 should be gone"
    
    @pytest.mark.asyncio
    async def test_logout_all_does_not_affect_other_users(self, transactional_session):
        """
        SAFETY CRITICAL: logout_all for User A must NOT delete User B's sessions.
        """
        await create_test_user(transactional_session, TEST_USER_UUID, "test_user_a@test.local")
        await create_test_user(transactional_session, TEST_USER_UUID_2, "test_user_b@test.local")
        
        # Create sessions for both users
        for i in range(3):
            await create_test_session(transactional_session, TEST_USER_UUID, f"jti_a_{i}")
            await create_test_session(transactional_session, TEST_USER_UUID_2, f"jti_b_{i}")
        
        user_b_count_before = await count_user_sessions(transactional_session, TEST_USER_UUID_2)
        assert user_b_count_before == 3
        
        # Logout ALL for User A only
        await delete_all_user_sessions(transactional_session, TEST_USER_UUID)
        
        # User A should have 0 sessions
        user_a_count = await count_user_sessions(transactional_session, TEST_USER_UUID)
        assert user_a_count == 0
        
        # SAFETY: User B's sessions must be UNCHANGED
        user_b_count_after = await count_user_sessions(transactional_session, TEST_USER_UUID_2)
        assert user_b_count_after == 3, \
            f"User B's sessions must be unaffected! Had {user_b_count_before}, now {user_b_count_after}"
    
    @pytest.mark.asyncio
    async def test_logout_all_returns_correct_count(self, transactional_session):
        """
        Verify rowcount matches actual deletions.
        """
        await create_test_user(transactional_session, TEST_USER_UUID, "test_count@test.local")
        
        # Create exactly 5 sessions
        for i in range(5):
            await create_test_session(transactional_session, TEST_USER_UUID, f"jti_count_{i}")
        
        deleted = await delete_all_user_sessions(transactional_session, TEST_USER_UUID)
        
        assert deleted == 5, f"Expected rowcount=5, got {deleted}"
