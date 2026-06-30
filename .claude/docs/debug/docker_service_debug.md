# Debug: Docker Service

## When to Use

Challenge service fails to start or ports are unclear.

## Quick Checks

```bash
find "$WORKDIR/challenge" -maxdepth 3 -type f -name 'Dockerfile' -o -name 'docker-compose.yml'
```

## Next Action

Inspect exposed ports, entrypoint, environment, and logs before exploiting.

## Evidence Standard

Save service startup logs and reachable endpoint checks.
