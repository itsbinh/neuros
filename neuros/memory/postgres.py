"""Async SQLAlchemy models and session for structured Postgres storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from neuros.config import settings

logger = logging.getLogger("neuros.memory.postgres")


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


# ── Tables ───────────────────────────────────────────────────────

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    input_text = Column(Text, nullable=False)
    output_text = Column(Text, nullable=False)
    skill = Column(String(128), nullable=True)
    ts = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Fact(Base):
    __tablename__ = "facts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(256), nullable=False, index=True)
    value = Column(Text, nullable=False)
    source = Column(String(256), nullable=True)
    ts = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Config(Base):
    __tablename__ = "config"

    key = Column(String(256), primary_key=True)
    value = Column(Text, nullable=False)


# ── Engine & session factory ─────────────────────────────────────

_engine = create_async_engine(settings.postgres_dsn, echo=False)
_session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    """Get a new async database session."""
    return _session_factory()


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Postgres tables ensured")
