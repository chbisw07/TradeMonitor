"""External integration adapters for TradeMonitor.

Adapters translate external source-specific formats into TradeMonitor's canonical
intake contract. Core domains must not depend on the schema of any adapter.
"""

from .intake import CanonicalTradeObservation, MappingTradeAdapter

__all__ = ["CanonicalTradeObservation", "MappingTradeAdapter"]
