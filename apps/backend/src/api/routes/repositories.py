"""API routes for repository listing and filtering."""
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.dependencies import get_db
from src.services.repository_service import (
    list_repositories,
    DEFAULT_LIMIT,
    MAX_LIMIT,
)

router = APIRouter()


# Response Models

class RepositoryItemResponse(BaseModel):
    """Single repository item."""
    name: str
    primary_language: str | None
    issue_count: int


class RepositoriesResponse(BaseModel):
    """List of repositories."""
    repositories: list[RepositoryItemResponse]


# Endpoints

@router.get("", response_model=RepositoriesResponse)
async def list_repositories_endpoint(
    db: AsyncSession = Depends(get_db),
    language: Annotated[Optional[str], Query(description="Filter by primary language")] = None,
    q: Annotated[Optional[str], Query(description="Search in repository name")] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> RepositoriesResponse:
    """
    Lists available repositories for filter suggestions.
    
    No authentication required - public endpoint for search dropdowns.
    Supports filtering by language and search query.
    Results ordered by stargazer count (popularity).
    """
    repos = await list_repositories(
        db,
        language=language,
        search_query=q,
        limit=limit,
    )
    
    return RepositoriesResponse(
        repositories=[
            RepositoryItemResponse(
                name=r.name,
                primary_language=r.primary_language,
                issue_count=r.issue_count,
            )
            for r in repos
        ]
    )
