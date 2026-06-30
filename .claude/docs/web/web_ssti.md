# Web: SSTI

## When to Use

User input is reflected through a server-side template engine.

## Quick Checks

```bash
curl -s "$TARGET/?q={{7*7}}"
curl -s "$TARGET/?q=${7*7}"
```

## Next Action

Confirm template engine, then read config or execute a minimal command only if the challenge scope requires server-side flag access.

## Evidence Standard

Save request and response showing the expression result, then final flag response.
