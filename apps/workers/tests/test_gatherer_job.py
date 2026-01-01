"""Unit tests for gatherer job orchestration"""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Mock external dependencies before importing the module
sys.modules["core"] = MagicMock()
sys.modules["core.config"] = MagicMock()
sys.modules["ingestion"] = MagicMock()
sys.modules["ingestion.embeddings"] = MagicMock()
sys.modules["ingestion.gatherer"] = MagicMock()
sys.modules["ingestion.github_client"] = MagicMock()
sys.modules["ingestion.persistence"] = MagicMock()
sys.modules["ingestion.scout"] = MagicMock()
sys.modules["session"] = MagicMock()


class TestGathererJobValidation:
    @pytest.mark.asyncio
    async def test_raises_without_git_token(self):
        """Should raise ValueError if GIT_TOKEN is missing"""
        # Create mock settings
        mock_settings = MagicMock()
        mock_settings.git_token = ""
        mock_get_settings = MagicMock(return_value=mock_settings)
        
        # Patch at module level
        with patch.dict(sys.modules, {
            "core.config": MagicMock(get_settings=mock_get_settings),
        }):
            # Import after mocking
            from jobs import gatherer_job
            gatherer_job.get_settings = mock_get_settings
            
            with pytest.raises(ValueError, match="GIT_TOKEN"):
                await gatherer_job.run_gatherer_job()

    @pytest.mark.asyncio
    async def test_valid_token_proceeds(self):
        """Should proceed with valid git_token"""
        mock_settings = MagicMock()
        mock_settings.git_token = "ghp_valid_token"
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_scout = MagicMock()
        mock_scout.discover_repositories = AsyncMock(return_value=[])
        
        from jobs import gatherer_job
        gatherer_job.get_settings = MagicMock(return_value=mock_settings)
        gatherer_job.GitHubGraphQLClient = MagicMock(return_value=mock_client)
        gatherer_job.Scout = MagicMock(return_value=mock_scout)
        
        result = await gatherer_job.run_gatherer_job()
        
        assert result["repos_discovered"] == 0


class TestGathererJobExecution:
    @pytest.mark.asyncio
    async def test_returns_stats_dict_empty_repos(self):
        """Should return dict with zeros when Scout finds no repos"""
        mock_settings = MagicMock()
        mock_settings.git_token = "ghp_test_token"
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_scout = MagicMock()
        mock_scout.discover_repositories = AsyncMock(return_value=[])
        
        from jobs import gatherer_job
        gatherer_job.get_settings = MagicMock(return_value=mock_settings)
        gatherer_job.GitHubGraphQLClient = MagicMock(return_value=mock_client)
        gatherer_job.Scout = MagicMock(return_value=mock_scout)
        
        result = await gatherer_job.run_gatherer_job()
        
        assert "repos_discovered" in result
        assert "issues_persisted" in result
        assert result["repos_discovered"] == 0
        assert result["issues_persisted"] == 0

    @pytest.mark.asyncio
    async def test_pipeline_runs_with_repos(self):
        """Should run full pipeline when repos are found"""
        mock_settings = MagicMock()
        mock_settings.git_token = "ghp_test_token"
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_repo = MagicMock()
        mock_repo.node_id = "R_123"
        mock_repo.full_name = "test/repo"
        
        mock_scout = MagicMock()
        mock_scout.discover_repositories = AsyncMock(return_value=[mock_repo])
        
        mock_persistence = MagicMock()
        mock_persistence.upsert_repositories = AsyncMock(return_value=1)
        mock_persistence.persist_stream = AsyncMock(return_value=50)
        
        mock_embedder = MagicMock()
        mock_embedder.close = MagicMock()
        
        mock_gatherer = MagicMock()
        
        async def empty_gen():
            return
            yield
        
        mock_gatherer.harvest_issues = MagicMock(return_value=empty_gen())
        
        mock_session = MagicMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)
        
        async def mock_embed(*args, **kwargs):
            return
            yield
        
        from jobs import gatherer_job
        gatherer_job.get_settings = MagicMock(return_value=mock_settings)
        gatherer_job.GitHubGraphQLClient = MagicMock(return_value=mock_client)
        gatherer_job.Scout = MagicMock(return_value=mock_scout)
        gatherer_job.async_session_factory = MagicMock(return_value=mock_session_factory)
        gatherer_job.StreamingPersistence = MagicMock(return_value=mock_persistence)
        gatherer_job.Gatherer = MagicMock(return_value=mock_gatherer)
        gatherer_job.NomicEmbedder = MagicMock(return_value=mock_embedder)
        gatherer_job.embed_issue_stream = mock_embed
        
        result = await gatherer_job.run_gatherer_job()
        
        assert result["repos_discovered"] == 1
        assert result["issues_persisted"] == 50


