"""Deterministic execution simulator for TM4/TGT2 failure/replay validation.

The simulator is deliberately separate from the minimal TGT1 mock.  It models
ugly execution cases while remaining PAPER-only: accept-then-timeout, disconnect
before acceptance, delayed order visibility, fetch disconnects, partial fills,
rejections and later broker-truth transitions.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from threading import RLock

from trademonitor.brokers.execution import ExecutionBroker
from trademonitor.domain.enums import BrokerOrderStatus
from trademonitor.domain.models import (
    BrokerAccountSnapshot,
    BrokerInstrument,
    BrokerOrderRequest,
    BrokerOrderSnapshot,
    utc_now,
)


class SubmitFault(StrEnum):
    NONE = "NONE"
    DISCONNECT_BEFORE_ACCEPT = "DISCONNECT_BEFORE_ACCEPT"
    ACCEPT_THEN_TIMEOUT = "ACCEPT_THEN_TIMEOUT"


class SimulatedExecutionBroker(ExecutionBroker):
    """Stateful PAPER broker with deterministic failure injection.

    Client-order idempotency is broker-side as well as TM-side.  A simulated
    accept-then-timeout stores the order before raising, reproducing the classic
    "did the broker receive it?" ambiguity without risking a real account.
    """

    def __init__(
        self,
        *,
        name: str = "SIM_EXEC",
        initial_snapshot: BrokerAccountSnapshot | None = None,
        auto_status: BrokerOrderStatus = BrokerOrderStatus.ACKNOWLEDGED,
    ) -> None:
        self._name = name
        self._snapshot = initial_snapshot or BrokerAccountSnapshot.create(broker=name)
        self._auto_status = BrokerOrderStatus(auto_status)
        self._orders_by_id: dict[str, BrokerOrderSnapshot] = {}
        self._orders_by_client: dict[str, str] = {}
        self._next_order_number = 1
        self._submit_faults: list[SubmitFault] = []
        self._client_visibility_delay: dict[str, int] = {}
        self._fetch_failures_remaining = 0
        self._lock = RLock()
        self.submit_count = 0
        self.fetch_count = 0

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_simulation(self) -> bool:
        return True

    def fetch_account_snapshot(self) -> BrokerAccountSnapshot:
        with self._lock:
            return self._snapshot

    def set_account_snapshot(self, snapshot: BrokerAccountSnapshot) -> None:
        if snapshot.broker != self._name:
            raise ValueError("broker identity mismatch")
        with self._lock:
            self._snapshot = snapshot

    def resolve_instrument(
        self, *, exchange: str, symbol: str, product: str, instrument_token: str | None = None
    ) -> BrokerInstrument:
        if not exchange.strip() or not symbol.strip() or not product.strip():
            raise ValueError("exchange, symbol and product are required")
        return BrokerInstrument(
            broker=self._name,
            exchange=exchange,
            symbol=symbol,
            product=product,
            instrument_token=instrument_token or f"{exchange}:{symbol}",
        )

    def queue_submit_fault(self, fault: SubmitFault) -> None:
        with self._lock:
            self._submit_faults.append(SubmitFault(fault))

    def delay_client_visibility(self, client_order_id: str, *, fetches: int) -> None:
        if fetches < 0:
            raise ValueError("fetches cannot be negative")
        with self._lock:
            self._client_visibility_delay[client_order_id] = int(fetches)

    def fail_next_fetches(self, count: int) -> None:
        if count < 0:
            raise ValueError("count cannot be negative")
        with self._lock:
            self._fetch_failures_remaining += int(count)

    def submit_order(self, order: BrokerOrderRequest) -> BrokerOrderSnapshot:
        if order.broker != self._name:
            raise ValueError("order broker does not match adapter")
        with self._lock:
            existing_id = self._orders_by_client.get(order.client_order_id)
            if existing_id:
                return self._orders_by_id[existing_id]

            fault = self._submit_faults.pop(0) if self._submit_faults else SubmitFault.NONE
            if fault == SubmitFault.DISCONNECT_BEFORE_ACCEPT:
                self.submit_count += 1
                raise ConnectionError("simulated disconnect before broker acceptance")

            self.submit_count += 1
            broker_order_id = f"SIM-{self._next_order_number:06d}"
            self._next_order_number += 1
            filled = order.quantity if self._auto_status == BrokerOrderStatus.FILLED else 0
            avg = order.limit_price if filled else None
            snap = BrokerOrderSnapshot(
                broker=self._name,
                broker_order_id=broker_order_id,
                client_order_id=order.client_order_id,
                status=self._auto_status,
                requested_quantity=order.quantity,
                filled_quantity=filled,
                average_fill_price=avg,
                observed_at=utc_now(),
            )
            self._orders_by_id[broker_order_id] = snap
            self._orders_by_client[order.client_order_id] = broker_order_id

            if fault == SubmitFault.ACCEPT_THEN_TIMEOUT:
                raise TimeoutError("simulated acknowledgement loss after broker acceptance")
            return snap

    def _maybe_fail_fetch(self) -> None:
        self.fetch_count += 1
        if self._fetch_failures_remaining > 0:
            self._fetch_failures_remaining -= 1
            raise ConnectionError("simulated broker reconciliation disconnect")

    def fetch_order(self, broker_order_id: str) -> BrokerOrderSnapshot | None:
        with self._lock:
            self._maybe_fail_fetch()
            return self._orders_by_id.get(broker_order_id)

    def fetch_order_by_client_id(self, client_order_id: str) -> BrokerOrderSnapshot | None:
        with self._lock:
            self._maybe_fail_fetch()
            remaining = self._client_visibility_delay.get(client_order_id, 0)
            if remaining > 0:
                self._client_visibility_delay[client_order_id] = remaining - 1
                return None
            oid = self._orders_by_client.get(client_order_id)
            return None if oid is None else self._orders_by_id[oid]

    def cancel_order(self, broker_order_id: str) -> BrokerOrderSnapshot:
        with self._lock:
            current = self._orders_by_id.get(broker_order_id)
            if current is None:
                raise KeyError(broker_order_id)
            if current.status in {
                BrokerOrderStatus.FILLED,
                BrokerOrderStatus.REJECTED,
                BrokerOrderStatus.CANCELLED,
            }:
                return current
            updated = replace(current, status=BrokerOrderStatus.CANCELLED, observed_at=utc_now())
            self._orders_by_id[broker_order_id] = updated
            return updated

    def set_order_truth(
        self,
        broker_order_id: str,
        *,
        status: BrokerOrderStatus,
        filled_quantity: int | None = None,
        average_fill_price: Decimal | str | int | float | None = None,
        rejection_reason: str | None = None,
        observed_at: datetime | None = None,
    ) -> BrokerOrderSnapshot:
        with self._lock:
            current = self._orders_by_id[broker_order_id]
            qty = current.filled_quantity if filled_quantity is None else int(filled_quantity)
            avg = current.average_fill_price if average_fill_price is None else Decimal(str(average_fill_price))
            updated = replace(
                current,
                status=BrokerOrderStatus(status),
                filled_quantity=qty,
                average_fill_price=avg,
                rejection_reason=rejection_reason,
                observed_at=observed_at or utc_now(),
            )
            self._orders_by_id[broker_order_id] = updated
            return updated

    def order_for_client(self, client_order_id: str) -> BrokerOrderSnapshot | None:
        """Inspection helper used by deterministic replay/failure tests."""
        with self._lock:
            oid = self._orders_by_client.get(client_order_id)
            return None if oid is None else self._orders_by_id[oid]
