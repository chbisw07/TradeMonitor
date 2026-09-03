"""Event placeholders for future milestones."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class DomainEvent:
    """TODO: replace with concrete auditable events in TM2."""

    name: str
    occurred_at: datetime
