"""Full round-trip memory test. Exit 0 only if all steps pass."""

from __future__ import annotations

import asyncio
import sys

from qdrant_client import AsyncQdrantClient

from neuros.config import settings
from neuros.llm.embedder import embed as embed_fn
from neuros.memory.graphiti_store import GraphitiStore
from neuros.memory.manager import MemoryManager
from neuros.memory.postgres import PostgresStore
from neuros.memory.qdrant import QdrantStore
from neuros.memory.redis import RedisStore

PASS = "[PASS]"
FAIL = "[FAIL]"
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"{PASS} {label}")
    else:
        msg = f"{FAIL} {label}" + (f": {detail}" if detail else "")
        print(msg)
        failures.append(label)


async def main() -> None:
    print("NeurOS — Memory Round-Trip Test")
    print("=" * 50)

    qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)
    postgres = PostgresStore()
    redis = RedisStore()
    qdrant = QdrantStore(embedder=embed_fn, client=qdrant_client)

    await postgres.create_tables()
    await redis.connect()
    await qdrant.ensure_collection(postgres=postgres)

    graphiti = GraphitiStore(
        neo4j_uri=settings.neo4j_uri,
        neo4j_user=settings.neo4j_user,
        neo4j_password=settings.neo4j_password,
        llm_base_url=settings.lts1_base_url,
        llm_model=settings.model_fast,
        embed_base_url=settings.lts1_embed_url,
    )
    await graphiti.initialize()
    memory = MemoryManager(qdrant=qdrant, redis=redis, postgres=postgres, graphiti=graphiti)

    # ── Step 1: EMBED ──────────────────────────────────────────────
    try:
        vec = await embed_fn("NeurOS memory test string")
        check("EMBED", len(vec) > 0, f"dim={len(vec)}")
        print(f"       vector dim = {len(vec)}")
    except Exception as e:
        check("EMBED", False, str(e))
        vec = []

    # ── Step 2: UPSERT ─────────────────────────────────────────────
    point_id: str | None = None
    try:
        point_id = await memory.store(
            "NeurOS memory test string",
            {"source": "test", "session_id": "test-001"},
        )
        check("UPSERT", bool(point_id), f"id={point_id}")
    except Exception as e:
        check("UPSERT", False, str(e))

    # ── Step 3: SEARCH ─────────────────────────────────────────────
    try:
        results = await memory.recall("memory test", k=5)
        ids = [r.id for r in results]
        texts = [r.text for r in results]
        found = point_id in ids or any("memory test" in t.lower() for t in texts)
        check("SEARCH", found, f"top ids={ids[:3]}")
        for i, r in enumerate(results):
            print(f"       [{i + 1}] score={r.score:.4f} — {r.text[:60]}")
    except Exception as e:
        check("SEARCH", False, str(e))

    # ── Step 4: REDIS set_context ──────────────────────────────────
    try:
        await memory.set_context("test_key", {"hello": "neuros"}, ttl=60)
        check("REDIS set_context", True)
    except Exception as e:
        check("REDIS set_context", False, str(e))

    # ── Step 5: REDIS get_context ──────────────────────────────────
    try:
        val = await memory.get_context("test_key")
        check("REDIS get_context", val == {"hello": "neuros"}, f"got={val!r}")
    except Exception as e:
        check("REDIS get_context", False, str(e))

    # ── Step 6: RECENT push + get ──────────────────────────────────
    try:
        await memory.push_recent("test message 1", "test-001")
        await memory.push_recent("test message 2", "test-001")
        recent = await memory.get_recent("test-001", n=2)
        has_both = "test message 1" in recent and "test message 2" in recent
        check("RECENT", has_both, f"got={recent!r}")
    except Exception as e:
        check("RECENT", False, str(e))

    # ── Step 7: POSTGRES log_interaction ──────────────────────────
    interaction_id: str | None = None
    try:
        interaction_id = await memory.log_interaction(
            session_id="test-001",
            input="hello",
            output="hi there",
            latency_ms=42,
        )
        check("POSTGRES log_interaction", bool(interaction_id), f"id={interaction_id}")
    except Exception as e:
        check("POSTGRES log_interaction", False, str(e))

    # ── Step 8: POSTGRES recent_interactions ──────────────────────
    try:
        rows = await postgres.recent_interactions(n=1)
        has_row = len(rows) >= 1 and rows[0]["session_id"] == "test-001"
        check("POSTGRES recent_interactions", has_row, f"rows={rows[:1]}")
    except Exception as e:
        check("POSTGRES recent_interactions", False, str(e))

    # ── Step 9: CLEANUP ────────────────────────────────────────────
    try:
        if point_id:
            await qdrant.delete(point_id)
        await redis.flush_session("test-001")
        check("CLEANUP", True)
    except Exception as e:
        check("CLEANUP", False, str(e))

    # ── Step 10: HEALTH ────────────────────────────────────────────
    try:
        h = await memory.health()
        all_ok = all(
            (v == "ok" if isinstance(v, str) else v.get("status") in ("ok", "disabled"))
            for v in h.values()
        )
        check("HEALTH", all_ok, str(h))
        print(f"       {h}")
    except Exception as e:
        check("HEALTH", False, str(e))

    # ── Summary ────────────────────────────────────────────────────
    await redis.disconnect()
    await qdrant_client.close()

    print("=" * 50)
    if failures:
        print(f"FAILED: {len(failures)} step(s): {', '.join(failures)}")
        sys.exit(1)
    else:
        print("All steps passed.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
