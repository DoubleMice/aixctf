from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any


class ClaudeRunner:
    def __init__(self, agent_root: Path, workspace: Path):
        self.agent_root = agent_root
        self.workspace = workspace
        self.logs_dir = workspace / "logs"
        self.prompts_dir = workspace / "prompts"
        self.init_warning: str | None = None
        try:
            self.logs_dir.mkdir(parents=True, exist_ok=True)
            self.prompts_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.init_warning = str(exc)

    def run(self, round_id: int, prompt: str, timeout_seconds: int, dry_run: bool) -> dict[str, Any]:
        prompt_path = self.prompts_dir / f"round_{round_id:03d}.md"
        try:
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt, encoding="utf-8")
        except OSError as exc:
            return {
                "mode": "dry-run" if dry_run else "real",
                "exit_code": 126,
                "stdout": "",
                "stderr": f"could not write round prompt: {exc}",
                "log_path": "",
                "prompt_write_error": True,
            }
        if dry_run:
            return self._dry_run(round_id, prompt_path)
        return self._real_run(round_id, prompt_path, timeout_seconds)

    def _dry_run(self, round_id: int, prompt_path: Path) -> dict[str, Any]:
        stdout = {
            "research_question": "Does the AutoResearch runtime advance one bounded round?",
            "hypothesis": "Dry-run mode can validate loop, state, progress, and result plumbing without ClaudeCode.",
            "experiment": f"Generate round prompt at {prompt_path} and synthesize structured round output.",
            "observations": [f"dry-run round {round_id} prompt generated at {prompt_path}"],
            "evidence": [str(prompt_path)],
            "conclusion": "Runtime loop executed without invoking ClaudeCode.",
            "state_delta": {"active_strategy": "dry_run_validation"},
            "candidate_flags": [],
            "failure_reason": "dry_run_no_solver",
            "next_experiment": "Run with AIXCTF_DRY_RUN=0 and ANTHROPIC_API_KEY to invoke ClaudeCode.",
            "do_not_repeat": [],
        }
        log_path = self.logs_dir / f"claude_round_{round_id:03d}.log"
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps(stdout, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            return {"mode": "dry-run", "exit_code": 0, "stdout": json.dumps(stdout), "stderr": str(exc), "log_path": "", "log_write_warning": True}
        return {"mode": "dry-run", "exit_code": 0, "stdout": json.dumps(stdout), "stderr": "", "log_path": str(log_path)}

    def _real_run(self, round_id: int, prompt_path: Path, timeout_seconds: int) -> dict[str, Any]:
        log_path = self.logs_dir / f"claude_round_{round_id:03d}.log"
        err_path = self.logs_dir / f"claude_round_{round_id:03d}.err.log"
        command = os.environ.get("CLAUDE_CODE_CMD", "claude -p")
        args = shlex.split(command)
        if not args or shutil.which(args[0]) is None:
            message = f"ClaudeCode command not found: {args[0] if args else command}"
            write_text_best_effort(log_path, "")
            write_text_best_effort(err_path, message + "\n")
            return {
                "mode": "real",
                "exit_code": 127,
                "stdout": "",
                "stderr": message,
                "log_path": str(log_path),
                "stderr_path": str(err_path),
                "env_error": True,
            }
        env = os.environ.copy()
        env.setdefault("AIXCTF_AGENT_ROOT", str(self.agent_root))
        env["WORKDIR"] = str(self.workspace)
        env["CHALLENGE_DIR"] = str(self.workspace / "challenge")
        env["AIXCTF_ROUND_ID"] = str(round_id)
        try:
            proc = subprocess.run(
                args,
                cwd=self.workspace,
                env=env,
                text=True,
                input=prompt_path.read_text(encoding="utf-8"),
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
            log_warning = write_text_best_effort(log_path, proc.stdout)
            err_warning = write_text_best_effort(err_path, proc.stderr)
            warnings = [warning for warning in [log_warning, err_warning] if warning]
            return {
                "mode": "real",
                "exit_code": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "log_path": str(log_path),
                "stderr_path": str(err_path),
                "write_warnings": warnings,
            }
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            warnings = [warning for warning in [write_text_best_effort(log_path, stdout), write_text_best_effort(err_path, stderr)] if warning]
            return {
                "mode": "real",
                "exit_code": 124,
                "stdout": stdout,
                "stderr": stderr,
                "log_path": str(log_path),
                "stderr_path": str(err_path),
                "timeout": True,
                "write_warnings": warnings,
            }
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            write_text_best_effort(err_path, message + "\n")
            return {
                "mode": "real",
                "exit_code": 127,
                "stdout": "",
                "stderr": message,
                "log_path": str(log_path),
                "stderr_path": str(err_path),
            }


def write_text_best_effort(path: Path, content: str) -> str | None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", errors="replace")
        return None
    except OSError as exc:
        return f"could not write {path}: {exc}"
