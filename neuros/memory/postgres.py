"""Async SQLAlchemy models and session for structured Postgres storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text, desc, func, select
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
    session_id = Column(String(128), nullable=True, index=True)
    input = Column(Text, nullable=False)
    output = Column(Text, nullable=False)
    skill_used = Column(String(128), nullable=True)
    model_used = Column(String(128), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


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


class PostgresStore:
    """High-level store used by MemoryManager."""

    def __init__(self) -> None:
        self._session_factory = _session_factory

    async def create_tables(self) -> None:
        await init_db()

    async def log_interaction(
        self,
        session_id: str,
        input: str,
        output: str,
        skill_used: str | None = None,
        model_used: str | None = None,
        latency_ms: int | None = None,
    ) -> str:
        async with self._session_factory() as session:
            row = Interaction(
                session_id=session_id,
                input=input,
                output=output,
                skill_used=skill_used,
                model_used=model_used,
                latency_ms=latency_ms,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return str(row.id)

    async def recent_interactions(self, n: int = 10) -> list[Interaction]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(Interaction).order_by(desc(Interaction.created_at)).limit(n)
            )
            return list(result.scalars().all())

    async def get_config(self, key: str) -> str | None:
        async with self._session_factory() as session:
            row = await session.get(Config, key)
            return row.value if row else None

    async def set_config(self, key: str, value: str) -> None:
        async with self._session_factory() as session:
            row = await session.get(Config, key)
            if row is None:
                session.add(Config(key=key, value=value))
            else:
                row.value = value
            await session.commit()
