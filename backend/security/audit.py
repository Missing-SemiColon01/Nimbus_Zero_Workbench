"""Lightweight local audit logging for sovereign workflow evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    event_type: str
    timestamp: str
    task_id: str | None
    payload: dict[str, Any]


class AuditLogger:
    """Append-only JSONL audit log for local prototype execution traces."""

    def __init__(self, data_dir: Path) -> None:
        self.path = data_dir / "audit" / "events.jsonl"

    def record(self, event_type: str, payload: dict[str, Any], *, task_id: str | None = None) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=task_id,
            payload=payload,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_as_jsonable(event), sort_keys=True) + "\n")
        return event

    def tail(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines[-limit:] if line.strip()]


def _as_jsonable(event: AuditEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "task_id": event.task_id,
        "payload": event.payload,
    }
