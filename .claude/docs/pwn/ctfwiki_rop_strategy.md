# CTF Wiki: ROP Strategy

## When to Use

Use after proving stack control and NX/PIE/canary status. This card covers the common escalation path from direct code reuse to libc or syscall chains.

## Triage

```bash
checksec ./chall
file ./chall
ROPgadget --binary ./chall | tee "$WORKDIR/logs/rop_gadgets.log"
readelf -s ./chall | grep -E ' win|system|puts|read|write|main'
```

## Strategy Order

1. `ret2text`: if a win/get_flag function exists and PIE is disabled or leaked.
2. `ret2shellcode`: if writable executable memory exists or NX is disabled.
3. `ret2syscall`: if enough gadgets exist to set syscall number and argument registers.
4. `ret2libc`: if a PLT/GOT leak is available and libc base can be computed.
5. `ret2dlresolve` or SROP: if ordinary libc resolution or gadgets are missing.

## Evidence Checks

Prove offset with cyclic pattern, then prove one controlled return before building the full chain. Record leaked addresses, computed bases, gadget addresses, and final transcript.

## Avoid

Do not assume local libc matches remote. Do not skip stack alignment on amd64 when calling libc functions.

## Source

Derived from CTF Wiki:
[basic-rop.md](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/pwn/linux/user-mode/stackoverflow/x86/basic-rop.md) and
[medium-rop.md](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/pwn/linux/user-mode/stackoverflow/x86/medium-rop.md),
licensed [CC BY-NC-SA 4.0](https://github.com/ctf-wiki/ctf-wiki/blob/master/LICENSE).
