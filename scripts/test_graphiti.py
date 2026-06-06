"""Full round-trip test for Graphiti temporal knowledge graph.

Run: python scripts/test_graphiti.py
Exits 0 only if all steps pass.
"""

from __future__ import annotations

import asyncio
import sys
import time

from neuros.config import settings

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    status = PASS if ok else FAIL
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


async def main() -> None:
    print("NeurOS — Graphiti Round-Trip Test")
    print("=" * 50)

    # ── 1. NEO4J_CONNECT ───────────────────────────────────────────
    print("\n[1] NEO4J_CONNECT")
    driver = None
    try:
        from neo4j import AsyncGraphDatabase

        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        await driver.verify_connectivity()
        record("NEO4J_CONNECT", True, f"bolt={settings.neo4j_uri}")
    except Exception as e:
        record("NEO4J_CONNECT", False, str(e))
        print("\nNeo4j unreachable — aborting remaining tests.")
        _summarize()
        sys.exit(1)

    # ── 2. ADD_EPISODE ─────────────────────────────────────────────
    print("\n[2] ADD_EPISODE")
    from neuros.memory.graphiti_store import GraphitiStore

    store = GraphitiStore(
        neo4j_uri=settings.neo4j_uri,
        neo4j_user=settings.neo4j_user,
        neo4j_password=settings.neo4j_password,
        llm_base_url=settings.lts1_base_url,
        llm_model=settings.model_fast,
        embed_base_url=settings.lts1_embed_url,
    )
    await store.initialize()

    if not store._client:
        record("ADD_EPISODE", False, "Graphiti client not initialized")
        _summarize()
        sys.exit(1)

    ep1 = await store.add_episode(
        "NeurOS is a personal AI OS running on Mac Mini, lts1, and lts2. "
        "lts1 runs Qwen3-35B-A3B and Qwen3-27B.",
        session_id="test-graphiti-001",
        source="user",
    )
    record("ADD_EPISODE", ep1 is not None, f"episode_id={ep1}")

    # ── 3. ENTITY_EXTRACT ─────────────────────────────────────────
    print("\n[3] ENTITY_EXTRACT")
    await asyncio.sleep(2)  # let Graphiti extract entities
    search_results = await store.search("NeurOS", k=3)
    found = any(
        "neuros" in r.content.lower() or "lts1" in r.content.lower() for r in search_results
    )
    record("ENTITY_EXTRACT", found, f"{len(search_results)} result(s)")

    # ── 4. GET_ENTITY ─────────────────────────────────────────────
    print("\n[4] GET_ENTITY")
    entity = await store.get_entity("lts1")
    record("GET_ENTITY", entity is not None, f"entity={entity.name if entity else None}")

    # ── 5. GET_RELATED ────────────────────────────────────────────
    print("\n[5] GET_RELATED")
    relations = await store.get_related("NeurOS", max_hops=2)
    record("GET_RELATED", len(relations) > 0, f"{len(relations)} relation(s)")

    # ── 6. SECOND_EPISODE ─────────────────────────────────────────
    print("\n[6] SECOND_EPISODE")
    ep2 = await store.add_episode(
        "lts1 GPU server was upgraded, now running Qwen3-72B",
        session_id="test-graphiti-001",
        source="user",
    )
    record("SECOND_EPISODE", ep2 is not None, f"episode_id={ep2}")
    await asyncio.sleep(2)

    # ── 7. TIMELINE ───────────────────────────────────────────────
    print("\n[7] TIMELINE")
    events = await store.entity_timeline("lts1")
    chronological = all(
        events[i].timestamp <= events[i + 1].timestamp for i in range(len(events) - 1)
    )
    record(
        "TIMELINE",
        len(events) >= 1 and chronological,
        f"{len(events)} event(s), chronological={chronological}",
    )

    # ── 8. INVALIDATE ─────────────────────────────────────────────
    print("\n[8] INVALIDATE")
    ok = await store.invalidate_fact("lts1", "runs", "model upgraded")
    record("INVALIDATE", ok is not None, f"result={ok}")

    # ── 9. MERGED_RECALL ──────────────────────────────────────────
    print("\n[9] MERGED_RECALL")
    from qdrant_client import AsyncQdrantClient
    from neuros.llm.embedder import embed as embed_fn
    from neuros.memory.qdrant import QdrantStore
    from neuros.memory.redis import RedisStore
    from neuros.memory.postgres import PostgresStore
    from neuros.memory.manager import MemoryManager

    qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)
    qdrant = QdrantStore(embedder=embed_fn, client=qdrant_client)
    redis = RedisStore()
    await redis.connect()
    postgres = PostgresStore()
    mem = MemoryManager(qdrant=qdrant, redis=redis, postgres=postgres, graphiti=store)

    merged = await mem.recall("tell me about lts1", k=5, session_id="test-graphiti-001")
    has_graph = any(r.metadata.get("source") == "graphiti" for r in merged)
    has_qdrant = any(r.metadata.get("source") != "graphiti" for r in merged)
    record(
        "MERGED_RECALL",
        len(merged) > 0,
        f"{len(merged)} result(s), graph={has_graph}, qdrant={has_qdrant}",
    )

    # ── 10. HEALTH ────────────────────────────────────────────────
    print("\n[10] HEALTH")
    health = await mem.health()
    all_ok = all(
        (v == "ok" if isinstance(v, str) else v.get("status") == "ok") for v in health.values()
    )
    record("HEALTH", all_ok, str(health))

    # ── 11. CLEANUP ───────────────────────────────────────────────
    print("\n[11] CLEANUP")
    try:
        async with driver.session() as session:
            await session.run(
                "MATCH (n) WHERE n.group_id = $gid AND n.session_id = $sid DETACH DELETE n",
                gid="neuros",
                sid="test-graphiti-001",
            )
        record("CLEANUP", True, "test nodes removed")
    except Exception as e:
        record("CLEANUP", False, str(e))

    await redis.disconnect()
    await qdrant_client.close()
    if driver:
        await driver.close()

    _summarize()


def _summarize() -> None:
    print("\n" + "=" * 50)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    if passed < total:
        print("Failed steps:")
        for name, ok, detail in results:
            if not ok:
                print(f"  - {name}: {detail}")
        sys.exit(1)
    else:
        print("All steps passed.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
