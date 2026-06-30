# Debug: pwntools Runtime

## When to Use

`EOFError`, `Got EOF`, `Broken pipe`, or `recvuntil` hangs.

## Quick Checks

```bash
LOCAL=1 python3 "$WORKDIR/scripts/exploit.py"
python3 -m py_compile "$WORKDIR/scripts/exploit.py"
```

## Fix Strategy

Synchronize on prompts, avoid `interactive()` as the only output path, and save `recvall()` transcripts.

## Evidence Standard

A fixed run reaches the expected prompt, crash, leak, shell, or flag deterministically.
