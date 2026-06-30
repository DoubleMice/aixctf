# Tool: pwntools

## When to Use

Use for pwn exploit scripts, local/remote process handling, cyclic offsets, packing, and ROP helpers.

## Commands

```bash
python3 -m py_compile "$WORKDIR/scripts/exploit.py"
LOCAL=1 python3 "$WORKDIR/scripts/exploit.py"
REMOTE=1 HOST="$HOST" PORT="$PORT" python3 "$WORKDIR/scripts/exploit.py"
```

## Evidence Standard

Save `recvall()` or command output to `$WORKDIR/evidence/`; do not rely only on `interactive()`.
