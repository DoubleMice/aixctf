# Pwn: PIE Leak

## When to Use

PIE is enabled and exploit needs binary text addresses.

## Quick Checks

```bash
checksec ./chall
readelf -s ./chall | grep -Ei 'main|win|puts|printf'
```

## Next Action

Leak a code pointer, compute PIE base, then rebuild ROP addresses relative to base.

## Evidence Standard

Save leaked pointer, computed base, and final exploit output.
