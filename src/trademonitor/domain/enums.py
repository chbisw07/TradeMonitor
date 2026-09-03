"""Canonical domain enums used by the TradeMonitor runtime."""

from enum import StrEnum


class ExecutionMode(StrEnum):
    """Execution mode names. Only PAPER is actionable in TM1."""

    PAPER = "PAPER"
    SEMI_AUTO = "SEMI_AUTO"
    AUTO = "AUTO"


class SystemState(StrEnum):
    """System state names. Exact semantics remain specification-controlled."""

    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    SAFE = "SAFE"
    EMERGENCY = "EMERGENCY"


class HealthStatus(StrEnum):
    """Health of a domain/component as seen by the TM control plane."""

    UNKNOWN = "UNKNOWN"
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    RECOVERING = "RECOVERING"


class AttentionLevel(StrEnum):
    """Operator-facing significance used by the Attention queue."""

    INFO = "INFO"
    ATTENTION = "ATTENTION"
    CRITICAL = "CRITICAL"


class AttentionStatus(StrEnum):
    """Lifecycle of an operator attention item."""

    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class ManagementStatus(StrEnum):
    """Whether TradeMonitor has authority to manage a broker position."""

    MANAGED = "MANAGED"
    UNMANAGED = "UNMANAGED"


class PositionState(StrEnum):
    """Broker-reconciled position lifecycle state required by TM1/TGT2."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class PositionOrigin(StrEnum):
    """How a canonical TM position first entered the position context."""

    TM_NATIVE = "TM_NATIVE"
    BROKER_ADOPTED = "BROKER_ADOPTED"
    BROKER_EXTERNAL = "BROKER_EXTERNAL"

class EpisodeStatus(StrEnum):
    """Lifecycle of a time-relevant manifestation of a broad trade outcome."""

    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"


class EpisodeDecision(StrEnum):
    """Result of reconciling an observation with an existing episode."""

    SAME_EPISODE = "SAME_EPISODE"
    NEW_EPISODE = "NEW_EPISODE"
    STALE_OBSERVATION = "STALE_OBSERVATION"


class IntakeDisposition(StrEnum):
    """Operator/audit-friendly result of one intake observation."""

    NEW_OUTCOME = "NEW_OUTCOME"
    NEW_EPISODE = "NEW_EPISODE"
    UPDATED_EPISODE = "UPDATED_EPISODE"
    DUPLICATE_OBSERVATION = "DUPLICATE_OBSERVATION"
    REDISCOVERED_EXISTING_EXPOSURE = "REDISCOVERED_EXISTING_EXPOSURE"
    STALE_OBSERVATION = "STALE_OBSERVATION"


class ExposureRelation(StrEnum):
    """How an incoming opportunity relates to current broker-confirmed exposure."""

    NONE = "NONE"
    SAME_UNDERLYING = "SAME_UNDERLYING"
    EXACT_CONTRACT = "EXACT_CONTRACT"

class TradeType(StrEnum):
    """Holding intent; independent from instrument type."""

    DAY = "DAY"
    BTST = "BTST"
    STBT = "STBT"
    POS = "POS"


class AssetClass(StrEnum):
    """Initial TradeMonitor asset scope."""

    EQUITY = "EQUITY"
    INDEX = "INDEX"


class InstrumentType(StrEnum):
    """Tradable instrument shape. CASH is retained for later stock support."""

    CASH = "CASH"
    FUTURE = "FUTURE"
    OPTION = "OPTION"


class EntryIntentState(StrEnum):
    """Operational state of a monitored entry intent."""

    MONITORING = "MONITORING"
    TRIGGERED = "TRIGGERED"
    CONFIRMING = "CONFIRMING"
    RETREAT_WAIT = "RETREAT_WAIT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    AGENT_REVIEW_PENDING = "AGENT_REVIEW_PENDING"
    USER_DECISION_PENDING = "USER_DECISION_PENDING"
    READY_FOR_RISK = "READY_FOR_RISK"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_BLOCKED = "RISK_BLOCKED"
    REJECTED = "REJECTED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class AgentVerdict(StrEnum):
    """Mandatory verdict returned by the external Agents service."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    RETREAT_WAIT = "RETREAT_WAIT"


class AgentReviewStatus(StrEnum):
    """Lifecycle of an external entry validation request."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ConditionOperator(StrEnum):
    ABOVE = "ABOVE"
    AT_OR_ABOVE = "AT_OR_ABOVE"
    BELOW = "BELOW"
    AT_OR_BELOW = "AT_OR_BELOW"



class RiskDecision(StrEnum):
    """Authoritative result of a Risk Management gate."""

    PASS = "PASS"
    BLOCK = "BLOCK"


class RiskChangeStatus(StrEnum):
    """Lifecycle of a deliberate Setup/Admin Risk configuration change."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
