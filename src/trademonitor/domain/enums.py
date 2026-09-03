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
