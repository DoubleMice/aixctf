# Web Template

## When to Use

Use when the challenge provides an HTTP target, web source tree, or metadata category `web`.

## Quick Checks

```bash
python3 /aixctf-agent/tools/web_triage.py
curl -i "$TARGET/" 2>/dev/null | tee "$WORKDIR/logs/web_root.log"
curl -i "$TARGET/robots.txt" 2>/dev/null | tee "$WORKDIR/logs/web_robots.log" || true
```

## Solve Script Standard

Create `$WORKDIR/scripts/solve_web.py` with:
- `requests`.
- target read from `TARGET`.
- request and response transcript saved to `$WORKDIR/evidence/`.
- no access outside challenge scope.

## Common Paths

- Reflected input: test SSTI, command injection, XSS only if relevant to server-side flag access.
- Auth/session: inspect cookies, JWT, Flask session, CSRF flow.
- Source provided: enumerate routes, templates, config, upload handlers, path joins.

## Evidence Standard

Solved requires the exact flag in an HTTP response transcript and the script or curl command that produced it.
