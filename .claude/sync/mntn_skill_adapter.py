from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from tools.flag_utils import redact_flags


class MntnSkillAdapter:
    def __init__(self, timeout_seconds: int = 5, fail_open: bool = True):
        self.timeout_seconds = timeout_seconds
        self.fail_open = fail_open
        self.endpoint = os.environ.get("MNTN_SKILL_ENDPOINT") or os.environ.get("MNTN_ENDPOINT")

    def submit(self, payload: dict[str, Any]) -> dict[str, Any]:
        payload = redact(payload)
        if not self.endpoint:
            return {"ok": False, "fail_open": self.fail_open, "reason": "mntn endpoint not configured"}
        try:
            data = json.dumps(payload).encode("utf-8")
            request = urllib.request.Request(
                self.endpoint,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": response.status, "body": body[:1000]}
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            return {"ok": False, "fail_open": self.fail_open, "reason": str(exc)}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if secret_key(key) else redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        if os.environ.get("ANTHROPIC_API_KEY"):
            value = value.replace(os.environ["ANTHROPIC_API_KEY"], "[REDACTED]")
        return redact_flags(value)
    return value


def secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in ["api_key", "token", "secret", "password"])
