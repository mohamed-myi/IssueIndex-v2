"""add issue state column

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6
Create Date: 2026-01-04

Adds state column to ingestion.issue table for tracking whether GitHub issues
are open or closed. Existing rows default to 'open' since the Gatherer previously
only fetched open issues.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'g1h2i3j4k5l6'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'issue',
        sa.Column('state', sa.String(), nullable=False, server_default='open'),
        schema='ingestion'
    )
    op.create_index(
        'ix_ingestion_issue_state',
        'issue',
        ['state'],
        schema='ingestion'
    )


def downgrade() -> None:
    op.drop_index('ix_ingestion_issue_state', table_name='issue', schema='ingestion')
    op.drop_column('issue', 'state', schema='ingestion')

