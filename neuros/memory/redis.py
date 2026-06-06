"""Redis cache for session context and rolling recent interactions."""

from __future__ import annotations

import logging

import redis.asyncio as aioredis

from neuros.config import settings

logger = logging.getLogger("neuros.memory.redis")

_DEFAULT_TTL = 3600  # 1 hour


class RedisStore:
    """Async Redis client for short-lived context."""

    def __init__(self) -> None:
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Establish Redis connection."""
        self._client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        logger.info("Redis connected to %s", settings.redis_url)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()

    # ── Context storage ──────────────────────────────────────────

    async def set_context(self, key: str, value: str, ttl: int = _DEFAULT_TTL) -> None:
        """Store a context key-value pair with TTL."""
        if self._client:
            await self._client.setex(key, ttl, value)

    async def get_context(self, key: str) -> str | None:
        """Retrieve a context value by key."""
        if self._client:
            return await self._client.get(key)
        return None

    # ── Rolling recent interactions ──────────────────────────────

    async def push_recent(self, text: str, session_id: str = "default") -> None:
        """Push a recent interaction into the rolling window list."""
        if self._client:
            key = f"recent:{session_id}"
            await self._client.lpush(key, text)
            await self._client.ltrim(key, 0, 99)  # keep last 100

    async def get_recent(self, session_id: str = "default", n: int = 10) -> list[str]:
        """Get the N most recent interactions for a session."""
        if self._client:
            key = f"recent:{session_id}"
            items = await self._client.lrange(key, 0, n - 1)
            return items
        return []


# Backwards-compatible alias
RedisCache = RedisStore

# Module-level singleton
cache = RedisStore()
