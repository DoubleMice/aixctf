from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

from runner.paths import safe_path_segment


class ChallengeLoader:
    def __init__(self, source: Path, workspace: Path, challenge_id: str | None = None):
        self.source = source
        self.workspace = workspace
        self.challenge_dir = workspace / "challenge"
        self.challenge_id = safe_path_segment(challenge_id)

    def sync_challenge(self) -> None:
        try:
            self.challenge_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._warn(f"could not create challenge directory: {exc}")
            return
        try:
            source_exists = self.source.exists()
            source_is_file = self.source.is_file()
        except OSError as exc:
            self._warn(f"could not inspect source {self.source}: {exc}")
            return
        if not source_exists:
            return
        if source_is_file:
            try:
                shutil.copy2(self.source, self.challenge_dir / self.source.name)
            except OSError as exc:
                self._warn(f"could not copy challenge file {self.source}: {exc}")
            return
        try:
            shutil.copytree(self.source, self.challenge_dir, dirs_exist_ok=True, ignore=self._ignore_for_copy())
        except (OSError, shutil.Error) as exc:
            self._warn(f"could not copy challenge directory {self.source}: {exc}")

    def load_context(self) -> dict:
        readme = self._read_first(["README.md", "readme.md", "DESCRIPTION.md", "description.md"])
        metadata = self._load_metadata()
        target_text = self._read_first(["target.txt"])
        files = self._file_list()
        allowed_scope = derive_allowed_scope(target_text, metadata)
        return {
            "challenge_id": safe_path_segment(metadata.get("challenge_id") or metadata.get("id") or self.challenge_id),
            "readme": readme,
            "target": target_text.strip(),
            "metadata": metadata,
            "files": files,
            "summary": self._summary(readme, target_text, metadata, files),
            "allowed_scope": allowed_scope,
        }

    @staticmethod
    def detect_challenge_id(source: Path, use_env: bool = True) -> str:
        env_id = os.environ.get("CHALLENGE_ID") if use_env else None
        if env_id:
            return safe_path_segment(env_id)

        metadata = ChallengeLoader._metadata_from_source(source)
        if metadata.get("challenge_id") or metadata.get("id"):
            return safe_path_segment(metadata.get("challenge_id") or metadata.get("id"))

        if source.exists():
            return safe_path_segment(source.stem if source.is_file() else source.name)
        return "unknown"

    @staticmethod
    def _metadata_from_source(source: Path) -> dict:
        try:
            metadata_path = source / "metadata.json" if source.is_dir() else None
        except OSError:
            metadata_path = None
        if not metadata_path or not metadata_path.exists():
            return {}
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _read_first(self, names: list[str]) -> str:
        for name in names:
            path = self.challenge_dir / name
            try:
                if path.exists() and path.is_file():
                    return path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                self._warn(f"could not read {path}: {exc}")
        return ""

    def _load_metadata(self) -> dict:
        path = self.challenge_dir / "metadata.json"
        try:
            exists = path.exists()
        except OSError as exc:
            return {"metadata_read_error": str(exc)}
        if not exists:
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            return {"metadata_read_error": str(exc)}
        except json.JSONDecodeError:
            return {"metadata_parse_error": str(path)}

    def _file_list(self) -> list[str]:
        files = []
        try:
            paths = self.challenge_dir.rglob("*")
            for path in paths:
                try:
                    if path.is_file():
                        files.append(str(path.relative_to(self.challenge_dir)))
                except OSError as exc:
                    self._warn(f"could not inspect challenge path {path}: {exc}")
        except OSError as exc:
            self._warn(f"could not list challenge files: {exc}")
        return sorted(files)

    def _warn(self, message: str) -> None:
        try:
            path = self.workspace / "logs" / "challenge_loader_warnings.log"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(message + "\n")
        except OSError:
            pass

    def _ignore_for_copy(self):
        ignored_top = {".git", ".claude", "__pycache__"}
        try:
            if self.challenge_dir.is_relative_to(self.source):
                ignored_top.add(self.challenge_dir.relative_to(self.source).parts[0])
        except ValueError:
            pass

        def ignore(directory: str, names: list[str]) -> set[str]:
            directory_path = Path(directory)
            ignored = {name for name in names if name in {".git", "__pycache__", ".pytest_cache"}}
            if directory_path == self.source:
                ignored.update(name for name in names if name in ignored_top)
            return ignored

        return ignore

    @staticmethod
    def _summary(readme: str, target: str, metadata: dict, files: list[str]) -> str:
        parts = []
        if metadata:
            parts.append(f"metadata={json.dumps(metadata, ensure_ascii=False)}")
        if target.strip():
            parts.append(f"target={target.strip()}")
        if readme.strip():
            parts.append("readme:\n" + readme.strip()[:4000])
        if files:
            parts.append("files:\n" + "\n".join(files[:200]))
        if not parts:
            return "No challenge files were provided. Continue with generic initialization."
        return "\n\n".join(parts)


def derive_allowed_scope(target_text: str, metadata: dict) -> dict:
    raw_targets = []
    for env_name in ["TARGET", "HOST"]:
        value = os.environ.get(env_name)
        if value:
            raw_targets.append(value)
    if os.environ.get("HOST") and os.environ.get("PORT"):
        raw_targets.append(f"{os.environ['HOST']}:{os.environ['PORT']}")
    if target_text:
        raw_targets.extend(line.strip() for line in target_text.splitlines() if line.strip())
    for key in ["target", "url", "host"]:
        if metadata.get(key):
            raw_targets.append(str(metadata[key]))

    scope = {"targets": [], "hosts": [], "ports": [], "urls": []}
    for target in raw_targets:
        if target not in scope["targets"]:
            scope["targets"].append(target)
        try:
            parsed = urlparse(target if "://" in target else f"tcp://{target}")
        except ValueError:
            continue
        if parsed.scheme in ["http", "https"] and target not in scope["urls"]:
            scope["urls"].append(target)
        host = parsed.hostname
        if host and host not in scope["hosts"]:
            scope["hosts"].append(host)
        try:
            port = parsed.port
        except ValueError:
            port = None
        if port and port not in scope["ports"]:
            scope["ports"].append(port)
    return scope
