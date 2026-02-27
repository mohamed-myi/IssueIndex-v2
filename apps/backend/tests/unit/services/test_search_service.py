"""
Search Service Unit Tests

Tests RRF logic, filter handling, cache key generation, two-stage SQL building,
and edge case handling.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from gim_backend.services.search_service import (
    CANDIDATE_LIMIT,
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    RRF_K,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    Stage1Result,
    _build_stage1_sql,
    hybrid_search,
)


class TestSearchFilters:
    """Tests for SearchFilters dataclass."""

    def test_empty_filters_is_empty(self):
        filters = SearchFilters()
        assert filters.is_empty() is True

    def test_filters_with_languages_not_empty(self):
        filters = SearchFilters(languages=["Python"])
        assert filters.is_empty() is False

    def test_filters_with_labels_not_empty(self):
        filters = SearchFilters(labels=["bug"])
        assert filters.is_empty() is False

    def test_filters_with_repos_not_empty(self):
        filters = SearchFilters(repos=["facebook/react"])
        assert filters.is_empty() is False

    def test_cache_key_deterministic(self):
        """Same filters should produce same cache key."""
        filters1 = SearchFilters(languages=["Python", "Rust"])
        filters2 = SearchFilters(languages=["Rust", "Python"])

        # Order should not matter due to sorting
        assert filters1.to_cache_key() == filters2.to_cache_key()

    def test_cache_key_different_for_different_filters(self):
        """Different filters should produce different cache keys."""
        filters1 = SearchFilters(languages=["Python"])
        filters2 = SearchFilters(languages=["Rust"])

        assert filters1.to_cache_key() != filters2.to_cache_key()


class TestSearchRequest:
    """Tests for SearchRequest dataclass."""

    def test_default_pagination(self):
        """Default pagination values should be set."""
        request = SearchRequest(query="test")

        assert request.page == 1
        assert request.page_size == DEFAULT_PAGE_SIZE
        assert request.offset == 0

    def test_offset_calculation(self):
        """Offset should be calculated from page and page_size."""
        request = SearchRequest(query="test", page=3, page_size=10)

        assert request.offset == 20  # (3-1) * 10

    def test_page_clamping_minimum(self):
        """Page should be clamped to minimum 1."""
        request = SearchRequest(query="test", page=0)

        assert request.page == 1

    def test_page_size_clamping_minimum(self):
        """Page size should be clamped to minimum 1."""
        request = SearchRequest(query="test", page_size=0)

        assert request.page_size == DEFAULT_PAGE_SIZE

    def test_page_size_clamping_maximum(self):
        """Page size should be clamped to maximum."""
        request = SearchRequest(query="test", page_size=1000)

        assert request.page_size == MAX_PAGE_SIZE

    def test_cache_key_includes_all_fields(self):
        """Cache key should include query, filters, and pagination."""
        request1 = SearchRequest(query="test", page=1)
        request2 = SearchRequest(query="test", page=2)

        # Different pages should have different cache keys
        assert request1.cache_key() != request2.cache_key()

    def test_cache_key_deterministic(self):
        """Same request should produce same cache key."""
        request1 = SearchRequest(
            query="test",
            filters=SearchFilters(languages=["Python"]),
            page=1,
        )
        request2 = SearchRequest(
            query="test",
            filters=SearchFilters(languages=["Python"]),
            page=1,
        )

        assert request1.cache_key() == request2.cache_key()

    def test_cache_key_with_user_id(self):
        """Cache key should optionally include user_id for personalization."""
        user_id = uuid4()
        request = SearchRequest(query="test", user_id=user_id)

        key_without_user = request.cache_key(include_user=False)
        key_with_user = request.cache_key(include_user=True)

        assert key_without_user != key_with_user

    def test_cache_key_without_user_id_ignores_flag(self):
        """Cache key should be same regardless of flag when user_id is None."""
        request = SearchRequest(query="test", user_id=None)

        key_without_user = request.cache_key(include_user=False)
        key_with_user = request.cache_key(include_user=True)

        assert key_without_user == key_with_user


class TestRRFLogic:
    """Tests for RRF scoring calculations."""

    def test_rrf_score_calculation(self):
        """RRF score should be calculated correctly."""
        # RRF formula: 1/(k + rank)
        # For k=60 and rank=1: 1/(60+1) = 0.01639...
        expected_single = 1.0 / (RRF_K + 1)

        # Combined score for rank 1 in both paths
        expected_combined = 2 * expected_single

        assert abs(expected_single - 0.01639) < 0.001
        assert abs(expected_combined - 0.03279) < 0.001

    def test_rrf_k_constant(self):
        """RRF K constant should be 60 (standard value)."""
        assert RRF_K == 60

    def test_candidate_limit_is_500(self):
        """Candidate limit should be 500 for better recall with filters."""
        assert CANDIDATE_LIMIT == 500


class TestStage1SQLBuilder:
    """Tests for _build_stage1_sql function (two-stage retrieval)."""

    def test_extracted_sql_builder_matches_facade_export(self):
        from gim_backend.services.search_sql import _build_stage1_sql as extracted_build_stage1_sql

        filters = SearchFilters(languages=["Python"], labels=["bug"], repos=["org/repo"])

        assert extracted_build_stage1_sql(filters, use_vector_path=True) == _build_stage1_sql(
            filters,
            use_vector_path=True,
        )

    def test_sql_with_vector_path_enabled(self):
        """SQL should include both vector and BM25 CTEs when vector path enabled."""
        filters = SearchFilters()
        sql = _build_stage1_sql(filters, use_vector_path=True)

        assert "vector_results" in sql
        assert "bm25_results" in sql
        assert "fused" in sql
        assert "rrf_score" in sql
        assert "COUNT(*) OVER()" in sql

    def test_sql_with_vector_path_disabled(self):
        """SQL should only include BM25 CTE when vector path disabled (embedding failure)."""
        filters = SearchFilters()
        sql = _build_stage1_sql(filters, use_vector_path=False)

        assert "vector_results" not in sql
        assert "bm25_results" in sql
        assert "fused" in sql
        assert "rrf_score" in sql

    def test_sql_has_no_filters_in_ctes(self):
        """Filters should NOT appear inside vector_results or bm25_results CTEs."""
        filters = SearchFilters(languages=["Python"], labels=["bug"])
        sql = _build_stage1_sql(filters, use_vector_path=True)

        # Split SQL by CTEs to check filter placement
        vector_cte_end = sql.find("bm25_results")
        vector_cte = sql[:vector_cte_end]

        # Filters should not be in the vector CTE
        assert "primary_language = ANY" not in vector_cte
        assert "labels &&" not in vector_cte

    def test_sql_applies_filters_post_fusion(self):
        """Filters should be applied in the 'filtered' CTE after RRF fusion."""
        filters = SearchFilters(languages=["Python"], labels=["bug"])
        sql = _build_stage1_sql(filters, use_vector_path=True)

        # Filters should appear in the filtered CTE (after fused)
        filtered_section = sql[sql.find("filtered AS") :]
        assert "primary_language = ANY(:langs)" in filtered_section
        assert "fused.labels && :labels" in filtered_section

    def test_sql_with_language_filter_post_fusion(self):
        """Language filter should be in filtered CTE."""
        filters = SearchFilters(languages=["Python"])
        sql = _build_stage1_sql(filters, use_vector_path=True)

        assert "r.primary_language = ANY(:langs)" in sql

    def test_sql_with_labels_filter_post_fusion(self):
        """Labels filter should use fused.labels in filtered CTE."""
        filters = SearchFilters(labels=["bug"])
        sql = _build_stage1_sql(filters, use_vector_path=True)

        assert "fused.labels && :labels" in sql

    def test_sql_with_repos_filter_post_fusion(self):
        """Repos filter should be in filtered CTE."""
        filters = SearchFilters(repos=["facebook/react"])
        sql = _build_stage1_sql(filters, use_vector_path=True)

        assert "r.full_name = ANY(:repos)" in sql

    def test_sql_orders_by_final_score_then_qscore(self):
        """Results should be ordered by final_score DESC, then q_score DESC for tie-breaking."""
        filters = SearchFilters()
        sql = _build_stage1_sql(filters, use_vector_path=True)

        assert "ORDER BY final_score DESC, q_score DESC" in sql

    def test_sql_includes_freshness_formula(self):
        filters = SearchFilters()
        sql = _build_stage1_sql(filters, use_vector_path=True)
        assert "GREATEST(fused.ingested_at, fused.github_created_at)" in sql
        assert "POWER(" in sql

    def test_vector_and_bm25_only_modes_share_score_formula_fragment(self):
        from gim_backend.services.search_sql import _build_stage1_score_columns_sql

        filters = SearchFilters()
        vector_sql = _build_stage1_sql(filters, use_vector_path=True)
        bm25_only_sql = _build_stage1_sql(filters, use_vector_path=False)
        score_fragment = _build_stage1_score_columns_sql("fused")

        def normalize(sql: str) -> str:
            return " ".join(sql.split())

        assert normalize(score_fragment) in normalize(vector_sql)
        assert normalize(score_fragment) in normalize(bm25_only_sql)


class TestStage2StateEnforcement:
    def test_stage2_filters_open_issues(self):
        import inspect

        from gim_backend.services import search_execution

        src = inspect.getsource(search_execution._execute_stage2)
        assert "i.state = 'open'" in src

    def test_stage2_probes_schema_for_github_url(self):
        import inspect

        from gim_backend.services import search_execution

        src = inspect.getsource(search_execution._execute_stage2)
        assert "_issue_has_github_url_column" in src

    def test_stage2_has_legacy_schema_fallback_for_github_url(self):
        import inspect

        from gim_backend.services import search_execution

        src = inspect.getsource(search_execution._execute_stage2)
        assert "NULL::text AS github_url" in src


class TestSchemaProbe:
    @pytest.mark.asyncio
    async def test_issue_has_github_url_column_true(self):
        from gim_backend.services.search_schema_probe import _issue_has_github_url_column

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.one.return_value = (True,)
        mock_db.exec = AsyncMock(return_value=mock_result)

        assert await _issue_has_github_url_column(mock_db) is True

    @pytest.mark.asyncio
    async def test_issue_has_github_url_column_false(self):
        from gim_backend.services.search_schema_probe import _issue_has_github_url_column

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.one.return_value = (False,)
        mock_db.exec = AsyncMock(return_value=mock_result)

        assert await _issue_has_github_url_column(mock_db) is False

    def test_sql_uses_full_outer_join(self):
        """Vector and BM25 results should be combined with FULL OUTER JOIN."""
        filters = SearchFilters()
        sql = _build_stage1_sql(filters, use_vector_path=True)

        assert "FULL OUTER JOIN" in sql

    def test_sql_uses_english_text_search(self):
        """SQL should use English text search configuration."""
        filters = SearchFilters()
        sql = _build_stage1_sql(filters, use_vector_path=True)

        assert "plainto_tsquery('english'" in sql

    def test_sql_uses_cosine_distance(self):
        """SQL should use cosine distance operator for vectors."""
        filters = SearchFilters()
        sql = _build_stage1_sql(filters, use_vector_path=True)

        assert "<=>" in sql  # cosine distance operator

    def test_sql_filters_open_issues_in_vector_cte(self):
        """Vector CTE should only include open issues."""
        filters = SearchFilters()
        sql = _build_stage1_sql(filters, use_vector_path=True)

        # Find the vector_results CTE
        vector_cte_start = sql.find("vector_results AS")
        bm25_cte_start = sql.find("bm25_results AS")
        vector_cte = sql[vector_cte_start:bm25_cte_start]

        assert "i.state = 'open'" in vector_cte

    def test_sql_filters_open_issues_in_bm25_cte(self):
        """BM25 CTE should only include open issues."""
        filters = SearchFilters()
        sql = _build_stage1_sql(filters, use_vector_path=True)

        # Find the bm25_results CTE
        bm25_cte_start = sql.find("bm25_results AS")
        fused_start = sql.find("fused AS")
        bm25_cte = sql[bm25_cte_start:fused_start]

        assert "i.state = 'open'" in bm25_cte

    def test_sql_filters_open_issues_in_bm25_only_mode(self):
        """BM25-only SQL (embedding failed) should filter open issues."""
        filters = SearchFilters()
        sql = _build_stage1_sql(filters, use_vector_path=False)

        assert "i.state = 'open'" in sql


class TestStage1Result:
    """Tests for Stage1Result dataclass."""

    def test_empty_stage1_result(self):
        """Empty Stage1Result should have empty lists and zero total."""
        result = Stage1Result(node_ids=[], rrf_scores={}, total=0)

        assert len(result.node_ids) == 0
        assert len(result.rrf_scores) == 0
        assert result.total == 0

    def test_stage1_result_with_data(self):
        """Stage1Result should store IDs, scores, and total correctly."""
        result = Stage1Result(
            node_ids=["id1", "id2", "id3"],
            rrf_scores={"id1": 0.03, "id2": 0.02, "id3": 0.01},
            total=100,
        )

        assert len(result.node_ids) == 3
        assert result.rrf_scores["id1"] == 0.03
        assert result.total == 100


class TestSearchResultItem:
    """Tests for SearchResultItem dataclass."""

    def test_result_item_creation(self):
        """SearchResultItem should be creatable with all fields."""
        item = SearchResultItem(
            node_id="MDU6SXNzdWUx",
            title="Test Issue",
            body_preview="Test body content",
            labels=["bug", "help wanted"],
            q_score=0.75,
            repo_name="facebook/react",
            primary_language="JavaScript",
            github_created_at=datetime.now(UTC),
            rrf_score=0.025,
        )

        assert item.node_id == "MDU6SXNzdWUx"
        assert item.title == "Test Issue"
        assert len(item.labels) == 2
        assert item.q_score == 0.75


class TestSearchResponse:
    """Tests for SearchResponse dataclass."""

    def test_response_creation(self):
        """SearchResponse should be creatable with all fields."""
        search_id = uuid4()
        response = SearchResponse(
            search_id=search_id,
            results=[],
            total=0,
            page=1,
            page_size=20,
            has_more=False,
            query="test query",
            filters=SearchFilters(),
        )

        assert response.search_id == search_id
        assert response.total == 0
        assert response.has_more is False

    def test_response_with_results(self):
        """SearchResponse should handle multiple results."""
        item1 = SearchResultItem(
            node_id="1",
            title="Issue 1",
            body_preview="Body 1",
            labels=[],
            q_score=0.8,
            repo_name="repo1",
            primary_language="Python",
            github_created_at=datetime.now(UTC),
            rrf_score=0.03,
        )
        item2 = SearchResultItem(
            node_id="2",
            title="Issue 2",
            body_preview="Body 2",
            labels=["bug"],
            q_score=0.7,
            repo_name="repo2",
            primary_language="Rust",
            github_created_at=datetime.now(UTC),
            rrf_score=0.02,
        )

        response = SearchResponse(
            search_id=uuid4(),
            results=[item1, item2],
            total=2,
            page=1,
            page_size=20,
            has_more=False,
            query="test",
            filters=SearchFilters(),
        )

        assert len(response.results) == 2
        assert response.results[0].rrf_score > response.results[1].rrf_score

    def test_has_more_calculation(self):
        """has_more should be True when more results exist beyond current page."""
        response = SearchResponse(
            search_id=uuid4(),
            results=[],
            total=100,
            page=1,
            page_size=20,
            has_more=True,  # 100 > 20
            query="test",
            filters=SearchFilters(),
        )

        assert response.has_more is True
        assert response.total > response.page_size

    def test_total_is_capped_field_can_be_true(self):
        """SearchResponse should preserve explicit capped-total semantics."""
        response = SearchResponse(
            search_id=uuid4(),
            results=[],
            total=500,
            total_is_capped=True,
            page=1,
            page_size=20,
            has_more=True,
            query="test",
            filters=SearchFilters(),
        )

        assert response.total_is_capped is True


class TestHybridSearchCappedTotals:
    @pytest.mark.asyncio
    async def test_hybrid_search_propagates_stage1_capped_total_flag(self):
        request = SearchRequest(query="test query", page=1, page_size=20)
        stage1_result = Stage1Result(
            node_ids=["node_1"],
            rrf_scores={"node_1": 0.123},
            total=500,
            is_capped=True,
        )
        stage2_results = [
            SearchResultItem(
                node_id="node_1",
                title="Issue 1",
                body_preview="Body",
                labels=["bug"],
                q_score=0.8,
                repo_name="repo/name",
                primary_language="Python",
                github_created_at=datetime.now(UTC),
                rrf_score=0.123,
            )
        ]

        with (
            patch("gim_backend.services.search_service.embed_query", new=AsyncMock(return_value=None)),
            patch(
                "gim_backend.services.search_service._execute_stage1",
                new=AsyncMock(return_value=stage1_result),
            ) as mock_stage1,
            patch(
                "gim_backend.services.search_service._execute_stage2",
                new=AsyncMock(return_value=stage2_results),
            ) as mock_stage2,
        ):
            response = await hybrid_search(MagicMock(), request)

        mock_stage1.assert_awaited_once()
        mock_stage2.assert_awaited_once()
        assert response.total == 500
        assert response.total_is_capped is True
