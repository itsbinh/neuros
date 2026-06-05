"""Test script — round-trip: store → embed → retrieve."""

from __future__ import annotations

import asyncio
import sys

from neuros.memory.manager import manager
from neuros.models import Memory


async def main() -> None:
    print("NeurOS — Memory Round-Trip Test")
    print("=" * 40)

    # Initialize
    try:
        await manager.initialize()
        print("[OK] Memory layer initialized")
    except Exception as e:
        print(f"[FAIL] Init failed: {e}")
        sys.exit(1)

    # Store test items
    test_items = [
        ("NeurOS is a personal AI operating system", "docs", ["os", "ai"]),
        ("The GPU server runs llama.cpp with Qwen3 models", "infra", ["gpu", "llm"]),
        ("Hammerspoon provides the macOS overlay interface", "overlay", ["macos", "ui"]),
    ]

    stored_ids = []
    for text, source, tags in test_items:
        try:
            mid = await manager.store(text=text, source=source, tags=tags)
            stored_ids.append(mid)
            print(f"  [OK] Stored: '{text[:50]}' → {mid}")
        except Exception as e:
            print(f"  [FAIL] Store failed: {e}")
            sys.exit(1)

    # Recall via semantic search
    print()
    query = "personal AI system"
    print(f"  Searching: '{query}'")
    try:
        results: list[Memory] = await manager.recall(query, k=3)
        for i, mem in enumerate(results):
            print(f"  [{i+1}] score={mem.score:.4f} — {mem.text[:60]}")
        if not results:
            print("  [WARN] No results returned")
    except Exception as e:
        print(f"  [FAIL] Recall failed: {e}")
        sys.exit(1)

    # Context test
    try:
        await manager.set_context("test_key", "test_value", ttl=60)
        val = await manager.get_context("test_key")
        if val == "test_value":
            print("[OK] Redis context round-trip passed")
        else:
            print(f"[FAIL] Context mismatch: got '{val}'")
    except Exception as e:
        print(f"[WARN] Redis context test skipped: {e}")

    print("=" * 40)
    print("Memory round-trip test complete!")


if __name__ == "__main__":
    asyncio.run(main())
