"""Canonical domain enums used by the TradeMonitor runtime."""

from enum import StrEnum


class ExecutionMode(StrEnum):
    """Execution mode names only. Semantics are specification-controlled."""

    PAPER = "PAPER"
    SEMI_AUTO = "SEMI_AUTO"
    AUTO = "AUTO"


class SystemState(StrEnum):
    """System state names only. Exact semantics continue to evolve by roadmap."""

    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    SAFE = "SAFE"
    EMERGENCY = "EMERGENCY"


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
