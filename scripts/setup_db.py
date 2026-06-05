"""Setup script — create Postgres tables and Qdrant collection."""

from __future__ import annotations

import asyncio
import sys

from neuros.memory.postgres import init_db
from neuros.memory.qdrant import store as qdrant_store


async def main() -> None:
    print("NeurOS — Database Setup")
    print("=" * 40)

    # Postgres tables
    try:
        await init_db()
        print("[OK] Postgres tables created")
    except Exception as e:
        print(f"[FAIL] Postgres setup failed: {e}")
        sys.exit(1)

    # Qdrant collection
    try:
        await qdrant_store.ensure_collection(vector_size=3072)
        print("[OK] Qdrant collection created")
    except Exception as e:
        print(f"[FAIL] Qdrant setup failed: {e}")
        sys.exit(1)

    print("=" * 40)
    print("Setup complete!")


if __name__ == "__main__":
    asyncio.run(main())
