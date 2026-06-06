"""Read-only code skills: read_file, list_files, search_code, understand_file."""

from __future__ import annotations

import asyncio
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

from neuros.config import settings
from neuros.llm.client import chat
from neuros.llm.selector import select_model
from neuros.models import TaskType
from neuros.skills.base import BaseSkill, SkillResult, skill
from neuros.skills.code import _safety
from neuros.skills.code._safety import check_extension, resolve_safe

logger = logging.getLogger("neuros.skills.code.reader")


@skill("read_file", "Read a file from the NeurOS codebase")
class ReadFileSkill(BaseSkill):
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Project-relative file path"},
            "start_line": {"type": "integer", "description": "First line to read"},
            "end_line": {"type": "integer", "description": "Last line to read"},
        },
        "required": ["path"],
    }

    async def run(self, **params) -> SkillResult:
        path = params.get("path")
        start_line = params.get("start_line")
        end_line = params.get("end_line")

        if not path:
            return SkillResult.fail("path is required")

        try:
            target = resolve_safe(path)
            check_extension(target)
        except ValueError as e:
            return SkillResult.fail(str(e))

        if not target.is_file():
            return SkillResult.fail(f"Not a file: {path}")

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return SkillResult.fail(f"Read failed: {e}")

        lines = content.splitlines()
        line_count = len(lines)

        s = max(1, int(start_line)) if start_line else 1
        e = min(line_count, int(end_line)) if end_line else line_count
        slice_content = "\n".join(lines[s - 1 : e])

        return SkillResult.ok(
            {
                "path": path,
                "content": slice_content,
                "line_count": line_count,
                "start_line": s,
                "end_line": e,
            },
            skill_name=self.name,
        )


@skill("list_files", "List files in a NeurOS project directory")
class ListFilesSkill(BaseSkill):
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Project-relative directory"},
            "pattern": {"type": "string", "description": "Glob pattern"},
            "recursive": {"type": "boolean", "description": "Whether to recurse"},
        },
    }

    async def run(self, **params) -> SkillResult:
        path = params.get("path", ".")
        pattern = params.get("pattern", "*")
        recursive = bool(params.get("recursive", False))

        try:
            target = resolve_safe(path)
        except ValueError as e:
            return SkillResult.fail(str(e))

        if not target.is_dir():
            return SkillResult.fail(f"Not a directory: {path}")

        glob = target.rglob(pattern) if recursive else target.glob(pattern)
        root = _safety.project_root()
        files: list[dict] = []
        for p in glob:
            if not p.is_file():
                continue
            if any(part.startswith(".") for part in p.relative_to(root).parts):
                continue
            if "__pycache__" in p.parts or "node_modules" in p.parts:
                continue
            try:
                stat = p.stat()
                files.append(
                    {
                        "path": str(p.relative_to(root)),
                        "size_bytes": stat.st_size,
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    }
                )
            except OSError:
                continue

        files.sort(key=lambda f: f["path"])
        return SkillResult.ok(
            {"path": path, "files": files, "count": len(files)}, skill_name=self.name
        )


@skill("search_code", "Search NeurOS codebase for a pattern or keyword")
class SearchCodeSkill(BaseSkill):
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Text or regex to search for"},
            "file_pattern": {"type": "string", "description": "File glob to search"},
            "case_sensitive": {"type": "boolean", "description": "Use case-sensitive search"},
        },
        "required": ["query"],
    }

    async def run(self, **params) -> SkillResult:
        query = params.get("query")
        file_pattern = params.get("file_pattern", "*.py")
        case_sensitive = bool(params.get("case_sensitive", False))

        if not query:
            return SkillResult.fail("query is required")

        root = _safety.project_root()
        rg = shutil.which("rg")

        if rg:
            cmd = [rg, "--line-number", "--no-heading", "--color", "never"]
            if not case_sensitive:
                cmd.append("-i")
            cmd += ["--glob", file_pattern, str(query), str(root)]
        else:
            cmd = ["grep", "-r", "-n"]
            if not case_sensitive:
                cmd.append("-i")
            cmd += ["--include", file_pattern, str(query), str(root)]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        except TimeoutError:
            return SkillResult.fail("search timed out")
        except FileNotFoundError as e:
            return SkillResult.fail(f"search tool missing: {e}")

        matches: list[dict] = []
        for raw in stdout.decode("utf-8", errors="replace").splitlines():
            parts = raw.split(":", 2)
            if len(parts) < 3:
                continue
            file_path, lineno, line = parts
            try:
                rel = str(Path(file_path).resolve().relative_to(root))
            except ValueError:
                rel = file_path
            try:
                line_number = int(lineno)
            except ValueError:
                continue
            matches.append({"file": rel, "line_number": line_number, "line": line, "context": line})

        return SkillResult.ok(
            {"query": query, "matches": matches[:200], "total": len(matches)},
            skill_name=self.name,
        )


@skill("understand_file", "Analyze a NeurOS source file and explain what it does")
class UnderstandFileSkill(BaseSkill):
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Project-relative file path"},
            "focus": {"type": "string", "description": "Optional function or topic to focus on"},
        },
        "required": ["path"],
    }

    async def run(self, **params) -> SkillResult:
        path = params.get("path")
        focus = params.get("focus")

        if not path:
            return SkillResult.fail("path is required")

        reader = ReadFileSkill()
        read_result = await reader.run(path=path)
        if not read_result.success:
            return read_result

        content = read_result.data["content"]
        focus_line = f"Focus on: {focus}" if focus else "Cover the whole file."

        prompt = (
            "You are analyzing NeurOS source code.\n"
            "Explain what this file does, its key functions/classes,\n"
            "and how it fits into the NeurOS architecture.\n"
            f"Be concise. {focus_line}\n\n"
            f"File: {path}\nContent:\n{content[:12000]}"
        )

        model_config = select_model(TaskType.REASONING)
        try:
            summary = await chat(
                model=model_config.name,
                messages=[
                    {"role": "system", "content": "Concise senior engineer."},
                    {"role": "user", "content": prompt},
                ],
                base_url=model_config.base_url,
                temperature=0.2,
            )
        except Exception as e:
            logger.warning("understand_file: LLM failed: %s", e)
            summary = f"(LLM unavailable: {e})\n\nFirst 40 lines:\n" + "\n".join(
                content.splitlines()[:40]
            )

        if not isinstance(summary, str):
            summary = str(summary)

        key_components: list[str] = []
        for ln in content.splitlines():
            stripped = ln.strip()
            if stripped.startswith(("def ", "async def ", "class ")):
                key_components.append(stripped.split("(")[0].split(":")[0])

        try:
            import neuros.memory.manager as mm

            if mm.manager is not None:
                await mm.manager.store(
                    f"File {path}: {summary[:500]}",
                    {"source": "code_analysis", "file": path},
                )
        except Exception as e:
            logger.debug("understand_file: memory store skipped: %s", e)

        return SkillResult.ok(
            {
                "path": path,
                "summary": summary,
                "key_components": key_components[:50],
                "stored": True,
            },
            skill_name=self.name,
        )


_ = settings  # silence linter
