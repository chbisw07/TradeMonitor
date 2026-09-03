"""Port for the external Agents validation service."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from trademonitor.domain.models import AgentEntryReviewPacket, AgentEntryReviewResult


class AgentServiceUnavailable(RuntimeError):
    """Raised when the independent Agents service cannot provide a review."""


@runtime_checkable
class AgentGateway(Protocol):
    """Minimal synchronous boundary used by TM2/TGT3.

    The implementation lives outside the TradeMonitor core. A future HTTP/RPC
    adapter may implement this protocol without changing Entry-domain behavior.
    """

    def review_entry(self, packet: AgentEntryReviewPacket) -> AgentEntryReviewResult:
        """Return one mandatory verdict for the exact review packet."""
        ...
