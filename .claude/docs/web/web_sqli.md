# Web: SQL Injection

## When to Use

Input causes SQL syntax errors or authentication/search behavior changes with quotes.

## Quick Checks

```bash
curl -i "$TARGET/search?q=%27"
curl -i "$TARGET/login" -d "username=' or '1'='1&password=x"
```

## Next Action

Determine parameter, DB flavor, and whether UNION, boolean, or error-based extraction is viable.

## Evidence Standard

Save baseline and injected responses, then final flag extraction transcript.
