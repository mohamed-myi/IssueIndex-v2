"""Staging models for pending issue processing."""

from datetime import datetime
from typing import List
import sqlalchemy as sa
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import ARRAY


class PendingIssue(SQLModel, table=True):
    """Issue pending embedding generation.
    
    Collector writes here, Embedder reads and moves to ingestion.issue.
    """
    __tablename__ = "pending_issue"
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name='ck_pending_issue_status'
        ),
        # Partial index for claim_pending_batch(): WHERE status='pending' ORDER BY created_at
        sa.Index(
            "ix_pending_issue_claim",
            "created_at",
            postgresql_where=sa.text("status = 'pending'"),
        ),
        # Partial index for cleanup_completed(): WHERE status='completed' AND created_at < ...
        sa.Index(
            "ix_pending_issue_cleanup",
            "created_at",
            postgresql_where=sa.text("status = 'completed'"),
        ),
        {"schema": "staging"},
    )

    node_id: str = Field(primary_key=True)
    repo_id: str = Field(foreign_key="ingestion.repository.node_id", index=True)
    
    title: str
    body_text: str
    labels: List[str] = Field(default_factory=list, sa_column=Column(ARRAY(sa.String)))
    github_created_at: datetime = Field(
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False)
    )
    
    # Q-Score components
    has_code: bool = Field(default=False)
    has_template_headers: bool = Field(default=False)
    tech_stack_weight: float = Field(default=0.0)
    q_score: float = Field(default=0.0)
    
    state: str = Field(default="open")
    content_hash: str = Field(max_length=64)
    
    # Processing metadata
    status: str = Field(default="pending")
    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        )
    )
    attempts: int = Field(default=0)
