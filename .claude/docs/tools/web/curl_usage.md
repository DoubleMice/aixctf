# Tool: curl

## When to Use

Use for baseline HTTP probes, headers, cookies, redirects, and proof transcripts.

## Commands

```bash
curl -i "$TARGET/"
curl -iL -c "$WORKDIR/logs/cookies.txt" -b "$WORKDIR/logs/cookies.txt" "$TARGET/"
```

## Evidence Standard

Save request and response pairs when they support a conclusion or contain a flag.
