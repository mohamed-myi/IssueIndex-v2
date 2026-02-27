"""restore fingerprint column and staging performance indexes

Revision ID: b2c3d4e5f6a7
Revises: a1f2b3c4d5e6
Create Date: 2026-02-06 18:00:00.000000

Three fixes:
1. Ensures session.fingerprint column exists (safety net for d2e3f4a5b6c7
   which was neutralized -- ADD COLUMN IF NOT EXISTS is idempotent).
2. Creates ix_pending_issue_claim partial index on (created_at) WHERE
   status='pending' for claim_pending_batch() performance.
3. Creates ix_pending_issue_cleanup partial index on (created_at) WHERE
   status='completed' for cleanup_completed() performance.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1f2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Part 1: Ensure fingerprint column exists on public.session ----------
    # Idempotent: no-ops if the column already exists (e.g. production where
    # the neutralized d2e3f4a5b6c7 migration was already stamped as applied).
    op.execute(
        "ALTER TABLE public.session ADD COLUMN IF NOT EXISTS fingerprint VARCHAR"
    )
    # Ensure nullable to match the updated model (Optional[str]).
    # The original column was NOT NULL; the model now allows None for sessions
    # created without a fingerprint (e.g. OAuth callbacks).
    op.execute("ALTER TABLE public.session ALTER COLUMN fingerprint DROP NOT NULL")

    # --- Part 2: Restore staging performance indexes -------------------------
    # These replace the indexes dropped by a1f2b3c4d5e6, but as optimized
    # partial indexes tailored to the actual query patterns.

    # Serves claim_pending_batch(): WHERE status='pending' ORDER BY created_at
    op.create_index(
        "ix_pending_issue_claim",
        "pending_issue",
        ["created_at"],
        schema="staging",
        postgresql_where=sa.text("status = 'pending'"),
    )

    # Serves cleanup_completed(): WHERE status='completed' AND created_at < ...
    op.create_index(
        "ix_pending_issue_cleanup",
        "pending_issue",
        ["created_at"],
        schema="staging",
        postgresql_where=sa.text("status = 'completed'"),
    )


def downgrade() -> None:
    # Drop the two partial indexes
    op.drop_index(
        "ix_pending_issue_cleanup",
        table_name="pending_issue",
        schema="staging",
    )
    op.drop_index(
        "ix_pending_issue_claim",
        table_name="pending_issue",
        schema="staging",
    )

    # Drop fingerprint column (reverse of the ADD COLUMN IF NOT EXISTS)
    op.drop_column("session", "fingerprint", schema="public")
