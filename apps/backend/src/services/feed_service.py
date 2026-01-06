"""
Feed service for personalized issue recommendations.
Uses combined_vector for similarity search; falls back to trending when no profile.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from src.services.profile_service import get_or_create_profile

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 50
CANDIDATE_LIMIT: int = 200

TRENDING_CTA = "These are trending issues. Complete your profile for personalized recommendations."


@dataclass
class FeedItem:
    node_id: str
    title: str
    body_preview: str
    labels: list[str]
    q_score: float
    repo_name: str
    primary_language: Optional[str]
    github_created_at: datetime
    similarity_score: Optional[float]


@dataclass
class FeedResponse:
    results: list[FeedItem]
    total: int
    page: int
    page_size: int
    has_more: bool
    is_personalized: bool
    profile_cta: Optional[str]


async def get_feed(
    db: AsyncSession,
    user_id: UUID,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> FeedResponse:
    """
    Returns personalized feed using combined_vector; falls back to trending.
    Applies preferred_languages and min_heat_threshold filters when personalized.
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = DEFAULT_PAGE_SIZE
    if page_size > MAX_PAGE_SIZE:
        page_size = MAX_PAGE_SIZE
    
    profile = await get_or_create_profile(db, user_id)
    
    if profile.combined_vector is not None:
        return await _get_personalized_feed(
            db=db,
            combined_vector=profile.combined_vector,
            preferred_languages=profile.preferred_languages,
            min_heat_threshold=profile.min_heat_threshold,
            page=page,
            page_size=page_size,
        )
    
    return await _get_trending_feed(
        db=db,
        page=page,
        page_size=page_size,
    )


async def _get_personalized_feed(
    db: AsyncSession,
    combined_vector: list[float],
    preferred_languages: Optional[list[str]],
    min_heat_threshold: float,
    page: int,
    page_size: int,
) -> FeedResponse:
    """Vector similarity search against issue embeddings with preference filters."""
    offset = (page - 1) * page_size
    
    filter_conditions = ["i.embedding IS NOT NULL", "i.state = 'open'"]
    params: dict = {
        "combined_vec": str(combined_vector),
        "min_q_score": min_heat_threshold,
        "limit": CANDIDATE_LIMIT,
        "offset": offset,
        "page_size": page_size,
    }
    
    filter_conditions.append("i.q_score >= :min_q_score")
    
    if preferred_languages:
        filter_conditions.append("r.primary_language = ANY(:langs)")
        params["langs"] = preferred_languages
    
    where_clause = " AND ".join(filter_conditions)
    
    count_sql = f"""
    SELECT COUNT(*) as total
    FROM ingestion.issue i
    JOIN ingestion.repository r ON i.repo_id = r.node_id
    WHERE {where_clause}
    """
    
    count_result = await db.execute(text(count_sql), params)
    total = count_result.scalar() or 0
    
    if total == 0:
        return FeedResponse(
            results=[],
            total=0,
            page=page,
            page_size=page_size,
            has_more=False,
            is_personalized=True,
            profile_cta=None,
        )
    
    sql = f"""
    SELECT 
        i.node_id,
        i.title,
        i.body_text,
        i.labels,
        i.q_score,
        i.github_created_at,
        r.full_name AS repo_name,
        r.primary_language,
        1 - (i.embedding <=> CAST(:combined_vec AS vector)) AS similarity_score
    FROM ingestion.issue i
    JOIN ingestion.repository r ON i.repo_id = r.node_id
    WHERE {where_clause}
    ORDER BY i.embedding <=> CAST(:combined_vec AS vector) ASC, i.q_score DESC
    LIMIT :page_size
    OFFSET :offset
    """
    
    result = await db.execute(text(sql), params)
    rows = result.fetchall()
    
    results = [
        FeedItem(
            node_id=row.node_id,
            title=row.title,
            body_preview=row.body_text[:500] if row.body_text else "",
            labels=row.labels or [],
            q_score=float(row.q_score),
            repo_name=row.repo_name,
            primary_language=row.primary_language,
            github_created_at=row.github_created_at,
            similarity_score=float(row.similarity_score) if row.similarity_score else None,
        )
        for row in rows
    ]
    
    has_more = (offset + len(results)) < total
    
    logger.info(
        f"Personalized feed: user has combined_vector, returned {len(results)} of {total}"
    )
    
    return FeedResponse(
        results=results,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
        is_personalized=True,
        profile_cta=None,
    )


async def _get_trending_feed(
    db: AsyncSession,
    page: int,
    page_size: int,
) -> FeedResponse:
    """Trending issues: high q_score, recent, open."""
    offset = (page - 1) * page_size
    min_q_score = 0.6
    
    params = {
        "min_q_score": min_q_score,
        "limit": CANDIDATE_LIMIT,
        "offset": offset,
        "page_size": page_size,
    }
    
    count_sql = """
    SELECT COUNT(*) as total
    FROM ingestion.issue i
    JOIN ingestion.repository r ON i.repo_id = r.node_id
    WHERE i.q_score >= :min_q_score AND i.state = 'open'
    """
    
    count_result = await db.execute(text(count_sql), params)
    total = count_result.scalar() or 0
    
    if total == 0:
        return FeedResponse(
            results=[],
            total=0,
            page=page,
            page_size=page_size,
            has_more=False,
            is_personalized=False,
            profile_cta=TRENDING_CTA,
        )
    
    sql = """
    SELECT 
        i.node_id,
        i.title,
        i.body_text,
        i.labels,
        i.q_score,
        i.github_created_at,
        r.full_name AS repo_name,
        r.primary_language
    FROM ingestion.issue i
    JOIN ingestion.repository r ON i.repo_id = r.node_id
    WHERE i.q_score >= :min_q_score AND i.state = 'open'
    ORDER BY i.q_score DESC, i.github_created_at DESC
    LIMIT :page_size
    OFFSET :offset
    """
    
    result = await db.execute(text(sql), params)
    rows = result.fetchall()
    
    results = [
        FeedItem(
            node_id=row.node_id,
            title=row.title,
            body_preview=row.body_text[:500] if row.body_text else "",
            labels=row.labels or [],
            q_score=float(row.q_score),
            repo_name=row.repo_name,
            primary_language=row.primary_language,
            github_created_at=row.github_created_at,
            similarity_score=None,
        )
        for row in rows
    ]
    
    has_more = (offset + len(results)) < total
    
    logger.info(
        f"Trending feed: no combined_vector, returned {len(results)} of {total}"
    )
    
    return FeedResponse(
        results=results,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
        is_personalized=False,
        profile_cta=TRENDING_CTA,
    )


__all__ = [
    "FeedItem",
    "FeedResponse",
    "get_feed",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "TRENDING_CTA",
]

