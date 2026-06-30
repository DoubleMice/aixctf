# Pwn Template

## When to Use

Use when the challenge provides an ELF binary, `HOST`/`PORT`, or metadata category `pwn`.

## Quick Checks

```bash
python3 /aixctf-agent/tools/pwn_triage.py "$WORKDIR/challenge"
file "$WORKDIR"/challenge/* 2>/dev/null || true
checksec "$WORKDIR"/challenge/* 2>/dev/null || true
```

## Exploit Script Standard

Create `$WORKDIR/scripts/exploit.py` with:
- pwntools local and remote modes.
- `LOCAL=1` for local binary execution.
- `REMOTE=1 HOST=... PORT=...` for remote service.
- transcript saved to `$WORKDIR/evidence/`.

## Common Failures

- EOF means wrong offset, wrong protocol sync, or process crashed before send.
- GLIBC mismatch means run with challenge-provided `libc.so`/`ld-linux` or patch locally.
- Canary/PIE requires a leak before control-flow overwrite.

## Evidence Standard

Solved requires a command transcript containing the exact flag and the script or command that produced it.
