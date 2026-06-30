# Debug: HTTP

## When to Use

HTTP 403, 404, 500, redirects, cookie, or CSRF issues block progress.

## Quick Checks

```bash
curl -i "$TARGET/"
curl -iL "$TARGET/"
curl -i "$TARGET/" -H 'User-Agent: Mozilla/5.0'
```

## Fix Strategy

Preserve cookies, inspect redirects, include CSRF tokens, and compare baseline versus mutated requests.

## Evidence Standard

Save request and response pairs under `$WORKDIR/logs/`.
