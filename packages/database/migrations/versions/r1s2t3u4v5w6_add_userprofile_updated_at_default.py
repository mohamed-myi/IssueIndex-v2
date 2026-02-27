"""add_userprofile_updated_at_server_default

Revision ID: r1s2t3u4v5w6
Revises: p1q2r3s4t5u6
Create Date: 2026-02-08

Fixes: INSERT into userprofile without explicit updated_at fails with
NotNullViolationError because the column was created as NOT NULL without
a server-side DEFAULT.  The SQLAlchemy model declares server_default=func.now()
but the original migration omitted it.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "r1s2t3u4v5w6"
down_revision: Union[str, Sequence[str], None] = "p1q2r3s4t5u6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add server_default to userprofile.updated_at so INSERT without explicit value succeeds."""
    op.execute(
        """
        ALTER TABLE public.userprofile
        ALTER COLUMN updated_at SET DEFAULT now()
        """
    )


def downgrade() -> None:
    """Remove server_default from userprofile.updated_at."""
    op.execute(
        """
        ALTER TABLE public.userprofile
        ALTER COLUMN updated_at DROP DEFAULT
        """
    )
