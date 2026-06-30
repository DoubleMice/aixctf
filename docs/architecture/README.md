# Architecture Documentation

This directory contains the split version of the AIxCTF ClaudeCode AutoResearch / AutoExploit runtime handoff.

## Reading Order

1. [Overview](01-overview.md) explains the system goal and high-level architecture.
2. [AutoResearch Loop](02-autoresearch-loop.md) defines the outer controller loop, parallel challenge visits, and per-challenge round model.
3. [Runtime Components](03-runtime-components.md) maps each component to implementation responsibilities.
4. [State, Artifacts, and Results](04-state-artifacts-results.md) defines durable runtime outputs.
5. [Subagents and Handoff](05-subagents-and-handoff.md) explains bounded subtask execution.
6. [Hooks, Progress, and Human Sync](06-hooks-progress-sync.md) explains checkpointing and human-visible progress.
7. [Knowledge Library and Prompts](07-knowledge-library-prompts.md) explains prompt and document injection.
8. [Build, MVP Plan, and Acceptance](08-build-mvp-acceptance.md) captures delivery phases and validation.

## Diagrams

PlantUML sources and rendered PNGs live in [diagrams](diagrams/README.md).

## Full Handoff

[full-handoff-v1.md](full-handoff-v1.md) is the current monolithic handoff, updated to match the split documents and implementation.
