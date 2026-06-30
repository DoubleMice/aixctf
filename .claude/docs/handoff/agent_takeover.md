# Handoff: Agent Takeover

## When to Use

Use at the start of every round after reading `state.json`.

## Quick Checks

```bash
cat "$WORKDIR/state.json"
cat "$WORKDIR/handoff.md"
ls -R "$WORKDIR/logs" "$WORKDIR/evidence" "$WORKDIR/scripts" 2>/dev/null
```

## Next Action

Continue from `Best Next Step`; do not repeat failed paths.
