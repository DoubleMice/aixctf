from __future__ import annotations

import subprocess
from pathlib import Path


def run_command(command: list[str], cwd: Path, timeout: int = 600) -> dict:
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
        return {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except subprocess.TimeoutExpired as exc:
        return {"exit_code": 124, "stdout": exc.stdout or "", "stderr": exc.stderr or "command timed out", "timeout": True}
    except Exception as exc:
        return {"exit_code": 127, "stdout": "", "stderr": str(exc)}
