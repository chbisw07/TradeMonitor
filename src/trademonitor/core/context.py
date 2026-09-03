"""Runtime context containers coordinated by the Core TM Manager.

TM1/TGT1 intentionally keeps these contexts generic. Domain-specific models are
introduced in later targets while the coordination/persistence contract remains
stable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class RuntimeContext:
    """A named, versioned snapshot of one runtime concern.

    Contexts are deliberately small coordination surfaces. Domain modules own the
    meaning of their data; the Core Manager owns synchronization and persistence.
    """

    name: str
    data: dict[str, Any] = field(default_factory=dict)
    version: int = 0
    updated_at: datetime = field(default_factory=utc_now)

    def replace(self, values: Mapping[str, Any], *, updated_at: datetime | None = None) -> None:
        self.data = dict(values)
        self.version += 1
        self.updated_at = updated_at or utc_now()

    def patch(self, values: Mapping[str, Any], *, updated_at: datetime | None = None) -> None:
        self.data.update(values)
        self.version += 1
        self.updated_at = updated_at or utc_now()

    def to_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "data": dict(self.data),
            "version": self.version,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "RuntimeContext":
        updated_at_raw = record.get("updated_at")
        updated_at = (
            datetime.fromisoformat(str(updated_at_raw)) if updated_at_raw else utc_now()
        )
        return cls(
            name=str(record["name"]),
            data=dict(record.get("data", {})),
            version=int(record.get("version", 0)),
            updated_at=updated_at,
        )


_CONTEXT_NAMES = (
    "broker",
    "market",
    "trade",
    "position",
    "risk",
    "decision",
    "health",
)


@dataclass
class RuntimeContexts:
    """Canonical TM1 runtime context registry."""

    contexts: dict[str, RuntimeContext] = field(default_factory=dict)

    @classmethod
    def empty(cls) -> "RuntimeContexts":
        return cls({name: RuntimeContext(name=name) for name in _CONTEXT_NAMES})

    def get(self, name: str) -> RuntimeContext:
        try:
            return self.contexts[name]
        except KeyError as exc:
            raise KeyError(f"Unknown runtime context: {name}") from exc

    def to_records(self) -> list[dict[str, Any]]:
        return [self.contexts[name].to_record() for name in sorted(self.contexts)]

    @classmethod
    def from_records(cls, records: list[Mapping[str, Any]]) -> "RuntimeContexts":
        restored = {str(record["name"]): RuntimeContext.from_record(record) for record in records}
        for name in _CONTEXT_NAMES:
            restored.setdefault(name, RuntimeContext(name=name))
        return cls(restored)
