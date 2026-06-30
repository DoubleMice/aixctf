# Debug: Browser Flow

## When to Use

The target depends on JavaScript or complex form state.

## Quick Checks

```bash
grep -R "fetch\\|axios\\|XMLHttpRequest" -n "$WORKDIR/challenge" 2>/dev/null || true
```

## Next Action

Prefer source and HTTP reproduction. Use browser automation only when HTTP-only reproduction is insufficient.

## Evidence Standard

Save the reproduced HTTP requests, not only screenshots.
