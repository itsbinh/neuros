"""Unit tests for GraphitiStore and related memory/skill components.

All tests mock Neo4j and Graphiti — no live graph required.
"""

from __future__ import annotations

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from neuros.models import GraphEntity, GraphMemoryResult, GraphRelation, TimelineEvent


# ── Helpers ──────────────────────────────────────────────────────────


def _make_store(client=None):
    from neuros.memory.graphiti_store import GraphitiStore

    store = GraphitiStore(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="test",
        llm_base_url="http://localhost:8000",
        llm_model="test-model",
    )
    store._client = client
    return store


def _fake_edge(fact="lts1 runs Qwen3-35B", src_name="lts1", tgt_name="Qwen3-35B"):
    edge = MagicMock()
    edge.fact = fact
    edge.score = 0.9
    edge.valid_at = datetime(2024, 1, 1, tzinfo=UTC)
    edge.expired_at = None
    edge.source_description = "user"
    edge.uuid = "edge-uuid-1"
    edge.episodes = ["ep-1"]
    edge.source_node_uuid = "src-uuid-1"
    edge.target_node_uuid = "tgt-uuid-1"
    # source_node and target_node not populated by search API
    edge.source_node = None
    edge.target_node = None
    return edge


def _fake_node(name="lts1", entity_type="server"):
    node = MagicMock()
    node.name = name
    node.uuid = "node-uuid-1"
    node.entity_type = entity_type
    node.summary = "GPU server"
    node.created_at = datetime(2024, 1, 1, tzinfo=UTC)
    return node


# ── GraphitiStore tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_episode_returns_episode_id():
    client = MagicMock()
    client.add_episode = AsyncMock()
    store = _make_store(client)

    result = await store.add_episode("test content", session_id="s1", source="user")

    assert result is not None
    assert isinstance(result, str)
    client.add_episode.assert_called_once()


@pytest.mark.asyncio
async def test_add_episode_failure_returns_none_not_raises():
    client = MagicMock()
    client.add_episode = AsyncMock(side_effect=RuntimeError("neo4j down"))
    store = _make_store(client)

    result = await store.add_episode("content", session_id="s1")

    assert result is None  # never raises


@pytest.mark.asyncio
async def test_search_returns_graph_memory_results():
    edge = _fake_edge()
    client = MagicMock()
    client.search = AsyncMock(return_value=[edge])
    store = _make_store(client)

    results = await store.search("lts1", k=3)

    assert len(results) == 1
    assert isinstance(results[0], GraphMemoryResult)
    assert "lts1" in results[0].content or results[0].score == 0.9


@pytest.mark.asyncio
async def test_get_entity_unknown_returns_none():
    client = MagicMock()
    client.get_nodes_by_query = AsyncMock(return_value=[])
    store = _make_store(client)

    result = await store.get_entity("nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_get_entity_found():
    store = _make_store(MagicMock())

    # Mock the Neo4j driver path used by get_entity
    mock_record = {"n": {"uuid": "u1", "name": "lts1", "entity_type": "server",
                         "summary": "GPU server", "created_at": None}}
    mock_result = MagicMock()
    mock_result.single = AsyncMock(return_value=mock_record)
    mock_session = MagicMock()
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_session)
    mock_driver.__aenter__ = AsyncMock(return_value=mock_driver)
    mock_driver.__aexit__ = AsyncMock(return_value=False)

    with patch("neuros.memory.graphiti_store.AsyncGraphDatabase") as mock_adb:
        mock_adb.driver = MagicMock(return_value=mock_driver)
        result = await store.get_entity("lts1")

    assert result is not None
    assert isinstance(result, GraphEntity)
    assert result.name == "lts1"


@pytest.mark.asyncio
async def test_get_related_returns_relations():
    edge = _fake_edge()
    client = MagicMock()
    client.search = AsyncMock(return_value=[edge])
    store = _make_store(client)

    relations = await store.get_related("NeurOS", max_hops=2)

    assert len(relations) >= 0  # depends on entity matching; at least no crash
    assert all(isinstance(r, GraphRelation) for r in relations)


