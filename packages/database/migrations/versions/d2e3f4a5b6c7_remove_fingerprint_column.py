"""Remove fingerprint column from session table

Revision ID: d2e3f4a5b6c7
Revises: c1e2a3b4d5f6
Create Date: 2025-12-28 14:53:00.000000

NEUTRALIZED: The fingerprint column is actively used by the auth middleware,
session service, and risk assessment. Dropping it breaks the application.
A safety-net migration at HEAD ensures the column exists via ADD COLUMN IF NOT EXISTS.
"""
from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'c1e2a3b4d5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Intentionally empty -- see module docstring.
    pass


def downgrade() -> None:
    # Intentionally empty -- see module docstring.
    pass
