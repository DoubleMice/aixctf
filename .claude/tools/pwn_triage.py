#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    workspace = Path(os.environ.get("WORKDIR") or Path.cwd())
    challenge_dir = Path(argv[1] if len(argv) > 1 else os.environ.get("CHALLENGE_DIR", str(workspace / "challenge")))
    logs = workspace / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    binaries = find_binaries(challenge_dir)
    report = []
    report.append(f"challenge_dir={challenge_dir}")
    report.append("binaries=" + ", ".join(str(path) for path in binaries) if binaries else "binaries=none")
    for binary in binaries:
        report.append(section(f"file {binary}", run(["file", str(binary)], challenge_dir)))
        if shutil.which("checksec"):
            report.append(section(f"checksec {binary}", run(["checksec", str(binary)], challenge_dir)))
        report.append(section(f"readelf {binary}", run(["readelf", "-h", str(binary)], challenge_dir)))
        report.append(section(f"nm {binary}", run(["nm", "-an", str(binary)], challenge_dir)))
        report.append(section(f"strings {binary}", run(["strings", str(binary)], challenge_dir)))
    output = "\n\n".join(report) + "\n"
    path = logs / "pwn_triage.log"
    path.write_text(output, encoding="utf-8", errors="replace")
    print(output)
    print(f"[saved] {path}")
    return 0


def find_binaries(root: Path) -> list[Path]:
    found = []
    if not root.exists():
        return found
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            data = path.read_bytes()[:4]
        except OSError:
            continue
        if data == b"\x7fELF" or os.access(path, os.X_OK):
            found.append(path)
    return found[:20]


def run(command: list[str], cwd: Path) -> dict:
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=20, check=False)
        return {"exit_code": proc.returncode, "stdout": proc.stdout[:8000], "stderr": proc.stderr[:4000]}
    except Exception as exc:
        return {"exit_code": 127, "stdout": "", "stderr": str(exc)}


def section(title: str, result: dict) -> str:
    return f"## {title}\nexit={result['exit_code']}\n\nstdout:\n{result['stdout']}\n\nstderr:\n{result['stderr']}"


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as exc:
        print(f"[pwn_triage][error] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
