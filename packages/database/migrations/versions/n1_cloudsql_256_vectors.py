"""Cloud SQL fresh schema with 256-dim vectors

Revision ID: n1_cloudsql_256_vectors
Revises: h7i8j9k0l1m2
Create Date: 2026-01-15

Fresh schema setup for Cloud SQL migration with:
1. All vector columns using 256-dim (Matryoshka truncation from nomic-embed-text-v2-moe)
2. content_hash column for Pub/Sub message idempotency
3. HNSW indexes optimized for 256-dim vectors

This migration assumes the database is empty (AlloyDB had no data).
It drops and recreates the ingestion tables and alters profile vector columns.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "n1_cloudsql_256_vectors"
down_revision: Union[str, Sequence[str], None] = "h7i8j9k0l1m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Migrate to 256-dim vectors for Cloud SQL.

    Since AlloyDB is empty, we drop and recreate ingestion tables
    and alter profile vector columns to 256-dim.
    """

    # =========================================================================
    # Part 1: Recreate ingestion schema with 256-dim vectors and content_hash
    # =========================================================================

    # Drop existing ingestion tables (empty DB; no data loss)
    op.drop_index("ix_ingestion_issue_state", table_name="issue", schema="ingestion")
    op.drop_index("ix_issue_survival_vacuum", table_name="issue", schema="ingestion")
    op.drop_index(
        "ix_ingestion_issue_github_created_at", table_name="issue", schema="ingestion"
    )
    op.drop_index(
        "ix_ingestion_issue_ingested_at", table_name="issue", schema="ingestion"
    )
    op.drop_index(
        "ix_ingestion_issue_survival_score", table_name="issue", schema="ingestion"
    )
    op.drop_index("ix_ingestion_issue_q_score", table_name="issue", schema="ingestion")
    op.drop_index("ix_ingestion_issue_repo_id", table_name="issue", schema="ingestion")
    op.drop_table("issue", schema="ingestion")

    op.drop_index(
        "ix_ingestion_repository_last_scraped_at",
        table_name="repository",
        schema="ingestion",
    )
    op.drop_index(
        "ix_ingestion_repository_stargazer_count",
        table_name="repository",
        schema="ingestion",
    )
    op.drop_index(
        "ix_ingestion_repository_primary_language",
        table_name="repository",
        schema="ingestion",
    )
    op.drop_index(
        "ix_ingestion_repository_full_name", table_name="repository", schema="ingestion"
    )
    op.drop_table("repository", schema="ingestion")

    # Recreate repository table (unchanged structure)
    op.create_table(
        "repository",
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("primary_language", sa.String(), nullable=True),
        sa.Column(
            "issue_velocity_week", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("stargazer_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("languages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("topics", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("node_id"),
        sa.UniqueConstraint("full_name", name="uq_repository_full_name"),
        schema="ingestion",
    )

    op.create_index(
        "ix_ingestion_repository_full_name",
        "repository",
        ["full_name"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_repository_primary_language",
        "repository",
        ["primary_language"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_repository_stargazer_count",
        "repository",
        ["stargazer_count"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_repository_last_scraped_at",
        "repository",
        ["last_scraped_at"],
        schema="ingestion",
    )

    # Recreate issue table with 256-dim vectors and content_hash
    op.create_table(
        "issue",
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("repo_id", sa.String(), nullable=False),
        # Q-Score components
        sa.Column("has_code", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "has_template_headers", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "tech_stack_weight", postgresql.REAL(), nullable=False, server_default="0.0"
        ),
        # Calculated scores
        sa.Column("q_score", postgresql.REAL(), nullable=False, server_default="0.0"),
        sa.Column(
            "survival_score", postgresql.REAL(), nullable=False, server_default="0.0"
        ),
        # Content
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body_text", sa.String(), nullable=False),
        sa.Column("labels", postgresql.ARRAY(sa.String()), nullable=True),
        # 256-dim Nomic MoE embeddings (Matryoshka truncation)
        sa.Column(
            "embedding", sa.String(), nullable=True
        ),  # Will be cast to vector(256)
        # Idempotency
        sa.Column("content_hash", sa.String(64), nullable=True),
        # State
        sa.Column("state", sa.String(), nullable=False, server_default="open"),
        # Timestamps
        sa.Column("github_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["repo_id"], ["ingestion.repository.node_id"]),
        sa.PrimaryKeyConstraint("node_id"),
        schema="ingestion",
    )

    # Alter embedding column to vector(256) after table creation
    op.execute(
        "ALTER TABLE ingestion.issue ALTER COLUMN embedding TYPE vector(256) USING embedding::vector(256)"
    )

    # Issue indexes
    op.create_index(
        "ix_ingestion_issue_repo_id",
        "issue",
        ["repo_id"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_issue_q_score",
        "issue",
        ["q_score"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_issue_survival_score",
        "issue",
        ["survival_score"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_issue_ingested_at",
        "issue",
        ["ingested_at"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_issue_github_created_at",
        "issue",
        ["github_created_at"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_issue_state",
        "issue",
        ["state"],
        schema="ingestion",
    )

    # Composite index for Janitor pruning
    op.create_index(
        "ix_issue_survival_vacuum",
        "issue",
        ["survival_score", "ingested_at"],
        schema="ingestion",
    )

    # Content hash index for idempotency lookups
    op.create_index(
        "ix_ingestion_issue_content_hash",
        "issue",
        ["content_hash"],
        schema="ingestion",
    )

    # HNSW index for 256-dim vector similarity search
    op.execute("""
        CREATE INDEX ix_issue_embedding_hnsw
        ON ingestion.issue
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # =========================================================================
    # Part 2: Update profile vector columns from 768-dim to 256-dim
    # =========================================================================

    # Drop existing HNSW index on combined_vector (768-dim)
    op.execute("DROP INDEX IF EXISTS public.ix_userprofile_combined_vector")

    # Null out existing vectors (will be regenerated with 256-dim model)
    op.execute("""
        UPDATE public.userprofile SET
            intent_vector = NULL,
            resume_vector = NULL,
            github_vector = NULL,
            combined_vector = NULL
    """)

    # Alter vector columns to 256-dim
    op.execute(
        "ALTER TABLE public.userprofile ALTER COLUMN intent_vector TYPE vector(256)"
    )
    op.execute(
        "ALTER TABLE public.userprofile ALTER COLUMN resume_vector TYPE vector(256)"
    )
    op.execute(
        "ALTER TABLE public.userprofile ALTER COLUMN github_vector TYPE vector(256)"
    )
    op.execute(
        "ALTER TABLE public.userprofile ALTER COLUMN combined_vector TYPE vector(256)"
    )

    # Recreate HNSW index on combined_vector for 256-dim
    op.execute("""
        CREATE INDEX ix_userprofile_combined_vector
        ON public.userprofile
        USING hnsw (combined_vector vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    """
    Revert to 768-dim vectors.

    Note: This loses all embedding data as vectors must be regenerated.
    """

    # =========================================================================
    # Part 1: Revert profile vector columns to 768-dim
    # =========================================================================

    op.execute("DROP INDEX IF EXISTS public.ix_userprofile_combined_vector")

    op.execute("""
        UPDATE public.userprofile SET
            intent_vector = NULL,
            resume_vector = NULL,
            github_vector = NULL,
            combined_vector = NULL
    """)

    op.execute(
        "ALTER TABLE public.userprofile ALTER COLUMN intent_vector TYPE vector(768)"
    )
    op.execute(
        "ALTER TABLE public.userprofile ALTER COLUMN resume_vector TYPE vector(768)"
    )
    op.execute(
        "ALTER TABLE public.userprofile ALTER COLUMN github_vector TYPE vector(768)"
    )
    op.execute(
        "ALTER TABLE public.userprofile ALTER COLUMN combined_vector TYPE vector(768)"
    )

    op.execute("""
        CREATE INDEX ix_userprofile_combined_vector
        ON public.userprofile
        USING hnsw (combined_vector vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # =========================================================================
    # Part 2: Revert ingestion schema to 768-dim vectors without content_hash
    # =========================================================================

    # Drop 256-dim issue table
    op.execute("DROP INDEX IF EXISTS ingestion.ix_issue_embedding_hnsw")
    op.drop_index(
        "ix_ingestion_issue_content_hash", table_name="issue", schema="ingestion"
    )
    op.drop_index("ix_issue_survival_vacuum", table_name="issue", schema="ingestion")
    op.drop_index("ix_ingestion_issue_state", table_name="issue", schema="ingestion")
    op.drop_index(
        "ix_ingestion_issue_github_created_at", table_name="issue", schema="ingestion"
    )
    op.drop_index(
        "ix_ingestion_issue_ingested_at", table_name="issue", schema="ingestion"
    )
    op.drop_index(
        "ix_ingestion_issue_survival_score", table_name="issue", schema="ingestion"
    )
    op.drop_index("ix_ingestion_issue_q_score", table_name="issue", schema="ingestion")
    op.drop_index("ix_ingestion_issue_repo_id", table_name="issue", schema="ingestion")
    op.drop_table("issue", schema="ingestion")

    op.drop_index(
        "ix_ingestion_repository_last_scraped_at",
        table_name="repository",
        schema="ingestion",
    )
    op.drop_index(
        "ix_ingestion_repository_stargazer_count",
        table_name="repository",
        schema="ingestion",
    )
    op.drop_index(
        "ix_ingestion_repository_primary_language",
        table_name="repository",
        schema="ingestion",
    )
    op.drop_index(
        "ix_ingestion_repository_full_name", table_name="repository", schema="ingestion"
    )
    op.drop_table("repository", schema="ingestion")

    # Recreate with 768-dim (original AlloyDB schema)
    op.create_table(
        "repository",
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("primary_language", sa.String(), nullable=True),
        sa.Column(
            "issue_velocity_week", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column("stargazer_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("languages", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("topics", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("node_id"),
        sa.UniqueConstraint("full_name", name="uq_repository_full_name"),
        schema="ingestion",
    )

    op.create_index(
        "ix_ingestion_repository_full_name",
        "repository",
        ["full_name"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_repository_primary_language",
        "repository",
        ["primary_language"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_repository_stargazer_count",
        "repository",
        ["stargazer_count"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_repository_last_scraped_at",
        "repository",
        ["last_scraped_at"],
        schema="ingestion",
    )

    op.create_table(
        "issue",
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("repo_id", sa.String(), nullable=False),
        sa.Column("has_code", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "has_template_headers", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "tech_stack_weight", postgresql.REAL(), nullable=False, server_default="0.0"
        ),
        sa.Column("q_score", postgresql.REAL(), nullable=False, server_default="0.0"),
        sa.Column(
            "survival_score", postgresql.REAL(), nullable=False, server_default="0.0"
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body_text", sa.String(), nullable=False),
        sa.Column("labels", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("embedding", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=False, server_default="open"),
        sa.Column("github_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["repo_id"], ["ingestion.repository.node_id"]),
        sa.PrimaryKeyConstraint("node_id"),
        schema="ingestion",
    )

    op.execute(
        "ALTER TABLE ingestion.issue ALTER COLUMN embedding TYPE vector(768) USING embedding::vector(768)"
    )

    op.create_index(
        "ix_ingestion_issue_repo_id", "issue", ["repo_id"], schema="ingestion"
    )
    op.create_index(
        "ix_ingestion_issue_q_score", "issue", ["q_score"], schema="ingestion"
    )
    op.create_index(
        "ix_ingestion_issue_survival_score",
        "issue",
        ["survival_score"],
        schema="ingestion",
    )
    op.create_index(
        "ix_ingestion_issue_ingested_at", "issue", ["ingested_at"], schema="ingestion"
    )
    op.create_index(
        "ix_ingestion_issue_github_created_at",
        "issue",
        ["github_created_at"],
        schema="ingestion",
    )
    op.create_index("ix_ingestion_issue_state", "issue", ["state"], schema="ingestion")
    op.create_index(
        "ix_issue_survival_vacuum",
        "issue",
        ["survival_score", "ingested_at"],
        schema="ingestion",
    )
