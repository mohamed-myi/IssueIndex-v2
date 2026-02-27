"""Search orchestration and stage execution helpers."""

import logging
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from gim_backend.core.config import get_settings
from gim_backend.services.embedding_service import assert_vector_dim, embed_query
from gim_backend.services.search_models import (
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    Stage1Result,
)
from gim_backend.services.search_schema_probe import _issue_has_github_url_column
from gim_backend.services.search_sql import CANDIDATE_LIMIT, _build_stage1_sql

logger = logging.getLogger(__name__)

AsyncEmbedQueryFn = Callable[[str], Awaitable[list[float] | None]]
AssertVectorDimFn = Callable[..., None]
Stage1ExecutorFn = Callable[..., Awaitable[Stage1Result]]
Stage2ExecutorFn = Callable[..., Awaitable[list[SearchResultItem]]]
Stage1SqlBuilderFn = Callable[[SearchFilters, bool], str]
SettingsGetterFn = Callable[[], object]
SchemaProbeFn = Callable[[AsyncSession], Awaitable[bool]]
SearchIdFactory = Callable[[], UUID]


async def hybrid_search(
    db: AsyncSession,
    request: SearchRequest,
    *,
    embed_query_fn: AsyncEmbedQueryFn | None = None,
    assert_vector_dim_fn: AssertVectorDimFn | None = None,
    execute_stage1_fn: Stage1ExecutorFn | None = None,
    execute_stage2_fn: Stage2ExecutorFn | None = None,
    search_id_factory: SearchIdFactory | None = None,
) -> SearchResponse:
    """
    Executes two-stage hybrid search using RRF to combine vector and BM25 results.

    1: Get ordered candidate IDs and total count
    2: Hydrate current page with full metadata

    Args:
        db: Database session
        request: Search request with query, filters, pagination

    Returns:
        SearchResponse with paginated results and accurate total
    """
    embed_query_impl = embed_query if embed_query_fn is None else embed_query_fn
    assert_vector_dim_impl = assert_vector_dim if assert_vector_dim_fn is None else assert_vector_dim_fn
    stage1_executor = _execute_stage1 if execute_stage1_fn is None else execute_stage1_fn
    stage2_executor = _execute_stage2 if execute_stage2_fn is None else execute_stage2_fn
    new_search_id = uuid4 if search_id_factory is None else search_id_factory

    search_id = new_search_id()

    # Redact user queries in logs to prevent PII leakage
    def _redact(q: str, max_len: int = 20) -> str:
        return q if len(q) <= max_len else q[:max_len] + "..."

    logger.info(
        f"Search request: search_id={search_id}, query={_redact(request.query)!r}, "
        f"filters={request.filters}, page={request.page}"
    )

    query_embedding = await embed_query_impl(request.query)
    use_vector_path = query_embedding is not None

    if not use_vector_path:
        logger.warning(f"Embedding failed for search_id={search_id}; using BM25-only")
    else:
        try:
            assert_vector_dim_impl(query_embedding, context="search query")
        except ValueError as e:
            logger.warning("%s; using BM25-only", e)
            query_embedding = None
            use_vector_path = False

    stage1_result = await stage1_executor(
        db=db,
        query_text=request.query,
        query_embedding=query_embedding,
        filters=request.filters,
        use_vector_path=use_vector_path,
    )

    if stage1_result.total == 0:
        logger.info(f"Search completed: search_id={search_id}, results=0, total=0")
        return SearchResponse(
            search_id=search_id,
            results=[],
            total=0,
            total_is_capped=False,
            page=request.page,
            page_size=request.page_size,
            has_more=False,
            query=request.query,
            filters=request.filters,
        )

    start_idx = request.offset
    end_idx = start_idx + request.page_size
    page_ids = stage1_result.node_ids[start_idx:end_idx]

    if not page_ids:
        logger.info(
            f"Search completed: search_id={search_id}, "
            f"page={request.page} beyond available results, total={stage1_result.total}"
        )
        return SearchResponse(
            search_id=search_id,
            results=[],
            total=stage1_result.total,
            total_is_capped=stage1_result.is_capped,
            page=request.page,
            page_size=request.page_size,
            has_more=False,
            query=request.query,
            filters=request.filters,
        )

    results = await stage2_executor(
        db=db,
        page_ids=page_ids,
        rrf_scores=stage1_result.rrf_scores,
    )

    if len(results) < len(page_ids):
        missing_count = len(page_ids) - len(results)
        logger.warning(
            f"Stage 2 returned {len(results)} of {len(page_ids)} expected rows "
            f"for search_id={search_id}; {missing_count} issues may have been deleted"
        )

    has_more = (request.offset + len(results)) < stage1_result.total

    logger.info(f"Search completed: search_id={search_id}, results={len(results)}, total={stage1_result.total}")

    return SearchResponse(
        search_id=search_id,
        results=results,
        total=stage1_result.total,
        total_is_capped=stage1_result.is_capped,
        page=request.page,
        page_size=request.page_size,
        has_more=has_more,
        query=request.query,
        filters=request.filters,
    )


