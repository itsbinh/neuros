"""Unified memory manager — orchestrates Qdrant, Redis, Postgres, and Graphiti."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from neuros.memory.postgres import PostgresStore
from neuros.memory.qdrant import QdrantStore
from neuros.memory.redis import RedisStore
from neuros.models import GraphEntity, MemoryResult, TimelineEvent

logger = logging.getLogger("neuros.memory.manager")

# Module-level singleton — set by main.py lifespan before any skill runs.
manager: MemoryManager | None = None


class MemoryManager:
    """Single interface the graph nodes use. Nothing in graph.py imports stores directly."""

    def __init__(
        self,
        qdrant: QdrantStore,
        redis: RedisStore,
        postgres: PostgresStore,
        graphiti: Any | None = None,
    ) -> None:
        self._qdrant = qdrant
        self._redis = redis
        self._postgres = postgres
        self._graphiti = graphiti

    async def store(self, text: str, metadata: dict) -> str:
        """Embed and upsert text to Qdrant + add episode to Graphiti concurrently."""
        source = metadata.get("source", "user")
        session_id = metadata.get("session_id", "default")

        tasks = [self._qdrant.upsert(text, metadata)]
        if self._graphiti:
            tasks.append(
                self._graphiti.add_episode(text, session_id, source=source, metadata=metadata)
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        qdrant_result = results[0]
        if isinstance(qdrant_result, Exception):
            logger.warning("store: qdrant upsert failed: %s", qdrant_result)
            qdrant_result = ""
        if self._graphiti and len(results) > 1 and isinstance(results[1], Exception):
            logger.warning("store: graphiti add_episode failed: %s", results[1])

        return str(qdrant_result)

    async def recall(
        self, query: str, k: int = 5, session_id: str = "default"
    ) -> list[MemoryResult]:
        """Merge Qdrant + Graphiti + Redis recent, deduplicated, top-k."""
        tasks = [
            self._qdrant.search(query, k=k),
            self._redis.get_recent(session_id, n=5),
        ]
        if self._graphiti:
            tasks.append(self._graphiti.search(query, k=max(2, k // 2)))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        r0 = results[0]
        qdrant_results: list[MemoryResult] = [] if isinstance(r0, Exception) else r0
        if isinstance(r0, Exception):
            logger.warning("recall: qdrant search failed: %s", r0)

        recent_strs: list[str] = results[1] if not isinstance(results[1], Exception) else []
        if isinstance(results[1], Exception):
            logger.warning("recall: redis get_recent failed: %s", results[1])

        graph_results = []
        if self._graphiti:
            raw = results[2] if len(results) > 2 else []
            if isinstance(raw, Exception):
                logger.warning("recall: graphiti search failed: %s", raw)
            else:
                for gr in raw:
                    graph_results.append(
                        MemoryResult(
                            id=f"graph:{gr.content[:16]}",
                            text=gr.content,
                            score=gr.score,
                            metadata={"source": "graphiti", "entity_names": gr.entity_names},
                        )
                    )

        # Merge: recent first, then graph, then qdrant; deduplicate by first 100 chars
        merged: list[MemoryResult] = []
        seen: set[str] = set()

        for text in recent_strs:
            key = text[:100]
            if key not in seen:
                seen.add(key)
                merged.append(
                    MemoryResult(id="recent", text=text, score=1.0, metadata={"source": "redis"})
                )

        for r in graph_results:
            key = r.text[:100]
            if key not in seen:
                seen.add(key)
                merged.append(r)

        for r in qdrant_results:
            key = r.text[:100]
            if key not in seen:
                seen.add(key)
                merged.append(r)

        return merged[:k]

    async def remember_entity(self, text: str, session_id: str = "default") -> str:
        """Explicitly store fact in both Graphiti and Qdrant. Returns episode_id."""
        episode_id = None
        if self._graphiti:
            episode_id = await self._graphiti.add_episode(
                text, session_id, source="user", metadata={}
            )
        await self._qdrant.upsert(
            text, {"source": "user", "session_id": session_id, "type": "explicit_memory"}
        )
        return episode_id or ""

    async def get_entity(self, name: str) -> GraphEntity | None:
        if not self._graphiti:
            return None
        return await self._graphiti.get_entity(name)

    async def entity_timeline(self, entity_name: str, limit: int = 20) -> list[TimelineEvent]:
        if not self._graphiti:
            return []
        return await self._graphiti.entity_timeline(entity_name, limit=limit)

    async def invalidate_fact(self, subject: str, predicate: str, reason: str) -> bool:
        if not self._graphiti:
            return False
        return await self._graphiti.invalidate_fact(subject, predicate, reason)

    async def set_context(self, key: str, val: Any, ttl: int = 3600) -> None:
        await self._redis.set_context(key, val, ttl=ttl)

    async def get_context(self, key: str) -> Any | None:
        return await self._redis.get_context(key)

    async def push_recent(self, text: str, session_id: str) -> None:
        await self._redis.push_recent(text, session_id)

    async def get_recent(self, session_id: str, n: int = 5) -> list[str]:
        return await self._redis.get_recent(session_id, n=n)

    async def log_interaction(
        self,
        session_id: str,
        input: str,
        output: str,
        skill_used: str | None = None,
        model_used: str | None = None,
        latency_ms: int | None = None,
    ) -> str:
        return await self._postgres.log_interaction(
            session_id=session_id,
            input=input,
            output=output,
            skill_used=skill_used,
            model_used=model_used,
            latency_ms=latency_ms,
        )

    async def health(self) -> dict:
        result: dict[str, Any] = {}

        try:
            await self._qdrant.collection_info()
            result["qdrant"] = "ok"
        except Exception as e:
            logger.warning("Qdrant health check failed: %s", e)
            result["qdrant"] = "error"

        try:
            if self._redis._client:
                await self._redis._client.ping()
                result["redis"] = "ok"
            else:
                result["redis"] = "error"
        except Exception as e:
            logger.warning("Redis health check failed: %s", e)
            result["redis"] = "error"

        try:
            await self._postgres.recent_interactions(n=1)
            result["postgres"] = "ok"
        except Exception as e:
            logger.warning("Postgres health check failed: %s", e)
            result["postgres"] = "error"

        if self._graphiti:
            result["graphiti"] = await self._graphiti.health()
        else:
            result["graphiti"] = {"status": "disabled"}

        return result
