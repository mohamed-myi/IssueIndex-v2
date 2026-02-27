"""fix session expires_at timezone

Revision ID: q2r3s4t5u6v7
Revises: p1q2r3s4t5u6
Create Date: 2026-02-07

Alters session.expires_at from TIMESTAMP to TIMESTAMP WITH TIME ZONE
to match the timezone-aware datetimes used in Python code.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "q2r3s4t5u6v7"
down_revision: Union[str, Sequence[str], None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Convert expires_at from TIMESTAMP to TIMESTAMP WITH TIME ZONE.

    Existing values are interpreted as UTC and converted accordingly.
    """
    with op.batch_alter_table("session", schema="public") as batch_op:
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(),
            type_=sa.DateTime(timezone=True),
            existing_nullable=False,
            postgresql_using="expires_at AT TIME ZONE 'UTC'",
        )


def downgrade() -> None:
    """Revert expires_at back to TIMESTAMP without timezone."""
    with op.batch_alter_table("session", schema="public") as batch_op:
        batch_op.alter_column(
            "expires_at",
            existing_type=sa.DateTime(timezone=True),
            type_=sa.DateTime(),
            existing_nullable=False,
        )
