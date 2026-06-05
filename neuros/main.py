"""FastAPI application entry point for NeurOS."""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import AsyncQdrantClient

from neuros.config import settings
from neuros.graph import build_graph
from neuros.llm.embedder import embed as embed_fn
import neuros.memory.manager as memory_module
from neuros.memory.manager import MemoryManager
from neuros.memory.graphiti_store import GraphitiStore
from neuros.memory.postgres import PostgresStore
from neuros.memory.qdrant import QdrantStore
from neuros.memory.redis import RedisStore
from neuros.models import ActionInput, NeurOSResponse, NeurOSState, QueryInput
from neuros.skills.registry import SkillRegistry

logger = logging.getLogger("neuros")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize all stores and compile the graph on startup."""
    logger.info("NeurOS starting up")

    embedder = embed_fn
    qdrant_client = AsyncQdrantClient(url=settings.qdrant_url)

    qdrant = QdrantStore(embedder=embedder, client=qdrant_client)
    redis = RedisStore()
    postgres = PostgresStore()

    await postgres.create_tables()
    await redis.connect()
    await qdrant.ensure_collection(postgres=postgres)

    graphiti = GraphitiStore(
        neo4j_uri=settings.neo4j_uri,
        neo4j_user=settings.neo4j_user,
        neo4j_password=settings.neo4j_password,
        llm_base_url=settings.lts1_base_url,
        llm_model=settings.model_fast,
        embed_base_url=settings.lts1_embed_url,
    )
    await graphiti.initialize()

    memory = MemoryManager(qdrant=qdrant, redis=redis, postgres=postgres, graphiti=graphiti)
    memory_module.manager = memory
    registry = SkillRegistry.auto_discover()
    app.state.memory = memory
    app.state.registry = registry
    app.state.graph = build_graph(memory, registry)

    logger.info("NeurOS: %d skills loaded", len(registry.all_skills()))
    for s in registry.all_skills():
        logger.debug("  skill: %s — %s", s.name, s.description)
    logger.info("NeurOS ready")
    yield

    await redis.disconnect()
    await qdrant_client.close()
    logger.info("NeurOS shut down")


app = FastAPI(
    title="NeurOS",
    description="Personal AI operating system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    """Health check including memory store status."""
    memory_health = await app.state.memory.health()
    return {"status": "ok", "memory": memory_health, "version": "0.1.0"}


@app.get("/skills")
async def skills_list() -> list[dict]:
    """List all registered skills with metadata."""
    registry = app.state.registry
    return [
        {
            "name": s.name,
            "description": s.description,
            "parameter_count": len(s.parameters.get("properties", {})),
        }
        for s in registry.all_skills()
    ]


@app.post("/query", response_model=NeurOSResponse)
async def query(input: QueryInput) -> NeurOSResponse:
    """Process a user query through the agent graph."""
    session_id = input.session_id or str(uuid.uuid4())
    initial_state: NeurOSState = {
        "input": input.text,
        "session_id": session_id,
        "context": [],
        "response": "",
        "tool_calls": [],
        "skill_result": None,
        "model_used": "",
        "latency_ms": 0,
        "error": None,
    }
    result = await app.state.graph.ainvoke(initial_state)
    return NeurOSResponse(
        text=result.get("response", ""),
        model_used=result.get("model_used"),
        session_id=session_id,
    )


@app.post("/action", response_model=NeurOSResponse)
async def action(input: ActionInput) -> NeurOSResponse:
    """Invoke a specific skill directly."""
    raise HTTPException(status_code=501, detail="Skill dispatch not yet wired")
