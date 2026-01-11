"""
Public API routes for unauthenticated access.
Landing page content: trending issues and platform statistics.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel.ext.asyncio.session import AsyncSession

from src.api.dependencies import get_db
from src.services.feed_service import _get_trending_feed
from src.services.stats_service import get_platform_stats

router = APIRouter()


# Limit for public trending feed (vs 20 for authenticated)
PUBLIC_TRENDING_LIMIT = 10


class TrendingItemOutput(BaseModel):
    """Single issue in the trending feed."""
    node_id: str
    title: str
    body_preview: str
    labels: list[str]
    q_score: float
    repo_name: str
    primary_language: str | None
    github_created_at: str


class TrendingResponse(BaseModel):
    """Public trending issues response."""
    results: list[TrendingItemOutput]
    total: int
    limit: int = Field(
        description="Maximum items returned for public endpoint",
    )


class StatsResponse(BaseModel):
    """Platform statistics for landing page."""
    total_issues: int = Field(description="Total open issues indexed")
    total_repos: int = Field(description="Total repositories indexed")
    total_languages: int = Field(description="Distinct programming languages")
    indexed_at: str | None = Field(
        default=None,
        description="Most recent index update timestamp",
    )


@router.get("/feed/trending", response_model=TrendingResponse)
async def get_trending_route(
    db: AsyncSession = Depends(get_db),
) -> TrendingResponse:
    """
    Returns trending issues for landing page preview.

    No authentication required.
    Returns high-quality, recent, open issues ordered by q_score.
    Limited to 10 items for public access.

    Use authenticated /feed endpoint for full personalized recommendations.
    """
    # Reuse existing trending logic with limited page size
    feed = await _get_trending_feed(
        db=db,
        page=1,
        page_size=PUBLIC_TRENDING_LIMIT,
    )

    return TrendingResponse(
        results=[
            TrendingItemOutput(
                node_id=item.node_id,
                title=item.title,
                body_preview=item.body_preview,
                labels=item.labels,
                q_score=item.q_score,
                repo_name=item.repo_name,
                primary_language=item.primary_language,
                github_created_at=item.github_created_at.isoformat(),
            )
            for item in feed.results
        ],
        total=feed.total,
        limit=PUBLIC_TRENDING_LIMIT,
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats_route(
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """
    Returns platform statistics for landing page.

    No authentication required.
    Statistics are cached with 1-hour TTL for performance.

    Used for trust signals like "10,000+ issues indexed".
    """
    stats = await get_platform_stats(db)

    return StatsResponse(
        total_issues=stats.total_issues,
        total_repos=stats.total_repos,
        total_languages=stats.total_languages,
        indexed_at=stats.indexed_at.isoformat() if stats.indexed_at else None,
    )
