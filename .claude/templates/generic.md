# Generic CTF Template

## When to Use

Use when category is unknown or challenge data is incomplete.

## Quick Checks

```bash
find challenge -maxdepth 3 -type f -print
cat challenge/README.md 2>/dev/null || true
cat challenge/target.txt 2>/dev/null || true
python3 - <<'PY'
from pathlib import Path
for p in Path('challenge').rglob('*'):
    if p.is_file():
        print(p, p.stat().st_size)
PY
```

## Next Action

Classify as `pwn`, `web`, or keep `unknown` with the evidence that prevented classification.

## Evidence Standard

Save file listings and target observations under `$WORKDIR/logs/`.
