from __future__ import annotations

import os
import re
from pathlib import Path


def agent_root() -> Path:
    return Path(os.environ.get("AIXCTF_AGENT_ROOT", Path(__file__).resolve().parents[1])).resolve()


def workspace_base_root() -> Path:
    return Path(os.environ.get("AIXCTF_WORKSPACE_BASE", agent_root() / "workspace")).resolve()


def workspace_root(challenge_id: str | None = None) -> Path:
    explicit = os.environ.get("WORKDIR")
    if explicit:
        return Path(explicit).resolve()
    return workspace_base_root() / safe_path_segment(challenge_id or os.environ.get("CHALLENGE_ID") or "unknown")


def challenge_root() -> Path:
    return Path(os.environ.get("CHALLENGE_DIR", "/challenge")).resolve()


def output_root() -> Path:
    return Path(os.environ.get("OUTPUT_DIR", "/output")).resolve()


def safe_path_segment(value: str | None, default: str = "unknown") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip()).strip("._-")
    return cleaned or default


def ensure_workspace_dirs(workspace: Path) -> None:
    for name in [
        "challenge",
        "rounds",
        "events",
        "subtasks",
        "scripts",
        "logs",
        "evidence",
        "sync",
        "prompts",
        "state_snapshots",
    ]:
        (workspace / name).mkdir(parents=True, exist_ok=True)
    for name in ["events.jsonl", "spool.jsonl", "sync_log.jsonl"]:
        path = workspace / "sync" / name
        path.touch(exist_ok=True)
