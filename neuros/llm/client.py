"""Async OpenAI-compatible LLM client with retry and streaming."""

from __future__ import annotations

import logging
from typing import AsyncIterator

import httpx
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, RateLimitError

logger = logging.getLogger("neuros.llm.client")

_MAX_RETRIES = 3


def _make_client(base_url: str) -> AsyncOpenAI:
    """Create an async OpenAI-compatible client."""
    return AsyncOpenAI(
        api_key="local",  # local endpoints don't need auth
        base_url=base_url,
        timeout=httpx.Timeout(120.0, connect=10.0),
    )


async def chat(
    model: str,
    messages: list[dict],
    base_url: str,
    *,
    stream: bool = False,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> str | AsyncIterator[str]:
    """Send a chat completion request with exponential backoff retry.

    Args:
        model: Model name identifier.
        messages: List of role/content message dicts.
        base_url: Base URL of the inference endpoint.
        stream: If True, returns an async iterator of chunks.
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.

    Returns:
        Completed text string, or an async iterator if streaming.
    """
    client = _make_client(base_url)
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            if stream:
                return _stream_response(client, kwargs)
            response = await client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            logger.debug("chat response (%s, attempt %d): %s", model, attempt + 1, content[:80])
            return content
        except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
            last_error = exc
            wait = 2**attempt
            logger.warning(
                "chat attempt %d/%d failed (%s), retrying in %ds",
                attempt + 1, _MAX_RETRIES, exc, wait,
            )
            await _async_sleep(wait)
        except Exception as exc:
            logger.error("chat unrecoverable error: %s", exc)
            raise

    raise RuntimeError(f"LLM chat failed after {_MAX_RETRIES} attempts") from last_error


async def _stream_response(client: AsyncOpenAI, kwargs: dict) -> AsyncIterator[str]:
    """Yield streaming response chunks."""
    stream = await client.chat.completions.create(stream=True, **kwargs)
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def _async_sleep(seconds: float) -> None:
    """Async sleep wrapper."""
    import asyncio

    await asyncio.sleep(seconds)
