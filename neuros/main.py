"""FastAPI application entry point for NeurOS."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from qdrant_client import AsyncQdrantClient

import neuros.memory.manager as memory_module
from neuros.config import settings
from neuros.graph import _classify_dogfood, _is_entity_query, build_graph
from neuros.llm.client import chat
from neuros.llm.embedder import embed as embed_fn
from neuros.llm.registry import get_models
from neuros.llm.selector import select_model
from neuros.memory.graphiti_store import GraphitiStore
from neuros.memory.manager import MemoryManager
from neuros.memory.postgres import PostgresStore
from neuros.memory.qdrant import QdrantStore
from neuros.memory.redis import RedisStore
from neuros.models import ActionInput, NeurOSResponse, NeurOSState, QueryInput, TaskType
from neuros.skills.registry import SkillRegistry
from neuros.skills.search.searxng import SearXNGSkill

logger = logging.getLogger("neuros")


def _format_search_results(data: dict) -> str:
    results = data.get("results") or []
    if not results:
        return "No search results found."

    lines = []
    for idx, item in enumerate(results, start=1):
        title = item.get("title") or "(untitled)"
        url = item.get("url") or ""
        snippet = item.get("snippet") or ""
        source = item.get("source") or "search"
        lines.append(f"{idx}. {title}\n{url}\n{snippet}\nSource: {source}".strip())
    return "\n\n".join(lines)


def _requested_model_name(input: QueryInput) -> str | None:
    name = (input.model_name or "").strip()
    return name or None


def _validate_text_model(model_name: str | None) -> None:
    if model_name is None:
        return
    try:
        select_model(TaskType.REASONING, model_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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
    registry = getattr(app.state, "registry", None)
    skills_loaded = len(registry.all_skills()) if registry is not None else 0
    return {
        "status": "ok",
        "memory": memory_health,
        "skills_loaded": skills_loaded,
        "version": "0.1.0",
    }


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


@app.get("/models")
async def models_list() -> list[dict]:
    """List configured model names without exposing endpoint URLs."""
    default_model = select_model(TaskType.REASONING).name
    return [
        {
            "name": m.name,
            "capabilities": m.capabilities,
            "default": m.name == default_model,
        }
        for m in get_models()
        if "text" in m.capabilities
    ]


@app.post("/query", response_model=NeurOSResponse)
async def query(input: QueryInput) -> NeurOSResponse:
    """Process a user query through the agent graph."""
    session_id = input.session_id or str(uuid.uuid4())
    text = input.text.strip()
    model_name = _requested_model_name(input)
    _validate_text_model(model_name)
    t0 = time.monotonic()

    if text.lower().startswith("search:"):
        query_text = text.split(":", 1)[1].strip()
        if not query_text:
            return NeurOSResponse(
                text="Type a search query after search:",
                model_used="searxng",
                skill_used="searxng",
                latency_ms=0,
                session_id=session_id,
            )

        result = await SearXNGSkill().run(query=query_text)
        latency_ms = int((time.monotonic() - t0) * 1000)
        if not result.success:
            return NeurOSResponse(
                text=f"Search failed: {result.error}",
                model_used="searxng",
                skill_used="searxng",
                latency_ms=latency_ms,
                session_id=session_id,
            )

        return NeurOSResponse(
            text=_format_search_results(result.data or {}),
            search_results=(result.data or {}).get("results", []),
            model_used="searxng",
            skill_used="searxng",
            latency_ms=latency_ms,
            session_id=session_id,
        )

    initial_state: NeurOSState = {
        "input": input.text,
        "session_id": session_id,
        "model_name": model_name,
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
        skill_used=result.get("skill_used"),
        latency_ms=result.get("latency_ms"),
        session_id=session_id,
    )


async def _bg_store(
    session_id: str, input_text: str, response: str, model_used: str, latency_ms: int
) -> None:
    try:
        memory = app.state.memory
        await memory.push_recent(input_text, session_id)
        await memory.push_recent(response, session_id)
        await memory.store(
            input_text, {"source": "user", "session_id": session_id, "type": "interaction"}
        )
        await memory.log_interaction(
            session_id=session_id,
            input=input_text,
            output=response,
            model_used=model_used,
            latency_ms=latency_ms,
        )
    except Exception as e:
        logger.warning("stream: store failed: %s", e)


@app.post("/query/stream")
async def query_stream(input: QueryInput) -> StreamingResponse:
    """Stream a query response as SSE tokens."""
    session_id = input.session_id or str(uuid.uuid4())
    text = input.text.strip()
    model_name = _requested_model_name(input)
    _validate_text_model(model_name)

    async def event_gen():
        async def emit_text(text: str):
            for idx in range(0, len(text), 6):
                yield f"data: {json.dumps({'token': text[idx:idx + 6]})}\n\n"
                await asyncio.sleep(0.006)

        if text.lower().startswith("search:"):
            t0 = time.monotonic()
            query_text = text.split(":", 1)[1].strip()
            if not query_text:
                response_text = "Type a search query after search:"
            else:
                result = await SearXNGSkill().run(query=query_text)
                response_text = (
                    _format_search_results(result.data or {})
                    if result.success
                    else f"Search failed: {result.error}"
                )
            async for event in emit_text(response_text):
                yield event
            done = json.dumps(
                {
                    "done": True,
                    "model": "searxng",
                    "latency_ms": int((time.monotonic() - t0) * 1000),
                    "skill_used": "searxng",
                }
            )
            yield f"data: {done}\n\n"
            return

        # Non-streamable intents: run full graph, emit short character chunks
        if _classify_dogfood(text) or _is_entity_query(text):
            initial_state: NeurOSState = {
                "input": text,
                "session_id": session_id,
                "model_name": model_name,
                "context": [],
                "response": "",
                "tool_calls": [],
                "skill_result": None,
                "model_used": "",
                "latency_ms": 0,
                "error": None,
            }
            result = await app.state.graph.ainvoke(initial_state)
            response_text = result.get("response", "")
            model_used = result.get("model_used", "agent")
            latency_ms = result.get("latency_ms", 0)
            skill_used = result.get("skill_used")
            async for event in emit_text(response_text):
                yield event
            done = json.dumps(
                {
                    "done": True,
                    "model": model_used,
                    "latency_ms": latency_ms,
                    "skill_used": skill_used,
                }
            )
            yield f"data: {done}\n\n"
            return

        # Streaming path: recall → stream LLM
        context: list[str] = []
        try:
            results = await app.state.memory.recall(text, k=3, session_id=session_id)
            seen: set[str] = set()
            for r in results:
                if r.text not in seen:
                    context.append(r.text)
                    seen.add(r.text)
        except Exception as e:
            logger.warning("stream recall failed: %s", e)

        model_config = select_model(TaskType.REASONING, model_name)
        sys_prompt = "You are NeurOS, a personal AI assistant. Be direct and concise."
        messages: list[dict] = [{"role": "system", "content": sys_prompt}]
        if context:
            messages.append(
                {"role": "system", "content": "Relevant context:\n" + "\n".join(context)}
            )
        messages.append({"role": "user", "content": text})

        t0 = time.monotonic()
        full_response: list[str] = []

        try:
            stream = await chat(
                model=model_config.name,
                messages=messages,
                base_url=model_config.base_url,
                stream=True,
            )
            async for token in stream:
                full_response.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
        except Exception as e:
            logger.error("stream LLM failed: %s", e)
            yield f"data: {json.dumps({'token': f'Error: {e}'})}\n\n"

        latency_ms = int((time.monotonic() - t0) * 1000)
        done = json.dumps({"done": True, "model": model_config.name, "latency_ms": latency_ms})
        yield f"data: {done}\n\n"

        asyncio.create_task(
            _bg_store(session_id, text, "".join(full_response), model_config.name, latency_ms)
        )

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/proposals")
async def proposals_list(status: str | None = None, limit: int = 20) -> list[dict]:
    postgres = app.state.memory._postgres
    items = await postgres.list_proposals(status=status, limit=limit)
    return [p.model_dump(mode="json") for p in items]


@app.get("/proposals/{proposal_id}")
async def proposals_get(proposal_id: str) -> dict:
    postgres = app.state.memory._postgres
    p = await postgres.get_proposal(proposal_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return p.model_dump(mode="json")


@app.post("/proposals/{proposal_id}/approve")
async def proposals_approve(proposal_id: str) -> dict:
    from neuros.skills.code.applier import ApplyChangeSkill

    postgres = app.state.memory._postgres
    if await postgres.get_proposal(proposal_id) is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await postgres.update_proposal_status(proposal_id, "approved")
    apply_result = await ApplyChangeSkill().run(proposal_id=proposal_id, confirmed=True)
    p = await postgres.get_proposal(proposal_id)
    return {
        "proposal": p.model_dump(mode="json"),
        "apply_result": apply_result.model_dump(mode="json"),
    }


@app.post("/proposals/{proposal_id}/reject")
async def proposals_reject(proposal_id: str) -> dict:
    postgres = app.state.memory._postgres
    if await postgres.get_proposal(proposal_id) is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await postgres.update_proposal_status(proposal_id, "rejected")
    p = await postgres.get_proposal(proposal_id)
    return p.model_dump(mode="json")


@app.get("/git/status")
async def git_status_endpoint() -> dict:
    from neuros.skills.code.git_ops import GitStatusSkill

    result = await GitStatusSkill().run()
    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)
    return result.data


@app.post("/action", response_model=NeurOSResponse)
async def action(input: ActionInput) -> NeurOSResponse:
    """Invoke a specific skill directly by name."""
    session_id = input.session_id or str(uuid.uuid4())
    result = await app.state.registry.execute(input.skill, **input.params)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error or "Skill execution failed")
    return NeurOSResponse(
        text=str(result.data),
        model_used=input.skill,
        skill_used=input.skill,
        session_id=session_id,
    )