async def _execute_stage1(
    db: AsyncSession,
    query_text: str,
    query_embedding: list[float] | None,
    filters: SearchFilters,
    use_vector_path: bool,
    *,
    build_stage1_sql_fn: Stage1SqlBuilderFn | None = None,
    get_settings_fn: SettingsGetterFn | None = None,
    assert_vector_dim_fn: AssertVectorDimFn | None = None,
) -> Stage1Result:
    """
    Stage 1: Fetch candidate IDs from vector and BM25 paths without filters,
    perform RRF fusion, apply filters post-fusion, return ordered IDs with COUNT.

    Filters are applied AFTER RRF fusion to prevent recall gaps.
    """
    build_sql = _build_stage1_sql if build_stage1_sql_fn is None else build_stage1_sql_fn
    settings_getter = get_settings if get_settings_fn is None else get_settings_fn
    assert_vector_dim_impl = assert_vector_dim if assert_vector_dim_fn is None else assert_vector_dim_fn

    sql = build_sql(filters, use_vector_path)
    settings = settings_getter()

    params = {
        "query_text": query_text,
        "langs": filters.languages or None,
        "labels": filters.labels or None,
        "repos": filters.repos or None,
        "candidate_limit": CANDIDATE_LIMIT,
        "freshness_half_life_days": float(settings.search_freshness_half_life_days)
        if settings.search_freshness_half_life_days > 0
        else 0.0001,
        "freshness_floor": float(settings.search_freshness_floor),
        "freshness_weight": float(settings.search_freshness_weight),
    }

    if use_vector_path and query_embedding:
        assert_vector_dim_impl(query_embedding, context="stage1 query vector")
        params["query_vec"] = str(query_embedding)

    result = await db.exec(text(sql), params=params)
    rows = result.all()

    if not rows:
        return Stage1Result(node_ids=[], rrf_scores={}, total=0, is_capped=False)

    node_ids: list[str] = []
    rrf_scores: dict[str, float] = {}
    total = 0
    is_capped = False

    for row in rows:
        node_ids.append(row.node_id)
        rrf_scores[row.node_id] = float(row.rrf_score)
        # All rows have same total_count from window function
        total = row.total_count
        is_capped = bool(getattr(row, "vector_capped", False)) or bool(getattr(row, "bm25_capped", False))

    return Stage1Result(node_ids=node_ids, rrf_scores=rrf_scores, total=total, is_capped=is_capped)


async def _execute_stage2(
    db: AsyncSession,
    page_ids: list[str],
    rrf_scores: dict[str, float],
    *,
    issue_has_github_url_column_fn: SchemaProbeFn | None = None,
) -> list[SearchResultItem]:
    """
    Stage 2: Hydrate page IDs with full metadata.
    Uses array_position to preserve RRF ordering from Stage 1.
    """
    if not page_ids:
        return []

    schema_probe = _issue_has_github_url_column if issue_has_github_url_column_fn is None else issue_has_github_url_column_fn
    has_github_url = await schema_probe(db)
    github_url_select = "i.github_url AS github_url" if has_github_url else "NULL::text AS github_url"

    sql = f"""
    SELECT
        i.node_id,
        i.title,
        i.body_text,
        {github_url_select},
        i.labels,
        i.q_score,
        i.github_created_at,
        r.full_name AS repo_name,
        r.primary_language
    FROM ingestion.issue i
    JOIN ingestion.repository r ON i.repo_id = r.node_id
    WHERE i.node_id = ANY(:ids) AND i.state = 'open'
    ORDER BY array_position(:ids, i.node_id)
    """

    result = await db.exec(text(sql), params={"ids": page_ids})
    rows = result.all()

    results: list[SearchResultItem] = []
    for row in rows:
        results.append(
            SearchResultItem(
                node_id=row.node_id,
                title=row.title,
                body_preview=row.body_text[:500] if row.body_text else "",
                github_url=row.github_url,
                labels=row.labels or [],
                q_score=row.q_score,
                repo_name=row.repo_name,
                primary_language=row.primary_language,
                github_created_at=row.github_created_at,
                rrf_score=rrf_scores.get(row.node_id, 0.0),
            )
        )

    return results


__all__ = [
    "hybrid_search",
    "_execute_stage1",
    "_execute_stage2",
]
