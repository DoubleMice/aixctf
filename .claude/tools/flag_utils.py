from __future__ import annotations

import os
import re
from pathlib import Path


DEFAULT_FLAG_REGEX = r"(?:flag|ctf|aixctf)\{[^}\s]{1,200}\}"


def flag_regex() -> re.Pattern[str]:
    return re.compile(os.environ.get("FLAG_REGEX", DEFAULT_FLAG_REGEX), re.IGNORECASE)


def extract_flags(text: str) -> list[str]:
    seen = []
    for match in flag_regex().finditer(text or ""):
        value = match.group(0)
        if value not in seen:
            seen.append(value)
    return seen


def redact_flags(text: str) -> str:
    return flag_regex().sub("[REDACTED_FLAG]", text or "")


def artifact_contains_flag(workspace: Path, relative_path: str, flag: str) -> bool:
    path = safe_workspace_path(workspace, relative_path)
    if path is None:
        return False
    if not path.exists() or not path.is_file():
        return False
    try:
        return flag in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def safe_workspace_path(workspace: Path, relative_path: str) -> Path | None:
    path = Path(str(relative_path))
    if path.is_absolute() or ".." in path.parts:
        return None
    try:
        resolved = (workspace / path).resolve()
        resolved.relative_to(workspace.resolve())
    except ValueError:
        return None
    return resolved
