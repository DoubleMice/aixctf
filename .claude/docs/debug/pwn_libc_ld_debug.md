# Debug: libc / ld

## When to Use

`GLIBC_* not found`, wrong libc offsets, or remote works differently from local.

## Quick Checks

```bash
ldd ./chall || true
ls -la libc* ld-* 2>/dev/null || true
patchelf --print-interpreter ./chall 2>/dev/null || true
```

## Fix Strategy

Use challenge-provided libc/ld or patch a local copy. Keep original binary intact.

## Evidence Standard

Save linked libraries and final exploit transcript.
