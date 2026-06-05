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

_IMPROVE_PATTERNS = (
    "improve ",
    "make ",  # "make X better"
    "fix ",
    "refactor ",
    "add error handling",
    "why is ",
    "what's wrong with",
    "update ",  # "update X to do Y"
)

_UUID_RE = __import__("re").compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", __import__("re").I
)


def _is_entity_query(text: str) -> bool:
    lower = text.lower().strip()
    return any(lower.startswith(p) or p in lower for p in _ENTITY_QUERY_PATTERNS)


def _classify_dogfood(text: str) -> str | None:
    """Return 'read' | 'understand' | 'improve' | 'apply' | 'commit' | 'reject' | None."""
    lower = text.lower().strip()

    if lower.startswith("read ") or lower.startswith("read the file "):
        return "read"
    if lower.startswith("what does ") and _extract_path(text):
        return "understand"
    if lower.startswith("explain ") and _extract_path(text):
        return "understand"
    if lower.startswith("understand ") and _extract_path(text):
        return "understand"

    if lower.startswith("apply ") or lower in {"yes apply it", "go ahead", "yes", "apply"}:
        return "apply"
    if lower in {"commit", "yes commit", "commit it", "yes, commit"}:
        return "commit"
    if lower.startswith("reject ") or lower in {"no", "discard it", "don't apply", "reject"}:
        return "reject"

    if any(lower.startswith(p) or (" " + p) in lower for p in _IMPROVE_PATTERNS):
        if "better" in lower or any(lower.startswith(p) for p in _IMPROVE_PATTERNS if p != "make "):
            return "improve"
        if lower.startswith("make ") and "better" in lower:
            return "improve"
    return None


def _extract_path(text: str) -> str | None:
    """Pull an obvious file path out of the user's text."""
    import re

    m = re.search(r"([a-zA-Z0-9_./-]+\.(?:py|lua|md|toml|yaml|yml|sh|txt))", text)
    return m.group(1) if m else None


