"""Embedding client — always routes to lts1:8005. Never uses LLM for embeddings."""

from __future__ import annotations

import logging

import httpx

from neuros.config import settings

logger = logging.getLogger("neuros.llm.embedder")

_DEFAULT_MODEL = "embed"  # adjust to match your embed server's model name


async def embed(text: str, model: str = _DEFAULT_MODEL) -> list[float]:
    """Generate an embedding vector for the given text.

    Always routes to lts1:8005 — never delegates to an LLM endpoint.

    Args:
        text: Input text to embed.
        model: Embedding model name.

    Returns:
        List of floats representing the embedding vector.
    """
    url = f"{settings.lts1_embed_url}/v1/embeddings"
    payload = {
        "model": model,
        "input": text,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    # OpenAI-compatible embedding response format
    if "data" in data and len(data["data"]) > 0:
        return data["data"][0]["embedding"]

    raise ValueError(f"Unexpected embed response format: {data}")


async def embed_batch(texts: list[str], model: str = _DEFAULT_MODEL) -> list[list[float]]:
    """Generate embeddings for multiple texts in one request.

    Args:
        texts: List of input texts.
        model: Embedding model name.

    Returns:
        List of embedding vectors, one per input text.
    """
    url = f"{settings.lts1_embed_url}/v1/embeddings"
    payload = {
        "model": model,
        "input": texts,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    if "data" in data:
        return [item["embedding"] for item in data["data"]]

    raise ValueError(f"Unexpected embed batch response format: {data}")
