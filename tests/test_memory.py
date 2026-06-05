"""Tests for memory layer components."""

from __future__ import annotations

import pytest

from neuros.memory.postgres import Base, Fact, Interaction


def test_interaction_model() -> None:
    """Interaction table has expected columns."""
    assert hasattr(Interaction, "id")
    assert hasattr(Interaction, "input_text")
    assert hasattr(Interaction, "output_text")
    assert hasattr(Interaction, "skill")
    assert hasattr(Interaction, "ts")


def test_fact_model() -> None:
    """Fact table has expected columns."""
    assert hasattr(Fact, "id")
    assert hasattr(Fact, "key")
    assert hasattr(Fact, "value")
    assert hasattr(Fact, "source")
    assert hasattr(Fact, "ts")


def test_base_metadata() -> None:
    """Base has table metadata."""
    tables = list(Base.metadata.tables.keys())
    assert "interactions" in tables
    assert "facts" in tables
    assert "config" in tables
