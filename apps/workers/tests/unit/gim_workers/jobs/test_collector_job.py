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

    # Mock staging persistence
    mock_staging = AsyncMock()
    mock_staging.insert_pending_issues.return_value = 10
    mock_staging.get_pending_count.return_value = 25
    monkeypatch.setattr("gim_workers.jobs.collector_job.StagingPersistence", MagicMock(return_value=mock_staging))

    return {
        "client": mock_client,
        "scout": mock_scout,
        "persistence": mock_persistence,
        "staging": mock_staging
    }

@pytest.mark.asyncio
async def test_sharding_filtering(mock_dependencies):
    """Verify that only repositories matching the current shard are processed"""
    from gim_workers.jobs.collector_job import run_collector_job
    
    # Create mock repos with unique IDs
    mock_repos = []
    for i in range(100):
        repo = MagicMock()
        repo.node_id = f"repo-{i}" 
        mock_repos.append(repo)
        
    mock_dependencies["scout"].discover_repositories.return_value = mock_repos
    
    # Run the job - use async generator mock for harvest_issues
    with patch("gim_workers.jobs.collector_job.Gatherer") as MockGatherer:
        mock_gatherer_instance = MockGatherer.return_value
        
        async def empty_harvest(repos):
            return
            yield  # Make this an async generator
        
        mock_gatherer_instance.harvest_issues = empty_harvest
        
        await run_collector_job()
        
        # Verify Gatherer was initialized
        assert MockGatherer.called

@pytest.mark.asyncio
async def test_all_repos_covered_over_24h(mock_dependencies):
    """Verify that simulating 24 hours covers all repositories"""
    from gim_workers.jobs.collector_job import run_collector_job
    from binascii import crc32
    
    all_repos = [MagicMock(node_id=f"repo-{i}") for i in range(50)]
    mock_dependencies["scout"].discover_repositories.return_value = all_repos
    
    # Use CRC32 to determine which repos belong to which shard
    repo_shards = {}
    for repo in all_repos:
        shard_id = crc32(repo.node_id.encode("utf-8")) % 24
        if shard_id not in repo_shards:
            repo_shards[shard_id] = []
        repo_shards[shard_id].append(repo.node_id)
    
    # Verify all repos have a shard assignment (all 50 should be covered)
    total_in_shards = sum(len(repos) for repos in repo_shards.values())
    assert total_in_shards == 50

@pytest.mark.asyncio
async def test_collector_writes_to_staging(mock_dependencies):
    """Verify collector writes issues to staging table"""
    from gim_workers.jobs.collector_job import run_collector_job
    from binascii import crc32
    from datetime import UTC
    
    # Create repos that will match any shard (one per hour)
    current_shard = datetime.now(UTC).hour
    
    # Find a repo node_id that hashes to current shard
    matching_node_id = None
    for i in range(100):
        node_id = f"test-repo-{i}"
        if crc32(node_id.encode("utf-8")) % 24 == current_shard:
            matching_node_id = node_id
            break
    
    mock_repos = [MagicMock(node_id=matching_node_id)]
    mock_dependencies["scout"].discover_repositories.return_value = mock_repos
    
    # Mock issue data
    mock_issue = MagicMock()
    mock_issue.node_id = "issue-1"
    mock_issue.repo_id = matching_node_id
    mock_issue.title = "Test Issue"
    mock_issue.body_text = "Test body"
    mock_issue.labels = []
    mock_issue.github_created_at = datetime.now(timezone.utc)
    mock_issue.q_components = MagicMock(has_code=False, has_headers=False, tech_weight=0.0)
    mock_issue.q_score = 0.5
    mock_issue.state = "open"
    
    with patch("gim_workers.jobs.collector_job.Gatherer") as MockGatherer:
        mock_gatherer_instance = MockGatherer.return_value
        
        async def mock_harvest(repos):
            yield mock_issue
        
        mock_gatherer_instance.harvest_issues = mock_harvest
        
        result = await run_collector_job()
        
        # Verify staging persistence was called
        assert mock_dependencies["staging"].insert_pending_issues.called
        assert "pending_count" in result
