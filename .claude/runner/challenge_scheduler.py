from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runner.paths import safe_path_segment


STRONG_MARKERS = {"metadata.json", "target.txt"}
WEAK_MARKERS = {"README.md", "readme.md", "DESCRIPTION.md", "description.md"}
IGNORED_DIRS = {
    ".git",
    ".claude",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "workspace",
    "local_output",
    "output",
}


@dataclass
class ChallengeSource:
    source: Path
    challenge_id: str
    order: int


@dataclass
class ChallengeRecord:
    source: Path
    challenge_id: str
    workspace: Path
    output_dir: Path
    order: int
    status: str = "pending"
    visits: int = 0
    last_round: int = 0
    last_phase: str = "init"
    failure_count: int = 0
    last_selected_seq: int = 0
    pause_reason: str | None = None
    last_result: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "status": self.status,
            "workspace": str(self.workspace),
            "output_dir": str(self.output_dir),
            "rounds": self.last_round,
            "phase": self.last_phase,
            "failures": self.failure_count,
            "visits": self.visits,
            "pause_reason": self.pause_reason,
            "result": self.last_result,
        }


class ChallengeScheduler:
    def __init__(self, max_rounds_per_visit: int):
        self.max_rounds_per_visit = max(1, int(max_rounds_per_visit))
        self.selection_seq = 0

    def all_solved(self, records: list[ChallengeRecord]) -> bool:
        return bool(records) and all(record.status == "solved" for record in records)

    def next_challenge(self, records: list[ChallengeRecord]) -> ChallengeRecord | None:
        candidates = [record for record in records if record.status not in {"active", "solved", "exhausted", "failed"}]
        if not candidates:
            return None
        selected = min(candidates, key=self.priority_key)
        self.selection_seq += 1
        selected.last_selected_seq = self.selection_seq
        selected.status = "active"
        return selected

    def priority_key(self, record: ChallengeRecord) -> tuple[int, int, int, int, int]:
        status_rank = {"pending": 0, "active": 1, "paused": 2, "failed": 4}
        return (
            status_rank.get(record.status, 3),
            record.failure_count,
            record.visits,
            record.last_round,
            record.last_selected_seq or record.order,
        )

    def update(
        self,
        record: ChallengeRecord,
        state: dict[str, Any],
        result: dict[str, Any],
        pause_reason: str | None,
    ) -> None:
        record.visits += 1
        record.last_round = safe_int(state.get("round", 0), 0, minimum=0)
        record.last_phase = str(state.get("phase", "init"))
        record.failure_count = len(state.get("failures", []))
        record.last_result = result
        record.pause_reason = pause_reason
        max_rounds = safe_int(state.get("runtime_limits", {}).get("max_rounds", 12), 12, minimum=1)

        if result.get("status") == "solved":
            record.status = "solved"
            record.pause_reason = None
        elif result.get("runtime_error") or pause_reason == "runtime_exception":
            record.status = "failed"
            record.pause_reason = pause_reason or "runtime_exception"
        elif record.last_round >= max_rounds:
            record.status = "exhausted"
            record.pause_reason = "max_rounds_reached"
        else:
            record.status = "paused"
            record.pause_reason = pause_reason or "waiting_for_next_visit"


def discover_challenge_sources(root: Path) -> list[ChallengeSource]:
    mode = os.environ.get("AIXCTF_CHALLENGE_MODE", "auto").strip().lower()
    if mode not in {"auto", "single", "multi"}:
        mode = "auto"

    if mode == "single" or root.is_file() or not root.exists():
        return [ChallengeSource(root, safe_path_segment(root.stem if root.is_file() else root.name), 0)]

    max_depth = safe_int(os.environ.get("AIXCTF_DISCOVERY_DEPTH"), 3, minimum=1)
    candidates = find_challenge_dirs(root, max_depth=max_depth)

    root_strength = challenge_strength(root)
    if mode == "multi":
        selected = candidates or [root]
    elif root_strength >= 2:
        selected = [root]
    elif len(candidates) > 1:
        selected = candidates
    elif len(candidates) == 1 and root_strength < 2:
        selected = candidates
    else:
        selected = [root]

    sources: list[ChallengeSource] = []
    for index, source in enumerate(sorted(dict.fromkeys(selected), key=lambda path: str(path))):
        sources.append(ChallengeSource(source, safe_path_segment(source.stem if source.is_file() else source.name), index))
    return sources


def find_challenge_dirs(root: Path, max_depth: int) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.is_dir():
        return []
    return _find_challenge_dirs(root, current_depth=0, max_depth=max_depth, is_root=True)


def _find_challenge_dirs(root: Path, current_depth: int, max_depth: int, is_root: bool) -> list[Path]:
    strength = challenge_strength(root)
    if strength >= 2 and not is_root:
        return [root]
    if current_depth >= max_depth:
        return [root] if strength > 0 else []

    child_candidates: list[Path] = []
    for child in sorted(safe_iterdir(root)):
        if not safe_is_dir(child) or child.name in IGNORED_DIRS or child.name.startswith("."):
            continue
        child_candidates.extend(_find_challenge_dirs(child, current_depth + 1, max_depth, is_root=False))

    if child_candidates:
        return child_candidates
    if strength > 0:
        return [root]
    return []


def challenge_strength(path: Path) -> int:
    if safe_is_file(path):
        return 3
    if not safe_is_dir(path):
        return 0
    if any((path / marker).is_file() for marker in STRONG_MARKERS):
        return 3
    for child in safe_iterdir(path):
        if safe_is_file(child) and not child.name.startswith(".") and child.name not in WEAK_MARKERS:
            return 2
    if any((path / marker).is_file() for marker in WEAK_MARKERS):
        return 1
    return 0


def safe_iterdir(path: Path) -> list[Path]:
    try:
        return list(path.iterdir())
    except OSError:
        return []


def safe_is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def safe_int(value: object, default: int, minimum: int | None = None) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        return max(minimum, parsed)
    return parsed
