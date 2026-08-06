"""Redis-backed caching helpers (transcription cache, simple counters)."""
from __future__ import annotations

import json
from typing import Any

from redis.asyncio import Redis, from_url

from config import settings

_redis: Redis | None = None

TRANSCRIPTION_TTL_SECONDS = 60 * 60 * 24  # 1 day, per README: cache transcriptions


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = from_url(settings.redis_url, decode_responses=True)
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def cache_transcription(voice_file_unique_id: str, text: str) -> None:
    redis = get_redis()
    await redis.set(f"transcript:{voice_file_unique_id}", text, ex=TRANSCRIPTION_TTL_SECONDS)


async def get_cached_transcription(voice_file_unique_id: str) -> str | None:
    redis = get_redis()
    return await redis.get(f"transcript:{voice_file_unique_id}")


async def set_json(key: str, value: Any, ttl_seconds: int | None = None) -> None:
    redis = get_redis()
    await redis.set(key, json.dumps(value), ex=ttl_seconds)


async def get_json(key: str) -> Any | None:
    redis = get_redis()
    raw = await redis.get(key)
    return json.loads(raw) if raw is not None else None


async def delete(key: str) -> None:
    redis = get_redis()
    await redis.delete(key)
