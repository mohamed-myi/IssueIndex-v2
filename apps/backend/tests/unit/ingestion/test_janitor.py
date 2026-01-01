"""Unit tests for Janitor set-based pruning"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, call

# Mock sqlalchemy before importing janitor
sys.modules["sqlalchemy"] = MagicMock()
mock_text = MagicMock()
sys.modules["sqlalchemy"].text = mock_text
sys.modules["sqlmodel"] = MagicMock()
sys.modules["sqlmodel.ext"] = MagicMock()
sys.modules["sqlmodel.ext.asyncio"] = MagicMock()
sys.modules["sqlmodel.ext.asyncio.session"] = MagicMock()

from src.ingestion.janitor import Janitor


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def janitor(mock_session):
    return Janitor(session=mock_session)


class TestJanitorConfig:
    def test_prune_percentile_is_20_percent(self):
        assert Janitor.PRUNE_PERCENTILE == 0.2


class TestGetTableStats:
    async def test_returns_row_count(self, janitor, mock_session):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(cnt=100)
        mock_session.execute.return_value = mock_result

        stats = await janitor._get_table_stats()

        assert stats["row_count"] == 100

    async def test_returns_zero_for_empty_table(self, janitor, mock_session):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(cnt=0)
        mock_session.execute.return_value = mock_result

        stats = await janitor._get_table_stats()

        assert stats["row_count"] == 0

    async def test_returns_zero_when_fetchone_is_none(self, janitor, mock_session):
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        stats = await janitor._get_table_stats()

        assert stats["row_count"] == 0


class TestDeleteBottomPercentile:
    async def test_executes_delete_query(self, janitor, mock_session):
        mock_result = MagicMock()
        mock_result.rowcount = 20
        mock_session.execute.return_value = mock_result

        deleted = await janitor._delete_bottom_percentile()

        assert deleted == 20
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

    async def test_passes_percentile_parameter(self, janitor, mock_session):
        mock_result = MagicMock()
        mock_result.rowcount = 10
        mock_session.execute.return_value = mock_result

        await janitor._delete_bottom_percentile()

        call_args = mock_session.execute.call_args
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("parameters", {})
        assert params.get("percentile") == 0.2

    async def test_returns_zero_when_nothing_deleted(self, janitor, mock_session):
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result

        deleted = await janitor._delete_bottom_percentile()

        assert deleted == 0


class TestExecutePruning:
    async def test_returns_stats_dict(self, janitor, mock_session):
        # Setup: table has 100 rows, delete returns 20
        stats_result = MagicMock()
        stats_result.fetchone.return_value = MagicMock(cnt=100)

        delete_result = MagicMock()
        delete_result.rowcount = 20

        after_stats_result = MagicMock()
        after_stats_result.fetchone.return_value = MagicMock(cnt=80)

        mock_session.execute.side_effect = [
            stats_result,   # _get_table_stats before
            delete_result,  # _delete_bottom_percentile
            after_stats_result,  # _get_table_stats after
        ]

        result = await janitor.execute_pruning()

        assert result["deleted_count"] == 20
        assert result["remaining_count"] == 80

    async def test_handles_empty_table(self, janitor, mock_session):
        stats_result = MagicMock()
        stats_result.fetchone.return_value = MagicMock(cnt=0)
        mock_session.execute.return_value = stats_result

        result = await janitor.execute_pruning()

        assert result["deleted_count"] == 0
        assert result["remaining_count"] == 0
        # Should only call stats once, not attempt delete
        assert mock_session.execute.call_count == 1

    async def test_calls_methods_in_order(self, janitor, mock_session):
        stats_result = MagicMock()
        stats_result.fetchone.return_value = MagicMock(cnt=50)

        delete_result = MagicMock()
        delete_result.rowcount = 10

        mock_session.execute.side_effect = [
            stats_result,   # before
            delete_result,  # delete
            stats_result,   # after (reuse same mock)
        ]

        await janitor.execute_pruning()

        # Should be called 3 times: stats, delete, stats
        assert mock_session.execute.call_count == 3


class TestEdgeCases:
    async def test_single_row_table(self, janitor, mock_session):
        """Single row table: percentile calculation should still work"""
        stats_result = MagicMock()
        stats_result.fetchone.return_value = MagicMock(cnt=1)

        delete_result = MagicMock()
        delete_result.rowcount = 0  # Nothing deleted (only row is above P20)

        after_stats_result = MagicMock()
        after_stats_result.fetchone.return_value = MagicMock(cnt=1)

        mock_session.execute.side_effect = [
            stats_result,
            delete_result,
            after_stats_result,
        ]

        result = await janitor.execute_pruning()

        assert result["deleted_count"] == 0
        assert result["remaining_count"] == 1

    async def test_all_same_survival_score(self, janitor, mock_session):
        """
        When all issues have identical survival_score,
        PERCENTILE_CONT returns that score, and nothing is deleted
        since no value is strictly less than the threshold.
        """
        stats_result = MagicMock()
        stats_result.fetchone.return_value = MagicMock(cnt=100)

        delete_result = MagicMock()
        delete_result.rowcount = 0  # All equal, nothing < threshold

        after_stats_result = MagicMock()
        after_stats_result.fetchone.return_value = MagicMock(cnt=100)

        mock_session.execute.side_effect = [
            stats_result,
            delete_result,
            after_stats_result,
        ]

        result = await janitor.execute_pruning()

        assert result["deleted_count"] == 0
        assert result["remaining_count"] == 100

    async def test_custom_percentile(self, mock_session):
        """Verify percentile can be customized via class attribute"""
        janitor = Janitor(session=mock_session)
        janitor.PRUNE_PERCENTILE = 0.3  # Custom 30%

        mock_result = MagicMock()
        mock_result.rowcount = 30
        mock_session.execute.return_value = mock_result

        await janitor._delete_bottom_percentile()

        call_args = mock_session.execute.call_args
        params = call_args[0][1]
        assert params.get("percentile") == 0.3

