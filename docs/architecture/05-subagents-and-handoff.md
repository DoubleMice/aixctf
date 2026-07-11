# Execution and Handoff Protocols

AIxCTF uses handoff as a protocol between disposable Executions, not merely as a
human summary. The protocol has two levels: challenge handoff between fresh
Claude Code processes and Task handoff from a bounded native Task to its primary
agent.

## Challenge Handoff Protocol

Protocol identifier: `aixctf.challenge-handoff/v1`.

The next Execution starts from three durable inputs:

```text
state.json + handoff.md + referenced artifacts
```

- `state.json` is runtime-owned machine state.
- `handoff.md` is model-owned semantic state.
- logs, scripts, events, evidence, and Task results provide verifiable detail.

The model has freedom to organize `handoff.md`; the runtime does not parse fixed
headings or generate tactical conclusions. The handoff should preserve what a
fresh model needs to continue a strongly related task without reading the full
history.

### Normal Checkpoint

```text
Fresh Execution reads state + handoff
  -> runs related experiments and native Tasks
  -> updates handoff.md
  -> returns structured state output
  -> Runtime merges state and records execution_completed
```

The Stop hook compares the handoff modification time with the Execution start
time. If it was not updated, the hook blocks Stop once and asks the model to
externalize its state. A second failed attempt is allowed to exit to avoid an
infinite hook loop and is recorded as an incomplete checkpoint.

### Interruption Recovery

An `execution_started` event without a matching `execution_completed`, or an
incomplete checkpoint, adds a recovery notice to the next prompt. Recovery always
uses a fresh Execution; it never depends on `--resume` or a surviving Claude Code
session.

The recovering model treats `state.json` as machine state, reads the existing
handoff as potentially stale, inspects newer durable artifacts, updates the
handoff, and then continues. AIxCTF does not use a handoff hash, checkpoint
directory, or cross-file transaction.

## Task Handoff Protocol

Protocol identifier: `aixctf.task-handoff/v1`.

Native `Task` calls are for local, context-heavy work. The primary agent decides
when to delegate; the runtime records and normalizes the Task exchange as:

```text
$WORKDIR/subtasks/task_XXX/
  input.json
  output.md
  result.json
  handoff.md
```

`result.json` includes the protocol identifier and classifies the outcome as
`confirmed`, `falsified`, `inconclusive`, or `blocked`. It may contain evidence,
facts, falsified hypotheses, a recommendation, and do-not-repeat items. The
primary model decides what belongs in the challenge-level handoff.

Use a Task when a question is bounded, produces a verifiable local result, or
would otherwise consume substantial primary context. Do not delegate vague whole-
challenge goals or work requiring continuous global strategy.

See [subagent handoff](diagrams/subagent-handoff.png) and [Execution checkpoint
and recovery](diagrams/execution-checkpoint-recovery.png).

## Design Reference

The file-persisted, fresh-execution framing is informed by the
[Deli AutoResearch protocol](https://victorchen96.github.io/auto_research/framework.html).
AIxCTF adopts the protocol framing, not its heartbeat/watchdog or zero-interaction
system.
