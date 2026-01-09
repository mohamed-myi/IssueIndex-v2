from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.main import app
from src.middleware.auth import require_auth
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
def authenticated_client(client):
    user = type("U", (), {"id": uuid4()})
    session = type("S", (), {"id": uuid4(), "user_id": user.id})

    def _mock_require_auth():
        return (user, session)

    app.dependency_overrides[require_auth] = _mock_require_auth
    yield client
    app.dependency_overrides.clear()


class _Why:
    def __init__(self, entity: str, score: float):
        self.entity = entity
        self.score = score


class _Item:
    def __init__(self):
        self.node_id = "issue_1"
        self.title = "t"
        self.body_preview = "b"
        self.labels = []
        self.q_score = 0.8
        self.repo_name = "r"
        self.primary_language = "Python"
        self.github_created_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
        self.similarity_score = 0.9
        self.why_this = [_Why("Python", 3.0)]


class _Feed:
    def __init__(self, is_personalized: bool):
        self.results = [_Item()]
        self.total = 1
        self.page = 1
        self.page_size = 20
        self.has_more = False
        self.is_personalized = is_personalized
        self.profile_cta = None


def test_feed_includes_why_this_only_when_personalized(authenticated_client):
    with patch("src.api.routes.feed.get_feed", return_value=_Feed(is_personalized=True)):
        resp = authenticated_client.get("/feed")
    assert resp.status_code == 200
    payload = resp.json()
    assert "recommendation_batch_id" in payload
    assert payload["results"][0]["why_this"][0]["entity"] == "Python"

    with patch("src.api.routes.feed.get_feed", return_value=_Feed(is_personalized=False)):
        resp2 = authenticated_client.get("/feed")
    assert resp2.status_code == 200
    payload2 = resp2.json()
    assert payload2["results"][0].get("why_this") is None


