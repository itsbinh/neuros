"""Graphiti temporal knowledge graph store."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from neo4j import AsyncGraphDatabase

from neuros.models import GraphEntity, GraphMemoryResult, GraphRelation, TimelineEvent

logger = logging.getLogger("neuros.memory.graphiti")


def _to_dt(val: Any) -> datetime:
    """Convert neo4j.time.DateTime or None to Python datetime."""
    if val is None:
        return datetime.now(UTC)
    if isinstance(val, datetime):
        return val
    # neo4j.time.DateTime has .to_native() method
    if hasattr(val, "to_native"):
        native = val.to_native()
        if native.tzinfo is None:
            return native.replace(tzinfo=UTC)
        return native
    return datetime.now(UTC)


class GraphitiStore:
    """Wraps graphiti-core Graphiti client for temporal entity memory.

    Failures never propagate — all public methods catch and log exceptions,
    returning empty/None/False so the pipeline continues via Qdrant fallback.
    """

    def __init__(
        self,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        llm_base_url: str,
        llm_model: str,
        embed_base_url: str = "",
        embed_model: str = "embed",
        group_id: str = "neuros",
    ) -> None:
        self._uri = neo4j_uri
        self._user = neo4j_user
        self._password = neo4j_password
        self._llm_base_url = llm_base_url
        self._llm_model = llm_model
        self._embed_base_url = embed_base_url or llm_base_url
        self._embed_model = embed_model
        self._group_id = group_id
        self._client: Any = None

    async def initialize(self) -> None:
        """Create Graphiti client, build indices/constraints, log entity count."""
        try:
            from graphiti_core import Graphiti
            from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
            from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
            from graphiti_core.llm_client.config import LLMConfig
            from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

            base_v1 = self._llm_base_url.rstrip("/") + "/v1"
            llm_config = LLMConfig(api_key="local", model=self._llm_model, base_url=base_v1)
            llm_client = OpenAIGenericClient(config=llm_config)

            embed_v1 = self._embed_base_url.rstrip("/") + "/v1"
            embed_config = OpenAIEmbedderConfig(
                api_key="local",
                embedding_model=self._embed_model,
                base_url=embed_v1,
            )
            embedder = OpenAIEmbedder(config=embed_config)

            cross_encoder_config = LLMConfig(api_key="local", model=self._llm_model, base_url=base_v1)
            cross_encoder = OpenAIRerankerClient(config=cross_encoder_config)

            self._client = Graphiti(
                self._uri,
                self._user,
                self._password,
                llm_client=llm_client,
                embedder=embedder,
                cross_encoder=cross_encoder,
            )
            await self._client.build_indices_and_constraints()
            logger.info("Graphiti initialized (group_id=%s)", self._group_id)
        except Exception as e:
            logger.warning("Graphiti initialization failed: %s", e)
            self._client = None

    async def add_episode(
        self,
        content: str,
        session_id: str,
        source: str = "user",
        metadata: dict | None = None,
    ) -> str | None:
        """Add episode to Graphiti. Entity extraction runs asynchronously via LLM."""
        if not self._client:
            return None
        try:
            episode_id = str(uuid.uuid4())
            await self._client.add_episode(
                name=episode_id,
                episode_body=content,
                source_description=source,
                reference_time=datetime.now(UTC),
                group_id=self._group_id,
            )
            logger.debug("graphiti: added episode %s (session=%s)", episode_id, session_id)
            return episode_id
        except Exception as e:
            logger.warning("graphiti: add_episode failed: %s", e)
            return None

    async def search(
        self,
        query: str,
        k: int = 5,
        center_node_uuid: str | None = None,
    ) -> list[GraphMemoryResult]:
        """Hybrid search: semantic + BM25 + graph traversal."""
        if not self._client:
            return []
        try:
            results = await self._client.search(
                query=query,
                group_ids=[self._group_id],
                num_results=k,
                center_node_uuid=center_node_uuid,
            )
            out: list[GraphMemoryResult] = []
            for r in results:
                fact = getattr(r, "fact", None) or getattr(r, "content", "") or str(r)
                score = float(getattr(r, "score", 0.0) or 0.0)
                # entity names extracted from fact text (nodes not populated in search results)
                entity_names: list[str] = []
                src_uuid = getattr(r, "source_node_uuid", None)
                tgt_uuid = getattr(r, "target_node_uuid", None)
                if src_uuid:
                    entity_names.append(src_uuid)
                if tgt_uuid:
                    entity_names.append(tgt_uuid)
                out.append(
                    GraphMemoryResult(
                        content=fact,
                        score=score,
                        entity_names=entity_names,
                        valid_from=getattr(r, "valid_at", None),
                        valid_until=getattr(r, "expired_at", None),
                        source="graphiti",
                    )
                )
            return out
        except Exception as e:
            logger.warning("graphiti: search failed: %s", e)
            return []

    async def _neo4j_session(self):
        """Async context manager for a Neo4j session."""
        return AsyncGraphDatabase.driver(self._uri, auth=(self._user, self._password))

    async def get_entity(self, name: str) -> GraphEntity | None:
        """Find entity node by name (case-insensitive) via direct Neo4j query."""
        if not self._client:
            return None
        try:
            async with AsyncGraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            ) as driver:
                async with driver.session() as session:
                    result = await session.run(
                        "MATCH (n:Entity) WHERE toLower(n.name) = toLower($name) "
                        "AND n.group_id = $gid RETURN n LIMIT 1",
                        name=name,
                        gid=self._group_id,
                    )
                    record = await result.single()
                    if not record:
                        return None
                    n = record["n"]
                    return GraphEntity(
                        uuid=str(n.get("uuid", "")),
                        name=n.get("name", name),
                        entity_type=n.get("entity_type", "") or "entity",
                        summary=n.get("summary"),
                        created_at=_to_dt(n.get("created_at")),
                    )
        except Exception as e:
            logger.warning("graphiti: get_entity failed: %s", e)
            return None

    async def get_related(
        self,
        entity_name: str,
        max_hops: int = 2,
    ) -> list[GraphRelation]:
        """Return facts about entity by querying edges in Neo4j directly."""
        if not self._client:
            return []
        try:
            async with AsyncGraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            ) as driver:
                async with driver.session() as session:
                    result = await session.run(
                        "MATCH (src:Entity)-[r:RELATES_TO]->(tgt:Entity) "
                        "WHERE (toLower(src.name) = toLower($name) "
                        "   OR toLower(tgt.name) = toLower($name)) "
                        "AND r.group_id = $gid "
                        "RETURN src.name AS src, tgt.name AS tgt, "
                        "r.fact AS fact, r.name AS rel_type, "
                        "r.valid_at AS valid_at, "
                        "r.invalid_at AS invalid_at, r.uuid AS ruuid "
                        "LIMIT $limit",
                        name=entity_name,
                        gid=self._group_id,
                        limit=20,
                    )
                    records = await result.data()
                    relations: list[GraphRelation] = []
                    for rec in records:
                        valid_at = rec.get("valid_at")
                        invalid_at = rec.get("invalid_at")
                        relations.append(
                            GraphRelation(
                                subject=rec.get("src", ""),
                                predicate=rec.get("fact", "") or rec.get("rel_type", ""),
                                object=rec.get("tgt", ""),
                                valid_from=_to_dt(valid_at) if valid_at else None,
                                valid_until=_to_dt(invalid_at) if invalid_at else None,
                                episode_id="",
                            )
                        )
                    return relations
        except Exception as e:
            logger.warning("graphiti: get_related failed: %s", e)
            return []

    async def invalidate_fact(
        self,
        subject: str,
        predicate: str,
        reason: str,
    ) -> bool:
        """Mark matching edges as invalid via Neo4j (bi-temporal)."""
        if not self._client:
            return False
        try:
            now = datetime.now(UTC)
            async with AsyncGraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            ) as driver:
                async with driver.session() as session:
                    result = await session.run(
                        "MATCH (src:Entity)-[r:RELATES_TO]->(:Entity) "
                        "WHERE toLower(src.name) = toLower($subject) "
                        "AND toLower(r.fact) CONTAINS toLower($predicate) "
                        "AND r.group_id = $gid "
                        "AND r.invalid_at IS NULL "
                        "SET r.invalid_at = $now "
                        "RETURN count(r) AS invalidated",
                        subject=subject,
                        predicate=predicate,
                        gid=self._group_id,
                        now=now,
                    )
                    record = await result.single()
                    invalidated = record["invalidated"] if record else 0
            logger.info(
                "graphiti: invalidated %d edge(s) for %s/%s",
                invalidated,
                subject,
                predicate,
            )
            return invalidated > 0
        except Exception as e:
            logger.warning("graphiti: invalidate_fact failed: %s", e)
            return False

    async def entity_timeline(
        self,
        entity_name: str,
        limit: int = 20,
    ) -> list[TimelineEvent]:
        """Return chronological facts about entity via Neo4j query."""
        if not self._client:
            return []
        try:
            async with AsyncGraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            ) as driver:
                async with driver.session() as session:
                    result = await session.run(
                        "MATCH (src:Entity)-[r:RELATES_TO]->(tgt:Entity) "
                        "WHERE (toLower(src.name) = toLower($name) "
                        "   OR toLower(tgt.name) = toLower($name)) "
                        "AND r.group_id = $gid "
                        "RETURN r.fact AS fact, r.created_at AS ts, "
                        "r.invalid_at AS invalid_at "
                        "ORDER BY r.created_at ASC LIMIT $limit",
                        name=entity_name,
                        gid=self._group_id,
                        limit=limit,
                    )
                    records = await result.data()
                    events: list[TimelineEvent] = []
                    for rec in records:
                        events.append(
                            TimelineEvent(
                                timestamp=_to_dt(rec.get("ts")),
                                fact=rec.get("fact", ""),
                                source="graphiti",
                                still_valid=rec.get("invalid_at") is None,
                            )
                        )
                    events.sort(key=lambda e: e.timestamp)
                    return events
        except Exception as e:
            logger.warning("graphiti: entity_timeline failed: %s", e)
            return []

    async def health(self) -> dict:
        """Return status with entity and edge counts."""
        if not self._client:
            return {"status": "error", "entity_count": 0, "edge_count": 0}
        try:
            async with AsyncGraphDatabase.driver(
                self._uri, auth=(self._user, self._password)
            ) as driver:
                async with driver.session() as session:
                    node_res = await session.run("MATCH (n) RETURN count(n) as c")
                    node_rec = await node_res.single()
                    edge_res = await session.run("MATCH ()-[r]->() RETURN count(r) as c")
                    edge_rec = await edge_res.single()
                    entity_count = node_rec["c"] if node_rec else 0
                    edge_count = edge_rec["c"] if edge_rec else 0
            return {"status": "ok", "entity_count": entity_count, "edge_count": edge_count}
        except Exception as e:
            logger.warning("graphiti: health check failed: %s", e)
            return {"status": "error", "entity_count": 0, "edge_count": 0}
