# Pwn: ret2libc

## When to Use

NX is enabled, no direct win function is available, and a libc leak is possible.

## Quick Checks

```bash
checksec ./chall
ROPgadget --binary ./chall | grep 'pop rdi'
readelf -r ./chall | grep -E 'puts|printf|read'
```

## Next Action

Leak a libc address, compute base, call `system('/bin/sh')` or a flag-reading function.

## Evidence Standard

Save leak values and final command transcript containing the flag.
