

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from gim_backend.ingestion.embeddings import EmbeddedIssue
from gim_backend.ingestion.gatherer import IssueData
from gim_backend.ingestion.scout import RepositoryData


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.exec = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def persistence(mock_session, monkeypatch):

    mock_sqlalchemy = MagicMock()
    mock_sqlalchemy.text = MagicMock()

    monkeypatch.setitem(__import__("sys").modules, "sqlalchemy", mock_sqlalchemy)
    monkeypatch.setitem(__import__("sys").modules, "sqlalchemy.text", MagicMock())
    monkeypatch.setitem(__import__("sys").modules, "sqlmodel", MagicMock())
    monkeypatch.setitem(__import__("sys").modules, "sqlmodel.ext", MagicMock())
    monkeypatch.setitem(__import__("sys").modules, "sqlmodel.ext.asyncio", MagicMock())
    monkeypatch.setitem(__import__("sys").modules, "sqlmodel.ext.asyncio.session", MagicMock())


    from gim_backend.ingestion.persistence import StreamingPersistence

    return StreamingPersistence(session=mock_session)


@pytest.fixture
def make_embedded_issue(sample_q_components):
    def _make(node_id: str = "I_123", q_score: float = 0.75, state: str = "open"):
        issue = IssueData(
            node_id=node_id,
            repo_id="R_456",
            title="Bug report",
            body_text="Description",
            labels=["bug"],
            github_created_at=datetime.now(UTC),
            q_score=q_score,
            q_components=sample_q_components,
            state=state,
        )
        return EmbeddedIssue(
            issue=issue,
            embedding=[0.1] * 256,  # 256-dim for Matryoshka truncation
        )

    return _make


@pytest.fixture
def make_repository():
    def _make(node_id: str = "R_123", full_name: str = "owner/repo"):
        return RepositoryData(
            node_id=node_id,
            full_name=full_name,
            primary_language="Python",
            stargazer_count=1000,
            issue_count_open=50,
            topics=["python", "api"],
        )

    return _make


class TestStreamingPersistence:
    def test_batch_size_is_50(self, persistence):
        assert persistence.BATCH_SIZE == 50


class TestUpsertRepositories:
    async def test_upserts_single_repo(self, persistence, mock_session, make_repository):
        repo = make_repository()

        count = await persistence.upsert_repositories([repo])

        assert count == 1
        mock_session.exec.assert_called_once()
        mock_session.commit.assert_called_once()

    async def test_upserts_multiple_repos(self, persistence, mock_session, make_repository):
        repos = [make_repository(f"R_{i}", f"owner/repo{i}") for i in range(5)]

        count = await persistence.upsert_repositories(repos)

        assert count == 5
        assert mock_session.exec.call_count == len(repos)
        assert mock_session.commit.call_count == len(repos)

    async def test_returns_zero_for_empty_list(self, persistence, mock_session):
        count = await persistence.upsert_repositories([])

        assert count == 0
        mock_session.exec.assert_not_called()

    async def test_passes_correct_params(self, persistence, mock_session, make_repository):
        repo = make_repository(node_id="R_test", full_name="test/repo")

        await persistence.upsert_repositories([repo])

        call_args = mock_session.exec.call_args[1]["params"]
        assert call_args["node_id"] == "R_test"
        assert call_args["full_name"] == "test/repo"
        assert call_args["primary_language"] == "Python"
        assert call_args["stargazer_count"] == 1000


class TestPersistStream:
    async def test_persists_single_issue(self, persistence, mock_session, make_embedded_issue):
        async def single_issue():
            yield make_embedded_issue()

        count = await persistence.persist_stream(single_issue())

        assert count == 1
        mock_session.exec.assert_called_once()
        mock_session.commit.assert_called()

    async def test_batches_at_50(self, persistence, mock_session, make_embedded_issue):
        async def issue_stream():
            for i in range(50):
                yield make_embedded_issue(node_id=f"I_{i}")

        count = await persistence.persist_stream(issue_stream())

        assert count == 50
        assert mock_session.exec.call_count == 1

    async def test_two_batches_for_75_issues(self, persistence, mock_session, make_embedded_issue):
        async def issue_stream():
            for i in range(75):
                yield make_embedded_issue(node_id=f"I_{i}")

        count = await persistence.persist_stream(issue_stream())

        assert count == 75
        assert mock_session.exec.call_count == 2

    async def test_handles_empty_stream(self, persistence, mock_session):
        async def empty_stream():
            return
            yield

        count = await persistence.persist_stream(empty_stream())

        assert count == 0
        mock_session.exec.assert_not_called()


