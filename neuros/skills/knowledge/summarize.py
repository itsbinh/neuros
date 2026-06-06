"""Knowledge summarize skill — map-reduce summarization via LLM."""

from __future__ import annotations

import logging

from neuros.llm.client import chat
from neuros.llm.selector import select_model
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.knowledge.summarize")


@skill("summarize", "Map-reduce summarize text via LLM")
class SummarizeSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        texts = params.get("texts", [])
        if not texts:
            return SkillResult.fail("No texts provided to summarize")

        try:
            model = select_model()
            # Map phase: summarize each chunk independently
            chunks = []
            for text in texts:
                summary = await chat(
                    model=model.name,
                    messages=[
                        {
                            "role": "user",
                            "content": f"Summarize this in 2-3 sentences:\n\n{text}",
                        }
                    ],
                    base_url=model.base_url,
                )
                chunks.append(summary)

            # Reduce phase: combine summaries
            combined = "\n\n".join(chunks)
            if len(combined) < 500:
                final = combined
            else:
                final = await chat(
                    model=model.name,
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                f"Combine these summaries into one cohesive summary:\n\n{combined}"
                            ),
                        }
                    ],
                    base_url=model.base_url,
                )

            return SkillResult.ok({"summary": final, "sources": len(texts)})
        except Exception as exc:
            return SkillResult.fail(str(exc))
