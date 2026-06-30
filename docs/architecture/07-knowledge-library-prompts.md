# Knowledge Library and Prompts

The knowledge library is a set of tactical cards, not long tutorials. Every document should support the next concrete action.

## Knowledge Layers

```text
templates/
  generic.md
  pwn.md
  web.md
  subagent.md

docs/
  knowledge_index.yaml
  pwn/
  web/
  tools/
  debug/
  handoff/
```

## Injection Limits

Each round should inject a small, relevant set:

- one template
- up to two skill docs
- up to two tool docs
- up to one debug doc
- optionally one handoff doc

## Selection Strategy

`runner/knowledge_router.py` scores docs by:

- category match
- phase match
- trigger match in state, failures, facts, and observations
- recent-doc penalty to avoid repeating stale context

## ClaudeCode Prompt Contract

Round prompts include:

- current `state.json`
- challenge context
- allowed scope
- current research loop
- runtime path and state status
- selected docs
- previous failures
- native Task delegation contract
- required structured JSON output

The required output must include research question, hypothesis, experiment, observations, evidence, conclusion, state delta, flags, failure reason, next experiment, and do-not-repeat items.
