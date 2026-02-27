"""create staging pending issue table

Revision ID: o1p2q3r4s5t6
Revises: n1_cloudsql_256_vectors
Create Date: 2026-01-30 19:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "o1p2q3r4s5t6"
down_revision: Union[str, Sequence[str], None] = "n1_cloudsql_256_vectors"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create staging schema and pending_issue table."""
    # Create staging schema
    op.execute("CREATE SCHEMA IF NOT EXISTS staging")

    # Create pending_issue table
    op.create_table(
        "pending_issue",
        sa.Column("node_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("repo_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("labels", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("github_created_at", sa.DateTime(timezone=True), nullable=False),
        # Q-Score components
        sa.Column("has_code", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "has_template_headers", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "tech_stack_weight", sa.Float(), nullable=False, server_default="0.0"
        ),
        sa.Column("q_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "state",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "content_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        # Processing metadata
        sa.Column(
            "status",
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["repo_id"], ["ingestion.repository.node_id"]),
        sa.PrimaryKeyConstraint("node_id"),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_pending_issue_status",
        ),
        schema="staging",
    )

    # Create partial index for pending issues (most common query)
    op.create_index(
        "ix_pending_issue_status_pending",
        "pending_issue",
        ["status"],
        schema="staging",
        postgresql_where=sa.text("status = 'pending'"),
    )

    # Create index on created_at for ordering
    op.create_index(
        "ix_pending_issue_created_at", "pending_issue", ["created_at"], schema="staging"
    )


def downgrade() -> None:
    """Drop pending_issue table and staging schema."""
    op.drop_index(
        "ix_pending_issue_created_at", table_name="pending_issue", schema="staging"
    )
    op.drop_index(
        "ix_pending_issue_status_pending", table_name="pending_issue", schema="staging"
    )
    op.drop_table("pending_issue", schema="staging")
    op.execute("DROP SCHEMA IF EXISTS staging")
