from __future__ import annotations

import re
from pathlib import Path

from hooks.hook_io import command_from_payload, is_native_task_tool, tool_input, tool_name
from runner.event_store import EventStore
from runner.paths import workspace_root
from runner.state_store import StateStore
from sync.sync_queue import SyncQueue
from tools.scope_utils import command_uses_network_tool, hosts_in_scope, looks_like_large_scan


DANGEROUS_PATTERNS = [
    r"\brm\s+-rf\s+/",
    r"\bmkfs(?:\.\w+)?\b",
    r"\bdd\s+.*\bof=/dev/",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;",
]


def check(payload: dict) -> dict:
    workspace = workspace_root()
    state = StateStore(workspace).load_or_create()
    name = tool_name(payload)
    input_data = tool_input(payload)
    command = command_from_payload(payload)
    allowed, reason = evaluate(name, command, state.get("allowed_scope", {}), input_data, workspace)
    event = {
        "tool": name,
        "tool_input": tool_input(payload),
        "command": command,
        "pre_check": {"allowed": allowed, "reason": reason},
    }
    event_store = EventStore(workspace)
    round_id = event_store.current_round()
    event_store.append(round_id, event)
    SyncQueue(workspace).emit_simple(
        source="hook",
        event_type="tool_started" if allowed else "tool_blocked",
        level="info" if allowed else "warning",
        round_id=round_id,
        phase=state.get("phase"),
        category=state.get("category"),
        message=reason,
        summary={"tool": name, "command": command},
        hook="PreToolUse",
        tool=name,
    )
    return {"allowed": allowed, "reason": reason}


def evaluate(name: str, command: str, allowed_scope: dict, input_data: dict | None = None, workspace: Path | None = None) -> tuple[bool, str]:
    if is_native_task_tool(name):
        return evaluate_task_tool(input_data or {}, allowed_scope)
    if name in {"Write", "Edit", "MultiEdit"}:
        ok, reason = writable_workspace_path(input_data or {}, workspace)
        if not ok:
            return False, reason
    if name != "Bash" and not command:
        return True, "non-Bash tool allowed"
    lowered = command.lower()
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, lowered):
            return False, f"dangerous command blocked: {pattern}"
    target = bash_runtime_mutation_target(command, workspace)
    if target:
        return False, f"runtime-owned path is read-only for agents: {target}"
    if looks_like_large_scan(command):
        return False, "large or unbounded scan blocked"
    if command_uses_network_tool(command):
        ok, reason = hosts_in_scope(command, allowed_scope)
        if not ok:
            return False, reason
    protected = [str(workspace / name) for name in ["state.json", "result.json", "rounds", "events"]]
    if any(f"rm " in lowered and item in command for item in protected):
        return False, "deleting workspace state artifacts is blocked"
    return True, "within challenge scope"


def evaluate_task_tool(input_data: dict, allowed_scope: dict) -> tuple[bool, str]:
    agent_type = str(input_data.get("subagent_type") or input_data.get("agent_type") or input_data.get("type") or "general-purpose")
    normalized_type = agent_type.replace("_", "-")
    if normalized_type != "general-purpose":
        return False, f"unsupported Task subagent type: {agent_type}"

    prompt = task_prompt_text(input_data).lower()
    if not prompt.strip():
        return False, "Task prompt is empty"

    for token in ["claude -p", "modify runtime", "edit runtime"]:
        if token in prompt:
            return False, f"Task prompt targets runtime-owned control plane: {token}"
    target = runtime_control_plane_target(prompt)
    if target:
        return False, f"Task prompt targets runtime-owned control plane: {target}"

    if command_uses_network_tool(prompt):
        ok, reason = hosts_in_scope(prompt, allowed_scope)
        if not ok:
            return False, reason

    if any(token in prompt for token in ["solve the whole challenge", "take over the whole challenge", "ignore scope"]):
        return False, "Task prompt is not bounded"

    return True, "bounded native Task subagent allowed"


def runtime_control_plane_target(prompt: str) -> str | None:
    prompt = prompt.lower()
    targets = ["state.json", "result.json", "rounds/", "events/", "sync/", ".claude/"]
    target_verbs = {
        "read",
        "open",
        "inspect",
        "parse",
        "load",
        "cat",
        "write",
        "edit",
        "modify",
        "delete",
        "remove",
        "update",
        "append",
        "overwrite",
        "patch",
        "scan",
        "reading",
        "writing",
        "editing",
        "modifying",
        "deleting",
    }
    for target in targets:
        for match in re.finditer(re.escape(target), prompt):
            before = prompt[max(0, match.start() - 80) : match.start()]
            verb = nearest_target_verb(before, target_verbs)
            if verb and not verb_is_negated(before, verb):
                return target
    return None


def nearest_target_verb(before: str, target_verbs: set[str]) -> re.Match[str] | None:
    matches = [match for match in re.finditer(r"[a-z0-9_.-]+", before) if match.group(0) in target_verbs]
    return matches[-1] if matches else None


