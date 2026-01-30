"""Unit tests for Collector Job sharding logic"""

from unittest.mock import MagicMock, patch, AsyncMock
import pytest
from datetime import datetime, timezone
import logging

# Filter out unrelated logs
logging.basicConfig(level=logging.ERROR)

@pytest.fixture
def mock_dependencies(monkeypatch):
    """Mock external dependencies"""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    
    mock_gh_client_cls = MagicMock(return_value=mock_client)
    monkeypatch.setattr("gim_workers.jobs.collector_job.GitHubGraphQLClient", mock_gh_client_cls)
    
    mock_scout = AsyncMock()
    monkeypatch.setattr("gim_workers.jobs.collector_job.Scout", MagicMock(return_value=mock_scout))
    
    # Mock settings
    mock_settings = MagicMock()
    mock_settings.git_token = "fake-token"
    mock_settings.pubsub_project = "fake-project"
    mock_settings.gatherer_concurrency = 2
    mock_settings.max_issues_per_repo = 10
    monkeypatch.setattr("gim_workers.jobs.collector_job.get_settings", MagicMock(return_value=mock_settings))
    
    # Mock persistence
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    monkeypatch.setattr("gim_workers.jobs.collector_job.async_session_factory", MagicMock(return_value=mock_session))
    
    mock_persistence = AsyncMock()
    mock_persistence.upsert_repositories.return_value = 5
    monkeypatch.setattr("gim_workers.jobs.collector_job.StreamingPersistence", MagicMock(return_value=mock_persistence))

    # Mock producer
    mock_producer = AsyncMock()
    mock_producer.publish_stream.return_value = 10
    monkeypatch.setattr("gim_workers.jobs.collector_job.IssuePubSubProducer", MagicMock(return_value=mock_producer))

    return {
        "client": mock_client,
        "scout": mock_scout,
        "persistence": mock_persistence,
        "producer": mock_producer
    }

@pytest.mark.asyncio
async def test_sharding_filtering(mock_dependencies):
    """Verify that only repositories matching the current shard are processed"""
    from gim_workers.jobs.collector_job import run_collector_job
    
    # Create test repos with known IDs
    # Create mock repos with unique IDs
    
    mock_repos = []
    for i in range(100):
        repo = MagicMock()
        repo.node_id = f"repo-{i}" 
        mock_repos.append(repo)
        
    mock_dependencies["scout"].discover_repositories.return_value = mock_repos
    
    # Run the job
    with patch("gim_workers.jobs.collector_job.Gatherer") as MockGatherer:
        mock_gatherer_instance = MockGatherer.return_value
        mock_gatherer_instance.harvest_issues.return_value = [] # Empty stream
        
        await run_collector_job()
        
        # Verify Gatherer was initialized
        assert MockGatherer.called
        
        # Get the filtered repos passed to harvest_issues
        call_args = mock_gatherer_instance.harvest_issues.call_args[0]
        filtered_repos = call_args[0]
        
        # Assert sharding happened (we shouldn't process all 100)
        assert len(filtered_repos) < 100
        assert len(filtered_repos) > 0
        
        # Verify shard consistency
        # Calculate current shard to verify logic
        from binascii import crc32
        current_shard = datetime.now(timezone.utc).hour
        
        for repo in filtered_repos:
            expected_shard = crc32(repo.node_id.encode("utf-8")) % 24
            assert expected_shard == current_shard

@pytest.mark.asyncio
async def test_all_repos_covered_over_24h(mock_dependencies):
    """Verify that simulating 24 hours covers all repositories"""
    from gim_workers.jobs.collector_job import run_collector_job
    
    all_repos = [MagicMock(node_id=f"repo-{i}") for i in range(50)]
    mock_dependencies["scout"].discover_repositories.return_value = all_repos
    
    processed_repos = set()
    
    with patch("gim_workers.jobs.collector_job.Gatherer") as MockGatherer:
        mock_gatherer = MockGatherer.return_value
        mock_gatherer.harvest_issues.return_value = []
        
        # Simulate each hour of the day
        for hour in range(24):
            # Mock datetime.now to return specific hour
            mock_now = datetime(2025, 1, 1, hour, 0, 0, tzinfo=timezone.utc)
            
            # Patch datetime.now() to return fixed hour
            with patch("datetime.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_now
                mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
                
                await run_collector_job()
                
                # Collect repos processed in this "hour"
                filtered_repos = mock_gatherer.harvest_issues.call_args[0][0]
                for r in filtered_repos:
                    processed_repos.add(r.node_id)
                    
    # Verify all repos were eventually processed
    assert len(processed_repos) == 50
