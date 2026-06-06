"""Setup script — create Postgres tables and Qdrant collection."""

from __future__ import annotations

import asyncio
import sys

from qdrant_client import AsyncQdrantClient

from neuros.config import settings
from neuros.llm.embedder import embed as embed_fn
from neuros.memory.postgres import PostgresStore
from neuros.memory.qdrant import QdrantStore


async def main() -> None:
    print("NeurOS — Database Setup")
    print("=" * 40)

    # ── Postgres ────────────────────────────────────────────────────
    postgres = PostgresStore()
    try:
        await postgres.create_tables()
        print("[OK] Postgres tables created/verified")
    except Exception as e:
        print(f"[FAIL] Postgres setup failed: {e}")
        sys.exit(1)

    # ── Qdrant ─────────────────────────────────────────────────────
    qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)
    qdrant = QdrantStore(embedder=embed_fn, client=qdrant_client)
    try:
        await qdrant.ensure_collection(postgres=postgres)
        info = await qdrant.collection_info()
        print(
            f"[OK] Qdrant collection '{info['name']}' "
            f"(dim={info['vector_dim']}, vectors={info['vector_count']}, status={info['status']})"
        )
    except Exception as e:
        print(f"[FAIL] Qdrant setup failed: {e}")
        sys.exit(1)
    finally:
        await qdrant_client.close()

    # ── Neo4j ──────────────────────────────────────────────────────
    try:
        from neo4j import AsyncGraphDatabase

        async with AsyncGraphDatabase.driver(
            settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
        ) as driver:
            await driver.verify_connectivity()
            async with driver.session() as session:
                result = await session.run("MATCH (n) RETURN count(n) as count")
                record = await result.single()
                count = record["count"] if record else 0
        if count == 0:
            print("[OK] Neo4j connected (graph empty — will populate on first use)")
        else:
            print(f"[OK] Neo4j connected (entity count: {count})")
    except Exception as e:
        print(f"[WARN] Neo4j not reachable: {e}")

    # ── Graphiti indices ───────────────────────────────────────────
    try:
        from neuros.memory.graphiti_store import GraphitiStore

        g = GraphitiStore(
            neo4j_uri=settings.neo4j_uri,
            neo4j_user=settings.neo4j_user,
            neo4j_password=settings.neo4j_password,
            llm_base_url=settings.lts1_base_url,
            llm_model=settings.model_fast,
            embed_base_url=settings.lts1_embed_url,
        )
        await g.initialize()
        if g._client:
            print("[OK] Graphiti indices built")
        else:
            print("[WARN] Graphiti initialization skipped (check Neo4j + LLM)")
    except Exception as e:
        print(f"[WARN] Graphiti setup failed: {e}")

    # ── Summary ────────────────────────────────────────────────────
    print("=" * 40)
    dim_cfg = await postgres.get_config("qdrant_vector_dim")
    print(f"  Postgres DSN : {settings.postgres_dsn}")
    print(f"  Qdrant URL   : {settings.qdrant_url}")
    print(f"  Neo4j URI    : {settings.neo4j_uri}")
    print(f"  Vector dim   : {dim_cfg}")
    print("Setup complete!")


if __name__ == "__main__":
    asyncio.run(main())
