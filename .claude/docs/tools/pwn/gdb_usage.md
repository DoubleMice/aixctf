# Tool: GDB

## When to Use

Use to prove crash control, cyclic offsets, stack alignment, and register state.

## Commands

```bash
gdb -q ./chall -ex 'run' -ex 'info registers' -ex 'bt' -ex 'quit'
```

## Evidence Standard

Save the transcript under `$WORKDIR/logs/` and cite exact register or crash evidence.
