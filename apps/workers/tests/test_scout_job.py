"""Unit tests for Scout job (formerly Collector job)"""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRunScoutJob:
    """Tests for run_scout_job function"""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with required values."""
        settings = MagicMock()
        settings.git_token = "test-token"
        settings.pubsub_project = "test-project"
        settings.pubsub_repo_topic = "issueindex-repo-tasks"
        return settings

    @pytest.fixture
    def mock_repo(self):
        """Create a mock RepositoryData."""
        repo = MagicMock()
        repo.node_id = "R_123"
        repo.full_name = "owner/repo"
        repo.primary_language = "Python"
        repo.stargazer_count = 1000
        repo.issue_count_open = 50
        repo.topics = ["topic1"]
        return repo

    @pytest.mark.asyncio
    async def test_scout_job_returns_stats(self, mock_settings, mock_repo):
        """Should return stats dict with repos_discovered and repo_tasks_published"""
        # Import the module first to ensure it's loaded
        collector_job = importlib.import_module("jobs.collector_job")
        
        # Arrange
        with patch.object(collector_job, "get_settings", return_value=mock_settings), \
             patch.object(collector_job, "GitHubGraphQLClient") as mock_client_cls, \
             patch.object(collector_job, "Scout") as mock_scout_cls, \
             patch.object(collector_job, "async_session_factory") as mock_session_factory, \
             patch.object(collector_job, "StreamingPersistence") as mock_persistence_cls, \
             patch.object(collector_job, "RepoPubSubProducer") as mock_producer_cls:

            # Setup mocks
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            mock_scout = MagicMock()
            mock_scout.discover_repositories = AsyncMock(return_value=[mock_repo, mock_repo])
            mock_scout_cls.return_value = mock_scout

            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            mock_persistence = MagicMock()
            mock_persistence.upsert_repositories = AsyncMock(return_value=2)
            mock_persistence_cls.return_value = mock_persistence

            mock_producer = MagicMock()
            mock_producer.publish_repos = AsyncMock(return_value=2)
            mock_producer_cls.return_value = mock_producer

            # Act
            result = await collector_job.run_scout_job()

            # Assert
            assert result["repos_discovered"] == 2
            assert result["repo_tasks_published"] == 2
            assert "duration_s" in result

    @pytest.mark.asyncio
    async def test_scout_job_handles_no_repos(self, mock_settings):
        """Should return zeros when no repos discovered"""
        collector_job = importlib.import_module("jobs.collector_job")
        
        # Arrange
        with patch.object(collector_job, "get_settings", return_value=mock_settings), \
             patch.object(collector_job, "GitHubGraphQLClient") as mock_client_cls, \
             patch.object(collector_job, "Scout") as mock_scout_cls:

            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            mock_scout = MagicMock()
            mock_scout.discover_repositories = AsyncMock(return_value=[])
            mock_scout_cls.return_value = mock_scout

            # Act
            result = await collector_job.run_scout_job()

            # Assert
            assert result["repos_discovered"] == 0
            assert result["repo_tasks_published"] == 0

    @pytest.mark.asyncio
    async def test_scout_job_requires_git_token(self):
        """Should raise ValueError if GIT_TOKEN not set"""
        collector_job = importlib.import_module("jobs.collector_job")
        
        # Arrange
        mock_settings = MagicMock()
        mock_settings.git_token = ""
        mock_settings.pubsub_project = "test-project"

        with patch.object(collector_job, "get_settings", return_value=mock_settings):
            # Act & Assert
            with pytest.raises(ValueError, match="GIT_TOKEN"):
                await collector_job.run_scout_job()

    @pytest.mark.asyncio
    async def test_scout_job_requires_pubsub_project(self):
        """Should raise ValueError if PUBSUB_PROJECT not set"""
        collector_job = importlib.import_module("jobs.collector_job")
        
        # Arrange
        mock_settings = MagicMock()
        mock_settings.git_token = "test-token"
        mock_settings.pubsub_project = ""

        with patch.object(collector_job, "get_settings", return_value=mock_settings):
            # Act & Assert
            with pytest.raises(ValueError, match="PUBSUB_PROJECT"):
                await collector_job.run_scout_job()

    @pytest.mark.asyncio
    async def test_scout_job_closes_producer(self, mock_settings, mock_repo):
        """Should close producer even on success"""
        collector_job = importlib.import_module("jobs.collector_job")
        
        # Arrange
        with patch.object(collector_job, "get_settings", return_value=mock_settings), \
             patch.object(collector_job, "GitHubGraphQLClient") as mock_client_cls, \
             patch.object(collector_job, "Scout") as mock_scout_cls, \
             patch.object(collector_job, "async_session_factory") as mock_session_factory, \
             patch.object(collector_job, "StreamingPersistence") as mock_persistence_cls, \
             patch.object(collector_job, "RepoPubSubProducer") as mock_producer_cls:

            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client

            mock_scout = MagicMock()
            mock_scout.discover_repositories = AsyncMock(return_value=[mock_repo])
            mock_scout_cls.return_value = mock_scout

            mock_session = AsyncMock()
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            mock_persistence = MagicMock()
            mock_persistence.upsert_repositories = AsyncMock(return_value=1)
            mock_persistence_cls.return_value = mock_persistence

            mock_producer = MagicMock()
            mock_producer.publish_repos = AsyncMock(return_value=1)
            mock_producer_cls.return_value = mock_producer

            # Act
            await collector_job.run_scout_job()

            # Assert
            mock_producer.close.assert_called_once()


class TestBackwardsCompatibility:
    """Tests for backwards compatibility alias"""

    @pytest.mark.asyncio
    async def test_run_collector_job_calls_run_scout_job(self):
        """run_collector_job should call run_scout_job"""
        collector_job = importlib.import_module("jobs.collector_job")
        
        # Arrange
        with patch.object(collector_job, "run_scout_job") as mock_scout_job:
            mock_scout_job.return_value = {"repos_discovered": 5, "repo_tasks_published": 5}

            # Act
            result = await collector_job.run_collector_job()

            # Assert
            mock_scout_job.assert_called_once()
            assert result["repos_discovered"] == 5
