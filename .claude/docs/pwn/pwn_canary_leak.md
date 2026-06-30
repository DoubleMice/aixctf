# Pwn: Canary Leak

## When to Use

`checksec` shows canary and overflow is still reachable.

## Quick Checks

```bash
checksec ./chall
strings ./chall | grep -Ei 'printf|puts|read|gets|scanf'
```

## Next Action

Find an info leak before overwrite. Typical sources are format strings, over-read, debug endpoints, or echoed stack bytes.

## Evidence Standard

Record the leak source, leaked canary value, and final exploit transcript.
