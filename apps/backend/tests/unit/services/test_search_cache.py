"""
Search Cache Unit Tests

Tests cache serialization, deserialization, and key generation.
"""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from gim_backend.services.search_cache import (
    CACHE_PREFIX,
    CACHE_TTL_SECONDS,
    CONTEXT_PREFIX,
    _deserialize_response,
    _normalize_cached_response_payload,
    _serialize_response,
    cache_search_context,
    get_cached_search,
    get_cached_search_context,
)
from gim_backend.services.search_service import (
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
)


class TestCacheConstants:
    """Tests for cache configuration constants."""

    def test_cache_ttl_is_five_minutes(self):
        assert CACHE_TTL_SECONDS == 300

    def test_cache_prefix_is_search(self):
        assert CACHE_PREFIX == "search:"


class TestCacheSerialization:
    """Tests for response serialization and deserialization."""

    @pytest.fixture
    def sample_response(self):
        item = SearchResultItem(
            node_id="MDU6SXNzdWUx",
            title="Test Issue Title",
            body_preview="This is the body text of the issue.",
            labels=["bug", "help wanted"],
            q_score=0.75,
            repo_name="facebook/react",
            primary_language="JavaScript",
            github_created_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            rrf_score=0.025,
        )

        return SearchResponse(
            search_id=uuid4(),
            results=[item],
            total=1,
            total_is_capped=False,
            page=1,
            page_size=20,
            has_more=False,
            query="test query",
            filters=SearchFilters(
                languages=["JavaScript"],
                labels=["bug"],
                repos=[],
            ),
        )

    def test_serialize_produces_valid_json(self, sample_response):
        serialized = _serialize_response(sample_response)

        # Should be valid JSON
        parsed = json.loads(serialized)
        assert isinstance(parsed, dict)

    def test_serialize_uses_model_dump_json_shape(self, sample_response):
        serialized = _serialize_response(sample_response)
        parsed = json.loads(serialized)

        expected = sample_response.model_dump(mode="json")
        parsed.pop("_cache_schema_version", None)

        assert parsed == expected

    def test_serialize_includes_all_fields(self, sample_response):
        serialized = _serialize_response(sample_response)
        parsed = json.loads(serialized)

        assert "search_id" in parsed
        assert "results" in parsed
        assert "total" in parsed
        assert "page" in parsed
        assert "page_size" in parsed
        assert "has_more" in parsed
        assert "query" in parsed
        assert "filters" in parsed

    def test_serialize_includes_result_fields(self, sample_response):
        """Serialization should include all result item fields."""
        serialized = _serialize_response(sample_response)
        parsed = json.loads(serialized)

        result = parsed["results"][0]
        assert result["node_id"] == "MDU6SXNzdWUx"
        assert result["title"] == "Test Issue Title"
        assert result["body_preview"] == "This is the body text of the issue."
        assert result["labels"] == ["bug", "help wanted"]
        assert result["q_score"] == 0.75
        assert result["repo_name"] == "facebook/react"
        assert result["primary_language"] == "JavaScript"
        assert result["rrf_score"] == 0.025

    def test_serialize_includes_filters(self, sample_response):
        """Serialization should include filter data."""
        serialized = _serialize_response(sample_response)
        parsed = json.loads(serialized)

        filters = parsed["filters"]
        assert filters["languages"] == ["JavaScript"]
        assert filters["labels"] == ["bug"]
        assert filters["repos"] == []

    def test_deserialize_restores_response(self, sample_response):
        """Deserialization should restore the original response."""
        serialized = _serialize_response(sample_response)
        restored = _deserialize_response(serialized)

        assert str(restored.search_id) == str(sample_response.search_id)
        assert restored.total == sample_response.total
        assert restored.page == sample_response.page
        assert restored.page_size == sample_response.page_size
        assert restored.has_more == sample_response.has_more
        assert restored.query == sample_response.query

    def test_deserialize_restores_results(self, sample_response):
        """Deserialization should restore result items."""
        serialized = _serialize_response(sample_response)
        restored = _deserialize_response(serialized)

        assert len(restored.results) == 1
        result = restored.results[0]
        original = sample_response.results[0]

        assert result.node_id == original.node_id
        assert result.title == original.title
        assert result.body_preview == original.body_preview
        assert result.labels == original.labels
        assert result.q_score == original.q_score
        assert result.repo_name == original.repo_name
        assert result.primary_language == original.primary_language
        assert result.rrf_score == original.rrf_score

    def test_deserialize_restores_filters(self, sample_response):
        """Deserialization should restore filter data."""
        serialized = _serialize_response(sample_response)
        restored = _deserialize_response(serialized)

        assert restored.filters.languages == sample_response.filters.languages
        assert restored.filters.labels == sample_response.filters.labels
        assert restored.filters.repos == sample_response.filters.repos

    def test_roundtrip_preserves_datetime(self, sample_response):
        """Roundtrip should preserve datetime values."""
        serialized = _serialize_response(sample_response)
        restored = _deserialize_response(serialized)

        original_dt = sample_response.results[0].github_created_at
        restored_dt = restored.results[0].github_created_at

        assert restored_dt == original_dt

    def test_deserialize_supports_legacy_body_text_field(self, sample_response):
        payload = sample_response.model_dump(mode="json")
        payload["results"][0].pop("body_preview")
        payload["results"][0]["body_text"] = "Legacy cached body"

        restored = _deserialize_response(json.dumps(payload))

        assert restored.results[0].body_preview == "Legacy cached body"

    def test_empty_results_serialization(self):
        """Serialization should handle empty results."""
        response = SearchResponse(
            search_id=uuid4(),
            results=[],
            total=0,
            total_is_capped=False,
            page=1,
            page_size=20,
            has_more=False,
            query="no results query",
            filters=SearchFilters(),
        )

        serialized = _serialize_response(response)
        restored = _deserialize_response(serialized)

        assert len(restored.results) == 0
        assert restored.total == 0

    def test_roundtrip_preserves_total_is_capped(self, sample_response):
        """Serialization should preserve capped-total semantics."""
        sample_response.total_is_capped = True

        serialized = _serialize_response(sample_response)
        restored = _deserialize_response(serialized)

        assert restored.total_is_capped is True

    def test_multiple_results_serialization(self):
        """Serialization should handle multiple results."""
        items = [
            SearchResultItem(
                node_id=f"node_{i}",
                title=f"Issue {i}",
                body_preview=f"Body {i}",
                labels=[],
                q_score=0.5 + (i * 0.1),
                repo_name=f"repo_{i}",
                primary_language="Python",
                github_created_at=datetime.now(UTC),
                rrf_score=0.03 - (i * 0.01),
            )
            for i in range(3)
        ]

        response = SearchResponse(
            search_id=uuid4(),
            results=items,
            total=3,
            total_is_capped=False,
            page=1,
            page_size=20,
            has_more=False,
            query="test",
            filters=SearchFilters(),
        )

        serialized = _serialize_response(response)
        restored = _deserialize_response(serialized)

        assert len(restored.results) == 3
        for i, result in enumerate(restored.results):
            assert result.node_id == f"node_{i}"


