"""Ports for the separate external Agents validation service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from trademonitor.domain.models import (
    AgentEntryReviewPacket,
    AgentEntryReviewResult,
    AgentExitReviewPacket,
    AgentExitReviewResult,
)


class AgentServiceUnavailable(RuntimeError):
    """Raised when the independent Agents service cannot provide a review."""


@runtime_checkable
class AgentGateway(Protocol):
    """Minimal synchronous boundary to the external Agents service.

    TradeMonitor owns no Agent reasoning. A future HTTP/RPC adapter may implement
    this protocol without changing Entry or Exit domain behavior.
    """

    def review_entry(self, packet: AgentEntryReviewPacket) -> AgentEntryReviewResult:
        """Return one mandatory verdict for the exact entry review packet."""
        ...

    def review_exit(self, packet: AgentExitReviewPacket) -> AgentExitReviewResult:
        """Return one mandatory verdict for the exact exit review packet."""
        ...
