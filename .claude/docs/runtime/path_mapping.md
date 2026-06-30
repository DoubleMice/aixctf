# Runtime Path Mapping

Architecture diagram: [runtime-path-mapping.png](../../../docs/architecture/diagrams/runtime-path-mapping.png)

## Docker Path Model

The agent code is copied into the image at `/aixctf-agent`. Each challenge gets an isolated workspace under:

```text
/aixctf-agent/workspace/<challenge_id>/
```

`WORKDIR` is set in each ClaudeCode child process before it runs, and
ClaudeCode's current working directory is the same path. In multi-challenge
mode several ClaudeCode child processes may run at once, but each process gets
one isolated `WORKDIR`. Prefer `$WORKDIR` or relative paths such as
`challenge/`, `logs/`, `scripts/`, and `evidence/`.

## Challenge ID Resolution

The runtime chooses `<challenge_id>` in this order:

1. `CHALLENGE_ID` environment variable.
2. `metadata.json` field `challenge_id`.
3. `metadata.json` field `id`.
4. Challenge source file or directory name.
5. `unknown`.

The value is sanitized for use as a single path segment.

`AIXCTF_CHALLENGE_MODE=auto` is the default. Set it to `single` to force the
whole `CHALLENGE_DIR` to be one challenge, or `multi` to force child challenge
discovery.

`AIXCTF_MAX_PARALLEL_CHALLENGES` controls how many challenge visits can run at
the same time. The default is `2` for multi-challenge runs and `1` for
single-challenge runs. Each active visit owns one ClaudeCode process.

## Host to Docker Mapping

Default Docker Compose development mapping:

```text
Host path under .claude/          Docker path
sample_challenge/                /challenge:ro
workspace/                       /aixctf-agent/workspace
workspace/<challenge_id>/        /aixctf-agent/workspace/<challenge_id>
workspace/controller_result.json /aixctf-agent/workspace/controller_result.json
local_output/                    /output
local_output/<challenge_id>/     /output/<challenge_id>
```

The image's `/aixctf-agent` directory comes from the `.claude/` Docker build context. It is runtime-owned and should not be modified by challenge-solving agents.

## Workspace Layout

Inside `$WORKDIR`:

```text
challenge/          copied challenge input
rounds/             round JSON
events/             tool event logs
subtasks/           native Task subagent outputs
scripts/            solve scripts
logs/               command logs
evidence/           successful transcripts
sync/               human sync events and spool
state.json          current state
status.json         live status
progress.jsonl      progress stream
notes.md            working notes
handoff.md          takeover summary
result.json         final result
```

In multi-challenge mode, each challenge keeps this layout under its own
`workspace/<challenge_id>/`. The controller writes the aggregate summary to
`workspace/controller_result.json` and `/output/result.json`.

## Local Non-Docker Runs

For local tests, either set `WORKDIR` explicitly or let the runtime use `.claude/workspace/<challenge_id>/` from the host checkout.

```bash
CHALLENGE_ID=sample CHALLENGE_DIR=. OUTPUT_DIR=/tmp/aixctf-out \
  AIXCTF_DRY_RUN=1 AIXCTF_MAX_ROUNDS=2 AIXCTF_MAX_ROUNDS_PER_VISIT=1 \
  python3 .claude/entrypoint.py
```

`WORKDIR=/tmp/aixctf-ws` remains a supported explicit override when a one-off temporary workspace is preferred.
