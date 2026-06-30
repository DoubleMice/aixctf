# Pwn: Format String

## When to Use

Input is passed as a format string or output reflects `%p`, `%s`, `%n`.

## Quick Checks

```bash
python3 - <<'PY'
from pwn import *
for i in range(1, 20):
    print(i, f'%{i}$p')
PY
```

## Fix Strategy

1. Find stack offset.
2. Leak PIE/libc/canary if needed.
3. Write target such as GOT entry or return address only after confirming protections.

## Do Not Repeat

Do not write with `%n` before confirming the exact offset and target address.

## Evidence Standard

Save leak transcript and final exploit transcript separately.
