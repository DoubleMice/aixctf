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
    from runner.paths import workspace_root
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

    sys.stderr.write("usage: hook_entrypoint.py pre_tool|post_tool|stop\n")
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
    elif mode == "stop":
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
