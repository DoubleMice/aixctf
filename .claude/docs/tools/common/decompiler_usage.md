# Tool: Native Binary Decompilation

## When to Use

Use after pwn file triage identifies a native binary, especially ELF challenges with validation logic, parser state machines, hidden constants, or unclear control flow.

## Overview

```bash
r2 -A -q \
  -c 'iI' \
  -c 'afl' \
  -c 'izz' \
  -c 'q' \
  "$WORKDIR/challenge/chall" | tee "$WORKDIR/logs/r2_overview.log"
```

Decompile the main or suspicious function with radare2 pseudo-C and keep assembly as fallback:

```bash
r2 -A -q \
  -c 's main' \
  -c 'pdf' \
  -c 'pdc' \
  -c 'q' \
  "$WORKDIR/challenge/chall" | tee "$WORKDIR/logs/r2_main.log"
```

If symbols are stripped, use `afl` output plus strings and xrefs to choose functions, then replace `main` with the discovered address, for example `s 0x401234`.

## Evidence Standard

Save radare2 output under `$WORKDIR/logs/`. Cite function names, addresses, checks, constants, and exact file paths used for the next exploit step.
