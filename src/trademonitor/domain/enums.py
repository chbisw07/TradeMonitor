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