class TestCacheKeyGeneration:
    """Tests for cache key generation via SearchRequest."""

    def test_cache_key_is_sha256(self):
        """Cache key should be a SHA256 hash (64 hex chars)."""
        request = SearchRequest(query="test")
        key = request.cache_key()

        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_same_request_same_key(self):
        """Identical requests should produce identical cache keys."""
        request1 = SearchRequest(
            query="test query",
            filters=SearchFilters(languages=["Python"]),
            page=2,
            page_size=10,
        )
        request2 = SearchRequest(
            query="test query",
            filters=SearchFilters(languages=["Python"]),
            page=2,
            page_size=10,
        )

        assert request1.cache_key() == request2.cache_key()


class _FakeRedis:
    def __init__(self):
        self._kv: dict[str, tuple[int, str]] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._kv[key] = (ttl, value)

    async def get(self, key: str):
        item = self._kv.get(key)
        return item[1] if item else None


class TestSearchContextCaching:
    @pytest.mark.asyncio
    async def test_cache_search_context_writes_expected_key_and_payload(self):
        fake_redis = _FakeRedis()

        with patch("gim_backend.services.search_cache.get_redis", new=AsyncMock(return_value=fake_redis)):
            search_id = uuid4()
            await cache_search_context(
                search_id=search_id,
                query_text="python error",
                filters_json={"languages": ["Python"], "labels": [], "repos": []},
                result_count=123,
                page=2,
                page_size=20,
                page_node_ids=["n1", "n2"],
            )

        key = f"{CONTEXT_PREFIX}{search_id}"
        assert key in fake_redis._kv

        ttl, raw = fake_redis._kv[key]
        assert ttl == CACHE_TTL_SECONDS

        parsed = json.loads(raw)
        assert parsed["query_text"] == "python error"
        assert parsed["filters_json"]["languages"] == ["Python"]
        assert parsed["result_count"] == 123
        assert parsed["page"] == 2
        assert parsed["page_size"] == 20
        assert parsed["page_node_ids"] == ["n1", "n2"]

    @pytest.mark.asyncio
    async def test_get_cached_search_context_returns_parsed_dict(self):
        fake_redis = _FakeRedis()
        search_id = uuid4()
        key = f"{CONTEXT_PREFIX}{search_id}"
        fake_redis._kv[key] = (
            CACHE_TTL_SECONDS,
            json.dumps(
                {
                    "query_text": "q",
                    "filters_json": {"languages": [], "labels": [], "repos": []},
                    "result_count": 5,
                    "page": 1,
                    "page_size": 20,
                    "page_node_ids": ["issue_1", "issue_2"],
                }
            ),
        )

        with patch("gim_backend.services.search_cache.get_redis", new=AsyncMock(return_value=fake_redis)):
            ctx = await get_cached_search_context(search_id)

        assert ctx is not None
        assert ctx["query_text"] == "q"
        assert ctx["result_count"] == 5

    @pytest.mark.asyncio
    async def test_get_cached_search_context_returns_none_when_redis_unavailable(self):
        with patch("gim_backend.services.search_cache.get_redis", new=AsyncMock(return_value=None)):
            ctx = await get_cached_search_context(uuid4())
        assert ctx is None

    def test_different_query_different_key(self):
        """Different queries should produce different cache keys."""
        request1 = SearchRequest(query="query one")
        request2 = SearchRequest(query="query two")

        assert request1.cache_key() != request2.cache_key()

    def test_different_page_different_key(self):
        """Different pages should produce different cache keys."""
        request1 = SearchRequest(query="test", page=1)
        request2 = SearchRequest(query="test", page=2)

        assert request1.cache_key() != request2.cache_key()

    def test_different_page_size_different_key(self):
        """Different page sizes should produce different cache keys."""
        request1 = SearchRequest(query="test", page_size=10)
        request2 = SearchRequest(query="test", page_size=20)

        assert request1.cache_key() != request2.cache_key()

    def test_different_filters_different_key(self):
        """Different filters should produce different cache keys."""
        request1 = SearchRequest(
            query="test",
            filters=SearchFilters(languages=["Python"]),
        )
        request2 = SearchRequest(
            query="test",
            filters=SearchFilters(languages=["Rust"]),
        )

        assert request1.cache_key() != request2.cache_key()

    def test_filter_order_does_not_affect_key(self):
        """Filter order should not affect cache key (sorted internally)."""
        request1 = SearchRequest(
            query="test",
            filters=SearchFilters(languages=["Python", "Rust"]),
        )
        request2 = SearchRequest(
            query="test",
            filters=SearchFilters(languages=["Rust", "Python"]),
        )

        assert request1.cache_key() == request2.cache_key()


class TestCachedSearchReadBehavior:
    @pytest.mark.asyncio
    async def test_get_cached_search_returns_none_for_malformed_cached_payload(self):
        fake_redis = _FakeRedis()
        request = SearchRequest(query="test")
        fake_redis._kv[f"{CACHE_PREFIX}{request.cache_key()}"] = (CACHE_TTL_SECONDS, '{"results": "bad"}')

        with patch("gim_backend.services.search_cache.get_redis", new=AsyncMock(return_value=fake_redis)):
            result = await get_cached_search(request)

        assert result is None

    def test_normalize_cached_response_payload_rejects_non_object(self):
        with pytest.raises(ValueError):
            _normalize_cached_response_payload(["not", "an", "object"])
