"""Test script — embed a test string via lts1:8005 and validate the vector."""

from __future__ import annotations

import asyncio
import sys

from neuros.config import settings
from neuros.llm.embedder import embed


async def main() -> None:
    print("NeurOS — Embedding Test")
    print("=" * 40)

    test_text = "The quick brown fox jumps over the lazy dog."
    print(f"  Embedding: '{test_text}'")
    print(f"  Endpoint: {settings.lts1_embed_url}")

    try:
        vector = await embed(test_text)
        dim = len(vector)
        magnitude = sum(x * x for x in vector) ** 0.5

        print(f"  [OK] Vector dimension: {dim}")
        print(f"  [OK] Magnitude: {magnitude:.4f}")
        print(f"  [OK] First 5 values: {[round(x, 4) for x in vector[:5]]}")

        if dim == 0:
            print("[FAIL] Zero-dimensional vector")
            sys.exit(1)
        if magnitude < 0.01:
            print("[WARN] Very small magnitude — check embedding quality")

    except Exception as e:
        print(f"[FAIL] {e}")
        sys.exit(1)

    print("=" * 40)
    print("Embedding test passed!")


if __name__ == "__main__":
    asyncio.run(main())
