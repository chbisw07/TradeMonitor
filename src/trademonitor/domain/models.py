"""Domain models introduced by the TradeMonitor milestones."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
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


@dataclass(frozen=True)
class PriceCondition:
    """Simple deterministic price condition used by entry monitoring."""

    operator: "ConditionOperator"
    value: Decimal

    def __init__(self, operator, value) -> None:
        from trademonitor.domain.enums import ConditionOperator
        object.__setattr__(self, "operator", ConditionOperator(operator))
        object.__setattr__(self, "value", _decimal(value) or Decimal("0"))

    def matches(self, actual: Decimal | str | int | float) -> bool:
        from trademonitor.domain.enums import ConditionOperator
        price = _decimal(actual) or Decimal("0")
        if self.operator == ConditionOperator.ABOVE:
            return price > self.value
        if self.operator == ConditionOperator.AT_OR_ABOVE:
            return price >= self.value
        if self.operator == ConditionOperator.BELOW:
            return price < self.value
        if self.operator == ConditionOperator.AT_OR_BELOW:
            return price <= self.value
        raise ValueError(f"Unsupported operator: {self.operator}")

    def to_record(self) -> dict[str, str]:
        return {"operator": self.operator.value, "value": str(self.value)}

    @classmethod
    def from_record(cls, record: Mapping[str, Any] | None) -> "PriceCondition | None":
        if not record:
            return None
        return cls(record["operator"], record["value"])


@dataclass(frozen=True)
class EntryMarketSnapshot:
    """Current facts supplied to the Entry domain for one evaluation cycle."""

    observed_at: datetime
    spot: Decimal
    premium: Decimal | None = None
    completed_candle_close: Decimal | None = None

    def __init__(self, *, observed_at: datetime, spot, premium=None, completed_candle_close=None) -> None:
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "spot", _decimal(spot) or Decimal("0"))
        object.__setattr__(self, "premium", _decimal(premium))
        object.__setattr__(self, "completed_candle_close", _decimal(completed_candle_close))


@dataclass(frozen=True)
class EntryIntentRecord:
    """Durable monitored entry intent tied to one time-relevant Episode.

    This is not an ExecutionRequest. READY_FOR_REVIEW means only that deterministic
    entry monitoring passed and the opportunity may proceed to later Agent/RM gates.
    """

    entry_intent_id: str
    episode_id: str
    underlying: str
    direction: str
    trade_type: "TradeType"
    asset_class: "AssetClass"
    instrument_type: "InstrumentType"
    horizon_at: datetime
    trigger: PriceCondition
    confirmation: PriceCondition | None = None
    invalidation: PriceCondition | None = None
    expiry_date: date | None = None
    contract_symbol: str | None = None
    option_type: str | None = None
    strike: str | None = None
    premium_min: Decimal | None = None
    premium_max: Decimal | None = None
    state: "EntryIntentState" = None  # type: ignore[assignment]
    created_at: datetime = None  # type: ignore[assignment]
    updated_at: datetime = None  # type: ignore[assignment]
    last_spot: Decimal | None = None
    last_premium: Decimal | None = None
    last_reason: str | None = None

    def __init__(
        self,
        *,
        entry_intent_id: str,
        episode_id: str,
        underlying: str,
        direction: str,
        trade_type,
        asset_class,
        instrument_type,
        horizon_at: datetime,
        trigger: PriceCondition,
        confirmation: PriceCondition | None = None,
        invalidation: PriceCondition | None = None,
        expiry_date: date | str | None = None,
        contract_symbol: str | None = None,
        option_type: str | None = None,
        strike: str | None = None,
        premium_min=None,
        premium_max=None,
        state=None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        last_spot=None,
        last_premium=None,
        last_reason: str | None = None,
    ) -> None:
        from trademonitor.domain.enums import AssetClass, EntryIntentState, InstrumentType, TradeType
        now = utc_now()
        tt = TradeType(trade_type)
        ac = AssetClass(asset_class)
        it = InstrumentType(instrument_type)
        exp = date.fromisoformat(expiry_date) if isinstance(expiry_date, str) else expiry_date
        if horizon_at.tzinfo is None:
            raise ValueError("horizon_at must be timezone-aware")
        if it in {InstrumentType.FUTURE, InstrumentType.OPTION} and exp is None:
            raise ValueError("F&O entry intents require expiry_date")
        if it == InstrumentType.CASH and exp is not None:
            raise ValueError("CASH entry intents must not carry expiry_date")
        if exp is not None and horizon_at.date() > exp:
            raise ValueError("trade horizon cannot extend beyond contract expiry")
        pmin, pmax = _decimal(premium_min), _decimal(premium_max)
        if pmin is not None and pmax is not None and pmin > pmax:
            raise ValueError("premium_min cannot exceed premium_max")
        object.__setattr__(self, "entry_intent_id", entry_intent_id)
        object.__setattr__(self, "episode_id", episode_id)
        object.__setattr__(self, "underlying", underlying.strip().upper())
        object.__setattr__(self, "direction", direction.strip().upper())
        object.__setattr__(self, "trade_type", tt)
        object.__setattr__(self, "asset_class", ac)
        object.__setattr__(self, "instrument_type", it)
        object.__setattr__(self, "horizon_at", horizon_at)
        object.__setattr__(self, "trigger", trigger)
        object.__setattr__(self, "confirmation", confirmation)
        object.__setattr__(self, "invalidation", invalidation)
        object.__setattr__(self, "expiry_date", exp)
        object.__setattr__(self, "contract_symbol", contract_symbol.upper() if contract_symbol else None)
        object.__setattr__(self, "option_type", option_type.upper() if option_type else None)
        object.__setattr__(self, "strike", strike)
        object.__setattr__(self, "premium_min", pmin)
        object.__setattr__(self, "premium_max", pmax)
        object.__setattr__(self, "state", EntryIntentState(state or EntryIntentState.MONITORING))
        object.__setattr__(self, "created_at", created_at or now)
        object.__setattr__(self, "updated_at", updated_at or now)
        object.__setattr__(self, "last_spot", _decimal(last_spot))
        object.__setattr__(self, "last_premium", _decimal(last_premium))
        object.__setattr__(self, "last_reason", last_reason)

    @property
    def active(self) -> bool:
        from trademonitor.domain.enums import EntryIntentState
        return self.state not in {EntryIntentState.INVALIDATED, EntryIntentState.EXPIRED, EntryIntentState.CANCELLED}

    def to_record(self) -> dict[str, Any]:
        return {
            "entry_intent_id": self.entry_intent_id,
            "episode_id": self.episode_id,
            "underlying": self.underlying,
            "direction": self.direction,
            "trade_type": self.trade_type.value,
            "asset_class": self.asset_class.value,
            "instrument_type": self.instrument_type.value,
            "horizon_at": self.horizon_at.isoformat(),
            "trigger": self.trigger.to_record(),
            "confirmation": None if self.confirmation is None else self.confirmation.to_record(),
            "invalidation": None if self.invalidation is None else self.invalidation.to_record(),
            "expiry_date": None if self.expiry_date is None else self.expiry_date.isoformat(),
            "contract_symbol": self.contract_symbol,
            "option_type": self.option_type,
            "strike": self.strike,
            "premium_min": None if self.premium_min is None else str(self.premium_min),
            "premium_max": None if self.premium_max is None else str(self.premium_max),
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_spot": None if self.last_spot is None else str(self.last_spot),
            "last_premium": None if self.last_premium is None else str(self.last_premium),
            "last_reason": self.last_reason,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "EntryIntentRecord":
        return cls(
            entry_intent_id=str(record["entry_intent_id"]),
            episode_id=str(record["episode_id"]),
            underlying=str(record["underlying"]),
            direction=str(record["direction"]),
            trade_type=record["trade_type"],
            asset_class=record["asset_class"],
            instrument_type=record["instrument_type"],
            horizon_at=datetime.fromisoformat(str(record["horizon_at"])),
            trigger=PriceCondition.from_record(record["trigger"]),
            confirmation=PriceCondition.from_record(record.get("confirmation")),
            invalidation=PriceCondition.from_record(record.get("invalidation")),
            expiry_date=record.get("expiry_date"),
            contract_symbol=record.get("contract_symbol"),
            option_type=record.get("option_type"),
            strike=record.get("strike"),
            premium_min=record.get("premium_min"),
            premium_max=record.get("premium_max"),
            state=record.get("state"),
            created_at=datetime.fromisoformat(str(record["created_at"])),
            updated_at=datetime.fromisoformat(str(record["updated_at"])),
            last_spot=record.get("last_spot"),
            last_premium=record.get("last_premium"),
            last_reason=record.get("last_reason"),
        )