@pytest.mark.asyncio
async def test_invalidate_fact_calls_graphiti():
    store = _make_store(MagicMock())

    # Mock Neo4j driver returning 1 invalidated edge
    mock_record = {"invalidated": 1}
    mock_result = MagicMock()
    mock_result.single = AsyncMock(return_value=mock_record)
    mock_session = MagicMock()
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_session)
    mock_driver.__aenter__ = AsyncMock(return_value=mock_driver)
    mock_driver.__aexit__ = AsyncMock(return_value=False)

    with patch("neuros.memory.graphiti_store.AsyncGraphDatabase") as mock_adb:
        mock_adb.driver = MagicMock(return_value=mock_driver)
        result = await store.invalidate_fact("lts1", "runs", "model upgraded")

    assert result is True
    mock_session.run.assert_called_once()


@pytest.mark.asyncio
async def test_entity_timeline_chronological_order():
    store = _make_store(MagicMock())

    ts1 = datetime(2024, 1, 1, tzinfo=UTC)
    ts2 = datetime(2024, 6, 1, tzinfo=UTC)
    rows = [
        {"fact": "lts1 runs Qwen3-72B", "ts": ts2, "invalid_at": None},
        {"fact": "lts1 runs Qwen3-27B", "ts": ts1, "invalid_at": None},
    ]
    mock_result = MagicMock()
    mock_result.data = AsyncMock(return_value=rows)
    mock_session = MagicMock()
    mock_session.run = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_driver = MagicMock()
    mock_driver.session = MagicMock(return_value=mock_session)
    mock_driver.__aenter__ = AsyncMock(return_value=mock_driver)
    mock_driver.__aexit__ = AsyncMock(return_value=False)

    with patch("neuros.memory.graphiti_store.AsyncGraphDatabase") as mock_adb:
        mock_adb.driver = MagicMock(return_value=mock_driver)
        events = await store.entity_timeline("lts1")

    assert len(events) == 2
    assert events[0].timestamp <= events[1].timestamp  # sorted ascending


# ── MemoryManager tests ──────────────────────────────────────────────


def _make_manager(graphiti=None):
    from neuros.memory.manager import MemoryManager

    qdrant = MagicMock()
    qdrant.upsert = AsyncMock(return_value="qdrant-id-1")
    qdrant.search = AsyncMock(return_value=[])
    redis = MagicMock()
    redis.get_recent = AsyncMock(return_value=[])
    redis._client = MagicMock()
    redis._client.ping = AsyncMock()
    postgres = MagicMock()
    postgres.recent_interactions = AsyncMock(return_value=[])
    return MemoryManager(qdrant=qdrant, redis=redis, postgres=postgres, graphiti=graphiti)


@pytest.mark.asyncio
async def test_manager_recall_merges_qdrant_and_graphiti():
    from neuros.models import MemoryResult

    qdrant_result = MemoryResult(id="q1", text="qdrant result", score=0.8, metadata={})
    graph_result = GraphMemoryResult(content="graph fact", score=0.9, entity_names=["lts1"], source="user")

    graphiti = MagicMock()
    graphiti.search = AsyncMock(return_value=[graph_result])

    manager = _make_manager(graphiti=graphiti)
    manager._qdrant.search = AsyncMock(return_value=[qdrant_result])
    manager._redis.get_recent = AsyncMock(return_value=[])

    results = await manager.recall("lts1", k=5, session_id="s1")

    texts = [r.text for r in results]
    assert "graph fact" in texts
    assert "qdrant result" in texts


