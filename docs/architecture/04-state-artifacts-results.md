# State, Artifacts, and Results

Runtime state is externalized to the workspace so every round can resume from durable facts instead of model memory.
In multi-challenge mode, each challenge owns a separate workspace and therefore
an independent state ledger.

## Workspace Layout

```text
$WORKDIR/
  challenge/
  rounds/
  events/
  subtasks/
  scripts/
  logs/
  evidence/
  sync/
  state.json
  status.json
  progress.jsonl
  notes.md
  handoff.md
  result.json
```

## state.json

`state.json` tracks:

- challenge identity and category
- phase and round number
- confirmed and candidate flags
- allowed scope
- artifacts
- `research_loop`: current question, hypothesis, facts, open questions, next experiment
- failures and `do_not_repeat`
- `scheduler`: pending/active/paused/solved/exhausted status and pause reason
- runtime limit status
- sync status
- `handoff_protocol_version`, currently `aixctf.challenge-handoff/v1`

`state.json` is the machine-readable state used by the controller. It does not
replace `handoff.md`: JSON carries deterministic control and evidence indexes,
while the handoff carries the model's semantic understanding and next execution
intent.

## handoff.md

`handoff.md` is read at the start of every fresh Execution and maintained by the
model. In real mode the runtime does not rewrite its research content. It should
remain a compact execution state rather than a transcript: current understanding,
important relationships, evidence references, failed paths, and what the next
Execution should do.

Normal Stop requires the file to have been modified after the current Execution
started. This uses filesystem modification time only; there is no content hash or
cross-file transaction. If an Execution is interrupted, `state.json` remains the
machine state and the next model reconciles the handoff with newer artifacts.

## round_result.json

Each `rounds/round_XXX.json` contains:

- round metadata and phase transition
- `loop` research fields
- actions and artifacts
- candidate flags
- selected knowledge docs
- subtask summaries
- sync summary

## result.json

Solved results require:

- exact flag
- evidence artifact containing the flag
- reproducible script or command provenance
- handoff explaining flag source

Failed results require:

- `failure_reason`
- `notes.md`
- `handoff.md`
- at least one round result

`$WORKDIR/result.json` is always written for each challenge. In single-challenge
mode it is copied to `/output/result.json` when possible. In multi-challenge
mode each challenge result is copied to `/output/<challenge_id>/result.json`,
and `RuntimeController` writes `/output/result.json` as the controller summary.
In Docker, `$WORKDIR` defaults to `/aixctf-agent/workspace/<challenge_id>/`.

## Concurrent State Isolation

Parallel challenge visits never share a workspace. Hooks and ClaudeCode child
processes write to the `WORKDIR` injected for that child process. The
controller summary only reads per-challenge result records after a visit
finishes.

Within a single challenge, hooks may update `state.json` before the primary
ClaudeCode response returns. The round merge reloads that latest state first,
then applies the model-produced `round_result` so hook evidence is retained.

`progress.jsonl` records `execution_started` and `execution_completed`. An
unmatched start or a completion with `checkpoint_status: incomplete` causes the
next prompt to include recovery instructions; it does not create a separate
session-resume or recovery state machine.
