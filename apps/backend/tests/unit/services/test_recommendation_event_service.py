import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from gim_backend.services.recommendation_event_service import (
    RECO_EVENTS_QUEUE_KEY,
    RecommendationBatchContext,
    RecommendationEvent,
    enqueue_recommendation_events,
    get_recommendation_batch_context,
    store_recommendation_batch_context,
    validate_event_against_context,
)


class _FakeRedis:
    def __init__(self):
        self.kv: dict[str, str] = {}
        self.lists: dict[str, list[str]] = {}
        self.sets: dict[str, str] = {}

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.kv[key] = value

    async def get(self, key: str):
        return self.kv.get(key)

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool | None = None):
        if nx and key in self.sets:
            return None
        self.sets[key] = value
        return True

    async def expire(self, key: str, ttl: int) -> None:
        return None

    async def rpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).append(value)


@pytest.mark.asyncio
async def test_store_and_get_recommendation_batch_context_roundtrip():
    fake = _FakeRedis()
    batch_id = uuid4()
    served_at = datetime.now(UTC)

    with patch("gim_backend.services.recommendation_event_service.get_redis", new=AsyncMock(return_value=fake)):
        ok = await store_recommendation_batch_context(
            recommendation_batch_id=batch_id,
            issue_node_ids=["a", "b"],
            page=1,
            page_size=20,
            is_personalized=True,
            served_at=served_at,
        )
        assert ok is True

        ctx = await get_recommendation_batch_context(batch_id)
        assert ctx is not None
        assert ctx.recommendation_batch_id == batch_id
        assert ctx.issue_node_ids == ["a", "b"]
        assert ctx.is_personalized is True


def test_validate_event_against_context_position_matches():
    ctx = RecommendationBatchContext(
        recommendation_batch_id=uuid4(),
        issue_node_ids=["x", "y", "z"],
        page=1,
        page_size=20,
        is_personalized=False,
        served_at=datetime.now(UTC),
    )
    assert validate_event_against_context(context=ctx, issue_node_id="y", position=2) is True
    assert validate_event_against_context(context=ctx, issue_node_id="y", position=3) is False


@pytest.mark.asyncio
async def test_enqueue_recommendation_events_dedupes_on_event_id():
    fake = _FakeRedis()
    batch_id = uuid4()
    ctx = RecommendationBatchContext(
        recommendation_batch_id=batch_id,
        issue_node_ids=["x"],
        page=1,
        page_size=20,
        is_personalized=True,
        served_at=datetime.now(UTC),
    )
    user_id = uuid4()
    ev_id = uuid4()

    ev = RecommendationEvent(
        event_id=ev_id,
        recommendation_batch_id=batch_id,
        event_type="impression",
        issue_node_id="x",
        position=1,
        surface="feed",
        created_at=datetime.now(UTC),
        metadata={"k": "v"},
    )

    with patch("gim_backend.services.recommendation_event_service.get_redis", new=AsyncMock(return_value=fake)):
        queued1, deduped1 = await enqueue_recommendation_events(
            user_id=user_id,
            context=ctx,
            events=[ev],
        )
        queued2, deduped2 = await enqueue_recommendation_events(
            user_id=user_id,
            context=ctx,
            events=[ev],
        )

    assert queued1 == 1
    assert deduped1 == 0
    assert queued2 == 0
    assert deduped2 == 1

    assert len(fake.lists.get(RECO_EVENTS_QUEUE_KEY, [])) == 1
    payload = json.loads(fake.lists[RECO_EVENTS_QUEUE_KEY][0])
    assert payload["event_id"] == str(ev_id)
    assert payload["issue_node_id"] == "x"


