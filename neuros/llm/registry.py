"""Model registry — defines available models and their capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field

from neuros.config import settings


@dataclass
class ModelConfig:
    """Configuration for a single model endpoint."""

    name: str
    base_url: str
    capabilities: list[str] = field(default_factory=list)
    # e.g. ["text", "vision", "embedding"]


# ── Default model registrations ──────────────────────────────────

def get_models() -> list[ModelConfig]:
    """Return all registered models."""
    return [
        ModelConfig(
            name=settings.model_vision,
            base_url=settings.lts1_base_url,
            capabilities=["text", "vision"],
        ),
        ModelConfig(
            name=settings.model_fast,
            base_url=settings.lts1_base_url,
            capabilities=["text"],
        ),
        ModelConfig(
            name=settings.model_local,
            base_url=settings.mac_mini_url,
            capabilities=["text"],
        ),
    ]


# Pre-built lookup by name
_MODELS: dict[str, ModelConfig] = {}


def _build_lookup() -> dict[str, ModelConfig]:
    for m in get_models():
        _MODELS[m.name] = m
    return _MODELS


lookup = _build_lookup()


def get_model(name: str) -> ModelConfig | None:
    """Get model config by name."""
    return lookup.get(name)
