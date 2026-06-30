# Build, MVP Plan, and Acceptance

## Build Targets

The runtime is built from `.claude/Dockerfile`.

```bash
docker build -t aixctf-agent .claude
```

Local dry-run validation:

```bash
AIXCTF_DRY_RUN=1 AIXCTF_MAX_ROUNDS=2 AIXCTF_MAX_ROUNDS_PER_VISIT=1 \
  python3 .claude/entrypoint.py
```

Use temporary paths during local testing when a one-off workspace is preferred:

```bash
WORKDIR=/tmp/aixctf-ws OUTPUT_DIR=/tmp/aixctf-out CHALLENGE_DIR=. \
  AIXCTF_DRY_RUN=1 AIXCTF_MAX_ROUNDS=2 AIXCTF_MAX_ROUNDS_PER_VISIT=1 \
  python3 .claude/entrypoint.py
```

Without `WORKDIR`, local runs use `.claude/workspace/<challenge_id>/`; Docker runs use `/aixctf-agent/workspace/<challenge_id>/`.

Default runtime limits:

- `AIXCTF_MAX_ROUNDS=12`
- `AIXCTF_MAX_ROUNDS_PER_VISIT=3`
- `AIXCTF_MAX_SECONDS=7200`
- `AIXCTF_MAX_CMD_SECONDS=7200`
- `AIXCTF_MAX_PARALLEL_CHALLENGES=2` in multi-challenge mode

## MVP Phases

1. Repository skeleton and Docker entrypoint.
2. State, round runtime, dry-run, and result collection.
3. AutoResearch loop metadata and reflection.
4. ClaudeCode runner and round prompt.
5. Hook layer and evidence guard.
6. Progress export.
7. Human Sync Agent.
8. Subtask proposal and handoff collection.
9. Knowledge router and tactical docs.
10. Pwn/Web triage helpers.
11. Result quality hardening.

## Acceptance Criteria

System:

- Docker image builds.
- Workspace initializes.
- RuntimeController outer loop and per-challenge round loop run.
- Multi-challenge mode can run more than one active challenge visit when
  `AIXCTF_MAX_PARALLEL_CHALLENGES` is greater than 1.
- `state.json`, `rounds/*.json`, `events/*.json`, `progress.jsonl`, and `status.json` are generated.
- `result.json` is written.

Agent:

- Reads challenge context.
- Classifies pwn/web/unknown.
- Selects limited docs.
- Writes scripts and evidence.
- Iterates from failure signals.

Hook:

- Records tool calls.
- Blocks dangerous commands.
- Extracts candidate flags.
- Emits sync events.
- Validates solved evidence.

Quality:

- Solved requires flag plus evidence.
- Failed requires handoff and failure reason.
