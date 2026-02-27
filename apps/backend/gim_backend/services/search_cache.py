"""
Redis-based caching for search results, skipped if unavailable.
Time to Live: 5 min
"""

import json
import logging
from typing import Any
from uuid import UUID

from gim_backend.core.redis import get_redis
from gim_backend.services.search_service import (
    SearchRequest,
    SearchResponse,
)

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 300
CACHE_PREFIX = "search:"
CONTEXT_PREFIX = "searchctx:"
SEARCH_CACHE_SCHEMA_VERSION = 2


def _serialize_response(response: SearchResponse) -> str:
    data = response.model_dump(mode="json")
    data["_cache_schema_version"] = SEARCH_CACHE_SCHEMA_VERSION
    return json.dumps(data)


def _normalize_cached_response_payload(parsed: Any) -> dict[str, Any]:
    """Compatibility adapter for older cached payload shapes."""
    if not isinstance(parsed, dict):
        raise ValueError("Cached search payload must be a JSON object")

    normalized = dict(parsed)
    normalized.setdefault("total_is_capped", False)

    raw_results = normalized.get("results")
    if isinstance(raw_results, list):
        normalized_results: list[Any] = []
        for item in raw_results:
            if isinstance(item, dict):
                normalized_item = dict(item)
                # Legacy cache entries stored `body_text`; current model expects `body_preview`.
                if "body_preview" not in normalized_item and "body_text" in normalized_item:
                    normalized_item["body_preview"] = normalized_item["body_text"]
                normalized_results.append(normalized_item)
                continue
            normalized_results.append(item)
        normalized["results"] = normalized_results

    return normalized


def _deserialize_response(data: str) -> SearchResponse:
    parsed = json.loads(data)
    normalized = _normalize_cached_response_payload(parsed)
    return SearchResponse.model_validate(normalized)


def _context_key(search_id: UUID) -> str:
    return f"{CONTEXT_PREFIX}{search_id}"


async def cache_search_context(
    *,
    search_id: UUID,
    query_text: str,
    filters_json: dict[str, Any],
    result_count: int,
    page: int,
    page_size: int,
    page_node_ids: list[str],
) -> None:
    """
    Store validated search context for later interaction logging.
    Silently fails if Redis unavailable.
    """
    redis = await get_redis()
    if redis is None:
        return

    payload = {
        "query_text": query_text,
        "filters_json": filters_json,
        "result_count": int(result_count),
        "page": int(page),
        "page_size": int(page_size),
        "page_node_ids": page_node_ids,
    }

    try:
        await redis.setex(_context_key(search_id), CACHE_TTL_SECONDS, json.dumps(payload))
    except Exception as e:
        logger.warning(f"Search context cache write error: {e}")


async def get_cached_search_context(search_id: UUID) -> dict[str, Any] | None:
    """
    Retrieve cached search context for interaction validation.
    Returns None if missing or Redis unavailable.
    """
    redis = await get_redis()
    if redis is None:
        return None

    try:
        cached = await redis.get(_context_key(search_id))
        if not cached:
            return None
        parsed = json.loads(cached)
        if not isinstance(parsed, dict):
            return None
        return parsed
    except Exception as e:
        logger.warning(f"Search context cache read error: {e}")
        return None


async def get_cached_search(request: SearchRequest) -> SearchResponse | None:
    """
    Retrieve cached search response if available.
    Returns None if cache miss or Redis unavailable.
    """
    redis = await get_redis()
    if redis is None:
        return None

    cache_key = f"{CACHE_PREFIX}{request.cache_key()}"

    try:
        cached = await redis.get(cache_key)
        if cached:
            logger.debug(f"Cache hit: {cache_key}")
            return _deserialize_response(cached)
        logger.debug(f"Cache miss: {cache_key}")
        return None
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
        return None


async def cache_search_response(
    request: SearchRequest,
    response: SearchResponse,
) -> None:
    """
    Cache search response with 5-minute TTL.
    Silently fails if Redis unavailable.
    """
    redis = await get_redis()
    if redis is None:
        return

    cache_key = f"{CACHE_PREFIX}{request.cache_key()}"

    try:
        serialized = _serialize_response(response)
        await redis.setex(cache_key, CACHE_TTL_SECONDS, serialized)
        logger.debug(f"Cached search: {cache_key}")
    except Exception as e:
        logger.warning(f"Cache write error: {e}")


async def invalidate_search_cache(pattern: str = "*") -> int:
    """
    Invalidate cached search results matching pattern.
    Uses Redis pipeline to batch deletions in a single network round trip.
    Returns count of deleted keys.
    """
    redis = await get_redis()
    if redis is None:
        return 0

    try:
        full_pattern = f"{CACHE_PREFIX}{pattern}"

        # Collect all matching keys
        keys = [key async for key in redis.scan_iter(full_pattern)]

        if not keys:
            return 0

        # Use pipeline to delete all keys
        async with redis.pipeline(transaction=True) as pipe:
            for key in keys:
                pipe.delete(key)
            await pipe.execute()

        logger.debug(f"Invalidated {len(keys)} cache keys matching {full_pattern}")
        return len(keys)
    except Exception as e:
        logger.warning(f"Cache invalidation error: {e}")
        return 0


__all__ = [
    "CACHE_TTL_SECONDS",
    "CACHE_PREFIX",
    "CONTEXT_PREFIX",
    "get_cached_search",
    "cache_search_response",
    "cache_search_context",
    "get_cached_search_context",
    "invalidate_search_cache",
    "_serialize_response",
    "_deserialize_response",
    "_normalize_cached_response_payload",
]
