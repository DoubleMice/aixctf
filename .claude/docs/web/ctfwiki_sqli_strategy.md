# CTF Wiki: SQL Injection Strategy

## When to Use

Use when quotes, comments, boolean operators, ordering, or timing change database-backed behavior.

## Triage

```bash
curl -i "$TARGET/path?id=1"
curl -i "$TARGET/path?id=1%27"
curl -i "$TARGET/path?id=1%20and%201=1"
curl -i "$TARGET/path?id=1%20and%201=2"
```

Keep baseline, true, false, and error responses separate.

## Strategy Order

1. Identify injection location, parameter type, and quote context.
2. Determine DB flavor from errors, functions, comments, or system tables.
3. Test column count with `order by` or `union select null,...`.
4. Prefer UNION or error extraction when visible output exists.
5. Use boolean or time-based extraction only after stable response differences are proven.
6. For filters, try comments, encoding, concatenation, case changes, and equivalent functions.

## Evidence Checks

Record the shortest payload proving control, then the extraction query that obtains database, table, column, and flag values.

## Avoid

Do not jump to automated dumping before proving a stable primitive. Do not ignore redirects, cookies, CSRF tokens, or WAF-normalized responses.

## Source

Derived from CTF Wiki:
[web/sqli.md](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/web/sqli.md),
licensed [CC BY-NC-SA 4.0](https://github.com/ctf-wiki/ctf-wiki/blob/master/LICENSE).
