from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import json
import os
import shutil
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runner.category_classifier import classify_challenge
from runner.challenge_loader import ChallengeLoader
from runner.challenge_scheduler import ChallengeRecord, ChallengeScheduler, ChallengeSource, discover_challenge_sources
from runner.paths import (
    agent_root,
    challenge_root,
    ensure_workspace_dirs,
    output_root,
    safe_path_segment,
    workspace_base_root,
    workspace_root,
)
from runner.progress_exporter import ProgressExporter
from runner.result_collector import ResultCollector
from runner.round_manager import RoundManager
from runner.status_writer import StatusWriter
from runner.state_store import StateStore


class RuntimeController:
    def __init__(self):
        self.agent_root = agent_root()
        self.challenge_source = challenge_root()
        self.output_dir = output_root()
        self.initial_workdir = os.environ.get("WORKDIR")
        self.started_at = time.monotonic()
        self.challenge_sources = discover_challenge_sources(self.challenge_source)
        self.multi_challenge = len(self.challenge_sources) > 1
        self.scheduler = ChallengeScheduler(self.max_rounds_per_visit())
        self.records = self.build_records(self.challenge_sources)
        self.parallelism = self.max_parallel_challenges()

    def run(self) -> dict:
        dry_run = is_truthy(os.environ.get("AIXCTF_DRY_RUN", os.environ.get("DRY_RUN", "0")))
        if self.parallelism > 1 and len(self.records) > 1:
            termination_reason = self.run_parallel(dry_run)
        else:
            termination_reason = self.run_sequential(dry_run)

        if self.multi_challenge or not self.records:
            return self.write_controller_result(termination_reason)
        return self.records[0].last_result or self.write_controller_result(termination_reason)

    def run_sequential(self, dry_run: bool) -> str:
        while not self.scheduler.all_solved(self.records):
            if self.controller_timed_out():
                return "controller_timeout"
            record = self.scheduler.next_challenge(self.records)
            if record is None:
                return "no_schedulable_challenge"

            state, result, pause_reason = self.run_challenge_visit_safely(record, dry_run)
            self.scheduler.update(record, state, result, pause_reason)
        return "all_solved"

    def run_parallel(self, dry_run: bool) -> str:
        active: dict[Future[tuple[dict, dict, str | None]], ChallengeRecord] = {}
        executor = ThreadPoolExecutor(max_workers=self.parallelism, thread_name_prefix="aixctf-challenge")
        try:
            while not self.scheduler.all_solved(self.records):
                if self.controller_timed_out():
                    return "controller_timeout"

                while len(active) < self.parallelism and not self.controller_timed_out():
                    record = self.scheduler.next_challenge(self.records)
                    if record is None:
                        break
                    active[executor.submit(self.run_challenge_visit_safely, record, dry_run)] = record

                if not active:
                    return "no_schedulable_challenge"

                timeout = max(0.1, min(1.0, float(self.remaining_controller_seconds() or 1)))
                done, _ = wait(active.keys(), timeout=timeout, return_when=FIRST_COMPLETED)
                for future in done:
                    record = active.pop(future)
                    try:
                        state, result, pause_reason = future.result()
                    except Exception as exc:
                        state, result, pause_reason = self.handle_challenge_exception(record, exc)
                    self.scheduler.update(record, state, result, pause_reason)
            return "all_solved"
        finally:
            executor.shutdown(wait=True, cancel_futures=True)

    def build_records(self, sources: list[ChallengeSource]) -> list[ChallengeRecord]:
        records: list[ChallengeRecord] = []
        used_ids: dict[str, int] = {}
        for source in sources:
            challenge_id = ChallengeLoader.detect_challenge_id(source.source, use_env=not self.multi_challenge)
            challenge_id = self.unique_challenge_id(challenge_id, used_ids)
            workspace = self.workspace_for_challenge(challenge_id)
            challenge_output = self.output_dir / challenge_id if self.multi_challenge else self.output_dir
            records.append(
                ChallengeRecord(
                    source=source.source,
                    challenge_id=challenge_id,
                    workspace=workspace,
                    output_dir=challenge_output,
                    order=source.order,
                )
            )
        return records

    def unique_challenge_id(self, challenge_id: str, used_ids: dict[str, int]) -> str:
        base = safe_path_segment(challenge_id)
        count = used_ids.get(base, 0)
        used_ids[base] = count + 1
        if count == 0:
            return base
        return f"{base}_{count + 1}"

    def workspace_for_challenge(self, challenge_id: str) -> Path:
        if not self.multi_challenge:
            return workspace_root(challenge_id)
        explicit = self.initial_workdir
        base = Path(explicit).resolve() if explicit else workspace_base_root()
        return base / safe_path_segment(challenge_id)

    def run_challenge_visit_safely(self, record: ChallengeRecord, dry_run: bool) -> tuple[dict, dict, str | None]:
        try:
            return self.run_challenge_visit(record, dry_run)
        except Exception as exc:
            return self.handle_challenge_exception(record, exc)

    def run_challenge_visit(self, record: ChallengeRecord, dry_run: bool) -> tuple[dict, dict, str | None]:
        ensure_workspace_dirs(record.workspace)
        self.sync_agent_context(record.workspace)

        state_store = StateStore(record.workspace)
        round_manager = RoundManager(self.agent_root, record.workspace)
        result_collector = ResultCollector(record.workspace, record.output_dir)
        progress = ProgressExporter(record.workspace)
        status_writer = StatusWriter(record.workspace)

        challenge_loader = ChallengeLoader(record.source, record.workspace, record.challenge_id)
        challenge_loader.sync_challenge()
        challenge_context = challenge_loader.load_context()
        category = classify_challenge(challenge_context, record.workspace / "challenge")
        initial_state = {
            "challenge_id": challenge_context.get("challenge_id", record.challenge_id),
            "category": category,
            "allowed_scope": challenge_context.get("allowed_scope", {}),
        }
        state = state_store.load_or_create(initial_state)
        if state.get("category") == "unknown" and category != "unknown":
            state["category"] = category
            state_store.save(state)

        self.init_text_artifacts(record.workspace)
        state = self.mark_scheduler_state(state_store, state, "active", None)
        status_writer.write(state, "challenge_loaded", "challenge loaded")
        progress.emit(
            level="info",
            event="challenge_loaded",
            message="challenge loaded",
            round_id=safe_int(state.get("round", 0), 0, minimum=0),
            phase=state.get("phase", "init"),
            category=state.get("category", "unknown"),
            extra={"challenge_id": record.challenge_id},
        )

        visit_start_round = safe_int(state.get("round", 0), 0, minimum=0)
        pause_reason: str | None = None
        while not self.challenge_terminal(state, visit_start_round):
            if self.visit_rounds_used(state, visit_start_round) >= self.scheduler.max_rounds_per_visit:
                pause_reason = "visit_round_budget_reached"
                break
            if self.controller_timed_out():
                pause_reason = "controller_timeout"
                break

            round_id = safe_int(state.get("round", 0), 0, minimum=0) + 1
            limits = self.runtime_limits(state)
            round_result = round_manager.run_round(round_id, state, challenge_context, limits, dry_run)
            state = state_store.load_or_create(initial_state)
            state = state_store.apply_round_result(state, round_result)
            status_writer.write(state, "round_end", round_result.get("loop", {}).get("conclusion", "round ended"))

        pause_reason = pause_reason or self.pause_reason_for_state(state, visit_start_round)
        scheduler_status = "solved" if state.get("solved") and state.get("confirmed_flag") else "paused"
        if pause_reason == "max_rounds_reached":
            scheduler_status = "exhausted"
        state = self.mark_scheduler_state(state_store, state, scheduler_status, pause_reason)

        result = result_collector.write_result(state)
        if state.get("solved") and result.get("status") != "solved":
            pause_reason = "result_validation_failed"
            scheduler_status = "paused"
            state = self.reopen_invalid_solution(state_store, state, result)
            state = self.mark_scheduler_state(state_store, state, scheduler_status, pause_reason)
            result = result_collector.write_result(state)
        status_writer.write(state, "result_written", f"result written with status {result.get('status')}")
        progress.emit(
            level="success" if result.get("status") == "solved" else "warn",
            event=result.get("status", "result"),
            message="result written to result.json",
            round_id=safe_int(state.get("round", 0), 0, minimum=0),
            phase=state.get("phase", "unknown"),
            category=state.get("category", "unknown"),
            extra={"challenge_id": record.challenge_id, "scheduler_status": scheduler_status},
        )
        return state, result, pause_reason

    def handle_challenge_exception(self, record: ChallengeRecord, exc: Exception) -> tuple[dict, dict, str]:
        warnings: list[str] = []
        try:
            ensure_workspace_dirs(record.workspace)
        except OSError as ensure_exc:
            warnings.append(f"workspace_init_failed:{ensure_exc}")

        state = {
            "challenge_id": record.challenge_id,
            "category": "unknown",
            "phase": "failed",
            "round": record.last_round,
            "solved": False,
            "confirmed_flag": None,
            "failures": [],
            "runtime_limits": {"max_rounds": 12, "max_seconds": self.max_controller_seconds(), "max_command_seconds": 7200},
            "scheduler": {"status": "failed", "pause_reason": "runtime_exception", "updated_at": utc_now()},
        }
        if not warnings:
            try:
                state_store = StateStore(record.workspace)
                state = state_store.load_or_create({"challenge_id": record.challenge_id})
                next_state = dict(state)
                next_state["phase"] = "failed"
                next_state["solved"] = False
                next_state["confirmed_flag"] = None
                next_state.setdefault("failures", []).append(runtime_exception_failure(exc, state.get("round", 0)))
                next_state = self.mark_scheduler_state(state_store, next_state, "failed", "runtime_exception")
                state = next_state
            except Exception as state_exc:
                warnings.append(f"state_failure_record_failed:{type(state_exc).__name__}:{state_exc}")
                state.setdefault("failures", []).append(runtime_exception_failure(exc, state.get("round", 0)))
        else:
            state.setdefault("failures", []).append(runtime_exception_failure(exc, state.get("round", 0)))

        result = self.runtime_failure_result(record, state, exc, warnings)
        write_warnings = self.write_challenge_result_best_effort(record, result)
        if write_warnings:
            result.setdefault("write_warnings", []).extend(write_warnings)
            self.write_challenge_result_best_effort(record, result)
        self.record_runtime_warning(record.workspace, f"runtime_exception:{type(exc).__name__}: {exc}")
        return state, result, "runtime_exception"

    def challenge_terminal(self, state: dict, visit_start_round: int) -> bool:
        limits = state.get("runtime_limits", {})
        if state.get("solved") and state.get("confirmed_flag"):
            return True
        if safe_int(state.get("round", 0), 0, minimum=0) >= safe_int(limits.get("max_rounds", 12), 12, minimum=1):
            return True
        if self.controller_timed_out():
            return True
        if self.visit_rounds_used(state, visit_start_round) > 0 and state.get("phase") in {"failed", "blocked"}:
            return True
        return False

    def visit_rounds_used(self, state: dict, visit_start_round: int) -> int:
        return max(0, safe_int(state.get("round", 0), 0, minimum=0) - visit_start_round)

    def pause_reason_for_state(self, state: dict, visit_start_round: int) -> str | None:
        limits = state.get("runtime_limits", {})
        if state.get("solved") and state.get("confirmed_flag"):
            return None
        if safe_int(state.get("round", 0), 0, minimum=0) >= safe_int(limits.get("max_rounds", 12), 12, minimum=1):
            return "max_rounds_reached"
        if self.controller_timed_out():
            return "controller_timeout"
        if self.visit_rounds_used(state, visit_start_round) > 0 and state.get("phase") in {"failed", "blocked"}:
            return f"model_reported_{state.get('phase')}"
        if self.visit_rounds_used(state, visit_start_round) >= self.scheduler.max_rounds_per_visit:
            return "visit_round_budget_reached"
        return "waiting_for_next_visit"

    def runtime_limits(self, state: dict) -> dict:
        limits = state.get("runtime_limits", {})
        max_seconds = safe_int(limits.get("max_seconds", 7200), 7200, minimum=1)
        max_command_seconds = safe_int(limits.get("max_command_seconds", 7200), 7200, minimum=1)
        remaining = self.remaining_controller_seconds()
        if remaining > 0:
            max_command_seconds = min(max_command_seconds, remaining)
        return {
            "max_rounds": safe_int(limits.get("max_rounds", 12), 12, minimum=1),
            "max_seconds": max_seconds,
            "max_command_seconds": max(1, max_command_seconds),
        }

    def max_rounds_per_visit(self) -> int:
        return safe_int(os.environ.get("AIXCTF_MAX_ROUNDS_PER_VISIT"), 3, minimum=1)

    def max_controller_seconds(self) -> int:
        return safe_int(os.environ.get("AIXCTF_MAX_SECONDS"), 7200, minimum=1)

    def max_parallel_challenges(self) -> int:
        default = 2 if self.multi_challenge else 1
        raw = os.environ.get("AIXCTF_MAX_PARALLEL_CHALLENGES") or os.environ.get("AIXCTF_PARALLELISM")
        value = safe_int(raw, default, minimum=1)
        return min(value, max(1, len(self.records)))

    def controller_timed_out(self) -> bool:
        return self.elapsed_seconds() >= self.max_controller_seconds()

    def remaining_controller_seconds(self) -> int:
        return max(0, self.max_controller_seconds() - self.elapsed_seconds())

    def elapsed_seconds(self) -> int:
        return int(time.monotonic() - self.started_at)

    def mark_scheduler_state(self, state_store: StateStore, state: dict, status: str, pause_reason: str | None) -> dict:
        next_state = dict(state)
        scheduler_state = dict(next_state.get("scheduler") or {})
        scheduler_state.update(
            {
                "status": status,
                "pause_reason": pause_reason,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        next_state["scheduler"] = scheduler_state
        state_store.save(next_state)
        return next_state

    def reopen_invalid_solution(self, state_store: StateStore, state: dict, result: dict[str, Any]) -> dict:
        next_state = dict(state)
        claimed_flag = next_state.get("confirmed_flag")
        if claimed_flag and claimed_flag not in next_state.setdefault("candidate_flags", []):
            next_state["candidate_flags"].append(claimed_flag)
        next_state["solved"] = False
        next_state["confirmed_flag"] = None
        next_state["phase"] = "verify"
        next_state.setdefault("failures", []).append(
            {
                "round": next_state.get("round"),
                "phase": "verify",
                "reason": result.get("failure_reason") or "result_validation_failed",
                "observation": "Claimed solved state failed final result validation.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        state_store.save(next_state)
        return next_state

    def sync_agent_context(self, workspace: Path) -> None:
        for name in ["AGENTS.md", "CLAUDE.md"]:
            src = self.agent_root / name
            if src.exists():
                try:
                    shutil.copy2(src, workspace / name)
                except OSError as exc:
                    self.record_runtime_warning(workspace, f"could not copy {src.name}: {exc}")
        settings_src = self.agent_root / "settings.json"
        if settings_src.exists():
            try:
                settings_dir = workspace / ".claude"
                settings_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(settings_src, settings_dir / "settings.json")
            except OSError as exc:
                self.record_runtime_warning(workspace, f"could not copy settings.json: {exc}")

    def init_text_artifacts(self, workspace: Path) -> None:
        notes = workspace / "notes.md"
        try:
            if not notes.exists():
                notes.write_text("# Challenge Notes\n\n", encoding="utf-8")
        except OSError as exc:
            self.record_runtime_warning(workspace, f"could not initialize notes.md: {exc}")
        handoff = workspace / "handoff.md"
        try:
            if not handoff.exists():
                handoff.write_text("# Challenge Handoff\n\nNo rounds have run yet.\n", encoding="utf-8")
        except OSError as exc:
            self.record_runtime_warning(workspace, f"could not initialize handoff.md: {exc}")

    def runtime_failure_result(self, record: ChallengeRecord, state: dict, exc: Exception, warnings: list[str]) -> dict:
        result = {
            "status": "failed",
            "runtime_error": True,
            "challenge_id": state.get("challenge_id", record.challenge_id),
            "category": state.get("category", "unknown"),
            "phase": state.get("phase", "failed"),
            "scheduler": state.get("scheduler", {"status": "failed", "pause_reason": "runtime_exception"}),
            "flag": None,
            "confidence": 0.0,
            "evidence": [],
            "artifacts": [],
            "rounds": state.get("round", 0),
            "failure_reason": f"runtime_exception:{type(exc).__name__}",
            "exception": {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(limit=8),
            },
        }
        if warnings:
            result["warnings"] = warnings
        return result

    def write_challenge_result_best_effort(self, record: ChallengeRecord, result: dict) -> list[str]:
        warnings = []
        for path in [record.workspace / "result.json", record.output_dir / "result.json"]:
            try:
                atomic_write_json(path, result)
            except Exception as exc:
                warnings.append(f"could not write result to {path}: {exc}")
        return warnings

    def record_runtime_warning(self, workspace: Path, message: str) -> None:
        try:
            path = workspace / "logs" / "runtime_warnings.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(f"{utc_now()} {message}\n")
        except OSError:
            pass

    def write_controller_result(self, termination_reason: str) -> dict:
        solved_count = sum(1 for record in self.records if record.status == "solved")
        all_solved = bool(self.records) and solved_count == len(self.records)
        result = {
            "status": "solved" if all_solved else "failed",
            "controller_status": "all_solved" if all_solved else "incomplete",
            "termination_reason": termination_reason,
            "total_challenges": len(self.records),
            "solved_challenges": solved_count,
            "elapsed_seconds": self.elapsed_seconds(),
            "parallelism": self.parallelism,
            "challenges": [record.summary() for record in self.records],
        }
        controller_workspace = self.controller_workspace()
        warnings = []
        for path in [controller_workspace / "controller_result.json", self.output_dir / "result.json"]:
            try:
                atomic_write_json(path, result)
            except Exception as exc:
                warnings.append(f"could not write controller result to {path}: {exc}")
        if warnings:
            result["write_warnings"] = warnings
            try:
                atomic_write_json(controller_workspace / "controller_result.json", result)
            except Exception:
                pass
        return result

    def controller_workspace(self) -> Path:
        explicit = self.initial_workdir if self.multi_challenge else None
        if explicit:
            return Path(explicit).resolve()
        return workspace_base_root()


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def runtime_exception_failure(exc: Exception, round_id: Any) -> dict[str, Any]:
    return {
        "round": round_id,
        "phase": "runtime",
        "reason": f"runtime_exception:{type(exc).__name__}",
        "observation": str(exc),
        "timestamp": utc_now(),
    }


def safe_int(value: Any, default: int, minimum: int | None = None) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        return max(minimum, parsed)
    return parsed


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_truthy(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}
