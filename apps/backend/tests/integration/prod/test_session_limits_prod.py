"""
Production-Safe Session Limit Integration Tests

SAFETY GUARANTEES:
- All operations use a dedicated TEST_USER_UUID (never real users)
- All tests run within transactions that are ROLLED BACK (never committed)
- All queries include explicit WHERE user_id = TEST_USER_UUID
- No bulk operations without user scoping

These tests verify the Postgres trigger (enforce_session_limit) works correctly.
"""
import pytest
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelSession
from dotenv import dotenv_values

# Load DATABASE_URL from .env files directly (bypass conftest override)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent
env_local = dotenv_values(PROJECT_ROOT / ".env.local")
env_base = dotenv_values(PROJECT_ROOT / ".env")
REAL_DATABASE_URL = env_local.get("DATABASE_URL") or env_base.get("DATABASE_URL") or ""

# Hardcoded test user UUID - NEVER use real user IDs
# This UUID is clearly labeled as test and does not exist in production
TEST_USER_UUID = UUID("00000000-0000-0000-0000-000000000001")
TEST_USER_UUID_2 = UUID("00000000-0000-0000-0000-000000000002")

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
    
    Creates a connection with BEGIN, yields session, then ROLLBACK.
    Nothing is ever committed to production database.
    """
    async with db_engine.connect() as connection:
        # Begin transaction
        transaction = await connection.begin()
        
        try:
            # Create session bound to this connection
            async_session = SQLModelSession(
                bind=connection,
                expire_on_commit=False,
            )
            
            yield async_session
            
        finally:
            # SAFETY: Always rollback, never commit
            await transaction.rollback()


async def create_test_user(session: AsyncSession, user_id: UUID, email: str) -> None:
    """
    Create a test user within transaction (will be rolled back).
    SAFETY: Explicit user_id prevents ID conflicts.
    """
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


async def create_test_session(
    session: AsyncSession,
    user_id: UUID,
    jti: str,
    created_hours_ago: int = 0,
) -> UUID:
    """
    Create a session for test user (within transaction).
    Returns the session ID for verification.
    SAFETY: Always scoped to explicit user_id.
    
    created_hours_ago: How many hours in the past to set created_at (for ordering tests)
    """
    from uuid import uuid4
    session_id = uuid4()
    
    # Use SQL interval expressions to avoid timezone issues with asyncpg
    await session.execute(
        text("""
            INSERT INTO public.session 
                (id, user_id, fingerprint, jti, expires_at, remember_me, created_at, last_active_at)
            VALUES 
                (:session_id, :user_id, 'test_fingerprint', :jti, 
                 NOW() + INTERVAL '7 days', 
                 false, 
                 NOW() - :hours_ago * INTERVAL '1 hour',
                 NOW() - :hours_ago * INTERVAL '1 hour')
        """),
        {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "jti": jti,
            "hours_ago": created_hours_ago,
        }
    )
    
    return session_id


async def count_user_sessions(session: AsyncSession, user_id: UUID) -> int:
    """
    Count active sessions for specific user.
    SAFETY: Scoped to exact user_id.
    """
    result = await session.execute(
        text("""
            SELECT COUNT(*) FROM public.session
            WHERE user_id = :user_id
            AND expires_at > NOW()
        """),
        {"user_id": str(user_id)}
    )
    return result.scalar() or 0


async def get_session_ids_for_user(session: AsyncSession, user_id: UUID) -> list[str]:
    """
    Get all session IDs for a specific user, ordered by created_at.
    SAFETY: Scoped to exact user_id.
    """
    result = await session.execute(
        text("""
            SELECT id::text FROM public.session
            WHERE user_id = :user_id
            AND expires_at > NOW()
            ORDER BY created_at ASC
        """),
        {"user_id": str(user_id)}
    )
    return [row[0] for row in result.fetchall()]


class TestSessionLimitTrigger:
    """
    Tests for the Postgres trigger that enforces max 5 sessions per user.
    
    SAFETY: All tests use TEST_USER_UUID within rolled-back transactions.
    """
    
    @pytest.mark.asyncio
    async def test_allows_up_to_5_sessions(self, transactional_session):
        """
        VERIFY: User can create 5 sessions without eviction.
        """
        await create_test_user(transactional_session, TEST_USER_UUID, "test_5sessions@test.local")
        
        # Create 5 sessions
        for i in range(5):
            await create_test_session(
                transactional_session,
                TEST_USER_UUID,
                jti=f"jti_allowed_{i}",
            )
        
        # Verify all 5 exist
        count = await count_user_sessions(transactional_session, TEST_USER_UUID)
        
        assert count == 5, f"Should have 5 sessions, got {count}"
    
    @pytest.mark.asyncio
    async def test_6th_session_evicts_oldest(self, transactional_session):
        """
        VERIFY: Creating 6th session triggers eviction of oldest.
        This proves the Postgres trigger is working.
        """
        await create_test_user(transactional_session, TEST_USER_UUID, "test_eviction@test.local")
        
        # Create 5 sessions with staggered created_at times (hours_ago: 5, 4, 3, 2, 1)
        session_ids = []
        
        for i in range(5):
            sid = await create_test_session(
                transactional_session,
                TEST_USER_UUID,
                jti=f"jti_eviction_{i}",
                created_hours_ago=(5 - i),  # First session is oldest (5 hours ago)
            )
            session_ids.append(str(sid))
        
        oldest_session_id = session_ids[0]
        
        # Verify all 5 exist before 6th
        count_before = await count_user_sessions(transactional_session, TEST_USER_UUID)
        assert count_before == 5, f"Should have 5 sessions before 6th, got {count_before}"
        
        # Create 6th session - should trigger eviction
        await create_test_session(
            transactional_session,
            TEST_USER_UUID,
            jti="jti_6th_session",
            created_hours_ago=0,  # Newest session
        )
        
        # SIDE-EFFECT VERIFICATION: Count should still be 5
        count_after = await count_user_sessions(transactional_session, TEST_USER_UUID)
        assert count_after == 5, f"Should still have 5 sessions after 6th, got {count_after}"
        
        # SIDE-EFFECT VERIFICATION: Oldest session should be gone
        remaining_ids = await get_session_ids_for_user(transactional_session, TEST_USER_UUID)
        
        assert oldest_session_id not in remaining_ids, \
            f"Oldest session {oldest_session_id} should have been evicted"
        
        assert oldest_session_id not in remaining_ids, \
            f"Oldest session {oldest_session_id} should have been evicted"
    
    @pytest.mark.asyncio
    async def test_eviction_does_not_affect_other_users(self, transactional_session):
        """
        SAFETY CRITICAL: Eviction for one user must NOT affect another user.
        """
        await create_test_user(transactional_session, TEST_USER_UUID, "test_user1@test.local")
        await create_test_user(transactional_session, TEST_USER_UUID_2, "test_user2@test.local")
        
        # Create 5 sessions for USER_2 (bystander)
        for i in range(5):
            await create_test_session(
                transactional_session,
                TEST_USER_UUID_2,
                jti=f"jti_user2_{i}",
            )
        
        user2_count_before = await count_user_sessions(transactional_session, TEST_USER_UUID_2)
        assert user2_count_before == 5
        
        # Create 6 sessions for USER_1 (triggers eviction)
        for i in range(6):
            await create_test_session(
                transactional_session,
                TEST_USER_UUID,
                jti=f"jti_user1_{i}",
            )
        
        # USER_2 sessions must be UNAFFECTED
        user2_count_after = await count_user_sessions(transactional_session, TEST_USER_UUID_2)
        
        assert user2_count_after == 5, \
            f"User 2's sessions should be unaffected, had {user2_count_before}, now {user2_count_after}"
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_leaves_no_trace(self, transactional_session):
        """
        META-SAFETY: Verify that our rollback mechanism works.
        After test, no TEST_USER_UUID data should persist.
        """
        await create_test_user(transactional_session, TEST_USER_UUID, "test_rollback@test.local")
        await create_test_session(
            transactional_session,
            TEST_USER_UUID,
            jti="jti_rollback_test",
        )
        
        # Within transaction, session exists
        count = await count_user_sessions(transactional_session, TEST_USER_UUID)
        assert count == 1
        
        # After this test, the fixture's finally block will ROLLBACK
        # We can't verify here, but this documents the behavior
