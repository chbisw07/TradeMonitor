"""Auditable event primitives for the TradeMonitor runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    """Immutable structured event recorded before runtime publication."""

    event_id: str
    name: str
    occurred_at: datetime
    source: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        name: str,
        *,
        source: str,
        payload: Mapping[str, Any] | None = None,
        occurred_at: datetime | None = None,
    ) -> "DomainEvent":
        return cls(
            event_id=str(uuid4()),
            name=name,
            occurred_at=occurred_at or datetime.now(UTC),
            source=source,
            payload=dict(payload or {}),
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "occurred_at": self.occurred_at.isoformat(),
            "source": self.source,
            "payload": dict(self.payload),
        }
