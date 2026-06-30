# Debug: GDB

## When to Use

Need crash register state, offset proof, or ROP debugging.

## Quick Checks

```bash
gdb -q ./chall -ex 'run' -ex 'info registers' -ex 'bt' -ex 'quit'
```

## Next Action

Record crash address and calculate cyclic offset before changing payloads.

## Evidence Standard

Save GDB transcript under `$WORKDIR/logs/`.
