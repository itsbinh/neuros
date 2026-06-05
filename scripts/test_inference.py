"""Test script — ping all 3 model endpoints and verify completions."""

from __future__ import annotations

import asyncio
import sys

from neuros.config import settings
from neuros.llm.client import chat


async def test_endpoint(name: str, base_url: str, model: str) -> bool:
    """Test a single model endpoint."""
    print(f"  Testing {name} ({model}) at {base_url}...", end=" ", flush=True)
    try:
        response = await chat(
            model=model,
            messages=[{"role": "user", "content": "Say 'ok' in one word."}],
            base_url=base_url,
            max_tokens=10,
        )
        if response.strip():
            print(f"[OK] '{response.strip()[:40]}'")
            return True
        else:
            print("[FAIL] Empty response")
            return False
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


async def main() -> None:
    print("NeurOS — Inference Stack Test")
    print("=" * 40)

    results = []
    results.append(await test_endpoint(
        "Vision", settings.lts1_base_url, settings.model_vision
    ))
    results.append(await test_endpoint(
        "Fast", settings.lts1_base_url, settings.model_fast
    ))
    results.append(await test_endpoint(
        "Local", settings.mac_mini_url, settings.model_local
    ))

    print("=" * 40)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} endpoints responding")

    if passed < total:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
