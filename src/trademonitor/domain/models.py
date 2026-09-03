"""Domain models introduced by the TradeMonitor milestones."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Mapping

from trademonitor.domain.enums import ManagementStatus, PositionOrigin, PositionState


def utc_now() -> datetime:
    return datetime.now(UTC)


def _decimal(value: Decimal | str | int | float | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


@dataclass(frozen=True)
class BrokerPositionSnapshot:
    """One broker-reported position at a point in time.

    `broker_position_key` must be stable for the broker/account/instrument/product
    identity represented by the adapter. Quantity is signed: positive is net long,
    negative is net short, and zero means no open exposure.
    """

    broker: str
    broker_position_key: str
    exchange: str
    symbol: str
    product: str
    quantity: int
    average_price: Decimal
    last_price: Decimal | None = None
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    instrument_token: str | None = None
    observed_at: datetime = field(init=False)

    def __init__(
        self,
        *,
        broker: str,
        broker_position_key: str,
        exchange: str,
        symbol: str,
        product: str,
        quantity: int,
        average_price: Decimal | str | int | float,
        last_price: Decimal | str | int | float | None = None,
        realized_pnl: Decimal | str | int | float | None = None,
        unrealized_pnl: Decimal | str | int | float | None = None,
        instrument_token: str | None = None,
        observed_at: datetime | None = None,
    ) -> None:
        object.__setattr__(self, "broker", broker)
        object.__setattr__(self, "broker_position_key", broker_position_key)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "product", product)
        object.__setattr__(self, "quantity", int(quantity))
        object.__setattr__(self, "average_price", _decimal(average_price) or Decimal("0"))
        object.__setattr__(self, "last_price", _decimal(last_price))
        object.__setattr__(self, "realized_pnl", _decimal(realized_pnl))
        object.__setattr__(self, "unrealized_pnl", _decimal(unrealized_pnl))
        object.__setattr__(self, "instrument_token", instrument_token)
        object.__setattr__(self, "observed_at", observed_at or utc_now())


@dataclass(frozen=True)
class BrokerFundsSnapshot:
    """Read-only broker account funds/margin summary."""

    available_cash: Decimal | None = None
    used_margin: Decimal | None = None
    net_value: Decimal | None = None

    @classmethod
    def create(
        cls,
        *,
        available_cash: Decimal | str | int | float | None = None,
        used_margin: Decimal | str | int | float | None = None,
        net_value: Decimal | str | int | float | None = None,
    ) -> "BrokerFundsSnapshot":
        return cls(
            available_cash=_decimal(available_cash),
            used_margin=_decimal(used_margin),
            net_value=_decimal(net_value),
        )


@dataclass(frozen=True)
class BrokerAccountSnapshot:
    """Atomic read-only broker truth used by a reconciliation cycle."""

    broker: str
    observed_at: datetime
    positions: tuple[BrokerPositionSnapshot, ...] = ()
    funds: BrokerFundsSnapshot | None = None
    order_count: int | None = None
    fill_count: int | None = None

    @classmethod
    def create(
        cls,
        *,
        broker: str,
        positions: tuple[BrokerPositionSnapshot, ...] | list[BrokerPositionSnapshot] = (),
        funds: BrokerFundsSnapshot | None = None,
        order_count: int | None = None,
        fill_count: int | None = None,
        observed_at: datetime | None = None,
    ) -> "BrokerAccountSnapshot":
        return cls(
            broker=broker,
            observed_at=observed_at or utc_now(),
            positions=tuple(positions),
            funds=funds,
            order_count=order_count,
            fill_count=fill_count,
        )


@dataclass(frozen=True)
class PositionRecord:
    """Canonical broker-reconciled position known to TradeMonitor.

    Management status is orthogonal to broker state. An UNMANAGED position is
    visible and risk-visible but is a hard read-only boundary until adoption.
    """

    position_id: str
    broker: str
    broker_position_key: str
    exchange: str
    symbol: str
    product: str
    quantity: int
    average_price: Decimal
    state: PositionState
    management_status: ManagementStatus
    origin: PositionOrigin
    last_price: Decimal | None = None
    realized_pnl: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    instrument_token: str | None = None
    first_seen_at: datetime = field(init=False)
    updated_at: datetime = field(init=False)

    def __init__(
        self,
        *,
        position_id: str,
        broker: str,
        broker_position_key: str,
        exchange: str,
        symbol: str,
        product: str,
        quantity: int,
        average_price: Decimal | str | int | float,
        state: PositionState,
        management_status: ManagementStatus,
        origin: PositionOrigin,
        last_price: Decimal | str | int | float | None = None,
        realized_pnl: Decimal | str | int | float | None = None,
        unrealized_pnl: Decimal | str | int | float | None = None,
        instrument_token: str | None = None,
        first_seen_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        now = utc_now()
        object.__setattr__(self, "position_id", position_id)
        object.__setattr__(self, "broker", broker)
        object.__setattr__(self, "broker_position_key", broker_position_key)
        object.__setattr__(self, "exchange", exchange)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "product", product)
        object.__setattr__(self, "quantity", int(quantity))
        object.__setattr__(self, "average_price", _decimal(average_price) or Decimal("0"))
        object.__setattr__(self, "state", PositionState(state))
        object.__setattr__(self, "management_status", ManagementStatus(management_status))
        object.__setattr__(self, "origin", PositionOrigin(origin))
        object.__setattr__(self, "last_price", _decimal(last_price))
        object.__setattr__(self, "realized_pnl", _decimal(realized_pnl))
        object.__setattr__(self, "unrealized_pnl", _decimal(unrealized_pnl))
        object.__setattr__(self, "instrument_token", instrument_token)
        object.__setattr__(self, "first_seen_at", first_seen_at or now)
        object.__setattr__(self, "updated_at", updated_at or now)

    @property
    def is_open(self) -> bool:
        return self.state == PositionState.OPEN and self.quantity != 0

    @property
    def is_managed(self) -> bool:
        return self.management_status == ManagementStatus.MANAGED

    def to_record(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "broker": self.broker,
            "broker_position_key": self.broker_position_key,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "product": self.product,
            "quantity": self.quantity,
            "average_price": str(self.average_price),
            "state": self.state.value,
            "management_status": self.management_status.value,
            "origin": self.origin.value,
            "last_price": None if self.last_price is None else str(self.last_price),
            "realized_pnl": None if self.realized_pnl is None else str(self.realized_pnl),
            "unrealized_pnl": None if self.unrealized_pnl is None else str(self.unrealized_pnl),
            "instrument_token": self.instrument_token,
            "first_seen_at": self.first_seen_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PositionRecord":
        return cls(
            position_id=str(record["position_id"]),
            broker=str(record["broker"]),
            broker_position_key=str(record["broker_position_key"]),
            exchange=str(record["exchange"]),
            symbol=str(record["symbol"]),
            product=str(record["product"]),
            quantity=int(record["quantity"]),
            average_price=str(record["average_price"]),
            state=PositionState(str(record["state"])),
            management_status=ManagementStatus(str(record["management_status"])),
            origin=PositionOrigin(str(record["origin"])),
            last_price=record.get("last_price"),
            realized_pnl=record.get("realized_pnl"),
            unrealized_pnl=record.get("unrealized_pnl"),
            instrument_token=record.get("instrument_token"),
            first_seen_at=datetime.fromisoformat(str(record["first_seen_at"])),
            updated_at=datetime.fromisoformat(str(record["updated_at"])),
        )


@dataclass(frozen=True)
class AttentionItem:
    """Durable operator-facing item surfaced by the TM control room."""

    attention_id: str
    level: str
    source: str
    title: str
    detail: str
    status: str
    created_at: datetime
    resolved_at: datetime | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "attention_id": self.attention_id,
            "level": self.level,
            "source": self.source,
            "title": self.title,
            "detail": self.detail,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "resolved_at": None if self.resolved_at is None else self.resolved_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "AttentionItem":
        resolved = record.get("resolved_at")
        return cls(
            attention_id=str(record["attention_id"]),
            level=str(record["level"]),
            source=str(record["source"]),
            title=str(record["title"]),
            detail=str(record.get("detail", "")),
            status=str(record["status"]),
            created_at=datetime.fromisoformat(str(record["created_at"])),
            resolved_at=datetime.fromisoformat(str(resolved)) if resolved else None,
        )
