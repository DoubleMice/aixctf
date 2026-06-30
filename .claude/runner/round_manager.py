from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from runner.claude_runner import ClaudeRunner
from runner.event_store import EventStore, event_action
from runner.feedback_loop import classify_failure
from runner.knowledge_router import KnowledgeRouter
from runner.loop_core import LoopCore
from runner.progress_exporter import ProgressExporter
from runner.reflection_engine import ReflectionEngine
from sync.human_sync_agent import HumanSyncAgent
from sync.sync_queue import SyncQueue


PHASE_ORDER = ["init", "classify", "triage", "hypothesis", "exploit", "verify", "solved"]


class RoundManager:
    def __init__(self, agent_root: Path, workspace: Path):
        self.agent_root = agent_root
        self.workspace = workspace
        self.event_store = EventStore(workspace)
        self.knowledge_router = KnowledgeRouter(agent_root)
        self.claude_runner = ClaudeRunner(agent_root, workspace)
        self.loop_core = LoopCore(agent_root, workspace)
        self.reflection_engine = ReflectionEngine()
        self.progress = ProgressExporter(workspace)
        self.sync_queue = SyncQueue(workspace)
        self.human_sync_agent = HumanSyncAgent(agent_root, workspace)

    def run_round(
        self,
        round_id: int,
        state: dict[str, Any],
        challenge_context: dict[str, Any],
        runtime_limits: dict[str, Any],
        dry_run: bool,
    ) -> dict[str, Any]:
        loop_plan = self.loop_core.prepare_round(state, round_id)
        state = dict(state)
        state.setdefault("research_loop", {})["active_strategy"] = loop_plan["active_strategy"]
        selected_docs = self.knowledge_router.select(state)
        selected_template = selected_docs["templates"][0]
        self.progress.emit(
            level="info",
            event="knowledge_selected",
            message=f"selected {selected_template}",
            round_id=round_id,
            phase=state.get("phase", "init"),
            category=state.get("category", "unknown"),
        )
        self.sync_queue.emit_simple(
            source="round_manager",
            event_type="round_started",
            round_id=round_id,
            phase=state.get("phase"),
            category=state.get("category"),
            message=f"Round {round_id} started.",
            summary={"selected_docs": selected_docs},
        )
        prompt = self.build_prompt(round_id, state, challenge_context, selected_docs, loop_plan)
        claude_result = self.claude_runner.run(round_id, prompt, int(runtime_limits.get("max_command_seconds", 7200)), dry_run)
        events = self.event_store.collect(round_id)
        subtasks = native_task_results_from_events(events)
        round_result = self.summarize(round_id, state, claude_result, events, selected_docs, loop_plan, subtasks)
        self.write_round_result(round_result)
        self.update_notes(round_result)
        self.update_handoff(state, challenge_context, round_result)
        self.sync_queue.emit_simple(
            source="round_manager",
            event_type="round_end",
            round_id=round_id,
            phase=round_result.get("phase_after"),
            category=round_result.get("category"),
            message=f"Round {round_id} ended with status {round_result.get('status')}.",
            summary={"conclusion": round_result.get("loop", {}).get("conclusion")},
            artifacts=round_result.get("new_artifacts", []),
        )
        sync_result = self.human_sync_agent.flush_round(state, round_result)
        round_result["sync_summary"] = {
            "events_emitted": len(self.sync_queue.read_events(limit=1000)),
            "human_sync_attempted": True,
            "human_sync_status": "sent" if sync_result.get("ok") else ("skipped" if sync_result.get("skipped") else "spooled"),
            "reason": sync_result.get("reason"),
        }
        self.write_round_result(round_result)
        self.progress.emit(
            level="success" if round_result.get("status") == "solved" else "info",
            event="round_end",
            message=round_result.get("loop", {}).get("conclusion", round_result.get("status", "round ended")),
            round_id=round_id,
            phase=round_result.get("phase_after", "unknown"),
            category=round_result.get("category", "unknown"),
            artifacts=round_result.get("new_artifacts", []),
        )
        return round_result

    def build_prompt(
        self,
        round_id: int,
        state: dict[str, Any],
        challenge_context: dict[str, Any],
        selected_docs: dict[str, list[str]],
        loop_plan: dict[str, Any],
    ) -> str:
        selected_template = selected_docs["templates"][0]
        template_content = self.knowledge_router.read_doc_excerpt(selected_template)
        docs_content = {
            group: "\n\n".join(f"## {doc}\n\n{self.knowledge_router.read_doc_excerpt(doc)}" for doc in docs)
            for group, docs in selected_docs.items()
            if group != "templates"
        }
        research = state.get("research_loop", {})
        return f"""# Round {round_id:03d} Input

## Current State

```json
{json.dumps(state, ensure_ascii=False, indent=2)}
```

## Challenge Context

{challenge_context.get("summary", "")}

## Runtime Paths

- ClaudeCode current working directory: `{self.workspace}`
- Challenge directory: `{self.workspace / "challenge"}`
- In Docker, the default workspace is `/aixctf-agent/workspace/<challenge_id>/`.
- `WORKDIR` is set to the current workspace. Use `$WORKDIR` or relative paths from the current directory.
- During local non-Docker tests, `WORKDIR` may be set to a temporary host path.

## Allowed Scope

```json
{json.dumps(state.get("allowed_scope", {}), ensure_ascii=False, indent=2)}
```

## Current Research Loop

- Research question: {research.get("current_question")}
- Current hypothesis: {research.get("current_hypothesis")}
- Active strategy: {research.get("active_strategy")}
- Open questions: {json.dumps(research.get("open_questions", []), ensure_ascii=False)}
- Known facts: {json.dumps(research.get("known_facts", []), ensure_ascii=False)}
- Falsified hypotheses: {json.dumps(research.get("falsified_hypotheses", []), ensure_ascii=False)}

## Selected Template

Path: `{selected_template}`

{template_content}

## Selected Skill Docs

{docs_content.get("skills", "")}

## Selected Tool Docs

{docs_content.get("tools", "")}

## Selected Debug Docs

{docs_content.get("debug", "")}

## Selected Handoff Docs

{docs_content.get("handoff", "")}

## Previous Failures

```json
{json.dumps(state.get("failures", []), ensure_ascii=False, indent=2)}
```

## Native Task Delegation

If a task is strongly bounded or context-heavy, use ClaudeCode's native `Task`
tool with `subagent_type: "general-purpose"`. The Task must be scoped to one
question, must not solve the whole challenge, and must not write runtime-owned
files. Ask the Task to return a compact JSON object with:

```json
{{
  "status": "confirmed|falsified|inconclusive|blocked",
  "conclusion": "",
  "confidence": 0.0,
  "evidence": [],
  "facts_added": [],
  "hypotheses_falsified": [],
  "next_recommendation": "",
  "do_not_repeat": []
}}
```

## Required Round Output

Before stopping this round, update these files under the workspace root:

- `notes.md`
- `handoff.md`
- `scripts/` if needed
- `evidence/` if success evidence exists

Do not write runtime-owned files or directories such as `state.json`, `result.json`,
`status.json`, `progress.jsonl`, `rounds/`, `events/`, `sync/`, or `.claude/`.
The runtime writes those after ClaudeCode exits. Return the required JSON as your
final response instead of writing it to `rounds/`.

Then end with a JSON object containing:

```json
{{
  "research_question": "",
  "hypothesis": "",
  "experiment": "",
  "observations": [],
  "evidence": [],
  "conclusion": "",
  "state_delta": {{}},
  "candidate_flags": [],
  "confirmed_flag": null,
  "failure_reason": null,
  "next_experiment": "",
  "task_results": [],
  "do_not_repeat": []
}}
```
"""

    def summarize(
        self,
        round_id: int,
        state: dict[str, Any],
        claude_result: dict[str, Any],
        events: list[dict[str, Any]],
        selected_docs: dict[str, list[str]],
        loop_plan: dict[str, Any],
        subtasks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        parsed = parse_round_json(claude_result.get("stdout", ""))
        if not parsed:
            parsed = parse_round_json_from_events(self.workspace, events)
        phase_after = parsed.get("phase_after") or next_phase(state.get("phase", "init"), parsed)
        status = "solved" if parsed.get("confirmed_flag") else "progress"
        failure_reason = claude_failure_reason(claude_result)
        if failure_reason:
            status = "failed"
            parsed.setdefault("failure_reason", failure_reason)
        if claude_result.get("timeout"):
            status = "failed"
            parsed["failure_reason"] = "TIMEOUT"
        artifacts = artifacts_from_result(self.workspace, claude_result, events)
        candidate_flags = merge_candidate_flags(parsed.get("candidate_flags") or [], events)
        observations = parsed.get("observations") or default_observations(claude_result)
        loop = self.reflection_engine.build_loop(state, parsed, observations, artifacts)
        round_result = {
            "round": round_id,
            "category": parsed.get("category") or state.get("category", "unknown"),
            "status": status,
            "phase_before": state.get("phase", "init"),
            "phase_after": phase_after,
            "loop": loop,
            "actions": [event_action(event) for event in events],
            "observations": observations,
            "progress_delta": parsed.get("progress_delta") or [],
            "candidate_flags": candidate_flags,
            "confirmed_flag": parsed.get("confirmed_flag"),
            "new_artifacts": artifacts,
            "failure_reason": parsed.get("failure_reason"),
            "recommended_docs_next": selected_docs,
            "subtasks": subtasks,
            "next_plan": loop.get("next_experiment") or "Continue from current state and avoid repeating failed paths.",
            "do_not_repeat": parsed.get("do_not_repeat") or [],
            "claude": {
                "mode": claude_result.get("mode"),
                "exit_code": claude_result.get("exit_code"),
                "log_path": relativize(self.workspace, claude_result.get("log_path")),
                "stderr_path": relativize(self.workspace, claude_result.get("stderr_path")),
            },
        }
        failure = classify_failure(round_result)
        if failure and not round_result.get("failure_reason"):
            round_result["failure_reason"] = failure
        return round_result

    def write_round_result(self, round_result: dict[str, Any]) -> None:
        path = self.workspace / "rounds" / f"round_{round_result['round']:03d}.json"
        try:
            atomic_write_json(path, round_result)
        except OSError as exc:
            self.record_warning(f"could not write round result {path}: {exc}")

    def update_notes(self, round_result: dict[str, Any]) -> None:
        path = self.workspace / "notes.md"
        loop = round_result.get("loop", {})
        block = f"""## Iteration {round_result['round']} Feedback

Research Question: {loop.get('research_question') or 'n/a'}
Hypothesis: {loop.get('hypothesis') or 'n/a'}
Experiment: {loop.get('experiment') or 'n/a'}
Observation: {'; '.join(str(item) for item in loop.get('observation', []))}
Evidence: {', '.join(str(item) for item in loop.get('evidence', [])) or 'n/a'}
What failed: {round_result.get('failure_reason') or 'n/a'}
Likely reason: {round_result.get('failure_reason') or 'progress round'}
Conclusion: {loop.get('conclusion') or 'n/a'}
Next experiment: {loop.get('next_experiment') or 'n/a'}
Do not repeat: {', '.join(str(item) for item in round_result.get('do_not_repeat', [])) or 'n/a'}
Recommended template docs: {', '.join(str(item) for item in round_result.get('recommended_docs_next', {}).get('templates', []))}
Recommended skill docs: {', '.join(str(item) for item in round_result.get('recommended_docs_next', {}).get('skills', []))}
Recommended tool docs: {', '.join(str(item) for item in round_result.get('recommended_docs_next', {}).get('tools', []))}
Recommended debug docs: {', '.join(str(item) for item in round_result.get('recommended_docs_next', {}).get('debug', []))}
Native Task results recorded: {bool(round_result.get('subtasks'))}

"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_text("# Challenge Notes\n\n", encoding="utf-8")
            with path.open("a", encoding="utf-8") as fh:
                fh.write(block)
        except OSError as exc:
            self.record_warning(f"could not update notes.md: {exc}")

    def update_handoff(self, state: dict[str, Any], challenge_context: dict[str, Any], round_result: dict[str, Any]) -> None:
        path = self.workspace / "handoff.md"
        try:
            rounds = sorted((self.workspace / "rounds").glob("round_*.json"))
        except OSError:
            rounds = []
        tried_rows = []
        for round_path in rounds:
            try:
                data = json.loads(round_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            tried_rows.append(
                f"| {data.get('round')} | {data.get('phase_before')} -> {data.get('phase_after')} | "
                f"{data.get('status')} | {'; '.join(str(item) for item in data.get('observations', [])[:2])} |"
            )
        loop = round_result.get("loop", {})
        content = f"""# Challenge Handoff

## Current Status

- Category: {round_result.get('category') or state.get('category')}
- Phase: {round_result.get('phase_after')}
- Solved: {str(round_result.get('status') == 'solved').lower()}
- Candidate flag: {', '.join(round_result.get('candidate_flags', [])) or 'n/a'}
- Confidence: {"0.95" if round_result.get('status') == 'solved' else "0.0"}

## Challenge Summary

{challenge_context.get('summary', 'No challenge summary available.')[:4000]}

## What Has Been Tried

| Round | Attempt | Result | Conclusion |
|---|---|---|---|
{chr(10).join(tried_rows)}

## Useful Observations

{bullet_list(round_result.get('observations', []))}

## Failed Paths

Do not repeat:

{bullet_list(round_result.get('do_not_repeat', []))}

## Current Hypotheses

1. {loop.get('hypothesis') or round_result.get('next_plan') or 'Continue triage.'}

## Current Research Loop

- Research question: {loop.get('research_question') or 'n/a'}
- Experiment: {loop.get('experiment') or 'n/a'}
- Conclusion: {loop.get('conclusion') or 'n/a'}
- Next experiment: {loop.get('next_experiment') or 'n/a'}

## Best Next Step

The next agent should run:

```bash
{suggested_command(round_result.get('category'), round_result.get('phase_after'))}
```

## Important Files

```text
state.json
notes.md
scripts/
logs/
evidence/
rounds/
subtasks/
sync/
progress.jsonl
status.json
```

## Evidence Collected

{bullet_list(round_result.get('new_artifacts', []))}
"""
        try:
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            self.record_warning(f"could not update handoff.md: {exc}")

    def record_warning(self, message: str) -> None:
        try:
            path = self.workspace / "logs" / "runtime_warnings.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(message + "\n")
        except OSError:
            pass


def parse_round_json(stdout: str) -> dict[str, Any]:
    stdout = stdout.strip()
    if not stdout:
        return {}
    try:
        parsed = json.loads(stdout)
        if isinstance(parsed, dict) and isinstance(parsed.get("result"), str):
            nested = parse_round_json(parsed["result"])
            if nested:
                return nested
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        pass
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", stdout, flags=re.DOTALL)
    for candidate in reversed(fenced):
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            continue
    for candidate in reversed(extract_balanced_json_objects(stdout)):
        try:
            parsed = json.loads(candidate)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            continue
    return {}


def parse_round_json_from_events(workspace: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in reversed(events):
        for text in event_text_candidates(workspace, event):
            parsed = parse_round_json(text)
            if looks_like_round_payload(parsed):
                return parsed
    return {}


def native_task_results_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results = []
    seen = set()
    for event in events:
        post = event.get("post_check") or {}
        result_path = post.get("task_result_path")
        if not result_path or result_path in seen:
            continue
        seen.add(result_path)
        task_dir = post.get("task_dir") or str(Path(result_path).parent)
        results.append(
            {
                "subtask_id": Path(task_dir).name,
                "type": "claudecode_native_task",
                "status": "recorded",
                "result_path": result_path,
                "handoff_path": post.get("task_handoff_path"),
            }
        )
    return results


def event_text_candidates(workspace: Path, event: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    tool_input = event.get("tool_input") or {}
    if isinstance(tool_input, dict):
        for key in ["content", "text", "value"]:
            value = tool_input.get(key)
            if isinstance(value, str) and value.strip():
                candidates.append(value)
    log_path = event.get("post_check", {}).get("log_path")
    if log_path:
        path = workspace / log_path
        if path.exists():
            try:
                candidates.append(path.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
    return candidates


def looks_like_round_payload(parsed: dict[str, Any]) -> bool:
    if not parsed:
        return False
    loop_keys = {"research_question", "hypothesis", "experiment", "observations", "conclusion", "state_delta", "next_experiment"}
    result_keys = {"candidate_flags", "confirmed_flag", "failure_reason"}
    return bool(loop_keys.intersection(parsed)) and bool(result_keys.intersection(parsed))


def extract_balanced_json_objects(text: str) -> list[str]:
    objects: list[str] = []
    for start, char in enumerate(text):
        if char != "{":
            continue
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(text)):
            current = text[index]
            if escape:
                escape = False
                continue
            if current == "\\":
                escape = True
                continue
            if current == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    objects.append(text[start : index + 1])
                    break
    return objects


def next_phase(current: str, parsed: dict[str, Any]) -> str:
    if parsed.get("confirmed_flag"):
        return "solved"
    if current not in PHASE_ORDER:
        return "triage"
    idx = PHASE_ORDER.index(current)
    return PHASE_ORDER[min(idx + 1, len(PHASE_ORDER) - 2)]


def default_observations(claude_result: dict[str, Any]) -> list[str]:
    if claude_result.get("timeout"):
        return ["ClaudeCode round timed out."]
    reason = claude_failure_reason(claude_result)
    if reason == "ENV_ERROR":
        return ["ClaudeCode environment error prevented the round from running."]
    if claude_result.get("exit_code") not in (0, None):
        return [f"ClaudeCode exited with code {claude_result.get('exit_code')}."]
    return ["ClaudeCode round completed."]


def claude_failure_reason(claude_result: dict[str, Any]) -> str | None:
    if claude_result.get("timeout"):
        return "TIMEOUT"
    if claude_result.get("exit_code") in (0, None):
        return None
    if claude_result.get("env_error"):
        return "ENV_ERROR"
    return "TOOL_ERROR"


def artifacts_from_result(workspace: Path, claude_result: dict[str, Any], events: list[dict[str, Any]]) -> list[str]:
    artifacts = []
    for key in ["log_path", "stderr_path"]:
        rel = relativize(workspace, claude_result.get(key))
        if rel:
            artifacts.append(rel)
    for event in events:
        post = event.get("post_check", {})
        for key in ["log_path", "evidence_path", "evidence_meta_path", "task_result_path", "task_handoff_path"]:
            value = post.get(key)
            if value:
                artifacts.append(value)
    return sorted(dict.fromkeys(artifact for artifact in artifacts if artifact))


def merge_candidate_flags(parsed_flags: list[Any], events: list[dict[str, Any]]) -> list[Any]:
    flags = list(parsed_flags)
    for event in events:
        post = event.get("post_check") or {}
        for flag in post.get("candidate_flags") or []:
            if flag not in flags:
                flags.append(flag)
    return flags


def relativize(workspace: Path, path_value: str | None) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    try:
        return str(path.relative_to(workspace))
    except ValueError:
        if "/workspace/" in str(path):
            return str(path).split("/workspace/", 1)[1]
        return str(path)


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def bullet_list(values: list[str]) -> str:
    if not values:
        return "- n/a"
    return "\n".join(f"- {value}" for value in values)


def suggested_command(category: str | None, phase: str | None) -> str:
    if category == "pwn" and phase in {"triage", "hypothesis"}:
        return 'python3 /aixctf-agent/tools/pwn_triage.py "$WORKDIR/challenge"'
    if category == "web" and phase in {"triage", "hypothesis"}:
        return "python3 /aixctf-agent/tools/web_triage.py"
    return 'cat "$WORKDIR/state.json" && cat "$WORKDIR/handoff.md"'
