# Hooks, Progress, and Human Sync

Hooks are deterministic checkpoints around ClaudeCode tool use. They enforce safety, record observations, emit sync events, and keep solving evidence-based.
Hooks run inside the ClaudeCode child process environment for one challenge
visit, so `$WORKDIR` points at that challenge's isolated workspace even when
multiple ClaudeCode instances are active.

## Hook Responsibilities

`PreToolUse`:

- parse tool and input
- block dangerous or out-of-scope commands
- record pending event
- emit `tool_started` or `tool_blocked`

`PostToolUse`:

- save stdout/stderr to `logs/`
- extract candidate flags
- detect failure signals
- persist native `Task` / `Agent` subagent exchanges under `subtasks/task_XXX/`
- update `state.json`
- emit `tool_finished`, `failure_signal_detected`, or `candidate_flag_found`

`Stop`:

- require `handoff.md` to be updated during the current Execution
- block once with checkpoint instructions when it is stale
- allow a second stop attempt and record `checkpoint_incomplete` to avoid loops
- run evidence guard checks
- emit `round_checkpoint` or `evidence_guard_failed`

`PreCompact` (`auto` only):

- block automatic context compaction
- ask the model to externalize handoff and structured state before ending
- emit `precompact_checkpoint_requested`

PreCompact is best-effort. If a context-limit error already prevents the model
from responding, the next fresh Execution recovers from existing durable files.

## Progress Export

The Docker image cannot assume external dashboards. Progress therefore uses:

- stdout lines prefixed with `[AIXCTF]`
- `$WORKDIR/progress.jsonl`
- `$WORKDIR/status.json`
- `$WORKDIR/handoff.md`

`progress.jsonl` also carries `execution_started` and `execution_completed`
records keyed by `execution_id`. Hook stdout must remain valid hook JSON, so
hook-originated progress records are written without console output.

Stdout must stay concise. Large outputs go to `logs/`.

## Human Sync Agent

Human Sync is a fail-open side path:

```text
Hook / Round / Subtask Events
  -> sync/events.jsonl
  -> Human Sync Agent
  -> mntn_skill Adapter
  -> Human Endpoint
```

Endpoint failure must not fail solving. Failed submissions are written to `sync/spool.jsonl`, and all attempts are logged in `sync/sync_log.jsonl`.

See [human sync flow](diagrams/human-sync-flow.png).

## Round Merge Semantics

Hook updates are mid-round durable checkpoints, not just logs. `PostToolUse`
can add candidate flags, evidence records, failure signals, and subtask
artifacts before ClaudeCode returns its final JSON. `RoundManager` reloads the
latest state after ClaudeCode exits and before applying the round result, so
those hook updates survive the round transition.
