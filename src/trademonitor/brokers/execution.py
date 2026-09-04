"""Write-capable broker contract used only by Module M from TM4 onward.

The existing :mod:`trademonitor.brokers.base` contract remains read-only.  A
broker adapter must deliberately opt into this stronger interface before Module M
can deploy an ExecutionRequest through it.
"""

from __future__ import annotations

from abc import abstractmethod

from trademonitor.brokers.base import Broker
from trademonitor.domain.models import BrokerInstrument, BrokerOrderRequest, BrokerOrderSnapshot


class ExecutionBroker(Broker):
    """Broker adapter capable of controlled order deployment.

    TGT1 ships no real-broker implementation.  The ``is_simulation`` flag lets the
    Core preserve PAPER-only runtime safety while the deployment machinery is
    exercised against deterministic test adapters.
    """

    @property
    @abstractmethod
    def is_simulation(self) -> bool: ...

    @abstractmethod
    def resolve_instrument(
        self, *, exchange: str, symbol: str, product: str, instrument_token: str | None = None
    ) -> BrokerInstrument: ...

    @abstractmethod
    def submit_order(self, order: BrokerOrderRequest) -> BrokerOrderSnapshot: ...

    @abstractmethod
    def fetch_order(self, broker_order_id: str) -> BrokerOrderSnapshot | None: ...

    @abstractmethod
    def fetch_order_by_client_id(self, client_order_id: str) -> BrokerOrderSnapshot | None: ...

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> BrokerOrderSnapshot: ...
