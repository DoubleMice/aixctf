#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path


def main() -> int:
    agent_root = Path(__file__).resolve().parent
    os.environ.setdefault("AIXCTF_AGENT_ROOT", str(agent_root))
    sys.path.insert(0, str(agent_root))

    try:
        from runner.runtime_controller import RuntimeController

        result = RuntimeController().run()
    except Exception as exc:
        result = fallback_result(exc)
        write_fallback_result(agent_root, result)
        sys.stderr.write(f"[AIXCTF][ERROR] runtime failed safely: {type(exc).__name__}: {exc}\n")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def fallback_result(exc: Exception) -> dict:
    return {
        "status": "failed",
        "controller_status": "runtime_exception",
        "termination_reason": "entrypoint_exception",
        "failure_reason": f"runtime_exception:{type(exc).__name__}",
        "exception": {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(limit=8),
        },
    }


def write_fallback_result(agent_root: Path, result: dict) -> None:
    challenge_id = os.environ.get("CHALLENGE_ID") or "unknown"
    workspace = Path(os.environ.get("WORKDIR") or Path(os.environ.get("AIXCTF_WORKSPACE_BASE", agent_root / "workspace")) / challenge_id)
    output_dir = Path(os.environ.get("OUTPUT_DIR", "/output"))
    for path in [workspace / "result.json", workspace / "controller_result.json", output_dir / "result.json"]:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as write_exc:
            sys.stderr.write(f"[AIXCTF][WARN] could not write fallback result to {path}: {write_exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