def verb_is_negated(before: str, verb: re.Match[str]) -> bool:
    prefix = before[max(0, verb.start() - 32) : verb.start()]
    return bool(re.search(r"(do\s+not|don't|must\s+not|never|avoid|without|forbidden\s+to|not\s+to)\s*$", prefix))


def task_prompt_text(input_data: dict) -> str:
    parts = []
    for key in ["description", "prompt", "instructions", "content"]:
        value = input_data.get(key)
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))
    return "\n".join(parts)


def writable_workspace_path(input_data: dict, workspace: Path | None) -> tuple[bool, str]:
    raw_path = input_data.get("file_path") or input_data.get("path")
    if not raw_path:
        return True, "non-Bash tool allowed"
    rel = workspace_relative(str(raw_path), workspace)
    if rel is None:
        return False, f"write target is outside workspace: {raw_path}"
    protected_files = {"state.json", "result.json", "status.json", "progress.jsonl", "AGENTS.md", "CLAUDE.md"}
    protected_dirs = {"rounds", "events", "state_snapshots", "sync", ".claude"}
    parts = Path(rel).parts
    if rel in protected_files or (parts and parts[0] in protected_dirs):
        return False, f"runtime-owned path is read-only for agents: {rel}"
    return True, "within writable workspace area"


def bash_runtime_mutation_target(command: str, workspace: Path | None) -> str | None:
    if workspace and re.search(r"\brm\s+[^;&|]*\s" + re.escape(str(workspace)) + r"(?:\s|/|$)", command):
        return str(workspace)
    if re.search(r"\brm\s+[^;&|]*\s(['\"]?)(?:\$\{WORKDIR\}|\$WORKDIR)\1(?:\s|$)", command):
        return "$WORKDIR"
    if re.search(r"\brm\s+[^;&|]*\s/(?:workspace)(?:\s|/|$)", command):
        return "/workspace"
    for match in re.finditer(r"(?:>>?|[12]>|&>)\s*(['\"]?)([^'\"\s;&|]+)\1", command):
        rel = protected_runtime_rel(match.group(2), workspace)
        if rel:
            return rel
    for match in re.finditer(r"\btee\b(?:\s+-a)?\s+(['\"]?)([^'\"\s;&|]+)\1", command):
        rel = protected_runtime_rel(match.group(2), workspace)
        if rel:
            return rel
    for match in re.finditer(r"\b(?:rm|unlink|touch|truncate|mkdir|rmdir|chmod|chown|mv|cp)\b([^;&|]*)", command):
        rel = protected_runtime_rel_in_text(match.group(1), workspace)
        if rel:
            return rel
    for match in re.finditer(r"\bsed\b([^;&|]*\s-i[^;&|]*)", command):
        rel = protected_runtime_rel_in_text(match.group(1), workspace)
        if rel:
            return rel
    for match in re.finditer(r"open\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"][^'\"]*[wa+][^'\"]*['\"]", command):
        rel = protected_runtime_rel(match.group(1), workspace)
        if rel:
            return rel
    for match in re.finditer(r"['\"]([^'\"]+)['\"]\.write_text\(", command):
        rel = protected_runtime_rel(match.group(1), workspace)
        if rel:
            return rel
    return None


def protected_runtime_rel_in_text(text: str, workspace: Path | None) -> str | None:
    for raw in re.findall(
        r"['\"]?((?:\$\{WORKDIR\}|\$WORKDIR)(?:/[^'\"\s;&|]+)?|/workspace(?:/[^'\"\s;&|]+)?|\.claude(?:/[^'\"\s;&|]+)?|[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)['\"]?",
        text,
    ):
        rel = protected_runtime_rel(raw, workspace)
        if rel:
            return rel
    return None


def protected_runtime_rel(raw_path: str, workspace: Path | None) -> str | None:
    rel = workspace_relative(raw_path.strip("'\""), workspace)
    if rel is None:
        return None
    rel = rel.rstrip("/")
    if rel in {"", "."}:
        return "."
    protected_files = {"state.json", "result.json", "status.json", "progress.jsonl", "AGENTS.md", "CLAUDE.md"}
    protected_dirs = {"rounds", "events", "state_snapshots", "sync", ".claude"}
    parts = Path(rel).parts
    if rel in protected_files or (parts and parts[0] in protected_dirs):
        return rel
    return None


def workspace_relative(raw_path: str, workspace: Path | None) -> str | None:
    raw_path = raw_path.strip("'\"")
    if raw_path in {"$WORKDIR", "${WORKDIR}"}:
        return "."
    for prefix in ["$WORKDIR/", "${WORKDIR}/"]:
        if raw_path.startswith(prefix):
            return raw_path[len(prefix) :]
    if raw_path.startswith("/workspace/"):
        return raw_path.split("/workspace/", 1)[1]
    path = Path(raw_path)
    if not path.is_absolute():
        return str(path)
    if workspace is None:
        return None
    try:
        return str(path.resolve().relative_to(workspace.resolve()))
    except ValueError:
        return None
