# Repository Guidelines

## Project Structure & Module Organization

This repository implements the AIxCTF ClaudeCode agent runtime described in `arch.md`. Runtime code lives under `.claude/`.

- `.claude/entrypoint.py`: container and local runtime entrypoint.
- `.claude/runner/`: AutoResearch loop, Claude runner, state/event/result stores, progress/status, subtask handoff, and knowledge routing.
- `.claude/hooks/`: Claude Code hook adapters and deterministic guards.
- `.claude/sync/`: fail-open human progress sync queue, policy, and mntn adapter.
- `.claude/templates/`: category-level solve prompts and native Task subagent contracts.
- `.claude/docs/`: tactical skill, tool, debug, and handoff cards indexed by `docs/knowledge_index.yaml`.
- `.claude/tools/`: helper scripts such as `pwn_triage.py` and `web_triage.py`.

Runtime outputs are intentionally ignored: `.claude/workspace/`, `.claude/output/`, and local challenge/output folders.

## Build, Test, and Development Commands

- `python3 -m compileall .claude`: syntax-check all Python modules.
- `AIXCTF_DRY_RUN=1 AIXCTF_MAX_ROUNDS=2 python3 .claude/entrypoint.py`: run the dry-run AutoResearch loop using default `/workspace` paths.
- `WORKDIR=/tmp/aixctf-ws OUTPUT_DIR=/tmp/aixctf-out CHALLENGE_DIR=. AIXCTF_DRY_RUN=1 python3 .claude/entrypoint.py`: run locally without polluting the repo.
- `docker build -t aixctf-agent .claude`: build the runtime image from the `.claude` Docker context.

## Coding Style & Naming Conventions

Use Python 3 with 4-space indentation, type hints for public helpers, and small modules with explicit responsibilities. Prefer `snake_case` for functions, files, and JSON keys. Keep hook logic deterministic: allow, deny, log, parse, emit sync events, update state, and validate evidence only.

## Testing Guidelines

There is no formal test suite yet. For runtime changes, run `compileall` plus a dry-run and verify `state.json`, `rounds/`, `progress.jsonl`, `status.json`, and `sync/events.jsonl`. For hook changes, test stdin JSON manually against `.claude/hooks/hook_entrypoint.py pre_tool|post_tool|stop`. Do not commit generated workspace, evidence, logs, or caches.

## Commit & Pull Request Guidelines

Existing history uses concise summary commits, for example `Initial AIxCTF runtime`. Use short imperative titles such as `Add hook evidence checks`. PRs should describe changed runtime behavior, validation commands, and any security or scope-control impact.

## Security & Configuration Tips

Never weaken challenge scope checks without documenting why. Keep flags evidence-based: solved results require an exact flag, an evidence artifact, and reproducible provenance. Store secrets such as `ANTHROPIC_API_KEY` in the environment, not in committed files.
