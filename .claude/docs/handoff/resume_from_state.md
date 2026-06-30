# Handoff: Resume From State

## When to Use

Use when another agent resumes the challenge.

## Quick Checks

```bash
cat "$WORKDIR/state.json"
tail -100 "$WORKDIR/notes.md"
cat "$WORKDIR/handoff.md"
```

## Next Action

Trust artifacts over prose, then run the smallest command that validates the next hypothesis.
