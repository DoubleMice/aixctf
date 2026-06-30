# Tool: File Inspection

## When to Use

Use during classification and triage.

## Commands

```bash
find "$WORKDIR/challenge" -maxdepth 3 -type f -print
file "$WORKDIR"/challenge/* 2>/dev/null || true
strings "$WORKDIR"/challenge/* 2>/dev/null | head -200 || true
```

## Evidence Standard

Save concise listings or command logs under `$WORKDIR/logs/` when they affect category or strategy.
