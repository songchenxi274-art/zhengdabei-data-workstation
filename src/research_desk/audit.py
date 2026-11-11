from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class AuditLogger:
    """Writes metadata-only audit events without prompts, values, or file paths."""

    def __init__(self, path: Path):
        self.path = path

    def record(
        self,
        event: str,
        *,
        outcome: str,
        data_level: str | None = None,
        provider: str | None = None,
        fingerprint: str | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "outcome": outcome,
            "data_level": data_level,
            "provider": provider,
            "fingerprint": fingerprint,
        }
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
