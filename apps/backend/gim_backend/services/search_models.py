"""Pydantic request/response models and shared search constants."""

import hashlib
import json
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 50


class SearchFilters(BaseModel):
    """
    Multi-select filters for hybrid search.
    All filters use ANY semantics (OR within filter, AND across filters).
    """

    languages: list[str] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    repos: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.languages and not self.labels and not self.repos

    def to_cache_key(self) -> str:
        return json.dumps(
            {
                "languages": sorted(self.languages),
                "labels": sorted(self.labels),
                "repos": sorted(self.repos),
            },
            sort_keys=True,
        )


class SearchRequest(BaseModel):
    query: str
    filters: SearchFilters = Field(default_factory=SearchFilters)
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE
    user_id: UUID | None = None

    @model_validator(mode="after")
    def validate_pagination(self) -> "SearchRequest":
        if self.page < 1:
            self.page = 1
        if self.page_size < 1:
            self.page_size = DEFAULT_PAGE_SIZE
        if self.page_size > MAX_PAGE_SIZE:
            self.page_size = MAX_PAGE_SIZE
        return self

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def cache_key(self, include_user: bool = False) -> str:
        """SHA256 hash for Redis cache key."""
        key_data = f"{self.query}|{self.filters.to_cache_key()}|{self.page}|{self.page_size}"
        if include_user and self.user_id:
            key_data += f"|{self.user_id}"
        return hashlib.sha256(key_data.encode()).hexdigest()


class SearchResultItem(BaseModel):
    node_id: str
    title: str
    body_preview: str
    github_url: str | None = None
    labels: list[str]
    q_score: float
    repo_name: str
    primary_language: str | None
    github_created_at: datetime
    rrf_score: float


class SearchResponse(BaseModel):
    search_id: UUID
    results: list[SearchResultItem]
    total: int
    total_is_capped: bool = False
    page: int
    page_size: int
    has_more: bool
    query: str
    filters: SearchFilters


class Stage1Result(BaseModel):
    node_ids: list[str]
    rrf_scores: dict[str, float]
    total: int
    is_capped: bool = False


__all__ = [
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "SearchFilters",
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "Stage1Result",
]
