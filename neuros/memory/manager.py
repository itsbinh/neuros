"""Unified memory manager — orchestrates Qdrant, Redis, and Postgres."""

from __future__ import annotations

import logging
import uuid

from neuros.llm.embedder import embed
from neuros.memory.postgres import Interaction, get_session, init_db
from neuros.memory.qdrant import store as qdrant_store
from neuros.memory.redis import cache as redis_cache
from neuros.models import Memory

logger = logging.getLogger("neuros.memory.manager")


class MemoryManager:
    """Unified interface over all memory backends."""

    async def initialize(self) -> None:
        """Initialize all storage backends."""
        await init_db()
        await qdrant_store.ensure_collection()
        await redis_cache.connect()
        logger.info("Memory layer initialized")

    # ── Core operations ──────────────────────────────────────────

    async def store(
        self,
        text: str,
        *,
        source: str | None = None,
        tags: list[str] | None = None,
        session_id: str | None = None,
    ) -> str:
        """Embed and store text in Qdrant. Returns memory ID."""
        vector = await embed(text)
        item_id = str(uuid.uuid4())
        await qdrant_store.upsert(
            text=text,
            vector=vector,
            item_id=item_id,
            source=source,
            tags=tags,
            session_id=session_id,
        )
        return item_id

    async def recall(self, query: str, k: int = 5) -> list[Memory]:
        """Semantic search via Qdrant. Returns ranked Memory objects."""
        vector = await embed(query)
        results = await qdrant_store.search(vector, k=k)
        return [
            Memory(
                id=str(r.get("id", "")),
                text=r.get("text", ""),
                source=r.get("source"),
                tags=r.get("tags", []),
                score=r.get("score"),
            )
            for r in results
        ]

    # ── Context (Redis) ──────────────────────────────────────────

    async def set_context(self, key: str, value: str, ttl: int = 3600) -> None:
        """Store short-lived context."""
        await redis_cache.set_context(key, value, ttl=ttl)

    async def get_context(self, key: str) -> str | None:
        """Retrieve short-lived context."""
        return await redis_cache.get_context(key)

    # ── Logging (Postgres) ───────────────────────────────────────

    async def log_interaction(
        self,
        input_text: str,
        output_text: str,
        skill_used: str | None = None,
    ) -> None:
        """Persist an interaction record to Postgres."""
        session = await get_session()
        try:
            record = Interaction(
                input_text=input_text[:4096],
                output_text=output_text[:4096],
                skill=skill_used,
            )
            session.add(record)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to log interaction")
        finally:
            await session.close()

    # ── Recent context (Redis rolling window) ────────────────────

    async def push_recent(self, text: str, session_id: str = "default") -> None:
        """Push into the recent interactions rolling window."""
        await redis_cache.push_recent(text, session_id=session_id)

    async def get_recent(self, n: int = 10, session_id: str = "default") -> list[str]:
        """Get N most recent interactions."""
        return await redis_cache.get_recent(n, session_id=session_id)


# Module-level singleton
manager = MemoryManager()
