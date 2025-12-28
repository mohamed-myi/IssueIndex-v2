"""add session limit trigger

Revision ID: 84af9aabb0f8
Revises: f97190cb1a45
Create Date: 2025-12-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '84af9aabb0f8'
down_revision: Union[str, Sequence[str], None] = 'f97190cb1a45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    1. Adds missing columns to session table (schema drift fix)
    2. Creates a Postgres trigger that enforces max 5 sessions per user
    
    When a user attempts to create a 6th session, the trigger automatically
    deletes the oldest active session (FIFO eviction) before allowing the insert.
    """
    
    # First, add the missing columns that were in the model but not in the initial migration
    op.add_column(
        'session',
        sa.Column('remember_me', sa.Boolean(), nullable=False, server_default='false'),
        schema='public'
    )
    op.add_column(
        'session',
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        schema='public'
    )
    op.add_column(
        'session',
        sa.Column('last_active_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        schema='public'
    )
    op.add_column(
        'session',
        sa.Column('ip_address', sa.String(45), nullable=True),
        schema='public'
    )
    op.add_column(
        'session',
        sa.Column('user_agent_string', sa.String(512), nullable=True),
        schema='public'
    )
    
    # Also add missing column to user table
    op.add_column(
        'user',
        sa.Column('created_via', sa.String(), nullable=False, server_default='github'),
        schema='public'
    )
    
    # Create the enforcement function
    op.execute("""
        CREATE OR REPLACE FUNCTION enforce_session_limit()
        RETURNS TRIGGER AS $$
        DECLARE
            session_count INTEGER;
            max_sessions INTEGER := 5;
        BEGIN
            -- Count active (non-expired) sessions for this user
            SELECT COUNT(*) INTO session_count
            FROM public.session
            WHERE user_id = NEW.user_id 
              AND expires_at > NOW();
            
            -- If at or over limit, delete the oldest session
            IF session_count >= max_sessions THEN
                DELETE FROM public.session
                WHERE id = (
                    SELECT id 
                    FROM public.session
                    WHERE user_id = NEW.user_id 
                      AND expires_at > NOW()
                    ORDER BY created_at ASC
                    LIMIT 1
                );
            END IF;
            
            -- Allow the new session to be inserted
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # Create the trigger that fires BEFORE INSERT
    op.execute("""
        CREATE TRIGGER session_limit_trigger
        BEFORE INSERT ON public.session
        FOR EACH ROW
        EXECUTE FUNCTION enforce_session_limit();
    """)
    
    # Add index on (user_id, expires_at) for efficient session counting
    op.create_index(
        'ix_session_user_expires',
        'session',
        ['user_id', 'expires_at'],
        schema='public',
    )
    
    # Add index on (user_id, created_at) for efficient oldest session lookup
    op.create_index(
        'ix_session_user_created',
        'session',
        ['user_id', 'created_at'],
        schema='public',
    )


def downgrade() -> None:
    """Remove the session limit trigger, function, and added columns."""
    
    # Drop indexes
    op.drop_index('ix_session_user_created', table_name='session', schema='public')
    op.drop_index('ix_session_user_expires', table_name='session', schema='public')
    
    # Drop trigger first
    op.execute("DROP TRIGGER IF EXISTS session_limit_trigger ON public.session;")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS enforce_session_limit();")
    
    # Drop added columns
    op.drop_column('user', 'created_via', schema='public')
    op.drop_column('session', 'user_agent_string', schema='public')
    op.drop_column('session', 'ip_address', schema='public')
    op.drop_column('session', 'last_active_at', schema='public')
    op.drop_column('session', 'created_at', schema='public')
    op.drop_column('session', 'remember_me', schema='public')
