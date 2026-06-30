# CTF Wiki: Heap Exploitation Strategy

## When to Use

Use for menu binaries with add/edit/delete/show flows, dangling pointers, double free, off-by-one, overflow into chunk metadata, or unexpected allocator reuse.

## Triage

```bash
checksec ./chall
strings -a ./chall | grep -Ei 'malloc|calloc|realloc|free|puts|printf'
ldd ./chall 2>/dev/null || true
```

Map every heap operation: size control, index bounds, edit length, show behavior, free clearing, and whether chunks can be reallocated at the same address.

## Attack Selection

- UAF: leak through stale show or overwrite function pointers/hooks after reuse.
- Double free / tcache dup: create repeated allocation of the same chunk, then steer the freelist.
- Tcache poisoning: overwrite a freed chunk `next` pointer and allocate toward a controlled target.
- Fastbin attack: use size-compatible fake chunks and allocator checks carefully.
- Unsorted bin leak: free a large enough chunk and read main arena pointers for libc base.
- Off-by-one / unlink: target size fields and consolidation behavior.

## Evidence Checks

Capture allocator version, chunk size class, allocation sequence, leak values, and a heap-state note before each destructive write.

## Avoid

Do not mix techniques before proving allocator version and bin path. Do not assume old hook targets exist on modern glibc.

## Source

Derived from CTF Wiki ptmalloc2 heap chapters including
[tcache](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/pwn/linux/user-mode/heap/ptmalloc2/tcache-attack.md),
[UAF](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/pwn/linux/user-mode/heap/ptmalloc2/use-after-free.md),
[fastbin](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/pwn/linux/user-mode/heap/ptmalloc2/fastbin-attack.md),
[unlink](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/pwn/linux/user-mode/heap/ptmalloc2/unlink.md),
[off-by-one](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/pwn/linux/user-mode/heap/ptmalloc2/off-by-one.md), and
[unsorted bin](https://github.com/ctf-wiki/ctf-wiki/blob/master/docs/zh/docs/pwn/linux/user-mode/heap/ptmalloc2/unsorted-bin-attack.md),
licensed [CC BY-NC-SA 4.0](https://github.com/ctf-wiki/ctf-wiki/blob/master/LICENSE).
