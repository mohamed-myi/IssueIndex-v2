

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from gim_backend.ingestion.embeddings import (
    EMBEDDING_DIM,
    EmbeddedIssue,
    embed_issue_stream,
)
from gim_backend.ingestion.gatherer import IssueData


@pytest.fixture
def make_issue(sample_q_components):
    def _make(node_id: str = "I_123", title: str = "Bug report"):
        return IssueData(
            node_id=node_id,
            repo_id="R_456",
            title=title,
            body_text="Description of the bug",
            labels=["bug"],
            github_created_at=datetime.now(UTC),
            q_score=0.75,
            q_components=sample_q_components,
            state="open",
        )

    return _make


@pytest.fixture
def mock_provider():
    provider = AsyncMock()

    async def embed_batch(texts: list[str]) -> list[list[float]]:
        return [[0.1] * EMBEDDING_DIM for _ in texts]

    provider.embed_batch = AsyncMock(side_effect=embed_batch)
    return provider


class TestEmbeddedIssue:
    def test_dataclass_fields(self, make_issue):
        issue = make_issue()
        embedding = [0.1] * EMBEDDING_DIM

        embedded = EmbeddedIssue(issue=issue, embedding=embedding)

        assert embedded.issue.node_id == "I_123"
        assert len(embedded.embedding) == EMBEDDING_DIM


class TestEmbedIssueStream:
    async def test_batches_before_embedding(self, mock_provider, make_issue):
        batch_size = 25

        async def issue_generator():
            for i in range(batch_size):
                yield make_issue(node_id=f"I_{i}")

        results = [item async for item in embed_issue_stream(issue_generator(), mock_provider, batch_size=batch_size)]

        assert mock_provider.embed_batch.call_count == 1
        assert len(results) == batch_size

    async def test_flushes_partial_batch(self, mock_provider, make_issue):
        batch_size = 25
        issue_count = 30  # 25 + 5 partial

        async def issue_generator():
            for i in range(issue_count):
                yield make_issue(node_id=f"I_{i}")

        results = [item async for item in embed_issue_stream(issue_generator(), mock_provider, batch_size=batch_size)]

        assert mock_provider.embed_batch.call_count == 2
        assert len(results) == issue_count

    async def test_handles_empty_stream(self, mock_provider):

        async def empty_generator():
            return
            yield  # Never reached; makes this an async generator

        results = [item async for item in embed_issue_stream(empty_generator(), mock_provider, batch_size=25)]

        assert len(results) == 0
        mock_provider.embed_batch.assert_not_called()

    async def test_preserves_issue_data(self, mock_provider, make_issue):
        issue = make_issue(node_id="I_unique", title="Special bug")

        async def single_issue():
            yield issue

        results = [item async for item in embed_issue_stream(single_issue(), mock_provider, batch_size=25)]

        assert len(results) == 1
        assert results[0].issue.node_id == "I_unique"
        assert results[0].issue.title == "Special bug"

    async def test_embedding_dimension(self, mock_provider, make_issue):

        async def single_issue():
            yield make_issue()

        results = [item async for item in embed_issue_stream(single_issue(), mock_provider, batch_size=25)]

        assert len(results[0].embedding) == EMBEDDING_DIM

    async def test_text_format_title_newline_body(self, mock_provider, make_issue):
        issue = make_issue(title="My Title")
        issue.body_text = "My Body"

        async def single_issue():
            yield issue

        _ = [item async for item in embed_issue_stream(single_issue(), mock_provider, batch_size=25)]

        call_args = mock_provider.embed_batch.call_args[0][0]
        assert call_args == ["My Title\nMy Body"]

    async def test_multiple_batches(self, mock_provider, make_issue):
        batch_size = 10
        issue_count = 30

        async def issue_generator():
            for i in range(issue_count):
                yield make_issue(node_id=f"I_{i}")

        results = [item async for item in embed_issue_stream(issue_generator(), mock_provider, batch_size=batch_size)]

        assert mock_provider.embed_batch.call_count == 3
        assert len(results) == issue_count

    async def test_yields_in_order(self, mock_provider, make_issue):

        async def ordered_issues():
            for i in range(5):
                yield make_issue(node_id=f"I_{i}")

        results = [item async for item in embed_issue_stream(ordered_issues(), mock_provider, batch_size=25)]

        for i, result in enumerate(results):
            assert result.issue.node_id == f"I_{i}"


class TestProviderBatchSize:
    async def test_uses_provider_batch_size_when_not_specified(self, mock_provider, make_issue):
        mock_provider.BATCH_SIZE = 5

        async def issue_generator():
            for i in range(10):
                yield make_issue(node_id=f"I_{i}")

        results = [item async for item in embed_issue_stream(issue_generator(), mock_provider)]


        assert mock_provider.embed_batch.call_count == 2
        assert len(results) == 10

    async def test_explicit_batch_size_overrides_provider(self, mock_provider, make_issue):
        mock_provider.BATCH_SIZE = 5

        async def issue_generator():
            for i in range(10):
                yield make_issue(node_id=f"I_{i}")

        results = [item async for item in embed_issue_stream(issue_generator(), mock_provider, batch_size=10)]


        assert mock_provider.embed_batch.call_count == 1
        assert len(results) == 10

    async def test_defaults_to_25_without_provider_batch_size(self, mock_provider, make_issue):

        if hasattr(mock_provider, "BATCH_SIZE"):
            delattr(mock_provider, "BATCH_SIZE")

        async def issue_generator():
            for i in range(25):
                yield make_issue(node_id=f"I_{i}")

        results = [item async for item in embed_issue_stream(issue_generator(), mock_provider)]


        assert mock_provider.embed_batch.call_count == 1
        assert len(results) == 25
