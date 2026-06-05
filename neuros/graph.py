"""LangGraph agent pipeline: intake → recall → [entity_query] → think → act → store → respond."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from langgraph.graph import END, START, StateGraph

from neuros.llm.client import chat
from neuros.llm.selector import select_model
from neuros.models import NeurOSState, TaskType

logger = logging.getLogger("neuros.graph")

_ENTITY_QUERY_PATTERNS = (
    "what do you know about",
    "tell me about",
    "what is ",
    "who is ",
    "history of",
    "what changed",
    "what happened to",
)


def _is_entity_query(text: str) -> bool:
    lower = text.lower().strip()
    return any(lower.startswith(p) or p in lower for p in _ENTITY_QUERY_PATTERNS)


def _extract_entity_name(text: str) -> str:
    lower = text.lower().strip()
    for prefix in sorted(_ENTITY_QUERY_PATTERNS, key=len, reverse=True):
        if prefix in lower:
            idx = lower.index(prefix) + len(prefix)
            return text[idx:].strip().rstrip("?")
    return text.strip()


# ── Node factories ───────────────────────────────────────────────────


def _make_recall(memory: Any):
    async def recall(state: NeurOSState) -> dict:
        session_id = state.get("session_id", "")
        input_text = state.get("input", "")
        context: list[str] = []

        try:
            results = await memory.recall(input_text, k=3, session_id=session_id)
            seen: set[str] = set()
            for r in results:
                if r.text not in seen:
                    context.append(r.text)
                    seen.add(r.text)
        except Exception as e:
            logger.warning("recall: failed [session=%s]: %s", session_id, e)

        intent = "entity_query" if _is_entity_query(input_text) else "query"
        return {"context": context, "intent": intent}

    return recall


def _make_entity_query(memory: Any):
    async def entity_query(state: NeurOSState) -> dict:
        input_text = state.get("input", "")
        session_id = state.get("session_id", "")
        entity_name = _extract_entity_name(input_text)
        context = list(state.get("context") or [])

        try:
            entity = await memory.get_entity(entity_name)
            if entity:
                summary = entity.summary or ""
                context.insert(0, f"Entity: {entity.name} ({entity.entity_type}). {summary}")
        except Exception as e:
            logger.warning("entity_query: get_entity failed [session=%s]: %s", session_id, e)

        try:
            graphiti = getattr(memory, "_graphiti", None)
            relations = await graphiti.get_related(entity_name, max_hops=2) if graphiti else []
            for rel in relations[:10]:
                context.append(f"{rel.subject} {rel.predicate} {rel.object}")
        except Exception as e:
            logger.warning("entity_query: get_related failed [session=%s]: %s", session_id, e)

        return {"context": context}

    return entity_query


def _make_think(memory: Any, registry: Any = None):
    async def think(state: NeurOSState) -> dict:
        session_id = state.get("session_id", "")
        input_text = state.get("input", "")
        context = state.get("context") or []

        model_config = select_model(TaskType.REASONING)

        messages: list[dict] = [
            {
                "role": "system",
                "content": (
                    "You are NeurOS, a personal AI assistant. "
                    "You have access to the user's context and memory. "
                    "Be direct, concise, and action-oriented."
                ),
            }
        ]

        if context:
            messages.append(
                {
                    "role": "system",
                    "content": "Relevant context:\n" + "\n".join(context),
                }
            )

        messages.append({"role": "user", "content": input_text})

        start = time.monotonic()
        tool_schemas = None
        if registry is not None:
            tool_schemas = registry.to_tool_schemas()

        try:
            response = await chat(
                model=model_config.name,
                messages=messages,
                base_url=model_config.base_url,
                tools=tool_schemas if tool_schemas else None,
            )
        except Exception as e:
            logger.error("think: LLM call failed [session=%s]: %s", session_id, e)
            response = "I encountered an error generating a response."

        latency_ms = int((time.monotonic() - start) * 1000)

        tool_calls = []
        if isinstance(response, dict):
            tool_calls = response.get("tool_calls", []) or []
        elif hasattr(response, "tool_calls"):
            tool_calls = list(response.tool_calls) if response.tool_calls else []

        return {
            "response": response,
            "model_used": model_config.name,
            "latency_ms": latency_ms,
            "tool_calls": tool_calls,
        }

    return think


def _make_act(registry: Any, memory: Any):
    async def act(state: NeurOSState) -> dict:
        tool_calls = state.get("tool_calls") or []
        if not tool_calls:
            return {"skill_results": [], "skill_used": None}

        skill_results: list[Any] = []
        skill_names: list[str] = []
        session_id = state.get("session_id", "")

        for tc in tool_calls:
            if isinstance(tc, dict):
                skill_name = tc.get("name", "") or tc.get("function", {}).get("name", "")
                args_str = tc.get("args", "") or tc.get("function", {}).get("arguments", "{}")
            else:
                fn = getattr(tc, "function", None)
                skill_name = getattr(tc, "name", None) or (fn and getattr(fn, "name", ""))
                args_str = getattr(tc, "args", None) or (fn and getattr(fn, "arguments", "{}"))

            try:
                kwargs = json.loads(args_str) if isinstance(args_str, str) else args_str
            except (json.JSONDecodeError, TypeError):
                kwargs = {}

            skill_names.append(skill_name)
            logger.info("act: executing skill=%s args=%s", skill_name, kwargs)

            result = await registry.execute(skill_name, **kwargs)

            if result.success:
                skill_results.append(result.output)
                try:
                    out_str = json.dumps(result.output) if hasattr(result, "output") else ""
                    store_msg = f"Executed {skill_name}: {out_str}"
                    await memory.store(
                        store_msg,
                        {"source": "skill", "skill": skill_name, "session_id": session_id},
                    )
                except Exception as e:
                    logger.warning("act: store failed after skill %s: %s", skill_name, e)
            else:
                error_msg = getattr(result, "error", str(result)) if result else "unknown error"
                skill_results.append({"error": error_msg})
                logger.warning("act: skill %s failed: %s", skill_name, error_msg)

        return {
            "skill_results": skill_results,
            "skill_used": ",".join(skill_names),
        }

    return act


def _make_store(memory: Any):
    async def store(state: NeurOSState) -> dict:
        session_id = state.get("session_id", "")
        input_text = state.get("input", "")
        response = state.get("response", "")
        model_used = state.get("model_used")
        latency_ms = state.get("latency_ms")
        skill_used = state.get("skill_used")

        try:
            await memory.push_recent(input_text, session_id)
        except Exception as e:
            logger.warning("store: push_recent(input) failed [session=%s]: %s", session_id, e)

        try:
            await memory.push_recent(response, session_id)
        except Exception as e:
            logger.warning("store: push_recent(response) failed [session=%s]: %s", session_id, e)

        try:
            await memory.store(
                input_text,
                {
                    "source": "user",
                    "session_id": session_id,
                    "type": "interaction",
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )
        except Exception as e:
            logger.warning("store: memory.store failed [session=%s]: %s", session_id, e)

        if skill_used:
            try:
                await memory.store(
                    f"Used skill {skill_used} in response to: {input_text}",
                    {
                        "source": "skill",
                        "skill": skill_used,
                        "session_id": session_id,
                        "type": "skill_execution",
                    },
                )
            except Exception as e:
                logger.warning("store: skill episode store failed [session=%s]: %s", session_id, e)

        try:
            await memory.log_interaction(
                session_id=session_id,
                input=input_text,
                output=response,
                skill_used=skill_used,
                model_used=model_used,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.warning("store: log_interaction failed [session=%s]: %s", session_id, e)

        return {}

    return store


def _make_respond(memory: Any):
    async def respond(state: NeurOSState) -> dict:
        text = state.get("response") or "I'm not sure how to help with that."
        skill_results = state.get("skill_results") or []

        if skill_results:
            logger.info("respond: %d skill result(s) present", len(skill_results))

        return {"response": text}

    return respond


# ── Stateless nodes ──────────────────────────────────────────────────


async def intake(state: NeurOSState) -> dict:
    logger.info("intake: %s", state.get("input", "")[:80])
    return {}


# ── Routing ──────────────────────────────────────────────────────────


def _route_after_recall(state: NeurOSState) -> str:
    return "entity_query" if state.get("intent") == "entity_query" else "think"


# ── Graph construction ───────────────────────────────────────────────


def build_graph(memory: Any, registry: Any = None) -> Any:
    """Build and compile the agent pipeline with memory and registry injected."""
    graph = StateGraph(NeurOSState)

    graph.add_node("intake", intake)
    graph.add_node("recall", _make_recall(memory))
    graph.add_node("entity_query", _make_entity_query(memory))
    graph.add_node("think", _make_think(memory, registry))
    graph.add_node("act", _make_act(registry, memory))
    graph.add_node("store", _make_store(memory))
    graph.add_node("respond", _make_respond(memory))

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "recall")
    graph.add_conditional_edges(
        "recall", _route_after_recall, {"entity_query": "entity_query", "think": "think"}
    )
    graph.add_edge("entity_query", "think")
    graph.add_edge("think", "act")
    graph.add_edge("act", "store")
    graph.add_edge("store", "respond")
    graph.add_edge("respond", END)

    return graph.compile()