class TestUpsertStagedIssue:
    async def test_uses_worker_upsert_params_and_does_not_commit(self, persistence, mock_session):
        issue = {
            "node_id": "I_stage_1",
            "repo_id": "R_123",
            "title": "Staged issue",
            "body_text": "Body",
            "labels": ["bug"],
            "github_created_at": "2026-02-25T12:00:00Z",
            "has_code": True,
            "has_template_headers": False,
            "tech_stack_weight": 0.25,
            "q_score": 0.8,
            "state": "open",
            "content_hash": "hash-1",
        }
        embedding = [0.1] * 256

        await persistence.upsert_staged_issue(issue, embedding)

        call_args = mock_session.exec.call_args
        params = call_args.kwargs["params"]
        assert params["node_id"] == "I_stage_1"
        assert params["repo_id"] == "R_123"
        assert params["q_score"] == 0.8
        assert params["content_hash"] == "hash-1"
        assert "survival_score" in params
        assert isinstance(params["embedding"], str)
        assert params["github_created_at"].tzinfo is None
        mock_session.commit.assert_not_called()

    async def test_raises_for_invalid_embedding_dimension(self, persistence):
        issue = {
            "node_id": "I_bad_dim",
            "repo_id": "R_123",
            "title": "Bad dim",
            "body_text": "Body",
            "labels": [],
            "github_created_at": datetime.now(UTC),
            "content_hash": "hash-2",
        }

        with pytest.raises(ValueError, match="dimension mismatch"):
            await persistence.upsert_staged_issue(issue, [0.1] * 10)


class TestSurvivalScoreInjection:
    async def test_survival_score_calculated(self, persistence, mock_session, make_embedded_issue):

        async def single_issue():
            yield make_embedded_issue(q_score=0.8)

        await persistence.persist_stream(single_issue())

        call_args = mock_session.exec.call_args[1]["params"]
        assert "survival_score_0" in call_args
        assert call_args["survival_score_0"] > 0

    async def test_higher_q_score_means_higher_survival(self, persistence, mock_session, make_embedded_issue):
        survival_scores = []

        for q in [0.3, 0.9]:
            mock_session.reset_mock()

            async def single_issue():
                yield make_embedded_issue(q_score=q)

            await persistence.persist_stream(single_issue())

            params = mock_session.exec.call_args[1]["params"]
            survival_scores.append(params["survival_score_0"])

        assert survival_scores[1] > survival_scores[0]  # 0.9 > 0.3


class TestQScoreComponents:
    async def test_passes_q_components_to_sql(self, persistence, mock_session, make_embedded_issue):

        async def single_issue():
            yield make_embedded_issue()

        await persistence.persist_stream(single_issue())

        call_args = mock_session.exec.call_args[1]["params"]
        assert "has_code_0" in call_args
        assert "has_template_headers_0" in call_args
        assert "tech_stack_weight_0" in call_args
        assert call_args["has_code_0"] is True
        assert call_args["has_template_headers_0"] is True
        assert call_args["tech_stack_weight_0"] == 0.5


class TestEmbeddingStorage:
    async def test_embedding_passed_as_string(self, persistence, mock_session, make_embedded_issue):

        async def single_issue():
            yield make_embedded_issue()

        await persistence.persist_stream(single_issue())

        call_args = mock_session.exec.call_args[1]["params"]
        embedding_param = call_args["embedding_0"]

        assert isinstance(embedding_param, str)
        assert embedding_param.startswith("[")


class TestStateStorage:
    async def test_state_passed_to_sql(self, persistence, mock_session, make_embedded_issue):

        async def single_issue():
            yield make_embedded_issue(state="open")

        await persistence.persist_stream(single_issue())

        call_args = mock_session.exec.call_args[1]["params"]
        assert "state_0" in call_args
        assert call_args["state_0"] == "open"

    async def test_closed_state_passed_to_sql(self, persistence, mock_session, make_embedded_issue):

        async def single_issue():
            yield make_embedded_issue(state="closed")

        await persistence.persist_stream(single_issue())

        call_args = mock_session.exec.call_args[1]["params"]
        assert call_args["state_0"] == "closed"
