"""merge staging migration

Revision ID: 3e096f49481e
Revises: 2e4e3778e030, o1p2q3r4s5t6
Create Date: 2026-01-30 19:18:37.346198

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "3e096f49481e"
down_revision: Union[str, Sequence[str], None] = ("2e4e3778e030", "o1p2q3r4s5t6")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
