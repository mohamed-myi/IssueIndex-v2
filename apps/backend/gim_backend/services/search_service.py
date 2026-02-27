"""Compatibility facade for search service modules split by responsibility."""

from sqlmodel.ext.asyncio.session import AsyncSession

from gim_backend.core.config import get_settings
from gim_backend.services import search_execution as _search_execution
from gim_backend.services import search_schema_probe as _search_schema_probe
from gim_backend.services import search_sql as _search_sql
from gim_backend.services.embedding_service import assert_vector_dim, embed_query
from gim_backend.services.search_models import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    Stage1Result,
)
from gim_backend.services.search_sql import CANDIDATE_LIMIT, RRF_K


async def hybrid_search(
    db: AsyncSession,
    request: SearchRequest,
) -> SearchResponse:
    return await _search_execution.hybrid_search(
        db=db,
        request=request,
        embed_query_fn=embed_query,
        assert_vector_dim_fn=assert_vector_dim,
        execute_stage1_fn=_execute_stage1,
        execute_stage2_fn=_execute_stage2,
    )


async def _execute_stage1(
    db: AsyncSession,
    query_text: str,
    query_embedding: list[float] | None,
    filters: SearchFilters,
    use_vector_path: bool,
) -> Stage1Result:
    return await _search_execution._execute_stage1(
        db=db,
        query_text=query_text,
        query_embedding=query_embedding,
        filters=filters,
        use_vector_path=use_vector_path,
        build_stage1_sql_fn=_build_stage1_sql,
        get_settings_fn=get_settings,
        assert_vector_dim_fn=assert_vector_dim,
    )


async def _execute_stage2(
    db: AsyncSession,
    page_ids: list[str],
    rrf_scores: dict[str, float],
) -> list[SearchResultItem]:
    return await _search_execution._execute_stage2(
        db=db,
        page_ids=page_ids,
        rrf_scores=rrf_scores,
        issue_has_github_url_column_fn=_issue_has_github_url_column,
    )


async def _issue_has_github_url_column(db: AsyncSession) -> bool:
    return await _search_schema_probe._issue_has_github_url_column(db)


def _build_stage1_sql(filters: SearchFilters, use_vector_path: bool) -> str:
    return _search_sql._build_stage1_sql(filters, use_vector_path)


__all__ = [
    "SearchFilters",
    "SearchRequest",
    "SearchResultItem",
    "SearchResponse",
    "Stage1Result",
    "hybrid_search",
    "RRF_K",
    "CANDIDATE_LIMIT",
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "_build_stage1_sql",
]
