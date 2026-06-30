# Web: Upload Bypass

## When to Use

Challenge exposes upload, import, avatar, zip, image, or file conversion flows.

## Quick Checks

```bash
curl -i "$TARGET/upload"
```

## Next Action

Identify extension, MIME, magic-byte, path, and storage validation. Use server-side execution only if the stack supports it.

## Evidence Standard

Save upload request, stored path response, and final flag retrieval transcript.
