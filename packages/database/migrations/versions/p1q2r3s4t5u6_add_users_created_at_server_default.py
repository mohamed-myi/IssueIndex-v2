"""add_users_created_at_server_default

Revision ID: p1q2r3s4t5u6
Revises: b2c3d4e5f6a7
Create Date: 2026-02-07

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p1q2r3s4t5u6"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add server_default to users.created_at so INSERT without explicit value succeeds."""
    op.execute(
        """
        ALTER TABLE public.users
        ALTER COLUMN created_at SET DEFAULT now()
        """
    )


def downgrade() -> None:
    """Remove server_default from users.created_at."""
    op.execute(
        """
        ALTER TABLE public.users
        ALTER COLUMN created_at DROP DEFAULT
        """
    )
