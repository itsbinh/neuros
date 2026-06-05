"""Async SQLAlchemy models and session for structured Postgres storage."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import uuid

from sqlalchemy import Column, DateTime, Integer, String, Text, desc, func, select
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from neuros.config import settings
from neuros.models import ProposedChange

logger = logging.getLogger("neuros.memory.postgres")


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


# ── Tables ───────────────────────────────────────────────────────

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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


class Proposal(Base):
    __tablename__ = "proposals"

    id = Column(String(64), primary_key=True)
    path = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    risk = Column(String(16), nullable=False)
    original_text = Column(Text, nullable=False)
    replacement = Column(Text, nullable=False)
    tests_affected = Column(ARRAY(Text), nullable=True)
    status = Column(String(32), nullable=False, default="pending", index=True)
    proposed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    applied_at = Column(DateTime(timezone=True), nullable=True)
    test_result = Column(Text, nullable=True)


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

    # ── Proposals ─────────────────────────────────────────────────

    @staticmethod
    def _proposal_to_model(row: "Proposal") -> ProposedChange:
        return ProposedChange(
            id=row.id,
            path=row.path,
            summary=row.summary,
            reason=row.reason,
            risk=row.risk,
            original=row.original_text,
            replacement=row.replacement,
            tests_affected=list(row.tests_affected or []),
            proposed_at=row.proposed_at,
            status=row.status,
            applied_at=row.applied_at,
            test_result=row.test_result,
        )

    async def save_proposal(self, proposal: ProposedChange) -> str:
        async with self._session_factory() as session:
            row = Proposal(
                id=proposal.id or str(uuid.uuid4()),
                path=proposal.path,
                summary=proposal.summary,
                reason=proposal.reason,
                risk=proposal.risk,
                original_text=proposal.original,
                replacement=proposal.replacement,
                tests_affected=proposal.tests_affected or [],
                status=proposal.status,
                proposed_at=proposal.proposed_at or datetime.now(timezone.utc),
                applied_at=proposal.applied_at,
                test_result=proposal.test_result,
            )
            session.add(row)
            await session.commit()
            return row.id

    async def get_proposal(self, proposal_id: str) -> ProposedChange | None:
        async with self._session_factory() as session:
            row = await session.get(Proposal, proposal_id)
            return self._proposal_to_model(row) if row else None

    async def list_proposals(
        self, status: str | None = None, limit: int = 20
    ) -> list[ProposedChange]:
        async with self._session_factory() as session:
            stmt = select(Proposal).order_by(desc(Proposal.proposed_at)).limit(limit)
            if status:
                stmt = stmt.where(Proposal.status == status)
            result = await session.execute(stmt)
            return [self._proposal_to_model(r) for r in result.scalars().all()]

    async def update_proposal_status(
        self,
        proposal_id: str,
        status: str,
        test_result: str | None = None,
    ) -> None:
        async with self._session_factory() as session:
            row = await session.get(Proposal, proposal_id)
            if row is None:
                return
            row.status = status
            if test_result is not None:
                row.test_result = test_result
            if status == "applied":
                row.applied_at = datetime.now(timezone.utc)
            await session.commit()

    async def latest_proposal(self, status: str = "pending") -> ProposedChange | None:
        async with self._session_factory() as session:
            stmt = (
                select(Proposal)
                .where(Proposal.status == status)
                .order_by(desc(Proposal.proposed_at))
                .limit(1)
            )
            result = await session.execute(stmt)
            row = result.scalars().first()
            return self._proposal_to_model(row) if row else None
