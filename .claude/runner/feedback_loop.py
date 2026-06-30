from __future__ import annotations


def classify_failure(round_result: dict) -> str | None:
    reason = round_result.get("failure_reason")
    if reason:
        return reason
    observations = " ".join(round_result.get("observations", [])).lower()
    if "timeout" in observations:
        return "TIMEOUT"
    if "command not found" in observations or "not found" in observations and "claude" in observations:
        return "ENV_ERROR"
    if "no progress" in observations:
        return "NO_PROGRESS"
    return None
