# Supported Tools

## Scope

The runtime currently targets web and pwn CTF challenges only. It intentionally excludes Android/APK, firmware, blockchain, crypto-only, and forensics-specific toolchains unless they are added explicitly later.

## Pwn Tools

- Debugging and runtime tracing: `gdb`, `gdbserver`, `strace`, `ltrace`.
- Binary inspection: `file`, `checksec`, `readelf`, `objdump`, `nm`, `strings`, `xxd`.
- Exploit development: `pwntools`, `ROPGadget`, `one_gadget`, `patchelf`.
- Reversing support: `radare2` with `pdf` and `pdc` for native binary disassembly and pseudo-C.
- Symbolic and emulation helpers: `z3-solver`, `capstone`, `unicorn`.
- Network harnessing: `socat`, `netcat-openbsd`.

## Web Tools

- HTTP clients and scripting: `curl`, `requests`.
- Parsing: `beautifulsoup4`, `lxml`.
- Token and session helpers: `pyjwt`, `itsdangerous`, `flask-unsign`.
- Recon and connectivity: `nmap`, `dnsutils`, `iproute2`, `iputils-ping`.

## Runtime Tools

- Solver runtime: `claude-code`, `nodejs`, Python virtual environment.
- Shell and data helpers: `jq`, `ripgrep`, `unzip`, `ruby`.

## Explicitly Not Included

Do not assume `ghidra`, `jadx`, `apktool`, `binwalk`, Android SDK tools,
firmware extraction tools, `git`, `wget`, `tmux`, `ropper`, or Python `httpx`
are available.

## Source of Truth

The Docker image definition is `.claude/Dockerfile`; Python packages are listed in `.claude/requirements.txt`; Node packages are listed in `.claude/package.json`.