class TestEmbedderLifecycle:
    @pytest.mark.asyncio
    async def test_embedder_closed_on_success(self):
        """Embedder.close() should be called after successful run"""
        mock_settings = MagicMock()
        mock_settings.git_token = "ghp_test_token"
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_repo = MagicMock()
        mock_scout = MagicMock()
        mock_scout.discover_repositories = AsyncMock(return_value=[mock_repo])
        
        mock_persistence = MagicMock()
        mock_persistence.upsert_repositories = AsyncMock(return_value=1)
        mock_persistence.persist_stream = AsyncMock(return_value=10)
        
        mock_embedder = MagicMock()
        mock_embedder.close = MagicMock()
        
        mock_gatherer = MagicMock()
        
        async def empty_gen():
            return
            yield
        
        mock_gatherer.harvest_issues = MagicMock(return_value=empty_gen())
        
        mock_session = MagicMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)
        
        async def mock_embed(*args, **kwargs):
            return
            yield
        
        from jobs import gatherer_job
        gatherer_job.get_settings = MagicMock(return_value=mock_settings)
        gatherer_job.GitHubGraphQLClient = MagicMock(return_value=mock_client)
        gatherer_job.Scout = MagicMock(return_value=mock_scout)
        gatherer_job.async_session_factory = MagicMock(return_value=mock_session_factory)
        gatherer_job.StreamingPersistence = MagicMock(return_value=mock_persistence)
        gatherer_job.Gatherer = MagicMock(return_value=mock_gatherer)
        gatherer_job.NomicEmbedder = MagicMock(return_value=mock_embedder)
        gatherer_job.embed_issue_stream = mock_embed
        
        await gatherer_job.run_gatherer_job()
        
        mock_embedder.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_embedder_closed_on_error(self):
        """Embedder.close() should be called even if pipeline raises"""
        mock_settings = MagicMock()
        mock_settings.git_token = "ghp_test_token"
        
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        
        mock_repo = MagicMock()
        mock_scout = MagicMock()
        mock_scout.discover_repositories = AsyncMock(return_value=[mock_repo])
        
        mock_persistence = MagicMock()
        mock_persistence.upsert_repositories = AsyncMock(return_value=1)
        mock_persistence.persist_stream = AsyncMock(side_effect=Exception("DB Error"))
        
        mock_embedder = MagicMock()
        mock_embedder.close = MagicMock()
        
        mock_gatherer = MagicMock()
        
        async def empty_gen():
            return
            yield
        
        mock_gatherer.harvest_issues = MagicMock(return_value=empty_gen())
        
        mock_session = MagicMock()
        mock_session_factory = MagicMock()
        mock_session_factory.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_factory.__aexit__ = AsyncMock(return_value=None)
        
        async def mock_embed(*args, **kwargs):
            return
            yield
        
        from jobs import gatherer_job
        gatherer_job.get_settings = MagicMock(return_value=mock_settings)
        gatherer_job.GitHubGraphQLClient = MagicMock(return_value=mock_client)
        gatherer_job.Scout = MagicMock(return_value=mock_scout)
        gatherer_job.async_session_factory = MagicMock(return_value=mock_session_factory)
        gatherer_job.StreamingPersistence = MagicMock(return_value=mock_persistence)
        gatherer_job.Gatherer = MagicMock(return_value=mock_gatherer)
        gatherer_job.NomicEmbedder = MagicMock(return_value=mock_embedder)
        gatherer_job.embed_issue_stream = mock_embed
        
        with pytest.raises(Exception, match="DB Error"):
            await gatherer_job.run_gatherer_job()
        
        # Embedder should still be closed via finally block
        mock_embedder.close.assert_called_once()
