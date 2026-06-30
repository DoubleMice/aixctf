# Handoff: Evidence Standard

## When to Use

Use before declaring solved or writing final result.

## Solved Standard

- `result.json` has exact flag.
- `$WORKDIR/evidence/` contains a transcript with the exact flag.
- `$WORKDIR/scripts/` contains a reproducible script unless unnecessary.
- `$WORKDIR/handoff.md` explains the flag source.

## Failed Standard

- `handoff.md` exists.
- `notes.md` exists.
- At least one `rounds/round_*.json` exists.
- `failure_reason` explains why the run stopped.
