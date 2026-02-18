"""add_issue_number_and_github_url

Revision ID: u1v2w3x4y5z6
Revises: 7420c2e6f0a9
Create Date: 2026-02-18 13:30:00.000000

Adds canonical GitHub issue metadata storage:
- ingestion.issue.issue_number
- ingestion.issue.github_url
- staging.pending_issue.issue_number
- staging.pending_issue.github_url

Backfills existing ingestion rows using:
1) Bookmark URLs (authoritative where available)
2) Existing github_url parsing
3) Best-effort node_id suffix fallback
"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "u1v2w3x4y5z6"
down_revision: Union[str, Sequence[str], None] = "7420c2e6f0a9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Canonical issue metadata on ingestion.issue
    op.execute(
        """
        ALTER TABLE ingestion.issue
        ADD COLUMN IF NOT EXISTS issue_number INTEGER,
        ADD COLUMN IF NOT EXISTS github_url TEXT
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ingestion_issue_issue_number
        ON ingestion.issue (issue_number)
        """
    )

    # Keep staging schema aligned when it exists on this DB head.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'staging' AND table_name = 'pending_issue'
            ) THEN
                ALTER TABLE staging.pending_issue
                ADD COLUMN IF NOT EXISTS issue_number INTEGER,
                ADD COLUMN IF NOT EXISTS github_url TEXT;

                CREATE INDEX IF NOT EXISTS ix_staging_pending_issue_issue_number
                ON staging.pending_issue (issue_number);
            END IF;
        END
        $$;
        """
    )

    # 1) Backfill from user bookmarks where available (most reliable existing source)
    op.execute(
        """
        UPDATE ingestion.issue i
        SET github_url = b.github_url
        FROM (
            SELECT issue_node_id, MAX(github_url) AS github_url
            FROM public.bookmarkedissue
            WHERE github_url ~ '^https://github\\.com/.+/issues/[0-9]+$'
            GROUP BY issue_node_id
        ) b
        WHERE i.node_id = b.issue_node_id
          AND (i.github_url IS NULL OR i.github_url = '')
        """
    )

    # 2) Extract issue_number from github_url when available
    op.execute(
        """
        UPDATE ingestion.issue
        SET issue_number = CAST((regexp_match(github_url, '/issues/([0-9]+)$'))[1] AS INTEGER)
        WHERE issue_number IS NULL
          AND github_url ~ '/issues/[0-9]+$'
        """
    )

    # 3) Best-effort fallback for legacy rows without canonical URL
    op.execute(
        """
        UPDATE ingestion.issue
        SET issue_number = CAST((regexp_match(node_id, '([0-9]+)$'))[1] AS INTEGER)
        WHERE issue_number IS NULL
          AND regexp_match(node_id, '([0-9]+)$') IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE ingestion.issue i
        SET github_url = 'https://github.com/' || r.full_name || '/issues/' || i.issue_number::TEXT
        FROM ingestion.repository r
        WHERE i.repo_id = r.node_id
          AND (i.github_url IS NULL OR i.github_url = '')
          AND i.issue_number IS NOT NULL
        """
    )

    # Keep staging rows aligned (best-effort) when staging exists.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'staging' AND table_name = 'pending_issue'
            ) THEN
                UPDATE staging.pending_issue
                SET issue_number = CAST((regexp_match(node_id, '([0-9]+)$'))[1] AS INTEGER)
                WHERE issue_number IS NULL
                  AND regexp_match(node_id, '([0-9]+)$') IS NOT NULL;

                UPDATE staging.pending_issue p
                SET github_url = 'https://github.com/' || r.full_name || '/issues/' || p.issue_number::TEXT
                FROM ingestion.repository r
                WHERE p.repo_id = r.node_id
                  AND (p.github_url IS NULL OR p.github_url = '')
                  AND p.issue_number IS NOT NULL;
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_ingestion_issue_issue_number")
    op.execute("ALTER TABLE ingestion.issue DROP COLUMN IF EXISTS issue_number")
    op.execute("ALTER TABLE ingestion.issue DROP COLUMN IF EXISTS github_url")

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'staging' AND table_name = 'pending_issue'
            ) THEN
                DROP INDEX IF EXISTS staging.ix_staging_pending_issue_issue_number;
                ALTER TABLE staging.pending_issue DROP COLUMN IF EXISTS issue_number;
                ALTER TABLE staging.pending_issue DROP COLUMN IF EXISTS github_url;
            END IF;
        END
        $$;
        """
    )
