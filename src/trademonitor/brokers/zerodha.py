"""Optional Zerodha Kite Connect execution adapter for TM4/TGT3 SEMI_AUTO.

The adapter implements both read-only broker truth and controlled execution.  It
is deliberately optional; importing this module does not require kiteconnect
until a real client must be constructed.
"""

from __future__ import annotations

from datetime import datetime, UTC
from decimal import Decimal
import hashlib
from typing import Any

from trademonitor.brokers.base import Broker
from trademonitor.brokers.execution import ExecutionBroker
from trademonitor.domain.enums import BrokerOrderStatus, OrderSide, OrderType
from trademonitor.domain.models import (
    BrokerAccountSnapshot,
    BrokerFundsSnapshot,
    BrokerInstrument,
    BrokerOrderRequest,
    BrokerOrderSnapshot,
    BrokerPositionSnapshot,
    utc_now,
)


def _d(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _tag(client_order_id: str) -> str:
    # Kite order tags are intentionally short. A deterministic 72-bit digest
    # gives durable restart-safe lookup while retaining the full id internally.
    return "TM" + hashlib.sha256(client_order_id.encode()).hexdigest()[:18].upper()


class ZerodhaDependencyError(RuntimeError):
    pass




def _build_kite_client(*, api_key: str | None, access_token: str | None, kite: Any | None) -> Any:
    """Construct/authenticate Kite lazily so read-only use stays an optional dependency."""
    if kite is not None:
        return kite
    try:
        from kiteconnect import KiteConnect  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ZerodhaDependencyError(
            "Zerodha support is optional. Install with: pip install -e '[zerodha]'"
        ) from exc
    if not api_key or not access_token:
        raise ValueError("ZERODHA_API_KEY and ZERODHA_ACCESS_TOKEN are required")
    client = KiteConnect(api_key=api_key)
    client.set_access_token(access_token)
    return client


def _fetch_account_snapshot(*, kite: Any, broker_name: str) -> BrokerAccountSnapshot:
    """Map Zerodha factual account state into TM's broker-neutral snapshot."""
    observed = utc_now()
    raw_positions = kite.positions() or {}
    net = raw_positions.get("net", []) if isinstance(raw_positions, dict) else []
    positions: list[BrokerPositionSnapshot] = []
    for row in net:
        exchange = str(row.get("exchange") or "")
        symbol = str(row.get("tradingsymbol") or "")
        product = str(row.get("product") or "")
        if not exchange or not symbol or not product:
            continue
        qty = int(row.get("quantity") or 0)
        # Kite's net book can retain fully closed rows with quantity=0 during the
        # day. TM's account snapshot represents current exposure; absence of a
        # previously-open position is what drives broker-truth closure.
        if qty == 0:
            continue
        positions.append(
            BrokerPositionSnapshot(
                broker=broker_name,
                broker_position_key=f"{exchange}:{symbol}:{product}",
                exchange=exchange,
                symbol=symbol,
                product=product,
                quantity=qty,
                average_price=row.get("average_price") or 0,
                last_price=row.get("last_price"),
                realized_pnl=row.get("realised") if row.get("realised") is not None else row.get("realized"),
                unrealized_pnl=row.get("unrealised") if row.get("unrealised") is not None else row.get("unrealized"),
                instrument_token=(None if row.get("instrument_token") is None else str(row.get("instrument_token"))),
                observed_at=observed,
            )
        )

    funds = None
    try:
        margins = kite.margins("equity") or {}
        available = margins.get("available", {}) if isinstance(margins, dict) else {}
        utilised = margins.get("utilised", {}) if isinstance(margins, dict) else {}
        funds = BrokerFundsSnapshot.create(
            available_cash=available.get("cash") or available.get("live_balance"),
            used_margin=utilised.get("debits") or utilised.get("span") or utilised.get("exposure"),
            net_value=margins.get("net") if isinstance(margins, dict) else None,
        )
    except Exception:
        # Positions remain usable broker truth even if the margins endpoint is unavailable.
        funds = None

    try:
        order_count = len(kite.orders() or [])
    except Exception:
        order_count = None
    try:
        fill_count = len(kite.trades() or [])
    except Exception:
        fill_count = None

    return BrokerAccountSnapshot.create(
        broker=broker_name,
        positions=positions,
        funds=funds,
        order_count=order_count,
        fill_count=fill_count,
        observed_at=observed,
    )


class ZerodhaReadOnlyBroker(Broker):
    """Strict Zerodha truth adapter with no order-mutation capability.

    Use this adapter for initial account connection and reconciliation. It does
    not inherit ExecutionBroker and intentionally exposes no place/modify/cancel
    methods, making accidental broker writes impossible through this object.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        kite: Any | None = None,
        name: str = "ZERODHA",
    ) -> None:
        self._name = name
        self._kite = _build_kite_client(api_key=api_key, access_token=access_token, kite=kite)

    @property
    def name(self) -> str:
        return self._name

    def fetch_account_snapshot(self) -> BrokerAccountSnapshot:
        return _fetch_account_snapshot(kite=self._kite, broker_name=self._name)

    @classmethod
    def from_env(cls) -> "ZerodhaReadOnlyBroker":
        import os
        return cls(
            api_key=os.getenv("ZERODHA_API_KEY"),
            access_token=os.getenv("ZERODHA_ACCESS_TOKEN"),
        )


class ZerodhaExecutionBroker(ExecutionBroker):
    """Zerodha Kite Connect adapter used only behind TM SEMI_AUTO gates."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        access_token: str | None = None,
        kite: Any | None = None,
        name: str = "ZERODHA",
    ) -> None:
        self._name = name
        if kite is None:
            try:
                from kiteconnect import KiteConnect  # type: ignore
            except ImportError as exc:  # pragma: no cover - optional dependency
                raise ZerodhaDependencyError(
                    "Zerodha support is optional. Install with: pip install -e '.[zerodha]'"
                ) from exc
            if not api_key or not access_token:
                raise ValueError("ZERODHA_API_KEY and ZERODHA_ACCESS_TOKEN are required")
            kite = KiteConnect(api_key=api_key)
            kite.set_access_token(access_token)
        self._kite = kite
        self._client_by_order_id: dict[str, str] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_simulation(self) -> bool:
        return False

    def fetch_account_snapshot(self) -> BrokerAccountSnapshot:
        return _fetch_account_snapshot(kite=self._kite, broker_name=self._name)

    def resolve_instrument(
        self, *, exchange: str, symbol: str, product: str, instrument_token: str | None = None
    ) -> BrokerInstrument:
        if not exchange.strip() or not symbol.strip() or not product.strip():
            raise ValueError("exchange, symbol and product are required")
        token = instrument_token
        if not token:
            # Instrument token is not required for order placement, but TM's broker
            # contract carries one. Resolve lazily from official instrument data.
            for row in self._kite.instruments(exchange):
                if str(row.get("tradingsymbol")) == symbol:
                    token = str(row.get("instrument_token"))
                    break
        if not token:
            token = f"{exchange}:{symbol}"
        return BrokerInstrument(
            broker=self._name,
            exchange=exchange,
            symbol=symbol,
            product=product,
            instrument_token=str(token),
        )

    def submit_order(self, order: BrokerOrderRequest) -> BrokerOrderSnapshot:
        if order.broker != self._name:
            raise ValueError("order broker does not match Zerodha adapter")
        tag = _tag(order.client_order_id)
        kwargs = dict(
            variety="regular",
            exchange=order.instrument.exchange,
            tradingsymbol=order.instrument.symbol,
            transaction_type=order.side.value,
            quantity=order.quantity,
            product=order.instrument.product,
            order_type=order.order_type.value,
            validity="DAY",
            tag=tag,
        )
        if order.order_type == OrderType.LIMIT:
            kwargs["price"] = float(order.limit_price)
        broker_order_id = str(self._kite.place_order(**kwargs))
        self._client_by_order_id[broker_order_id] = order.client_order_id
        snapshot = self.fetch_order(broker_order_id)
        if snapshot is not None:
            return snapshot
        return BrokerOrderSnapshot(
            broker=self._name,
            broker_order_id=broker_order_id,
            client_order_id=order.client_order_id,
            status=BrokerOrderStatus.ACKNOWLEDGED,
            requested_quantity=order.quantity,
            filled_quantity=0,
            average_fill_price=None,
            observed_at=utc_now(),
        )

    def fetch_order_by_client_id(self, client_order_id: str) -> BrokerOrderSnapshot | None:
        wanted_tag = _tag(client_order_id)
        for row in reversed(self._kite.orders() or []):
            if str(row.get("tag") or "") == wanted_tag:
                oid = str(row.get("order_id"))
                self._client_by_order_id[oid] = client_order_id
                return self._normalize_order(row, client_order_id=client_order_id)
        return None

    def fetch_order(self, broker_order_id: str) -> BrokerOrderSnapshot | None:
        history = self._kite.order_history(broker_order_id) or []
        if not history:
            return None
        row = history[-1]
        client_id = self._client_by_order_id.get(str(broker_order_id))
        if client_id is None:
            tag = str(row.get("tag") or "")
            # A caller that only knows order_id cannot reverse a hashed tag. This
            # fallback remains observable; normal TM reconciliation first searches
            # by the full client idempotency key and populates this cache.
            client_id = tag
        return self._normalize_order(row, client_order_id=client_id)

    def cancel_order(self, broker_order_id: str) -> BrokerOrderSnapshot:
        self._kite.cancel_order(variety="regular", order_id=broker_order_id)
        snapshot = self.fetch_order(broker_order_id)
        if snapshot is None:
            raise RuntimeError("Zerodha cancellation returned no order truth")
        return snapshot

    def _normalize_order(self, row: dict[str, Any], *, client_order_id: str) -> BrokerOrderSnapshot:
        qty = int(row.get("quantity") or 0)
        filled = int(row.get("filled_quantity") or 0)
        raw = str(row.get("status") or "").upper()
        if raw == "COMPLETE":
            status = BrokerOrderStatus.FILLED
        elif raw == "REJECTED":
            status = BrokerOrderStatus.REJECTED
        elif raw == "CANCELLED":
            status = BrokerOrderStatus.CANCELLED
        elif filled > 0:
            status = BrokerOrderStatus.PARTIALLY_FILLED
        elif raw:
            status = BrokerOrderStatus.ACKNOWLEDGED
        else:
            status = BrokerOrderStatus.UNKNOWN
        return BrokerOrderSnapshot(
            broker=self._name,
            broker_order_id=str(row.get("order_id")),
            client_order_id=client_order_id,
            status=status,
            requested_quantity=qty,
            filled_quantity=filled,
            average_fill_price=row.get("average_price"),
            observed_at=utc_now(),
            rejection_reason=row.get("status_message") or row.get("status_message_raw"),
        )

    @classmethod
    def from_env(cls) -> "ZerodhaExecutionBroker":
        import os
        return cls(
            api_key=os.getenv("ZERODHA_API_KEY"),
            access_token=os.getenv("ZERODHA_ACCESS_TOKEN"),
        )
