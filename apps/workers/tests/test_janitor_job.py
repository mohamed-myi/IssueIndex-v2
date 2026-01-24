"""Unit tests for janitor job orchestration"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Remove global sys.modules patching
# sys.modules["ingestion"] = MagicMock()
# sys.modules["ingestion.janitor"] = MagicMock()
# sys.modules["session"] = MagicMock()

@pytest.fixture(autouse=True)
def mock_dependencies():
    """Mock external dependencies for all tests in this module"""
    with patch.dict(sys.modules, {
        "ingestion": MagicMock(),
        "ingestion.janitor": MagicMock(),
        "session": MagicMock()
    }):
        yield


class TestJanitorJobExecution:
    @pytest.mark.asyncio
    async def test_returns_stats_dict(self):
        """Should return dict with deleted_count and remaining_count"""
        mock_janitor = MagicMock()
        mock_janitor.execute_pruning = AsyncMock(return_value={
            "deleted_count": 20,
            "remaining_count": 80,
        })
        
        mock_session = MagicMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)
        
        from jobs import janitor_job
        janitor_job.async_session_factory = MagicMock(return_value=mock_session_factory)
        janitor_job.Janitor = MagicMock(return_value=mock_janitor)
        
        result = await janitor_job.run_janitor_job()
        
        assert "deleted_count" in result
        assert "remaining_count" in result
        assert result["deleted_count"] == 20
        assert result["remaining_count"] == 80

    @pytest.mark.asyncio
    async def test_handles_empty_table(self):
        """Should handle case where no issues exist"""
        mock_janitor = MagicMock()
        mock_janitor.execute_pruning = AsyncMock(return_value={
            "deleted_count": 0,
            "remaining_count": 0,
        })
        
        mock_session = MagicMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)
        
        from jobs import janitor_job
        janitor_job.async_session_factory = MagicMock(return_value=mock_session_factory)
        janitor_job.Janitor = MagicMock(return_value=mock_janitor)
        
        result = await janitor_job.run_janitor_job()
        
        assert result["deleted_count"] == 0
        assert result["remaining_count"] == 0

    @pytest.mark.asyncio
    async def test_janitor_instantiated_with_session(self):
        """Janitor should be instantiated with database session"""
        mock_janitor_class = MagicMock()
        mock_janitor_instance = MagicMock()
        mock_janitor_instance.execute_pruning = AsyncMock(return_value={
            "deleted_count": 10,
            "remaining_count": 90,
        })
        mock_janitor_class.return_value = mock_janitor_instance
        
        mock_session = MagicMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)
        
        from jobs import janitor_job
        janitor_job.async_session_factory = MagicMock(return_value=mock_session_factory)
        janitor_job.Janitor = mock_janitor_class
        
        await janitor_job.run_janitor_job()
        
        mock_janitor_class.assert_called_once_with(mock_session)


class TestJanitorJobErrors:
    @pytest.mark.asyncio
    async def test_propagates_database_error(self):
        """Database errors should propagate up"""
        mock_janitor = MagicMock()
        mock_janitor.execute_pruning = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        
        mock_session = MagicMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)
        
        from jobs import janitor_job
        janitor_job.async_session_factory = MagicMock(return_value=mock_session_factory)
        janitor_job.Janitor = MagicMock(return_value=mock_janitor)
        
        with pytest.raises(Exception, match="Database connection failed"):
            await janitor_job.run_janitor_job()

    @pytest.mark.asyncio
    async def test_propagates_percentile_error(self):
        """SQL errors from PERCENTILE_CONT should propagate"""
        mock_janitor = MagicMock()
        mock_janitor.execute_pruning = AsyncMock(
            side_effect=Exception("PERCENTILE_CONT requires numeric input")
        )
        
        mock_session = MagicMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)
        
        from jobs import janitor_job
        janitor_job.async_session_factory = MagicMock(return_value=mock_session_factory)
        janitor_job.Janitor = MagicMock(return_value=mock_janitor)
        
        with pytest.raises(Exception, match="PERCENTILE_CONT"):
            await janitor_job.run_janitor_job()


class TestJanitorJobStats:
    @pytest.mark.asyncio
    async def test_returns_exact_pruning_stats(self):
        """Should return exact stats from Janitor.execute_pruning"""
        mock_janitor = MagicMock()
        mock_janitor.execute_pruning = AsyncMock(return_value={
            "deleted_count": 42,
            "remaining_count": 158,
        })
        
        mock_session = MagicMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)
        
        from jobs import janitor_job
        janitor_job.async_session_factory = MagicMock(return_value=mock_session_factory)
        janitor_job.Janitor = MagicMock(return_value=mock_janitor)
        
        result = await janitor_job.run_janitor_job()
        
        assert result["deleted_count"] == 42
        assert result["remaining_count"] == 158
