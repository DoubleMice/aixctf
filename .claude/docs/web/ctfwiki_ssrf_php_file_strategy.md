# CTF Wiki: SSRF and PHP File Strategy

## When to Use

Use when a web challenge fetches URLs, processes files, includes paths, uploads PHP-adjacent content, or exposes PHP source-code audit clues.

## SSRF Triage

```bash
curl -i "$TARGET/fetch" --data-urlencode 'url=http://127.0.0.1/'
curl -i "$TARGET/fetch" --data-urlencode 'url=file:///etc/passwd'
```

Check whether schemes, hostnames, ports, redirects, DNS resolution, or response body are filtered.

## PHP File Triage

For include-like parameters, test readable local files first, then wrappers only if PHP behavior suggests they are enabled. For upload flows, record extension, MIME, magic bytes, image processing, storage path, and execution reachability.

## Useful Directions

- SSRF: internal HTTP services, loopback aliases, cloud metadata, port scanning, alternate schemes, redirect behavior.
- File include: path traversal, null or suffix handling, PHP wrappers, log/session inclusion.
- Upload: double extensions, case variants, content-type mismatch, magic-byte polyglots, archive extraction paths.
- PHP audit: variable override, weak comparisons, dynamic function calls, command execution sinks, backup/source leaks.

## Evidence Checks

Save request, response, final internal URL/path, uploaded stored path, and the exact proof that code execution or file read happened.

## Avoid

Do not run destructive commands. Do not assume upload equals execution; prove where the file is stored and how it is served.

## Source

Derived from CTF Wiki:
[web/ssrf.md](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/web/ssrf.md) and
[web/php/php.md](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/web/php/php.md),
licensed [CC BY-NC-SA 4.0](https://github.com/ctf-wiki/ctf-wiki/blob/master/LICENSE).
