# Runtime Components

The implementation is organized under `.claude/`.

## Runtime Controller

`runner/runtime_controller.py`

Outer loop over all discovered challenges. It initializes per-challenge
workspaces, runs bounded visits through `RoundManager`, pauses hard unsolved
challenges, and writes the final controller summary. In multi-challenge mode it
can run several visits at once, controlled by
`AIXCTF_MAX_PARALLEL_CHALLENGES`. It schedules only from persisted state and
model output status.

## Challenge Scheduler

`runner/challenge_scheduler.py`

Discovers single or multiple challenge directories and ranks runnable challenges
by scheduler status, failure count, visits, and rounds. It marks challenges as
`pending`, `active`, `paused`, `solved`, or `exhausted`; it does not inspect
challenge internals or choose exploit tactics. Active challenges are excluded
from new selections so the same challenge is not scheduled twice while a
ClaudeCode child process is still running.

## Loop Core

`runner/loop_core.py`

Coordinates the round-level AutoResearch flow:

- active strategy selection
- native Task subagent result merge

## Round Manager

`runner/round_manager.py`

Builds the round prompt, injects state, handoff, and selected knowledge, calls
ClaudeCode, collects tool and native Task events, writes
`rounds/round_XXX.json`, updates notes, and flushes human sync. In real mode the
model owns handoff research content; the runtime renderer is only a dry-run or
missing-file fallback.
Before merging the round result, it reloads the latest `state.json` so hook
updates produced during the ClaudeCode run are preserved.

## Claude Runner

`runner/claude_runner.py`

Runs ClaudeCode in real mode or dry-run mode. It stores stdout/stderr under `logs/` and lets dry-run validate the runtime without external model calls.
Each active challenge visit owns one ClaudeCode child process with isolated
`WORKDIR`, `CHALLENGE_DIR`, and `AIXCTF_ROUND_ID` environment values.
Each call also receives an `AIXCTF_EXECUTION_ID` and nanosecond start time so
hooks can gate a normal Stop without hashing handoff content.

## State, Event, and Result Stores

- `runner/state_store.py`: validates and atomically persists `state.json`
- `runner/event_store.py`: append-only tool event storage
- `runner/result_collector.py`: writes `$WORKDIR/result.json`; in multi-challenge mode each challenge copies to `/output/<challenge_id>/result.json`, while the controller writes `/output/result.json`

## Strategy and Reflection

- `runner/strategy_selector.py`: chooses the next active strategy
- `runner/reflection_engine.py`: builds the round `loop` summary
- `runner/hypothesis_manager.py`: records hypotheses and falsification

## Progress and Sync

- `runner/progress_exporter.py`: writes `[AIXCTF]` stdout lines and `progress.jsonl`
- `runner/status_writer.py`: writes current `status.json`
- `sync/*`: fail-open human sync queue and adapter

See [system architecture diagram](diagrams/system-architecture.png).
See also [parallel challenge scheduling](diagrams/parallel-challenge-scheduling.png).
