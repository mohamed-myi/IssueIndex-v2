import uuid
from uuid import UUID
from datetime import UTC, datetime
from typing import Optional, Dict, Any
import sqlalchemy as sa
from sqlmodel import SQLModel, Field, Column
from sqlalchemy.dialects.postgresql import JSONB

class RecommendationEvent(SQLModel, table=True):
    __tablename__ = "recommendation_events"
    __table_args__ = {"schema": "analytics"}

    event_id: UUID = Field(primary_key=True)
    user_id: UUID = Field(index=True)
    recommendation_batch_id: UUID = Field(index=True)
    
    event_type: str = Field(index=True)  # Ex: "impression", "click"
    issue_node_id: str = Field(index=True)
    
    position: int
    surface: str  # Ex: "feed", "search", "email"
    is_personalized: bool
    
    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            index=True
        )
    )
    
    event_metadata: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column("metadata", JSONB))


class SearchInteraction(SQLModel, table=True):
    __tablename__ = "search_interactions"
    __table_args__ = {"schema": "analytics"}

    id: UUID = Field(primary_key=True, default_factory=uuid.uuid4)
    search_id: UUID = Field(index=True)
    user_id: Optional[UUID] = Field(default=None, index=True)
    query_text: str
    filters_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    result_count: int = Field(default=0)
    selected_node_id: Optional[str] = Field(default=None)
    position: Optional[int] = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            index=True,
        )
    )
