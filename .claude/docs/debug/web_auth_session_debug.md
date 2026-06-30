# Debug: Auth Session

## When to Use

Login, role, cookie, session, or CSRF behavior is unclear.

## Quick Checks

```bash
curl -i -c "$WORKDIR/logs/cookies.txt" -b "$WORKDIR/logs/cookies.txt" "$TARGET/"
```

## Next Action

Use a persistent session in `$WORKDIR/scripts/solve_web.py` and save all intermediate responses.

## Evidence Standard

Evidence includes the authenticated request chain.
