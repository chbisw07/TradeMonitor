"""Read-only broker truth contract for TM1/TGT2.

Live broker write operations are intentionally absent from this milestone.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from trademonitor.domain.models import BrokerAccountSnapshot


class Broker(ABC):
    """Read-only broker adapter contract used for truth reconciliation."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def fetch_account_snapshot(self) -> BrokerAccountSnapshot:
        """Return one coherent broker-observed account snapshot.

        Adapters must not mutate broker state while satisfying this call.
        """
        ...
