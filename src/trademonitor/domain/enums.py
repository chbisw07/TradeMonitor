"""Domain enum placeholders for future milestones."""

from enum import StrEnum


class ExecutionMode(StrEnum):
    """Execution mode names only. Semantics are specification-controlled."""

    PAPER = "PAPER"
    SEMI_AUTO = "SEMI_AUTO"
    AUTO = "AUTO"


class SystemState(StrEnum):
    """System state names only. Semantics are specification-controlled."""

    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    SAFE = "SAFE"
    EMERGENCY = "EMERGENCY"