def _resolve_obvious_path(path: str) -> str:
    """Resolve bare filenames that clearly refer to files under neuros/."""
    from pathlib import Path

    root = Path.cwd()
    candidate = root / path
    if candidate.exists():
        return path

    neuros_candidate = root / "neuros" / path
    if "/" not in path and neuros_candidate.exists():
        return str(Path("neuros") / path)

    return path


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

        dog = _classify_dogfood(input_text)
        if dog:
            intent = f"dogfood_{dog}"
        elif _is_entity_query(input_text):
            intent = "entity_query"
        else:
            intent = "query"
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
            response_text = response.get("content", "")
        elif hasattr(response, "tool_calls"):
            tool_calls = list(response.tool_calls) if response.tool_calls else []
            response_text = getattr(response, "content", "") or ""
        else:
            response_text = response

        return {
            "response": response_text,
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
                skill_results.append(result.data)
                try:
                    out_str = json.dumps(result.data)
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


# ── Dogfood node ─────────────────────────────────────────────────────


def _make_dogfood(memory: Any):
    async def dogfood(state: NeurOSState) -> dict:
        from neuros.skills.code.applier import ApplyChangeSkill
        from neuros.skills.code.git_ops import GitCommitSkill, GitDiffSkill
        from neuros.skills.code.improver import ProposeImprovementSkill
        from neuros.skills.code.reader import SearchCodeSkill, UnderstandFileSkill

        input_text = state.get("input", "")
        intent = state.get("intent", "")
        postgres = memory._postgres

        try:
            if intent == "dogfood_improve":
                path = _extract_path(input_text)
                if not path:
                    # try to resolve a component name via search
                    name_match = input_text.lower()
                    for w in ("improve", "fix", "refactor", "update"):
                        name_match = name_match.replace(w, "", 1)
                    name_match = name_match.strip()
                    if name_match:
                        sr = await SearchCodeSkill().run(query=name_match.split()[0])
                        matches = (sr.data or {}).get("matches", []) if sr.success else []
                        if matches:
                            path = matches[0]["file"]
                if not path:
                    return {"response": "Could not identify a file to improve. Specify a path like neuros/memory/manager.py."}

                await UnderstandFileSkill().run(path=path)
                proposal_result = await ProposeImprovementSkill().run(
                    path=path, instruction=input_text
                )
                if not proposal_result.success:
                    return {"response": f"Proposal failed: {proposal_result.error}"}

                p = proposal_result.data
                text = (
                    f"📋 Proposed change to {p['path']}\n\n"
                    f"What: {p['summary']}\n"
                    f"Why: {p['reason']}\n"
                    f"Risk: {p['risk']}\n"
                    f"Tests: {', '.join(p['tests_affected']) or '(none specified)'}\n\n"
                    f"Original:\n{p['original'][:200]}{'...' if len(p['original']) > 200 else ''}\n\n"
                    f"Replacement:\n{p['replacement'][:200]}{'...' if len(p['replacement']) > 200 else ''}\n\n"
                    f"Reply 'apply {p['id']}' to apply, or 'reject {p['id']}' to discard."
                )
                return {"response": text}

            if intent == "dogfood_read":
                from neuros.skills.code.reader import ReadFileSkill, UnderstandFileSkill

                path = _extract_path(input_text)
                if not path:
                    return {"response": "Could not identify a file to read."}
                path = _resolve_obvious_path(path)

                read_result = await ReadFileSkill().run(path=path)
                if not read_result.success:
                    return {"response": f"Read failed: {read_result.error}"}

                understand_result = await UnderstandFileSkill().run(path=path)
                summary = (
                    understand_result.data.get("summary", "")
                    if understand_result.success and understand_result.data
                    else f"Summary unavailable: {understand_result.error}"
                )
                data = read_result.data
                return {
                    "response": (
                        f"File: {data['path']} ({data['line_count']} lines)\n\n"
                        f"Summary:\n{summary}\n\n"
                        f"Content:\n{data['content']}"
                    )
                }

            if intent == "dogfood_understand":
                from neuros.skills.code.reader import UnderstandFileSkill

                path = _extract_path(input_text)
                if not path:
                    return {"response": "Could not identify a file to explain."}
                path = _resolve_obvious_path(path)

                focus = input_text
                result = await UnderstandFileSkill().run(path=path, focus=focus)
                if not result.success:
                    return {"response": f"Understand failed: {result.error}"}

                data = result.data
                components = ", ".join(data.get("key_components", [])[:12])
                return {
                    "response": (
                        f"File: {data['path']}\n\n"
                        f"{data['summary']}\n\n"
                        f"Key components: {components or '(none found)'}"
                    )
                }

            if intent == "dogfood_apply":
                m = _UUID_RE.search(input_text)
                if m:
                    proposal_id = m.group(0)
                else:
                    pending = await postgres.latest_proposal(status="pending")
                    if pending is None:
                        return {"response": "No pending proposals to apply."}
                    proposal_id = pending.id

                await postgres.update_proposal_status(proposal_id, "approved")
                ar = await ApplyChangeSkill().run(proposal_id=proposal_id, confirmed=True)
                if not ar.success:
                    return {"response": f"Apply failed: {ar.error}"}

                data = ar.data
                if not data["tests_passed"]:
                    return {
                        "response": (
                            f"❌ Tests failed; changes reverted.\n\n{data['test_output'][:1500]}"
                        )
                    }

                diff = await GitDiffSkill().run(path=None)
                diff_text = (diff.data or {}).get("diff", "")[:1500] if diff.success else ""
                return {
                    "response": (
                        f"✅ Tests passed. Diff:\n{diff_text}\n\n"
                        "Commit this change? Reply 'commit' to confirm."
                    )
                }

            if intent == "dogfood_commit":
                applied = await postgres.latest_proposal(status="applied")
                if applied is None:
                    return {"response": "No applied proposals to commit."}

                msg = f"improve({applied.path}): {applied.summary}"
                cr = await GitCommitSkill().run(message=msg, confirmed=True)
                if not cr.success:
                    return {"response": f"Commit failed: {cr.error}"}
                d = cr.data
                return {"response": f"✅ Committed: {d['hash']}\n{d['message']}"}

            if intent == "dogfood_reject":
                m = _UUID_RE.search(input_text)
                if m:
                    proposal_id = m.group(0)
                else:
                    pending = await postgres.latest_proposal(status="pending")
                    if pending is None:
                        return {"response": "No pending proposals to reject."}
                    proposal_id = pending.id
                await postgres.update_proposal_status(proposal_id, "rejected")
                return {
                    "response": "Proposal discarded. Ask me to propose a different improvement."
                }
        except Exception as e:
            logger.exception("dogfood: error: %s", e)
            return {"response": f"Dogfood error: {e}"}

        return {"response": "Unknown dogfood intent."}

    return dogfood


# ── Stateless nodes ──────────────────────────────────────────────────


async def intake(state: NeurOSState) -> dict:
    logger.info("intake: %s", state.get("input", "")[:80])
    return {}


# ── Routing ──────────────────────────────────────────────────────────


def _route_after_recall(state: NeurOSState) -> str:
    intent = state.get("intent") or ""
    if intent.startswith("dogfood_"):
        return "dogfood"
    return "entity_query" if intent == "entity_query" else "think"


# ── Graph construction ───────────────────────────────────────────────


def build_graph(memory: Any, registry: Any = None) -> Any:
    """Build and compile the agent pipeline with memory and registry injected."""
    graph = StateGraph(NeurOSState)

    graph.add_node("intake", intake)
    graph.add_node("recall", _make_recall(memory))
    graph.add_node("entity_query", _make_entity_query(memory))
    graph.add_node("think", _make_think(memory, registry))
    graph.add_node("act", _make_act(registry, memory))
    graph.add_node("dogfood", _make_dogfood(memory))
    graph.add_node("store", _make_store(memory))
    graph.add_node("respond", _make_respond(memory))

    graph.add_edge(START, "intake")
    graph.add_edge("intake", "recall")
    graph.add_conditional_edges(
        "recall",
        _route_after_recall,
        {"entity_query": "entity_query", "think": "think", "dogfood": "dogfood"},
    )
    graph.add_edge("entity_query", "think")
    graph.add_edge("think", "act")
    graph.add_edge("act", "store")
    graph.add_edge("dogfood", "store")
    graph.add_edge("store", "respond")
    graph.add_edge("respond", END)

    return graph.compile()
