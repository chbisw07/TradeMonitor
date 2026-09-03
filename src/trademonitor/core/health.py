"""Health/fault semantics for TM1/TGT3.

The design follows the TM architecture thesis:
- vertical faults are handled by the nearest competent owner first;
- horizontal peer domains contain their own failures and report summarized
  health/impact to Core;
- a failure must not silently increase capability or authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from trademonitor.domain.enums import HealthStatus


@dataclass(frozen=True)
class DomainHealthReport:
    domain: str
    status: HealthStatus
    summary: str
    impact: tuple[str, ...] = ()
    capabilities: Mapping[str, str] | None = None
    parent: str | None = None
    escalated_from: str | None = None

    @classmethod
    def create(
        cls,
        domain: str,
        status: HealthStatus | str,
        summary: str,
        *,
        impact: Sequence[str] = (),
        capabilities: Mapping[str, str] | None = None,
        parent: str | None = None,
        escalated_from: str | None = None,
    ) -> "DomainHealthReport":
        return cls(
            domain=domain.upper(),
            status=HealthStatus(status),
            summary=summary,
            impact=tuple(impact),
            capabilities=dict(capabilities or {}),
            parent=parent.upper() if parent else None,
            escalated_from=escalated_from,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "domain": self.domain,
            "status": self.status.value,
            "summary": self.summary,
            "impact": list(self.impact),
            "capabilities": dict(self.capabilities or {}),
            "parent": self.parent,
            "escalated_from": self.escalated_from,
        }


@dataclass(frozen=True)
class FaultReport:
    """A fault expressed in domain language, not as a raw exception dump."""

    component: str
    owner_domain: str
    summary: str
    local_action: str
    resolved_locally: bool
    impact: tuple[str, ...] = ()
    escalate_to: str | None = None

    @classmethod
    def create(
        cls,
        component: str,
        owner_domain: str,
        summary: str,
        *,
        local_action: str,
        resolved_locally: bool,
        impact: Sequence[str] = (),
        escalate_to: str | None = None,
    ) -> "FaultReport":
        return cls(
            component=component.upper(),
            owner_domain=owner_domain.upper(),
            summary=summary,
            local_action=local_action,
            resolved_locally=resolved_locally,
            impact=tuple(impact),
            escalate_to=escalate_to.upper() if escalate_to else None,
        )
