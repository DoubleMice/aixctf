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
