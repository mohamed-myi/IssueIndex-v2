"""restore_search_vector_column

Revision ID: 2e4e3778e030
Revises: n1_cloudsql_256_vectors
Create Date: 2026-01-27 21:40:00.000000

Restores the search_vector generated column and index that were accidentally dropped
during the n1_cloudsql_256_vectors migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e4e3778e030'
down_revision: Union[str, Sequence[str], None] = '7420c2e6f0a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Restore search_vector column and GIN index.
    """
    # Add generated tsvector column
    op.execute("""
        ALTER TABLE ingestion.issue 
        ADD COLUMN search_vector tsvector 
        GENERATED ALWAYS AS (
            to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(body_text, ''))
        ) STORED
    """)
    
    # Add GIN index for full-text search
    op.execute("""
        CREATE INDEX ix_issue_search_vector 
        ON ingestion.issue 
        USING GIN (search_vector)
    """)


def downgrade() -> None:
    """
    Remove search_vector column and index.
    """
    op.execute("DROP INDEX IF EXISTS ingestion.ix_issue_search_vector")
    op.execute("ALTER TABLE ingestion.issue DROP COLUMN IF EXISTS search_vector")
