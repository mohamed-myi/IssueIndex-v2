"""add recommendation events analytics table

Revision ID: h7i8j9k0l1m2
Revises: g1h2i3j4k5l6
Create Date: 2026-01-08

Creates analytics.recommendation_events for recommendation impressions and clicks.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "h7i8j9k0l1m2"
down_revision: Union[str, Sequence[str], None] = "g1h2i3j4k5l6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")

    op.create_table(
        "recommendation_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "recommendation_batch_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("issue_node_id", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("surface", sa.Text(), nullable=False),
        sa.Column("is_personalized", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", name="uq_recommendation_events_event_id"),
        schema="analytics",
    )

    op.create_index(
        "ix_recommendation_events_batch_id",
        "recommendation_events",
        ["recommendation_batch_id"],
        schema="analytics",
    )
    op.create_index(
        "ix_recommendation_events_user_id",
        "recommendation_events",
        ["user_id"],
        schema="analytics",
    )
    op.create_index(
        "ix_recommendation_events_created_at",
        "recommendation_events",
        ["created_at"],
        schema="analytics",
    )

    op.create_index(
        "uq_recommendation_events_impression_composite",
        "recommendation_events",
        ["user_id", "recommendation_batch_id", "issue_node_id", "position", "surface"],
        unique=True,
        schema="analytics",
        postgresql_where=sa.text("event_type = 'impression'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_recommendation_events_impression_composite",
        table_name="recommendation_events",
        schema="analytics",
        postgresql_where=sa.text("event_type = 'impression'"),
    )
    op.drop_index(
        "ix_recommendation_events_created_at",
        table_name="recommendation_events",
        schema="analytics",
    )
    op.drop_index(
        "ix_recommendation_events_user_id",
        table_name="recommendation_events",
        schema="analytics",
    )
    op.drop_index(
        "ix_recommendation_events_batch_id",
        table_name="recommendation_events",
        schema="analytics",
    )
    op.drop_table("recommendation_events", schema="analytics")
