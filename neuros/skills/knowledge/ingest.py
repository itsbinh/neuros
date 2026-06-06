"""Ingest URLs — fetch, extract, summarize, store to memory."""

from __future__ import annotations

import logging
import re

from neuros.memory.manager import manager as memory_manager
from neuros.skills.base import BaseSkill, SkillResult, skill

logger = logging.getLogger("neuros.skills.knowledge.ingest")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _detect_source_type(url: str, content_type: str = "") -> str:
    url_lower = url.lower()
    if "youtu.be" in url_lower or "youtube.com" in url_lower:
        return "youtube"
    if url_lower.endswith(".pdf") or "application/pdf" in content_type:
        return "pdf"
    return "html"


def _strip_html(html: str) -> str:
    text = _TAG_RE.sub(" ", html)
    return _WS_RE.sub(" ", text).strip()


@skill("ingest", "Fetch a URL and store its content to memory")
class IngestSkill(BaseSkill):
    async def run(self, **params) -> SkillResult:
        url = params.get("url", "")
        tags = params.get("tags", [])

        if not url.strip():
            return SkillResult.fail("'url' param required")

        source_type = _detect_source_type(url)

        try:
            text = await self._extract(url, source_type)
        except Exception as exc:
            return SkillResult.fail(str(exc))

        if source_type == "pdf" and text is None:
            return SkillResult.fail("PDF ingestion requires pdfplumber")

        text = (text or "")[:4000]
        if not text.strip():
            return SkillResult.fail("No content extracted from URL")

        try:
            await memory_manager.store(
                text,
                {
                    "source": url,
                    "tags": tags,
                    "category": "ingest",
                    "para_path": "03-Resources",
                },
            )
        except Exception as exc:
            return SkillResult.fail(str(exc))

        return SkillResult.ok({"url": url, "chars_stored": len(text), "source_type": source_type})

    async def _extract(self, url: str, source_type: str) -> str | None:
        if source_type == "youtube":
            return await self._extract_youtube(url)
        if source_type == "pdf":
            return None  # pdfplumber not required; signal failure
        return await self._extract_html(url)

    async def _extract_youtube(self, url: str) -> str:
        video_id = self._parse_youtube_id(url)
        if video_id:
            try:
                from youtube_transcript_api import YouTubeTranscriptApi

                transcript = YouTubeTranscriptApi.get_transcript(video_id)
                return " ".join(t["text"] for t in transcript)
            except ImportError:
                pass
            except Exception as exc:
                logger.warning("youtube transcript failed for %s: %s", video_id, exc)

        # Fallback: fetch page and strip HTML
        return await self._extract_html(url)

    async def _extract_html(self, url: str) -> str:
        import httpx

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "NeurOS/1.0"})
            resp.raise_for_status()
            return _strip_html(resp.text)

    @staticmethod
    def _parse_youtube_id(url: str) -> str | None:
        m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
        return m.group(1) if m else None
