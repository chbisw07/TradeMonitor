"""Domain models introduced by the TradeMonitor milestones."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Mapping

from trademonitor.domain.enums import (
    EpisodeStatus,
    ExposureRelation,
    IntakeDisposition,
    ManagementStatus,
    PositionOrigin,
    PositionState,
)


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

@dataclass(frozen=True)
class NormalizedTradeIntent:
    """Normalized, broad trading intent used for intake identity.

    Outcome identity deliberately excludes contract-specific/market-time values such
    as strike, expiry, premium and reference price. Those values belong to the
    time-relevant Episode manifestation of the broader opportunity.
    """

    underlying: str
    direction: str
    setup: str
    trade_type: str | None = None
    instrument_type: str | None = None
    option_type: str | None = None
    contract_symbol: str | None = None
    expiry: str | None = None
    strike: str | None = None
    premium: str | None = None
    reference_price: str | None = None
    context_key: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("underlying", "direction", "setup"):
            value = str(getattr(self, field_name)).strip()
            if not value:
                raise ValueError(f"{field_name} is required")
            object.__setattr__(self, field_name, value.upper())
        for field_name in ("trade_type", "instrument_type", "option_type"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, str(value).strip().upper() or None)
        if self.contract_symbol is not None:
            object.__setattr__(self, "contract_symbol", str(self.contract_symbol).strip().upper() or None)

    def outcome_identity(self) -> dict[str, str | None]:
        return {
            "underlying": self.underlying,
            "direction": self.direction,
            "setup": self.setup,
            "trade_type": self.trade_type,
            "instrument_type": self.instrument_type,
            "option_type": self.option_type,
        }

    def episode_identity(self) -> dict[str, str | None]:
        return {
            "contract_symbol": self.contract_symbol,
            "expiry": self.expiry,
            "strike": self.strike,
            "context_key": self.context_key,
        }

    def to_record(self) -> dict[str, Any]:
        return {
            **self.outcome_identity(),
            "contract_symbol": self.contract_symbol,
            "expiry": self.expiry,
            "strike": self.strike,
            "premium": self.premium,
            "reference_price": self.reference_price,
            "context_key": self.context_key,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "NormalizedTradeIntent":
        return cls(**{key: record.get(key) for key in (
            "underlying", "direction", "setup", "trade_type", "instrument_type",
            "option_type", "contract_symbol", "expiry", "strike", "premium",
            "reference_price", "context_key"
        )})


@dataclass(frozen=True)
class SourceObservation:
    """One immutable intake observation from Scanner, Sheet, User, Agents, etc."""

    observation_id: str
    src_id: str
    source: str
    observed_at: datetime
    intent: NormalizedTradeIntent
    raw_payload: Mapping[str, Any] = field(default_factory=dict)
    dedupe_key: str = ""
    outcome_id: str | None = None
    episode_id: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "src_id": self.src_id,
            "source": self.source,
            "observed_at": self.observed_at.isoformat(),
            "intent": self.intent.to_record(),
            "raw_payload": dict(self.raw_payload),
            "dedupe_key": self.dedupe_key,
            "outcome_id": self.outcome_id,
            "episode_id": self.episode_id,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "SourceObservation":
        return cls(
            observation_id=str(record["observation_id"]),
            src_id=str(record["src_id"]),
            source=str(record["source"]),
            observed_at=datetime.fromisoformat(str(record["observed_at"])),
            intent=NormalizedTradeIntent.from_record(record["intent"]),
            raw_payload=dict(record.get("raw_payload", {})),
            dedupe_key=str(record.get("dedupe_key", "")),
            outcome_id=record.get("outcome_id"),
            episode_id=record.get("episode_id"),
        )


@dataclass(frozen=True)
class OutcomeRecord:
    """Broad opportunity identity shared by one or more time-relevant Episodes."""

    outcome_id: str
    outcome_key: str
    identity: Mapping[str, Any]
    created_at: datetime
    updated_at: datetime

    def to_record(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "outcome_key": self.outcome_key,
            "identity": dict(self.identity),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "OutcomeRecord":
        return cls(
            outcome_id=str(record["outcome_id"]),
            outcome_key=str(record["outcome_key"]),
            identity=dict(record["identity"]),
            created_at=datetime.fromisoformat(str(record["created_at"])),
            updated_at=datetime.fromisoformat(str(record["updated_at"])),
        )


@dataclass(frozen=True)
class EpisodeRecord:
    """Time-relevant manifestation of an Outcome in a particular market context."""

    episode_id: str
    outcome_id: str
    signature: Mapping[str, Any]
    status: EpisodeStatus
    started_at: datetime
    last_observed_at: datetime
    latest_observation_id: str

    def to_record(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "outcome_id": self.outcome_id,
            "signature": dict(self.signature),
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "last_observed_at": self.last_observed_at.isoformat(),
            "latest_observation_id": self.latest_observation_id,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "EpisodeRecord":
        return cls(
            episode_id=str(record["episode_id"]),
            outcome_id=str(record["outcome_id"]),
            signature=dict(record.get("signature", {})),
            status=EpisodeStatus(str(record["status"])),
            started_at=datetime.fromisoformat(str(record["started_at"])),
            last_observed_at=datetime.fromisoformat(str(record["last_observed_at"])),
            latest_observation_id=str(record["latest_observation_id"]),
        )


@dataclass(frozen=True)
class ExistingExposure:
    """Read-only awareness of broker-confirmed exposure related to an intake idea."""

    relation: ExposureRelation
    position_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntakeResult:
    """Result returned by the Trade Intake domain for one observation."""

    disposition: IntakeDisposition
    observation: SourceObservation
    outcome: OutcomeRecord
    episode: EpisodeRecord
    existing_exposure: ExistingExposure
    reason: str

    @property
    def creates_new_operational_path(self) -> bool:
        """Only a genuinely new opportunity/Episode can open a new downstream path.

        Replays, updates, stale observations and exposure rediscovery are context/provenance
        updates, never implicit add/scale-in permission.
        """
        return (
            self.existing_exposure.relation == ExposureRelation.NONE
            and self.disposition in {IntakeDisposition.NEW_OUTCOME, IntakeDisposition.NEW_EPISODE}
        )

