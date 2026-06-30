from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


DEFAULT_POLICY: dict[str, Any] = {
    "enabled": True,
    "mode": "hook_enqueue_round_flush",
    "mntn_skill": {"enabled": True, "timeout_seconds": 5, "max_retries": 3, "fail_open": True},
    "frequency": {
        "sync_on_round_end": True,
        "sync_on_phase_change": True,
        "sync_on_candidate_flag": True,
        "sync_on_subtask_completed": True,
        "sync_on_blocked": True,
        "sync_on_solved": True,
        "sync_on_failed": True,
        "min_interval_seconds": 15,
        "max_messages_per_round": 3,
        "dedupe_same_message": True,
    },
    "content": {
        "include_artifact_paths": True,
        "include_log_preview": True,
        "max_log_preview_chars": 800,
        "include_candidate_flag": False,
        "include_verified_flag": False,
        "redact_secrets": True,
    },
    "spool": {"enabled": True, "path": "sync/spool.jsonl"},
    "local_log": {"enabled": True, "path": "sync/sync_log.jsonl"},
}


def load_policy(agent_root: Path) -> dict[str, Any]:
    path = agent_root / "sync" / "sync_policy.yaml"
    if not path.exists() or yaml is None:
        return DEFAULT_POLICY.copy()
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return DEFAULT_POLICY.copy()
    if not isinstance(data, dict):
        return DEFAULT_POLICY.copy()
    return deep_merge(DEFAULT_POLICY.copy(), data)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = deep_merge(base[key], value)
        else:
            base[key] = value
    return base
