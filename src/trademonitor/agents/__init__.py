"""External Agents-service boundary for TradeMonitor.

TradeMonitor owns no agent reasoning here. It only defines the contract used to
request an independent review from a separate service.
"""

from .gateway import AgentGateway, AgentServiceUnavailable

__all__ = ["AgentGateway", "AgentServiceUnavailable"]
