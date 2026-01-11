import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.api.dependencies import get_db
from src.main import app
from src.middleware.rate_limit import reset_rate_limiter, reset_rate_limiter_instance


@pytest.fixture(autouse=True)
def reset_rate_limit():
    reset_rate_limiter()
    reset_rate_limiter_instance()
    yield
    reset_rate_limiter()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def db_override(mock_db):
    async def _override():
        yield mock_db
    app.dependency_overrides[get_db] = _override
    yield
    app.dependency_overrides.clear()


class TestSearchInteract:
    def test_interact_persists_context_fields(self, client, db_override, mock_db):
        search_id = uuid4()
        context = {
            "query_text": "python error",
            "filters_json": {"languages": ["Python"], "labels": [], "repos": []},
            "result_count": 100,
            "page": 2,
            "page_size": 20,
        }

        with patch("src.api.routes.search.get_cached_search_context", new=AsyncMock(return_value=context)):
            response = client.post("/search/interact", json={
                "search_id": str(search_id),
                "selected_node_id": "issue_1",
                "position": 25,
            })

        assert response.status_code == 204
        assert mock_db.execute.await_count == 1

        params = mock_db.execute.call_args.args[1]
        assert params["search_id"] == search_id
        assert params["query_text"] == "python error"
        assert params["result_count"] == 100
        assert params["selected_node_id"] == "issue_1"
        assert params["position"] == 25

        filters = json.loads(params["filters_json"])
        assert filters == context["filters_json"]

    def test_interact_returns_404_when_context_missing(self, client, db_override):
        search_id = uuid4()

        with patch("src.api.routes.search.get_cached_search_context", new=AsyncMock(return_value=None)):
            response = client.post("/search/interact", json={
                "search_id": str(search_id),
                "selected_node_id": "issue_1",
                "position": 1,
            })

        assert response.status_code == 404

    def test_interact_rejects_invalid_position(self, client, db_override):
        search_id = uuid4()
        context = {
            "query_text": "python",
            "filters_json": {"languages": [], "labels": [], "repos": []},
            "result_count": 30,
            "page": 1,
            "page_size": 20,
        }

        with patch("src.api.routes.search.get_cached_search_context", new=AsyncMock(return_value=context)):
            response = client.post("/search/interact", json={
                "search_id": str(search_id),
                "selected_node_id": "issue_1",
                "position": 25,
            })

        assert response.status_code == 400

    def test_interact_returns_204_on_db_failure(self, client, db_override, mock_db):
        search_id = uuid4()
        context = {
            "query_text": "python error",
            "filters_json": {"languages": ["Python"], "labels": [], "repos": []},
            "result_count": 10,
            "page": 1,
            "page_size": 20,
        }

        mock_db.execute = AsyncMock(side_effect=Exception("db down"))

        with patch("src.api.routes.search.get_cached_search_context", new=AsyncMock(return_value=context)):
            response = client.post("/search/interact", json={
                "search_id": str(search_id),
                "selected_node_id": "issue_1",
                "position": 1,
            })

        assert response.status_code == 204
        assert mock_db.rollback.await_count == 1


