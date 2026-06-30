# Subagents and Handoff

Subagents are ClaudeCode native `Task` calls for local, context-heavy work. The primary agent decides when to delegate; the runtime records, validates, and merges the resulting Task events. ClaudeCode may expose these hook payloads as `Agent`, so the implementation treats `Task` and `Agent` as the same native subagent surface.

## When to Use a Subagent

Use a subagent when:

- a task has a clear local goal
- the task requires many tool outputs
- current context pressure is high
- a strategy branch should be evaluated without polluting global state

Examples:

- pwn offset discovery
- gadget search
- libc/ld analysis
- web route discovery
- auth/session review
- HTTP failure debugging
- log summarization

## When Not to Use a Subagent

Do not create a subagent for:

- simple `ls`, `file`, `checksec`, or one-shot `curl`
- tasks that require global strategy continuity
- vague or unbounded goals
- "multi-agent" for its own sake

## Subtask Output Contract

The native Task returns JSON to the primary agent. The PostToolUse hook stores that exchange as:

```text
$WORKDIR/subtasks/task_XXX/
  input.json
  output.md
  result.json
  handoff.md
```

`result.json` must classify the outcome as `confirmed`, `falsified`, `inconclusive`, or `blocked`. Confirmed facts require evidence paths. StateStore may merge confirmed facts into `state.research_loop.known_facts`, falsified hypotheses into `falsified_hypotheses`, and recommendations into open questions.

See [subagent handoff diagram](diagrams/subagent-handoff.png).
