"""Query-count regression tests for feed_service pagination."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gim_backend.services.feed_service import (
    _build_feed_filters,
    _get_personalized_feed,
    _get_trending_feed,
    _row_to_feed_item,
)


def _result_with_rows(rows):
    result = MagicMock()
    result.fetchall.return_value = rows
    return result


def _scalar_result(value):
    result = MagicMock()
    result.scalar.return_value = value
    return result


class TestTrendingFeedQueries:
    @pytest.mark.asyncio
    async def test_uses_single_query_for_non_empty_first_page(self):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=_result_with_rows(
                [
                    SimpleNamespace(
                        node_id="ISSUE_1",
                        title="Fix bug",
                        body_text="Body",
                        github_url="https://github.com/o/r/issues/1",
                        labels=["bug"],
                        q_score=0.9,
                        github_created_at=datetime(2026, 1, 1, tzinfo=UTC),
                        repo_name="o/r",
                        primary_language="Python",
                        repo_topics=["backend"],
                        total_count=1,
                    )
                ]
            )
        )

        page = await _get_trending_feed(mock_db, page=1, page_size=20)

        assert mock_db.execute.await_count == 1
        assert page.total == 1
        assert len(page.results) == 1
        assert page.has_more is False

    @pytest.mark.asyncio
    async def test_falls_back_to_count_for_empty_deep_page(self):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            side_effect=[
                _result_with_rows([]),
                _scalar_result(42),
            ]
        )

        page = await _get_trending_feed(mock_db, page=5, page_size=20)

        assert mock_db.execute.await_count == 2
        assert page.results == []
        assert page.total == 42
        assert page.has_more is False


class TestPersonalizedFeedQueries:
    @pytest.mark.asyncio
    async def test_uses_single_query_for_non_empty_first_page(self):
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(
            return_value=_result_with_rows(
                [
                    SimpleNamespace(
                        node_id="ISSUE_1",
                        title="Improve search",
                        body_text="Body",
                        github_url="https://github.com/o/r/issues/2",
                        labels=["enhancement"],
                        q_score=0.95,
                        github_created_at=datetime(2026, 1, 1, tzinfo=UTC),
                        repo_name="o/r",
                        primary_language="TypeScript",
                        repo_topics=["web"],
                        similarity_score=0.88,
                        freshness=0.91,
                        final_score=1.23,
                        total_count=7,
                    )
                ]
            )
        )

        mock_profile = SimpleNamespace(
            preferred_languages=["TypeScript"],
            min_heat_threshold=0.6,
        )
        mock_settings = SimpleNamespace(
            feed_freshness_half_life_days=7.0,
            feed_freshness_floor=0.2,
            feed_freshness_weight=0.25,
            feed_debug_freshness=False,
        )

        with (
            patch("gim_backend.services.feed_service.get_settings", return_value=mock_settings),
            patch(
                "gim_backend.services.feed_service.compute_why_this",
                return_value=[],
            ),
        ):
            page = await _get_personalized_feed(
                db=mock_db,
                profile=mock_profile,
                combined_vector=[0.1] * 256,
                preferred_languages=["TypeScript"],
                min_heat_threshold=0.6,
                page=1,
                page_size=20,
            )

        assert mock_db.execute.await_count == 1
        assert page.total == 7
        assert len(page.results) == 1
        assert page.is_personalized is True


class TestFeedRowMapping:
    def test_maps_trending_row_without_personalized_scores(self):
        row = SimpleNamespace(
            node_id="ISSUE_1",
            title="Fix bug",
            body_text="Body text",
            github_url="https://github.com/o/r/issues/1",
            labels=["bug"],
            q_score=0.9,
            repo_name="o/r",
            primary_language="Python",
            repo_topics=["backend"],
            github_created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        item = _row_to_feed_item(row, include_personalized_scores=False)

        assert item.node_id == "ISSUE_1"
        assert item.body_preview == "Body text"
        assert item.similarity_score is None
        assert item.freshness is None
        assert item.final_score is None

    def test_maps_personalized_row_with_scores(self):
        row = SimpleNamespace(
            node_id="ISSUE_2",
            title="Improve search",
            body_text="Body text",
            github_url="https://github.com/o/r/issues/2",
            labels=["enhancement"],
            q_score=0.95,
            repo_name="o/r",
            primary_language="TypeScript",
            repo_topics=["web"],
            github_created_at=datetime(2026, 1, 1, tzinfo=UTC),
            similarity_score=0.88,
            freshness=0.91,
            final_score=1.23,
        )

        item = _row_to_feed_item(row, include_personalized_scores=True)

        assert item.similarity_score == 0.88
        assert item.freshness == 0.91
        assert item.final_score == 1.23


class TestFeedFilterBuilder:
    def test_builds_shared_filters_for_trending_and_personalized(self):
        where_clause, params = _build_feed_filters(
            min_q_score=0.6,
            languages=["Python"],
            labels=["bug"],
            repos=["o/r"],
            require_embedding=True,
        )

        assert "i.embedding IS NOT NULL" in where_clause
        assert "i.state = 'open'" in where_clause
        assert "i.q_score >= :min_q_score" in where_clause
        assert "r.primary_language = ANY(:langs)" in where_clause
        assert "i.labels && :labels" in where_clause
        assert "r.full_name = ANY(:repos)" in where_clause
        assert params["min_q_score"] == 0.6
        assert params["langs"] == ["Python"]
        assert params["labels"] == ["bug"]
        assert params["repos"] == ["o/r"]
