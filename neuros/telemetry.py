"""Lightweight skill telemetry — records success/failure/duration.

Falls back to a JSON file when Postgres is unavailable.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

_log_path = Path(__file__).parent.parent / "skill_telemetry.json"
logger = logging.getLogger("neuros.telemetry")


def _load() -> dict:
    if not _log_path.exists():
        return {"tool_stats": {}}
    try:
        return json.loads(_log_path.read_text())
    except Exception:
        return {"tool_stats": {}}


def _save(data: dict) -> None:
    _log_path.write_text(json.dumps(data, indent=2))


def record(skill_name: str, success: bool, duration_ms: int, error: str | None = None) -> None:
    """Fire-and-forget skill event recording. Never raises."""
    try:
        data = _load()
        stats = data["tool_stats"].setdefault(
            skill_name,
            {
                "success": 0,
                "failure": 0,
                "total": 0,
                "consecutive_failures": 0,
                "avg_duration_ms": 0.0,
                "last_success_at": None,
                "last_failure_at": None,
                "last_error": None,
            },
        )
        stats["total"] += 1
        key = "success" if success else "failure"
        stats[key] += 1
        if success:
            stats["consecutive_failures"] = 0
            stats["last_success_at"] = datetime.now(UTC).isoformat()
        else:
            stats["consecutive_failures"] += 1
            stats["last_failure_at"] = datetime.now(UTC).isoformat()
            stats["last_error"] = error
        # rolling average
        n = stats["total"]
        stats["avg_duration_ms"] = stats["avg_duration_ms"] * (n - 1) / n + duration_ms / n
        _save(data)
    except Exception as e:
        logger.debug("telemetry record failed: %s", e)
