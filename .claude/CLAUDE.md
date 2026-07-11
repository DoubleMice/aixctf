# Project Context

This repository implements a Dockerized AIxCTF AutoResearch / AutoExploit runtime.

Important paths:
- `$WORKDIR`: current challenge workspace. In Docker this defaults to `/aixctf-agent/workspace/<challenge_id>/`.
- `$WORKDIR/challenge`: challenge input
- `$WORKDIR/state.json`: current state
- `$WORKDIR/rounds`: round results
- `$WORKDIR/events`: tool event logs
- `$WORKDIR/subtasks`: subagent task outputs
- `$WORKDIR/scripts`: exploit or solve scripts
- `$WORKDIR/logs`: command logs
- `$WORKDIR/evidence`: successful transcripts
- `$WORKDIR/sync`: human sync events and logs
- `$WORKDIR/handoff.md`: model-maintained semantic state for the next fresh Execution
- `$WORKDIR/result.json`: final output

ClaudeCode current working directory is the active challenge workspace root. The
RuntimeController may switch to another challenge after this round; use durable
files under the current `$WORKDIR` so the next visit can resume. Use relative
paths such as `challenge/`, `notes.md`, `logs/`, and `handoff.md` unless an
absolute path is required.

At the start of every Execution, read both `state.json` and `handoff.md`. If the
runtime reports an interrupted or incomplete prior Execution, reconcile the
handoff with newer events, logs, scripts, and evidence before continuing. Before
stopping normally, update `handoff.md`; a Stop hook may keep the Execution alive
once if no update was made. The runtime owns `state.json`, while the model owns
the research meaning recorded in `handoff.md`.

Modify only files under the workspace root unless the runtime explicitly asks for agent code changes.
Runtime-owned files are read-only for the agent: `state.json`, `result.json`,
`status.json`, `progress.jsonl`, `rounds/`, `events/`, `sync/`, and `.claude/`.
Return round JSON as the final response; do not write it into `rounds/`.

Use templates:
- `templates/pwn.md` for pwn challenges
- `templates/web.md` for web challenges
- `templates/subagent.md` as the contract for native `Task` subagents
- `templates/generic.md` when classification is unknown

Use docs:
- `docs/knowledge_index.yaml` to locate relevant template, skill, tool, debug, and handoff docs.
- `docs/tools/supported_tools.md` for the supported web/pwn tool list and explicit exclusions.
- `docs/runtime/path_mapping.md` for host-to-Docker path mapping and workspace layout.
