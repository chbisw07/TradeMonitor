"""TM4/TGT4 AUTO-readiness evidence and gating.

AUTO is intentionally evidence-gated.  This module does not manufacture evidence:
operators/tests record the observed SEMI_AUTO results and the evaluator applies the
roadmap's minimum readiness contract deterministically.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Any, Mapping


class AutoReadinessError(RuntimeError):
    """Raised when AUTO is requested without satisfying the readiness gate."""


@dataclass(frozen=True)
class AutoReadinessEvidence:
    semi_auto_sessions: int = 0
    semi_auto_real_executions: int = 0
    unresolved_reconciliation_defects: int = 0
    duplicate_execution_defects: int = 0
    restart_recovery_validated: bool = False
    risk_management_validated: bool = False
    position_exit_validated: bool = False
    agent_degradation_validated: bool = False
    operating_safeguards_validated: bool = False
    note: str = ""
    recorded_at: str = ""
    recorded_by: str = ""

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "AutoReadinessEvidence":
        value = dict(value or {})
        allowed = set(cls.__dataclass_fields__)
        return cls(**{key: value[key] for key in allowed if key in value})

    def to_record(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AutoReadinessAssessment:
    ready: bool
    checks: Mapping[str, bool]
    blockers: tuple[str, ...]
    evidence_digest: str
    assessed_at: str

    def to_record(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "checks": dict(self.checks),
            "blockers": list(self.blockers),
            "evidence_digest": self.evidence_digest,
            "assessed_at": self.assessed_at,
        }


class AutoReadinessGate:
    """Deterministic TM4/TGT4 readiness evaluator.

    The small numeric minimums intentionally prove repetition rather than one lucky
    live action.  They are eligibility floors, not performance targets.
    """

    MIN_SEMI_AUTO_SESSIONS = 3
    MIN_SEMI_AUTO_REAL_EXECUTIONS = 3

    @classmethod
    def evidence_digest(cls, evidence: AutoReadinessEvidence) -> str:
        payload = evidence.to_record().copy()
        # Metadata does not alter the operational facts being approved.
        payload.pop("recorded_at", None)
        payload.pop("recorded_by", None)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(encoded).hexdigest()

    @classmethod
    def assess(
        cls, evidence: AutoReadinessEvidence, *, at: datetime | None = None
    ) -> AutoReadinessAssessment:
        checks = {
            "sufficient_semi_auto_sessions": evidence.semi_auto_sessions >= cls.MIN_SEMI_AUTO_SESSIONS,
            "sufficient_real_executions": evidence.semi_auto_real_executions >= cls.MIN_SEMI_AUTO_REAL_EXECUTIONS,
            "no_unresolved_reconciliation_defects": evidence.unresolved_reconciliation_defects == 0,
            "no_duplicate_execution_defects": evidence.duplicate_execution_defects == 0,
            "restart_recovery_validated": evidence.restart_recovery_validated,
            "risk_management_validated": evidence.risk_management_validated,
            "position_exit_validated": evidence.position_exit_validated,
            "agent_degradation_validated": evidence.agent_degradation_validated,
            "operating_safeguards_validated": evidence.operating_safeguards_validated,
        }
        blockers = tuple(name for name, passed in checks.items() if not passed)
        return AutoReadinessAssessment(
            ready=not blockers,
            checks=checks,
            blockers=blockers,
            evidence_digest=cls.evidence_digest(evidence),
            assessed_at=(at or datetime.now(UTC)).isoformat(),
        )
