# Architecture Overview

AIxCTF requires submitting a Docker image whose agent can solve CTF challenges autonomously. This project implements the runtime inside that image. It is not a CTF platform; it is a challenge-solving runtime centered on ClaudeCode.

## One-Sentence Definition

ClaudeCode-centered, hook-guarded, controller-loop-and-round-loop-based,
parallel-challenge-capable, stateful, template-guided, skill-assisted,
tool-aware, native-Task-subagent-capable, human-sync-enabled AIxCTF
AutoResearch / AutoExploit runtime.

## System Boundary

The runtime owns:

- challenge discovery and per-challenge workspace initialization from `/challenge`
- challenge context loading and category classification
- outer RuntimeController scheduling and per-challenge round lifecycle
- concurrent per-challenge ClaudeCode child processes when multi-challenge mode is active
- per-child-process `WORKDIR`, `CHALLENGE_ID`, and `AIXCTF_ROUND_ID` setup
- hook-based tool checkpointing
- state, event, progress, handoff, and result materialization
- optional bounded subtask execution
- fail-open human progress synchronization

The runtime does not own:

- the competition platform
- external dashboards
- GUI reverse engineering workflows
- unbounded multi-agent orchestration
- attacking targets outside the provided challenge scope

## Primary Flow

```text
Challenge Input
  -> Runtime Controller
  -> Challenge Scheduler
  -> Parallel Per-Challenge Visits
  -> ClaudeCode Child Process per Active Challenge
  -> Hook Checkpoints
  -> Evidence and Reflection
  -> State Update
  -> Result Collector
```

See [system architecture diagram](diagrams/system-architecture.png).

## Core Design Rule

Every round must externalize durable state. The system must not depend on ClaudeCode's natural-language context as the only memory. Durable files include `state.json`, `rounds/*.json`, `events/*.json`, `progress.jsonl`, `status.json`, `notes.md`, `handoff.md`, `evidence/`, and `result.json`.

In multi-challenge mode, durable state is isolated per challenge under
`workspace/<challenge_id>/`. The controller may run multiple active visits at
the same time, but it only schedules and transitions challenge records from
persisted status and model-produced outputs.
