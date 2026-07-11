# Handoff: Agent Takeover

## When to Use

Use at the start of every fresh Execution after reading `state.json` and
`handoff.md`.

## Quick Checks

```bash
cat "$WORKDIR/state.json"
cat "$WORKDIR/handoff.md"
ls -R "$WORKDIR/logs" "$WORKDIR/evidence" "$WORKDIR/scripts" 2>/dev/null
```

## Next Action

If the runtime reports an interrupted or incomplete prior Execution, first
reconcile the handoff with newer events, logs, scripts, and evidence. Otherwise
continue from the handoff's next execution intent; do not repeat failed paths.
