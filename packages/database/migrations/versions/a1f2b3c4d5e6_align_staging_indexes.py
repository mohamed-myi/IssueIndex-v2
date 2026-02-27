"""align staging indexes

Revision ID: a1f2b3c4d5e6
Revises: 3e096f49481e
Create Date: 2026-02-06 12:00:00.000000

Aligns the staging.pending_issue indexes with the current PendingIssue model:
- Adds repo_id index (declared via Field(index=True) in the model)
- Drops created_at and status_pending indexes that were manually added
  in the initial staging migration but are not in the model definition
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1f2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "3e096f49481e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add repo_id index, drop unused staging indexes."""
    # Add index on repo_id (matches model: Field(index=True))
    with op.batch_alter_table("pending_issue", schema="staging") as batch_op:
        batch_op.create_index(
            batch_op.f("ix_staging_pending_issue_repo_id"),
            ["repo_id"],
            unique=False,
        )

    # Drop indexes that are not reflected in the model
    op.drop_index(
        "ix_pending_issue_created_at",
        table_name="pending_issue",
        schema="staging",
    )
    op.drop_index(
        "ix_pending_issue_status_pending",
        table_name="pending_issue",
        schema="staging",
    )


def downgrade() -> None:
    """Restore original staging indexes, drop repo_id index."""
    # Recreate the original indexes
    op.create_index(
        "ix_pending_issue_created_at",
        "pending_issue",
        ["created_at"],
        schema="staging",
    )
    op.create_index(
        "ix_pending_issue_status_pending",
        "pending_issue",
        ["status"],
        schema="staging",
        postgresql_where=sa.text("status = 'pending'"),
    )

    # Drop the repo_id index
    with op.batch_alter_table("pending_issue", schema="staging") as batch_op:
        batch_op.drop_index(batch_op.f("ix_staging_pending_issue_repo_id"))
