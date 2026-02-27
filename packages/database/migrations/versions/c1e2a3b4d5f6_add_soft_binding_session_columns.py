"""add soft binding session columns

Revision ID: c1e2a3b4d5f6
Revises: 84af9aabb0f8
Create Date: 2025-12-28

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1e2a3b4d5f6"
down_revision: Union[str, Sequence[str], None] = "84af9aabb0f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add columns for soft metadata binding risk assessment"""
    op.add_column(
        "session", sa.Column("os_family", sa.String(32), nullable=True), schema="public"
    )
    op.add_column(
        "session", sa.Column("ua_family", sa.String(64), nullable=True), schema="public"
    )
    op.add_column(
        "session", sa.Column("asn", sa.String(32), nullable=True), schema="public"
    )
    op.add_column(
        "session",
        sa.Column("country_code", sa.String(2), nullable=True),
        schema="public",
    )
    op.add_column(
        "session",
        sa.Column("deviation_logged_at", sa.DateTime(), nullable=True),
        schema="public",
    )


def downgrade() -> None:
    """Remove soft binding columns"""
    op.drop_column("session", "deviation_logged_at", schema="public")
    op.drop_column("session", "country_code", schema="public")
    op.drop_column("session", "asn", schema="public")
    op.drop_column("session", "ua_family", schema="public")
    op.drop_column("session", "os_family", schema="public")
