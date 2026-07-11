# AutoResearch Loop

The runtime solves challenges through bounded, semantically coherent Executions.
An Execution is not "ask ClaudeCode for the flag" and need not stop after one
small experiment. The model may keep closely related tool calls, native Tasks,
debugging, and validation together, then externalize the state required by the
next fresh Execution.

## Controller Loop

The runtime is a large loop around smaller per-challenge loops:

```text
RuntimeController
  -> choose schedulable challenges by persisted status
  -> run up to AIXCTF_MAX_PARALLEL_CHALLENGES active visits
  -> each visit runs up to AIXCTF_MAX_ROUNDS_PER_VISIT rounds
  -> update per-challenge state/result when each visit returns
  -> solved: mark complete
  -> blocked, failed, or visit budget reached: pause and switch
  -> stop successfully only when every challenge is solved
```

`RuntimeController` does not solve challenges and does not inspect exploit
details to make tactical decisions. It schedules from model-produced
`state.json`, per-round status, failure count, phase, solved flag, and round
limits. Pending and lower-failure challenges are preferred; hard or repeated
unsolved challenges are paused so other challenges can make progress.

When more than one challenge is schedulable, the controller may launch several
ClaudeCode child processes in parallel. Each child process receives a dedicated
`WORKDIR` and writes only to that challenge's workspace. The controller does
not share ClaudeCode context across challenges.

## State Transition

```text
S_n + H_n + C + K_n
  -> AutoResearch / AutoExploit Execution
  -> Tool Events
  -> Hook Evaluation
  -> Subtask Handoff Collection
  -> Reflection
  -> Round Result
  -> Reload latest state.json
  -> S_{n+1}
```

- `S_n`: current `state.json`
- `H_n`: current model-maintained `handoff.md`
- `C`: challenge context, target, scope, and metadata
- `K_n`: selected template, skill, tool, debug, and handoff docs
- `Events`: tool, hook, sync, and subtask events

Hooks may update `state.json` while ClaudeCode is still running. At round end
the runtime reloads the latest state before applying `round_result`, so
candidate flags, evidence paths, failure signals, and subtask artifacts written
by hooks are not overwritten by the pre-round state snapshot.

## Disposable Execution

Each call uses a fresh `claude -p` process. Correctness does not depend on a
session ID or hidden conversation context surviving. An Execution becomes safe
to discard after it has updated `handoff.md`, returned its structured state
output, and the runtime has merged the result into durable state.

Normal Stop and automatic PreCompact hooks request this checkpoint. If a process
ends unexpectedly, the next fresh Execution receives an interruption notice and
reconciles the last JSON state and handoff with newer durable artifacts.

## Execution Output Contract

Each Execution must eventually answer these fields, but the model chooses the
semantic checkpoint and may run multiple related experiments before doing so:

- Research question: what question is this round answering?
- Hypothesis: what does the agent believe may be true?
- Experiment: what action validates or falsifies the hypothesis?
- Observation: what did tools or code show?
- Evidence: which artifacts support the observation?
- Conclusion: confirmed, falsified, inconclusive, or blocked?
- State delta: what changed in known facts, failures, or strategy?
- Next experiment: what should happen next?

## AutoExploit Refinement

Exploit work is an iterative loop:

```text
Exploit Hypothesis
  -> Payload Construction
  -> Local Test
  -> Failure Classification
  -> Payload Mutation
  -> Remote Test
  -> Evidence Verification
```

Pwn examples include offset discovery, ret2win alignment, ret2libc leak validation, and local-vs-remote debugging. Web examples include route discovery, SSTI probes, LFI path validation, auth/session analysis, and final scripted flag retrieval.

See [parallel challenge scheduling](diagrams/parallel-challenge-scheduling.png),
[round lifecycle sequence](diagrams/round-lifecycle.png), and [phase state
machine](diagrams/phase-state-machine.png).
