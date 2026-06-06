"""Path-safety helpers for code skills. ALL file I/O must go through resolve_safe()."""

from __future__ import annotations

from pathlib import Path

from neuros.config import settings

ALLOWED_EXTS = {".py", ".lua", ".md", ".toml", ".yaml", ".yml", ".sh", ".txt", ".example"}


def project_root() -> Path:
    return Path(settings.project_root).resolve()


def resolve_safe(path: str) -> Path:
    """Resolve `path` relative to project root, rejecting traversal/outside paths.

    Raises ValueError if the resolved path leaves the project root.
    """
    if ".." in Path(path).parts:
        raise ValueError(f"Path traversal rejected: {path}")

    root = project_root()
    candidate = (root / path).resolve() if not Path(path).is_absolute() else Path(path).resolve()

    try:
        candidate.relative_to(root)
    except ValueError:
        raise ValueError(f"Path outside project root: {path}") from None

    return candidate


def check_extension(path: Path) -> None:
    """Reject reads of disallowed file extensions."""
    name = path.name
    if name.endswith(".env.example"):
        return
    if path.suffix.lower() not in ALLOWED_EXTS:
        raise ValueError(f"Extension not allowed: {path.suffix}")
