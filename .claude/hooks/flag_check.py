from __future__ import annotations

from pathlib import Path

from tools.flag_utils import artifact_contains_flag, extract_flags


def validate_candidate(workspace: Path, flag: str, artifact: str, command: str | None = None) -> dict:
    if not flag:
        return {"ok": False, "reason": "missing flag"}
    if not artifact:
        return {"ok": False, "reason": "missing source artifact"}
    if not artifact_contains_flag(workspace, artifact, flag):
        return {"ok": False, "reason": "artifact does not contain exact flag"}
    if command is not None and not command.strip():
        return {"ok": False, "reason": "missing command or script provenance"}
    return {"ok": True, "reason": "candidate flag has source artifact evidence"}


def extract_from_artifact(path: Path) -> list[str]:
    if not path.exists():
        return []
    return extract_flags(path.read_text(encoding="utf-8", errors="replace"))
