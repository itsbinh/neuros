"""Qdrant vector store client for semantic memory."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http import models as qmodels

from neuros.config import settings

logger = logging.getLogger("neuros.memory.qdrant")

COLLECTION_NAME = "neuros_memory"


class QdrantStore:
    """Async Qdrant client wrapper."""

    def __init__(self) -> None:
        self._client = AsyncQdrantClient(url=settings.qdrant_url)
        self._collection = COLLECTION_NAME

    async def ensure_collection(self, vector_size: int = 3072) -> None:
        """Create the collection if it doesn't exist."""
        collections = await self._client.get_collections()
        names = {c.name for c in collections.collections}
        if self._collection not in names:
            logger.info("Creating Qdrant collection '%s' (dim=%d)", self._collection, vector_size)
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=qmodels.VectorParams(
                    size=vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )

    async def upsert(
        self,
        text: str,
        vector: list[float],
        *,
        item_id: str | None = None,
        source: str | None = None,
        tags: list[str] | None = None,
        session_id: str | None = None,
    ) -> str:
        """Store a text embedding with metadata.

        Returns the stored item ID.
        """
        point_id = item_id or str(uuid.uuid4())
        payload: dict[str, Any] = {
            "text": text,
            "source": source,
            "tags": tags or [],
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
        }

        await self._client.upsert(
            collection_name=self._collection,
            points=[
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )
        logger.debug("upserted %s", point_id)
        return point_id

    async def search(self, vector: list[float], k: int = 5) -> list[dict[str, Any]]:
        """Semantic search by embedding vector.

        Returns list of payload dicts with score.
        """
        results = await self._client.query_points(
            collection_name=self._collection,
            query=vector,
            limit=k,
        )
        return [
            {**point.payload, "id": str(point.id), "score": point.score}
            for point in results.points
        ]

    async def delete(self, item_id: str) -> bool:
        """Delete a point by ID."""
        await self._client.delete(
            collection_name=self._collection,
            points_selector=qmodels.PointIdsList(points=[item_id]),
        )
        logger.debug("deleted %s", item_id)
        return True


# Module-level singleton
store = QdrantStore()
