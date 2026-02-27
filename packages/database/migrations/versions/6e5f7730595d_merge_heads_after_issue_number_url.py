"""merge_heads_after_issue_number_url

Revision ID: 6e5f7730595d
Revises: q2r3s4t5u6v7, r1s2t3u4v5w6, u1v2w3x4y5z6
Create Date: 2026-02-17 20:27:36.153492

"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "6e5f7730595d"
down_revision: Union[str, Sequence[str], None] = (
    "q2r3s4t5u6v7",
    "r1s2t3u4v5w6",
    "u1v2w3x4y5z6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
