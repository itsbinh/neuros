"""Qdrant vector store for semantic memory."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TYPE_CHECKING

from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qmodels

from neuros.models import MemoryResult

if TYPE_CHECKING:
    from neuros.memory.postgres import PostgresStore

logger = logging.getLogger("neuros.memory.qdrant")

COLLECTION_NAME = "neuros_memory"
_DIM_CONFIG_KEY = "qdrant_vector_dim"


class QdrantStore:
    """Async Qdrant wrapper. Embedder and client are injected at construction."""

    def __init__(
        self,
        embedder: Callable[[str], Awaitable[list[float]]],
        client: AsyncQdrantClient,
    ) -> None:
        self._embed = embedder
        self._client = client
        self._collection = COLLECTION_NAME

    async def ensure_collection(self, postgres: PostgresStore | None = None) -> None:
        """Create or validate collection; detect dim from embedder; store dim in Postgres config."""
        probe = await self._embed("dimension probe")
        dim = len(probe)

        if postgres is not None:
            stored = await postgres.get_config(_DIM_CONFIG_KEY)
            if stored is None:
                await postgres.set_config(_DIM_CONFIG_KEY, str(dim))
            elif int(stored) != dim:
                raise RuntimeError(
                    f"Qdrant dim mismatch: config has {stored}, embedder returned {dim}"
                )

        collections = await self._client.get_collections()
        existing = {c.name for c in collections.collections}

        if self._collection in existing:
            info = await self._client.get_collection(self._collection)
            existing_dim = info.config.params.vectors.size
            if existing_dim != dim:
                raise RuntimeError(
                    f"Collection '{self._collection}' exists with dim={existing_dim} but "
                    f"embedder returns dim={dim}. Drop the collection and re-run setup."
                )
            logger.info("Qdrant collection '%s' OK (dim=%d)", self._collection, dim)
            return

        logger.info("Creating Qdrant collection '%s' (dim=%d)", self._collection, dim)
        await self._client.create_collection(
            collection_name=self._collection,
            vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
        )

    async def upsert(self, text: str, metadata: dict) -> str:
        """Embed text and upsert to Qdrant. Returns point_id (uuid4)."""
        vector = await self._embed(text)
        point_id = str(uuid.uuid4())
        payload = {"text": text, "timestamp": datetime.utcnow().isoformat(), **metadata}
        await self._client.upsert(
            collection_name=self._collection,
            points=[qmodels.PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        logger.debug("upserted %s", point_id)
        return point_id

    async def search(self, query: str, k: int = 5) -> list[MemoryResult]:
        """Embed query and search Qdrant. Returns ranked MemoryResult list."""
        vector = await self._embed(query)
        results = await self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=k,
        )
        return [
            MemoryResult(
                id=str(p.id),
                text=p.payload.get("text", ""),
                score=p.score,
                metadata={k: v for k, v in p.payload.items() if k not in ("text", "timestamp")},
                timestamp=p.payload.get("timestamp"),
            )
            for p in results.points
        ]

    async def delete(self, point_id: str) -> bool:
        """Delete a point by ID. Returns True if deleted."""
        await self._client.delete(
            collection_name=self._collection,
            points_selector=qmodels.PointIdsList(points=[point_id]),
        )
        logger.debug("deleted %s", point_id)
        return True

    async def collection_info(self) -> dict:
        """Return name, vector_count, vector_dim, status for the collection."""
        info = await self._client.get_collection(self._collection)
        count = getattr(info, "vectors_count", None) or getattr(info, "points_count", 0) or 0
        return {
            "name": self._collection,
            "vector_count": count,
            "vector_dim": info.config.params.vectors.size,
            "status": str(info.status),
        }
