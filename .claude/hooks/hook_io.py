from __future__ import annotations

import json
import sys
from typing import Any

NATIVE_TASK_TOOL_NAMES = {"Task", "Agent"}


def read_hook_input() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw, "_parse_error": True}


def write_json(data: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def tool_name(payload: dict[str, Any]) -> str:
    return str(payload.get("tool_name") or payload.get("tool") or payload.get("name") or "unknown")


def is_native_task_tool(name: str) -> bool:
    return name in NATIVE_TASK_TOOL_NAMES


def tool_input(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("tool_input") or payload.get("input") or {}
    return value if isinstance(value, dict) else {"value": value}


def command_from_payload(payload: dict[str, Any]) -> str:
    data = tool_input(payload)
    command = data.get("command") or data.get("cmd") or data.get("value")
    if command:
        return str(command)
    if is_native_task_tool(tool_name(payload)):
        return task_summary(data)
    return ""


def task_summary(data: dict[str, Any]) -> str:
    agent_type = data.get("subagent_type") or data.get("agent_type") or data.get("type") or "general-purpose"
    description = data.get("description") or data.get("task") or data.get("title") or ""
    prompt = task_prompt(data)
    preview = prompt.replace("\n", " ").strip()[:240]
    parts = [f"subagent_type={agent_type}"]
    if description:
        parts.append(f"description={description}")
    if preview:
        parts.append(f"prompt={preview}")
    return "; ".join(parts)


def task_prompt(data: dict[str, Any]) -> str:
    value = data.get("prompt") or data.get("instructions") or data.get("content") or ""
    if isinstance(value, list):
        return "\n".join(render_content_item(item) for item in value)
    return str(value)


def tool_output_text(payload: dict[str, Any]) -> tuple[str, str]:
    response = payload.get("tool_response") or payload.get("response") or {}
    if isinstance(response, str):
        return response, ""
    if not isinstance(response, dict):
        return str(response), ""
    stdout = response.get("stdout") or response.get("output") or response.get("content") or response.get("result") or response.get("text") or ""
    stderr = response.get("stderr") or response.get("error") or ""
    if isinstance(stdout, list):
        stdout = "\n".join(render_content_item(item) for item in stdout)
    if isinstance(stderr, list):
        stderr = "\n".join(render_content_item(item) for item in stderr)
    return str(stdout), str(stderr)


def render_content_item(item: Any) -> str:
    if isinstance(item, dict):
        for key in ["text", "content", "result", "output"]:
            if key in item:
                return str(item[key])
    return str(item)


def pretool_allow(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }


def pretool_deny(reason: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def posttool_context(context: str) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }


def stop_block(reason: str) -> dict[str, Any]:
    return {"decision": "block", "reason": reason}


def stop_allow(context: str) -> dict[str, Any]:
    return {}
