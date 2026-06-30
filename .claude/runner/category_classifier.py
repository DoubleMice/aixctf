from __future__ import annotations

import os
from pathlib import Path


PWN_EXTENSIONS = {"", ".bin", ".elf", ".out"}
WEB_NAMES = {"app.py", "server.py", "package.json", "routes.rb", "index.php", "composer.json"}


def classify_challenge(challenge_context: dict, challenge_dir: Path) -> str:
    metadata = challenge_context.get("metadata") or {}
    category = str(metadata.get("category") or metadata.get("type") or "").lower()
    if category in {"pwn", "web"}:
        return category

    target = (challenge_context.get("target") or os.environ.get("TARGET") or "").lower()
    if target.startswith(("http://", "https://")):
        return "web"

    files = [Path(name) for name in challenge_context.get("files", [])]
    if any(path.name in WEB_NAMES or path.suffix in {".php", ".js", ".ts", ".py"} for path in files):
        if any(path.name in WEB_NAMES or "route" in path.name.lower() for path in files):
            return "web"

    for rel in files:
        path = challenge_dir / rel
        if path.is_file() and is_probable_binary(path):
            return "pwn"

    if os.environ.get("HOST") and os.environ.get("PORT"):
        return "pwn"
    return "unknown"


def is_probable_binary(path: Path) -> bool:
    try:
        data = path.read_bytes()[:4096]
    except OSError:
        return False
    if data.startswith(b"\x7fELF"):
        return True
    if b"\x00" in data and path.suffix.lower() in PWN_EXTENSIONS:
        return True
    return False