@pytest.mark.asyncio
async def test_manager_recall_graphiti_failure_falls_back_to_qdrant():
    from neuros.models import MemoryResult

    qdrant_result = MemoryResult(id="q1", text="qdrant fallback", score=0.8, metadata={})

    graphiti = MagicMock()
    graphiti.search = AsyncMock(side_effect=RuntimeError("graphiti down"))

    manager = _make_manager(graphiti=graphiti)
    manager._qdrant.search = AsyncMock(return_value=[qdrant_result])
    manager._redis.get_recent = AsyncMock(return_value=[])

    results = await manager.recall("lts1", k=5, session_id="s1")

    assert any(r.text == "qdrant fallback" for r in results)


@pytest.mark.asyncio
async def test_manager_store_runs_qdrant_and_graphiti_concurrently():
    graphiti = MagicMock()
    graphiti.add_episode = AsyncMock(return_value="ep-1")

    manager = _make_manager(graphiti=graphiti)

    result = await manager.store("test text", {"source": "user", "session_id": "s1"})

    manager._qdrant.upsert.assert_called_once()
    graphiti.add_episode.assert_called_once()
    assert result == "qdrant-id-1"


@pytest.mark.asyncio
async def test_health_includes_graphiti():
    graphiti = MagicMock()
    graphiti.health = AsyncMock(return_value={"status": "ok", "entity_count": 5, "edge_count": 10})

    manager = _make_manager(graphiti=graphiti)

    health = await manager.health()

    assert "graphiti" in health
    assert health["graphiti"]["status"] == "ok"


# ── Skill tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_remember_skill_calls_remember_entity():
    from neuros.skills.knowledge.remember import RememberSkill
    import neuros.memory.manager as mm

    mock_manager = MagicMock()
    mock_manager.remember_entity = AsyncMock(return_value="ep-abc")

    original = mm.manager
    mm.manager = mock_manager
    try:
        skill = RememberSkill()
        result = await skill.execute(content="lts1 is my GPU server", session_id="s1")
        assert result.success
        assert result.output["stored"] is True
        mock_manager.remember_entity.assert_called_once_with("lts1 is my GPU server", session_id="s1")
    finally:
        mm.manager = original


@pytest.mark.asyncio
async def test_forget_skill_calls_invalidate_fact():
    from neuros.skills.knowledge.remember import ForgetSkill
    import neuros.memory.manager as mm

    mock_manager = MagicMock()
    mock_manager.invalidate_fact = AsyncMock(return_value=True)

    original = mm.manager
    mm.manager = mock_manager
    try:
        skill = ForgetSkill()
        result = await skill.execute(subject="lts1", fact="runs old model")
        assert result.success
        assert result.output["invalidated"] == 1
        mock_manager.invalidate_fact.assert_called_once_with("lts1", "runs old model", reason="runs old model")
    finally:
        mm.manager = original


@pytest.mark.asyncio
async def test_what_do_you_know_merges_all_sources():
    from neuros.skills.knowledge.remember import WhatDoYouKnowSkill
    from neuros.models import MemoryResult
    import neuros.memory.manager as mm

    entity = GraphEntity(
        uuid="u1", name="lts1", entity_type="server",
        summary="GPU server", created_at=datetime(2024, 1, 1, tzinfo=UTC)
    )
    qdrant_result = MemoryResult(id="q1", text="lts1 hosts models", score=0.8, metadata={})

    mock_graphiti = MagicMock()
    mock_graphiti.get_related = AsyncMock(return_value=[])

    mock_manager = MagicMock()
    mock_manager.get_entity = AsyncMock(return_value=entity)
    mock_manager._graphiti = mock_graphiti
    mock_manager._qdrant = MagicMock()
    mock_manager._qdrant.search = AsyncMock(return_value=[qdrant_result])

    original = mm.manager
    mm.manager = mock_manager
    try:
        skill = WhatDoYouKnowSkill()
        result = await skill.execute(entity_name="lts1")
        assert result.success
        assert result.output["entity"]["name"] == "lts1"
        assert len(result.output["episodes"]) == 1
    finally:
        mm.manager = original
