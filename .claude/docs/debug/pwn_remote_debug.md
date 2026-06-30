# Debug: Pwn Remote

## When to Use

Local exploit works but remote fails.

## Quick Checks

```bash
nc -vz "$HOST" "$PORT"
```

## Fix Strategy

Check architecture, libc, line buffering, prompt sync, and one-shot versus persistent connection behavior.

## Evidence Standard

Save remote connection transcript and final remote flag output.
