# Handoff: Resume From State

## When to Use

Use when a fresh Execution resumes the challenge from durable state. Do not
depend on a previous Claude Code session ID.

## Quick Checks

```bash
cat "$WORKDIR/state.json"
tail -100 "$WORKDIR/notes.md"
cat "$WORKDIR/handoff.md"
```

## Next Action

Treat `state.json` as machine state and `handoff.md` as model-maintained semantic
state. Trust artifacts over unsupported prose. If newer artifacts exist after an
interruption, reconcile and update handoff before continuing tactical work.
