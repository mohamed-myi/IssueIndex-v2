"""Remove fingerprint column from session table

Revision ID: d2e3f4a5b6c7
Revises: c1e2a3b4d5f6
Create Date: 2025-12-28 14:53:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'c1e2a3b4d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('session', 'fingerprint', schema='public')


def downgrade() -> None:
    op.add_column(
        'session',
        sa.Column('fingerprint', sa.VARCHAR(), nullable=False, server_default=''),
        schema='public'
    )
