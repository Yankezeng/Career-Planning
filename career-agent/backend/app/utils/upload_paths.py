from __future__ import annotations

from pathlib import Path
from typing import Any


def _is_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_upload_reference(
    *,
    upload_root: Path,
    reference: Any,
    must_exist: bool = True,
) -> Path | None:
    text = str(reference or "").strip()
    if not text:
        return None

    normalized = text.replace("\\", "/")
    root = upload_root.resolve()

    if normalized.startswith("/uploads/"):
        relative = normalized.replace("/uploads/", "", 1).lstrip("/")
        candidate = (root / relative).resolve()
        if not _is_within_root(candidate, root):
            return None
        if must_exist and not candidate.exists():
            return None
        return candidate

    direct_path = Path(text)
    if direct_path.is_absolute():
        resolved = direct_path.resolve()
        if not _is_within_root(resolved, root):
            return None
        if must_exist and not resolved.exists():
            return None
        return resolved

    relative_candidate = (root / normalized.lstrip("/")).resolve()
    if _is_within_root(relative_candidate, root):
        if not must_exist or relative_candidate.exists():
            return relative_candidate

    legacy_name = Path(normalized).name
    legacy_candidate = (root / legacy_name).resolve()
    if not _is_within_root(legacy_candidate, root):
        return None
    if must_exist and not legacy_candidate.exists():
        return None
    return legacy_candidate


def upload_path_to_url(*, upload_root: Path, absolute_path: Path) -> str:
    root = upload_root.resolve()
    path = Path(absolute_path).resolve()
    try:
        relative = path.relative_to(root).as_posix()
        return f"/uploads/{relative}"
    except ValueError:
        return str(absolute_path)
