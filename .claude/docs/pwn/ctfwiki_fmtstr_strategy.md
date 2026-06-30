# CTF Wiki: Format String Strategy

## When to Use

Use when user-controlled input is interpreted by `printf`-style functions, especially when `%p`, `%s`, `%n`, or positional parameters affect output.

## Detection

```bash
python3 - <<'PY'
for i in range(1, 30):
    print(f'%{i}$p')
PY
```

Send a short range first. Compare response shape with baseline output and save the exact request/response.

## Leak Plan

1. Find the argument index where controlled bytes appear.
2. Leak stack, PIE, canary, or libc pointers with positional reads.
3. For arbitrary reads, place a target address in the payload and read it with `%s` only after confirming the correct index.

## Write Plan

Use `%n` only after confirming the target address and byte count. Prefer byte or half-word writes for stable payloads. Write low bytes first when ordering matters, and log the exact values written.

## Avoid

Do not use `%s` against unknown invalid addresses during early probing. Do not overwrite GOT/return addresses until the leak and offset are reproducible.

## Source

Derived from CTF Wiki:
[fmtstr-detect.md](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/pwn/linux/user-mode/fmtstr/fmtstr-detect.md) and
[fmtstr-exploit.md](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/pwn/linux/user-mode/fmtstr/fmtstr-exploit.md),
licensed [CC BY-NC-SA 4.0](https://github.com/ctf-wiki/ctf-wiki/blob/master/LICENSE).
