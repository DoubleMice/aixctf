#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    target = os.environ.get("TARGET") or read_target_file()
    workspace = Path(os.environ.get("WORKDIR") or Path.cwd())
    logs = workspace / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    report = [f"target={target or 'unset'}"]
    if not target:
        report.append("No TARGET or challenge/target.txt found under WORKDIR.")
    else:
        for path in ["/", "/robots.txt", "/.git/config"]:
            url = target.rstrip("/") + path
            report.append(section(f"curl {url}", run(["curl", "-i", "-sS", "--max-time", "10", url])))
    source_hits = grep_source(workspace / "challenge")
    if source_hits:
        report.append("## source route hints\n" + source_hits)
    output = "\n\n".join(report) + "\n"
    path = logs / "web_triage.log"
    path.write_text(output, encoding="utf-8", errors="replace")
    print(output)
    print(f"[saved] {path}")
    return 0


def read_target_file() -> str:
    path = Path(os.environ.get("WORKDIR") or Path.cwd()) / "challenge" / "target.txt"
    try:
        if path.exists():
            lines = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
            return lines[0] if lines else ""
    except OSError:
        return ""
    return ""


def run(command: list[str]) -> dict:
    try:
        proc = subprocess.run(command, text=True, capture_output=True, timeout=15, check=False)
        return {"exit_code": proc.returncode, "stdout": proc.stdout[:12000], "stderr": proc.stderr[:4000]}
    except Exception as exc:
        return {"exit_code": 127, "stdout": "", "stderr": str(exc)}


def grep_source(root: Path) -> str:
    if not root.exists():
        return ""
    patterns = ["route", "app.", "Flask", "express", "require(", "include", "render"]
    lines = []
    for path in root.rglob("*"):
        try:
            if not path.is_file() or path.stat().st_size > 2_000_000:
                continue
            for idx, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
                if any(pattern in line for pattern in patterns):
                    lines.append(f"{path}:{idx}:{line[:200]}")
                    if len(lines) >= 200:
                        return "\n".join(lines)
        except OSError:
            continue
    return "\n".join(lines)


def section(title: str, result: dict) -> str:
    return f"## {title}\nexit={result['exit_code']}\n\nstdout:\n{result['stdout']}\n\nstderr:\n{result['stderr']}"


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except Exception as exc:
        print(f"[web_triage][error] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
