# Web: JWT / Flask Session

## When to Use

Cookies look like JWTs or Flask signed sessions.

## Quick Checks

```bash
python3 - <<'PY'
import os, jwt
token=os.environ.get('TOKEN','')
print(jwt.get_unverified_header(token) if token else 'no TOKEN')
print(jwt.decode(token, options={'verify_signature': False}) if token else '')
PY
```

## Next Action

Check algorithm confusion, weak secret, debug secret in source, and role claims.

## Evidence Standard

Save original token, decoded claims, modified request, and flag response.
