from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def make_event(
    *,
    source: str,
    event_type: str,
    message: str,
    level: str = "info",
    round_id: int | None = None,
    phase: str | None = None,
    category: str | None = None,
    summary: dict[str, Any] | None = None,
    artifacts: list[str] | None = None,
    requires_human_attention: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    event = {
        "time": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "type": event_type,
        "level": level,
        "round": round_id,
        "phase": phase,
        "category": category,
        "message": message,
        "summary": summary or {},
        "artifacts": artifacts or [],
        "requires_human_attention": requires_human_attention,
    }
    event.update({key: value for key, value in extra.items() if value is not None})
    return event
