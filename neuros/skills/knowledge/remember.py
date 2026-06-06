"""Knowledge skills using Graphiti: remember, forget, entity_timeline, what_do_you_know."""

from __future__ import annotations

import logging

from neuros.skills.base import Skill, SkillResult, skill

logger = logging.getLogger("neuros.skills.knowledge.remember")


@skill(
    "remember",
    "Explicitly store a fact or piece of information into long-term memory",
)
class RememberSkill(Skill):
    parameters = {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "The fact to remember"},
            "entity": {"type": "string", "description": "Entity this fact is about (optional)"},
        },
        "required": ["content"],
    }

    async def execute(self, **kwargs) -> SkillResult:
        from neuros.memory.manager import manager

        content = kwargs.get("content", "").strip()
        entity = kwargs.get("entity", "")
        session_id = kwargs.get("session_id", "default")

        if not content:
            return SkillResult.fail("No content provided", skill_name="remember")

        if not manager:
            return SkillResult.fail("Memory manager not initialized", skill_name="remember")

        metadata: dict = {}
        if entity:
            metadata["entity"] = entity

        episode_id = await manager.remember_entity(content, session_id=session_id)
        return SkillResult.ok(
            {"stored": True, "content": content, "episode_id": episode_id},
            skill_name="remember",
        )


@skill(
    "forget",
    "Invalidate an outdated fact in the knowledge graph",
)
class ForgetSkill(Skill):
    parameters = {
        "type": "object",
        "properties": {
            "subject": {"type": "string", "description": "Entity the fact is about"},
            "fact": {"type": "string", "description": "Description of what to invalidate"},
        },
        "required": ["subject", "fact"],
    }

    async def execute(self, **kwargs) -> SkillResult:
        from neuros.memory.manager import manager

        subject = kwargs.get("subject", "").strip()
        fact = kwargs.get("fact", "").strip()

        if not subject or not fact:
            return SkillResult.fail("subject and fact are required", skill_name="forget")

        if not manager:
            return SkillResult.fail("Memory manager not initialized", skill_name="forget")

        graph_ok = await manager.invalidate_fact(subject, fact, reason=fact)
        qdrant_deleted = await manager.forget_by_query(f"{subject} {fact}")
        return SkillResult.ok(
            {
                "invalidated": 1 if graph_ok else 0,
                "qdrant_deleted": qdrant_deleted,
                "subject": subject,
            },
            skill_name="forget",
        )


@skill(
    "entity_timeline",
    "Show the history of facts about a person, server, or project",
)
class EntityTimelineSkill(Skill):
    parameters = {
        "type": "object",
        "properties": {
            "entity_name": {"type": "string", "description": "Name of the entity"},
            "limit": {"type": "integer", "description": "Max events to return", "default": 20},
        },
        "required": ["entity_name"],
    }

    async def execute(self, **kwargs) -> SkillResult:
        from neuros.memory.manager import manager

        entity_name = kwargs.get("entity_name", "").strip()
        limit = int(kwargs.get("limit", 20))

        if not entity_name:
            return SkillResult.fail("entity_name is required", skill_name="entity_timeline")

        if not manager:
            return SkillResult.fail("Memory manager not initialized", skill_name="entity_timeline")

        events = await manager.entity_timeline(entity_name, limit=limit)
        return SkillResult.ok(
            {
                "entity": entity_name,
                "events": [
                    {
                        "timestamp": e.timestamp.isoformat(),
                        "fact": e.fact,
                        "source": e.source,
                        "still_valid": e.still_valid,
                    }
                    for e in events
                ],
            },
            skill_name="entity_timeline",
        )


@skill(
    "what_do_you_know",
    "Retrieve everything NeurOS knows about a specific entity",
)
class WhatDoYouKnowSkill(Skill):
    parameters = {
        "type": "object",
        "properties": {
            "entity_name": {"type": "string", "description": "Name of the entity to look up"},
        },
        "required": ["entity_name"],
    }

    async def execute(self, **kwargs) -> SkillResult:
        from neuros.memory.manager import manager

        entity_name = kwargs.get("entity_name", "").strip()

        if not entity_name:
            return SkillResult.fail("entity_name is required", skill_name="what_do_you_know")

        if not manager:
            return SkillResult.fail("Memory manager not initialized", skill_name="what_do_you_know")

        entity = await manager.get_entity(entity_name)

        relations: list[dict] = []
        if manager._graphiti:
            raw_relations = await manager._graphiti.get_related(entity_name, max_hops=2)
            relations = [
                {
                    "subject": r.subject,
                    "predicate": r.predicate,
                    "object": r.object,
                    "valid_from": r.valid_from.isoformat() if r.valid_from else None,
                    "valid_until": r.valid_until.isoformat() if r.valid_until else None,
                }
                for r in raw_relations
            ]

        episodes = await manager._qdrant.search(entity_name, k=5)
        episode_dicts = [
            {"text": e.text, "score": e.score, "metadata": e.metadata} for e in episodes
        ]

        total_facts = len(relations) + len(episode_dicts)

        return SkillResult.ok(
            {
                "entity": {
                    "uuid": entity.uuid,
                    "name": entity.name,
                    "entity_type": entity.entity_type,
                    "summary": entity.summary,
                    "created_at": entity.created_at.isoformat(),
                }
                if entity
                else None,
                "relations": relations,
                "episodes": episode_dicts,
                "total_facts": total_facts,
            },
            skill_name="what_do_you_know",
        )
