#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def bootstrap() -> Path:
    root = Path(os.environ.get("AIXCTF_AGENT_ROOT", Path(__file__).resolve().parents[1])).resolve()
    sys.path.insert(0, str(root))
    os.environ.setdefault("AIXCTF_AGENT_ROOT", str(root))
    return root


def main(argv: list[str]) -> int:
    bootstrap()
    from hooks.evidence_guard import validate_final_state
    from hooks.hook_io import posttool_context, pretool_allow, pretool_deny, read_hook_input, stop_allow, stop_block, write_json
    from hooks.post_tool_check import check as post_check
    from hooks.pre_tool_check import check as pre_check
    from runner.execution_lifecycle import handoff_updated_since
    from runner.paths import workspace_root
    from runner.progress_exporter import ProgressExporter
    from runner.state_store import StateStore
    from sync.sync_queue import SyncQueue

    mode = argv[1] if len(argv) > 1 else ""
    payload = read_hook_input()

    if mode == "pre_tool":
        result = pre_check(payload)
        write_json(pretool_allow(result["reason"]) if result["allowed"] else pretool_deny(result["reason"]))
        return 0

    if mode == "post_tool":
        result = post_check(payload)
        context = f"Tool output recorded at {result['log_path']}."
        if result["flags"]:
            context += f" Candidate flag(s): {', '.join(result['flags'])}."
        if result["signals"]:
            context += f" Signals: {', '.join(result['signals'])}."
        write_json(posttool_context(context))
        return 0

    if mode == "stop":
        workspace = workspace_root()
        state = StateStore(workspace).load_or_create()
        execution_id = os.environ.get("AIXCTF_EXECUTION_ID") or str(payload.get("session_id") or "unknown")
        started_at_ns = safe_int(os.environ.get("AIXCTF_EXECUTION_STARTED_AT_NS"), 0)
        checkpoint_ready = handoff_updated_since(workspace, started_at_ns)
        stop_hook_active = bool(payload.get("stop_hook_active"))
        if not checkpoint_ready:
            progress = ProgressExporter(workspace)
            progress.emit(
                level="warning",
                event="checkpoint_incomplete" if stop_hook_active else "checkpoint_requested",
                message="handoff.md was not updated during the current Execution.",
                round_id=safe_int(state.get("round", 0), 0) + 1,
                phase=state.get("phase", "unknown"),
                category=state.get("category", "unknown"),
                extra={"execution_id": execution_id, "started_at_ns": started_at_ns},
                console=False,
            )
            if not stop_hook_active:
                write_json(
                    stop_block(
                        "Before stopping, update handoff.md with the current research state, evidence references, "
                        "failed paths, and next execution intent, then return the required state JSON."
                    )
                )
                return 0
        guard = validate_final_state(workspace, state, final=False)
        SyncQueue(workspace).emit_simple(
            source="hook",
            event_type="round_checkpoint" if guard["ok"] else "evidence_guard_failed",
            level="info" if guard["ok"] else "warning",
            round_id=safe_int(state.get("round", 0), 0) + 1,
            phase=state.get("phase"),
            category=state.get("category"),
            message=guard["reason"],
            summary={"guard": guard},
            hook="Stop",
        )
        if not guard["ok"]:
            write_json(stop_block(guard["reason"]))
        else:
            write_json(stop_allow(guard["reason"]))
        return 0

    if mode == "pre_compact":
        workspace = workspace_root()
        state = StateStore(workspace).load_or_create()
        execution_id = os.environ.get("AIXCTF_EXECUTION_ID") or str(payload.get("session_id") or "unknown")
        ProgressExporter(workspace).emit(
            level="warning",
            event="precompact_checkpoint_requested",
            message="Automatic context compaction was blocked so the model can externalize state first.",
            round_id=safe_int(state.get("round", 0), 0) + 1,
            phase=state.get("phase", "unknown"),
            category=state.get("category", "unknown"),
            extra={"execution_id": execution_id, "trigger": payload.get("trigger")},
            console=False,
        )
        write_json(
            stop_block(
                "Do not compact this strongly related task. Update handoff.md, return the required state JSON, "
                "and end this Execution so the runtime can start a fresh one from durable state."
            )
        )
        return 0

    sys.stderr.write("usage: hook_entrypoint.py pre_tool|post_tool|stop|pre_compact\n")
    return 2


def fail_open(argv: list[str], exc: Exception) -> int:
    mode = argv[1] if len(argv) > 1 else ""
    reason = f"hook error fail-open: {type(exc).__name__}: {exc}"
    sys.stderr.write(f"[AIXCTF][WARN] {reason}\n")
    if mode == "pre_tool":
        payload = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": reason,
            }
        }
    elif mode == "post_tool":
        payload = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": reason}}
    elif mode in {"stop", "pre_compact"}:
        payload = {}
    else:
        payload = {"error": reason}
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


def safe_int(value: object, default: int) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as exc:
        raise SystemExit(fail_open(sys.argv, exc))
