# Pwn: Stack Buffer Overflow

## When to Use

Crash occurs after long input or source shows unbounded read into stack buffer.

## Quick Checks

```bash
checksec ./chall
python3 - <<'PY'
from pwn import *
print(cyclic(512))
PY
```

## Next Action

Use cyclic crash evidence to calculate offset, then decide ret2win, ret2libc, or ROP based on protections.

## Evidence Standard

Record crash, offset calculation, final payload run, and flag transcript.
