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
    AssetClass,
    InstrumentType,
    TradeType,
    ManagementRuleType,
    ManagementRuleStatus,
    ManagementSignal,
    ConditionOperator,
    ExitProposalClass,
    ExitAction,
    ExitProposalStatus,
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
class PositionManagementProfile:
    """Management metadata attached to a MANAGED position.

    Broker fields remain in ``PositionRecord`` as factual broker truth. This
    profile contains TradeMonitor management intent. Adopted and future
    TM-native positions use the same profile shape so downstream management
    logic does not need to care how the position entered TM.
    """

    position_id: str
    asset_class: AssetClass
    instrument_type: InstrumentType
    trade_type: TradeType
    horizon_at: datetime
    expiry_date: date | None
    activated_at: datetime
    activated_by: str
    activation_reason: str
    notes: str | None = None

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("position_id is required")
        if not self.activated_by.strip():
            raise ValueError("activated_by is required")
        if not self.activation_reason.strip():
            raise ValueError("activation_reason is required")
        if self.instrument_type in {InstrumentType.FUTURE, InstrumentType.OPTION} and self.expiry_date is None:
            raise ValueError("expiry_date is required for F&O positions")
        if self.instrument_type == InstrumentType.CASH and self.expiry_date is not None:
            raise ValueError("expiry_date is not applicable to CASH positions")
        if self.horizon_at < self.activated_at:
            raise ValueError("horizon_at cannot be earlier than activation time")

    def to_record(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "asset_class": self.asset_class.value,
            "instrument_type": self.instrument_type.value,
            "trade_type": self.trade_type.value,
            "horizon_at": self.horizon_at.isoformat(),
            "expiry_date": None if self.expiry_date is None else self.expiry_date.isoformat(),
            "activated_at": self.activated_at.isoformat(),
            "activated_by": self.activated_by,
            "activation_reason": self.activation_reason,
            "notes": self.notes,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PositionManagementProfile":
        return cls(
            position_id=str(record["position_id"]),
            asset_class=AssetClass(str(record["asset_class"])),
            instrument_type=InstrumentType(str(record["instrument_type"])),
            trade_type=TradeType(str(record["trade_type"])),
            horizon_at=datetime.fromisoformat(str(record["horizon_at"])),
            expiry_date=None if record.get("expiry_date") is None else date.fromisoformat(str(record["expiry_date"])),
            activated_at=datetime.fromisoformat(str(record["activated_at"])),
            activated_by=str(record["activated_by"]),
            activation_reason=str(record["activation_reason"]),
            notes=record.get("notes"),
        )


@dataclass(frozen=True)
class PositionAdoptionRequest:
    """Explicit User request to cross the UNMANAGED -> MANAGED boundary."""

    position_id: str
    asset_class: AssetClass
    instrument_type: InstrumentType
    trade_type: TradeType
    horizon_at: datetime
    expiry_date: date | None
    requested_at: datetime
    requested_by: str
    reason: str
    notes: str | None = None

    def to_profile(self) -> PositionManagementProfile:
        return PositionManagementProfile(
            position_id=self.position_id,
            asset_class=AssetClass(self.asset_class),
            instrument_type=InstrumentType(self.instrument_type),
            trade_type=TradeType(self.trade_type),
            horizon_at=self.horizon_at,
            expiry_date=self.expiry_date,
            activated_at=self.requested_at,
            activated_by=self.requested_by,
            activation_reason=self.reason,
            notes=self.notes,
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
        return self.state not in {
            EntryIntentState.REJECTED,
            EntryIntentState.INVALIDATED,
            EntryIntentState.EXPIRED,
            EntryIntentState.CANCELLED,
        }

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


@dataclass(frozen=True)
class AgentEntryReviewPacket:
    """Bounded entry-decision packet sent to the external Agents service.

    The packet carries only the current proposed trade facts needed for independent
    validation. It is not an ExecutionRequest and grants no execution authority.
    """

    review_id: str
    entry_intent_id: str
    episode_id: str
    requested_at: datetime
    underlying: str
    direction: str
    trade_type: str
    asset_class: str
    instrument_type: str
    horizon_at: datetime
    expiry_date: date | None
    contract_symbol: str | None
    option_type: str | None
    strike: str | None
    trigger: Mapping[str, Any]
    confirmation: Mapping[str, Any] | None
    invalidation: Mapping[str, Any] | None
    premium_min: Decimal | None
    premium_max: Decimal | None
    current_spot: Decimal | None
    current_premium: Decimal | None
    readiness_reason: str | None

    @classmethod
    def from_entry_intent(
        cls, *, review_id: str, requested_at: datetime, intent: "EntryIntentRecord"
    ) -> "AgentEntryReviewPacket":
        return cls(
            review_id=review_id,
            entry_intent_id=intent.entry_intent_id,
            episode_id=intent.episode_id,
            requested_at=requested_at,
            underlying=intent.underlying,
            direction=intent.direction,
            trade_type=intent.trade_type.value,
            asset_class=intent.asset_class.value,
            instrument_type=intent.instrument_type.value,
            horizon_at=intent.horizon_at,
            expiry_date=intent.expiry_date,
            contract_symbol=intent.contract_symbol,
            option_type=intent.option_type,
            strike=intent.strike,
            trigger=intent.trigger.to_record(),
            confirmation=None if intent.confirmation is None else intent.confirmation.to_record(),
            invalidation=None if intent.invalidation is None else intent.invalidation.to_record(),
            premium_min=intent.premium_min,
            premium_max=intent.premium_max,
            current_spot=intent.last_spot,
            current_premium=intent.last_premium,
            readiness_reason=intent.last_reason,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "entry_intent_id": self.entry_intent_id,
            "episode_id": self.episode_id,
            "requested_at": self.requested_at.isoformat(),
            "underlying": self.underlying,
            "direction": self.direction,
            "trade_type": self.trade_type,
            "asset_class": self.asset_class,
            "instrument_type": self.instrument_type,
            "horizon_at": self.horizon_at.isoformat(),
            "expiry_date": None if self.expiry_date is None else self.expiry_date.isoformat(),
            "contract_symbol": self.contract_symbol,
            "option_type": self.option_type,
            "strike": self.strike,
            "trigger": dict(self.trigger),
            "confirmation": None if self.confirmation is None else dict(self.confirmation),
            "invalidation": None if self.invalidation is None else dict(self.invalidation),
            "premium_min": None if self.premium_min is None else str(self.premium_min),
            "premium_max": None if self.premium_max is None else str(self.premium_max),
            "current_spot": None if self.current_spot is None else str(self.current_spot),
            "current_premium": None if self.current_premium is None else str(self.current_premium),
            "readiness_reason": self.readiness_reason,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "AgentEntryReviewPacket":
        return cls(
            review_id=str(record["review_id"]),
            entry_intent_id=str(record["entry_intent_id"]),
            episode_id=str(record["episode_id"]),
            requested_at=datetime.fromisoformat(str(record["requested_at"])),
            underlying=str(record["underlying"]),
            direction=str(record["direction"]),
            trade_type=str(record["trade_type"]),
            asset_class=str(record["asset_class"]),
            instrument_type=str(record["instrument_type"]),
            horizon_at=datetime.fromisoformat(str(record["horizon_at"])),
            expiry_date=None if record.get("expiry_date") is None else date.fromisoformat(str(record["expiry_date"])),
            contract_symbol=record.get("contract_symbol"),
            option_type=record.get("option_type"),
            strike=record.get("strike"),
            trigger=dict(record["trigger"]),
            confirmation=None if record.get("confirmation") is None else dict(record["confirmation"]),
            invalidation=None if record.get("invalidation") is None else dict(record["invalidation"]),
            premium_min=_decimal(record.get("premium_min")),
            premium_max=_decimal(record.get("premium_max")),
            current_spot=_decimal(record.get("current_spot")),
            current_premium=_decimal(record.get("current_premium")),
            readiness_reason=record.get("readiness_reason"),
        )


@dataclass(frozen=True)
class AgentEntryReviewResult:
    """Structured result returned by the external Agents service."""

    review_id: str
    verdict: "AgentVerdict"
    reason: str
    confidence: int | None = None
    suggestion: str | None = None
    responded_at: datetime = None  # type: ignore[assignment]

    def __init__(
        self, *, review_id: str, verdict, reason: str, confidence: int | None = None,
        suggestion: str | None = None, responded_at: datetime | None = None
    ) -> None:
        from trademonitor.domain.enums import AgentVerdict
        if confidence is not None and not 0 <= int(confidence) <= 100:
            raise ValueError("confidence must be between 0 and 100")
        object.__setattr__(self, "review_id", review_id)
        object.__setattr__(self, "verdict", AgentVerdict(verdict))
        object.__setattr__(self, "reason", reason.strip())
        object.__setattr__(self, "confidence", None if confidence is None else int(confidence))
        object.__setattr__(self, "suggestion", suggestion.strip() if suggestion else None)
        object.__setattr__(self, "responded_at", responded_at or utc_now())

    def to_record(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "suggestion": self.suggestion,
            "responded_at": self.responded_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "AgentEntryReviewResult":
        return cls(
            review_id=str(record["review_id"]),
            verdict=record["verdict"],
            reason=str(record.get("reason", "")),
            confidence=record.get("confidence"),
            suggestion=record.get("suggestion"),
            responded_at=datetime.fromisoformat(str(record["responded_at"])),
        )


@dataclass(frozen=True)
class EntryReviewRecord:
    """Durable audit record for one external Agent validation cycle."""

    review_id: str
    entry_intent_id: str
    packet: AgentEntryReviewPacket
    status: "AgentReviewStatus"
    created_at: datetime
    updated_at: datetime
    result: AgentEntryReviewResult | None = None
    user_decision: "AgentVerdict | None" = None
    user_reason: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "entry_intent_id": self.entry_intent_id,
            "packet": self.packet.to_record(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "result": None if self.result is None else self.result.to_record(),
            "user_decision": None if self.user_decision is None else self.user_decision.value,
            "user_reason": self.user_reason,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "EntryReviewRecord":
        from trademonitor.domain.enums import AgentReviewStatus, AgentVerdict
        return cls(
            review_id=str(record["review_id"]),
            entry_intent_id=str(record["entry_intent_id"]),
            packet=AgentEntryReviewPacket.from_record(record["packet"]),
            status=AgentReviewStatus(record["status"]),
            created_at=datetime.fromisoformat(str(record["created_at"])),
            updated_at=datetime.fromisoformat(str(record["updated_at"])),
            result=None if record.get("result") is None else AgentEntryReviewResult.from_record(record["result"]),
            user_decision=None if record.get("user_decision") is None else AgentVerdict(record["user_decision"]),
            user_reason=record.get("user_reason"),
        )


@dataclass(frozen=True)
class AgentExitReviewPacket:
    """Bounded strategic-exit packet sent to the external Agents service."""

    review_id: str
    exit_proposal_id: str
    position_id: str
    requested_at: datetime
    proposal_class: str
    action: str
    requested_quantity: int | None
    requested_percent: Decimal | None
    reasons: tuple[str, ...]
    symbol: str
    quantity: int
    average_price: Decimal
    last_price: Decimal | None
    unrealized_pnl: Decimal | None
    trade_type: str | None
    horizon_at: datetime | None
    expiry_date: date | None

    @classmethod
    def from_exit_proposal(
        cls, *, review_id: str, requested_at: datetime, proposal: "ExitProposal",
        position: "PositionRecord", profile: "PositionManagementProfile | None"
    ) -> "AgentExitReviewPacket":
        return cls(
            review_id=review_id,
            exit_proposal_id=proposal.proposal_id,
            position_id=proposal.position_id,
            requested_at=requested_at,
            proposal_class=proposal.proposal_class.value,
            action=proposal.action.value,
            requested_quantity=proposal.requested_quantity,
            requested_percent=proposal.requested_percent,
            reasons=proposal.reasons,
            symbol=position.symbol,
            quantity=position.quantity,
            average_price=position.average_price,
            last_price=position.last_price,
            unrealized_pnl=position.unrealized_pnl,
            trade_type=None if profile is None else profile.trade_type.value,
            horizon_at=None if profile is None else profile.horizon_at,
            expiry_date=None if profile is None else profile.expiry_date,
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "exit_proposal_id": self.exit_proposal_id,
            "position_id": self.position_id,
            "requested_at": self.requested_at.isoformat(),
            "proposal_class": self.proposal_class,
            "action": self.action,
            "requested_quantity": self.requested_quantity,
            "requested_percent": None if self.requested_percent is None else str(self.requested_percent),
            "reasons": list(self.reasons),
            "symbol": self.symbol,
            "quantity": self.quantity,
            "average_price": str(self.average_price),
            "last_price": None if self.last_price is None else str(self.last_price),
            "unrealized_pnl": None if self.unrealized_pnl is None else str(self.unrealized_pnl),
            "trade_type": self.trade_type,
            "horizon_at": None if self.horizon_at is None else self.horizon_at.isoformat(),
            "expiry_date": None if self.expiry_date is None else self.expiry_date.isoformat(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "AgentExitReviewPacket":
        return cls(
            review_id=str(record["review_id"]),
            exit_proposal_id=str(record["exit_proposal_id"]),
            position_id=str(record["position_id"]),
            requested_at=datetime.fromisoformat(str(record["requested_at"])),
            proposal_class=str(record["proposal_class"]),
            action=str(record["action"]),
            requested_quantity=record.get("requested_quantity"),
            requested_percent=_decimal(record.get("requested_percent")),
            reasons=tuple(str(x) for x in record.get("reasons", [])),
            symbol=str(record["symbol"]),
            quantity=int(record["quantity"]),
            average_price=_decimal(record["average_price"]) or Decimal("0"),
            last_price=_decimal(record.get("last_price")),
            unrealized_pnl=_decimal(record.get("unrealized_pnl")),
            trade_type=record.get("trade_type"),
            horizon_at=None if record.get("horizon_at") is None else datetime.fromisoformat(str(record["horizon_at"])),
            expiry_date=None if record.get("expiry_date") is None else date.fromisoformat(str(record["expiry_date"])),
        )


@dataclass(frozen=True)
class AgentExitReviewResult:
    """Structured independent opinion on one exact exit proposal."""

    review_id: str
    verdict: "AgentVerdict"
    reason: str
    confidence: int | None = None
    suggestion: str | None = None
    responded_at: datetime = None  # type: ignore[assignment]

    def __init__(
        self, *, review_id: str, verdict, reason: str, confidence: int | None = None,
        suggestion: str | None = None, responded_at: datetime | None = None
    ) -> None:
        from trademonitor.domain.enums import AgentVerdict
        if confidence is not None and not 0 <= int(confidence) <= 100:
            raise ValueError("confidence must be between 0 and 100")
        object.__setattr__(self, "review_id", review_id)
        object.__setattr__(self, "verdict", AgentVerdict(verdict))
        object.__setattr__(self, "reason", reason.strip())
        object.__setattr__(self, "confidence", None if confidence is None else int(confidence))
        object.__setattr__(self, "suggestion", suggestion.strip() if suggestion else None)
        object.__setattr__(self, "responded_at", responded_at or utc_now())

    def to_record(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "confidence": self.confidence,
            "suggestion": self.suggestion,
            "responded_at": self.responded_at.isoformat(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "AgentExitReviewResult":
        return cls(
            review_id=str(record["review_id"]), verdict=record["verdict"],
            reason=str(record.get("reason", "")), confidence=record.get("confidence"),
            suggestion=record.get("suggestion"),
            responded_at=datetime.fromisoformat(str(record["responded_at"])),
        )


@dataclass(frozen=True)
class ExitReviewRecord:
    """Durable audit record for one external strategic-exit review cycle."""

    review_id: str
    exit_proposal_id: str
    packet: AgentExitReviewPacket
    status: "AgentReviewStatus"
    created_at: datetime
    updated_at: datetime
    result: AgentExitReviewResult | None = None
    user_decision: "AgentVerdict | None" = None
    user_reason: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "exit_proposal_id": self.exit_proposal_id,
            "packet": self.packet.to_record(),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "result": None if self.result is None else self.result.to_record(),
            "user_decision": None if self.user_decision is None else self.user_decision.value,
            "user_reason": self.user_reason,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ExitReviewRecord":
        from trademonitor.domain.enums import AgentReviewStatus, AgentVerdict
        return cls(
            review_id=str(record["review_id"]),
            exit_proposal_id=str(record["exit_proposal_id"]),
            packet=AgentExitReviewPacket.from_record(record["packet"]),
            status=AgentReviewStatus(record["status"]),
            created_at=datetime.fromisoformat(str(record["created_at"])),
            updated_at=datetime.fromisoformat(str(record["updated_at"])),
            result=None if record.get("result") is None else AgentExitReviewResult.from_record(record["result"]),
            user_decision=None if record.get("user_decision") is None else AgentVerdict(record["user_decision"]),
            user_reason=record.get("user_reason"),
        )


@dataclass(frozen=True)
class RiskProfile:
    """Versioned Risk Management configuration.

    Numeric limits are optional so the bootstrap profile can exist without
    inventing business thresholds. Broker truth is still required by the entry
    gate before new exposure can be approved.
    """

    version: int
    created_at: datetime
    reason: str
    max_position_value: Decimal | None = None
    max_trade_loss: Decimal | None = None
    max_open_positions: int | None = None
    max_total_exposure: Decimal | None = None

    def __init__(
        self,
        *,
        version: int,
        created_at: datetime | None = None,
        reason: str,
        max_position_value=None,
        max_trade_loss=None,
        max_open_positions: int | None = None,
        max_total_exposure=None,
    ) -> None:
        if int(version) < 1:
            raise ValueError("Risk profile version must be >= 1")
        if not str(reason).strip():
            raise ValueError("Risk profile reason is required")
        for name, value in {
            "max_position_value": max_position_value,
            "max_trade_loss": max_trade_loss,
            "max_total_exposure": max_total_exposure,
        }.items():
            dec = _decimal(value)
            if dec is not None and dec <= 0:
                raise ValueError(f"{name} must be > 0 when configured")
        if max_open_positions is not None and int(max_open_positions) < 1:
            raise ValueError("max_open_positions must be >= 1 when configured")
        object.__setattr__(self, "version", int(version))
        object.__setattr__(self, "created_at", created_at or utc_now())
        object.__setattr__(self, "reason", str(reason).strip())
        object.__setattr__(self, "max_position_value", _decimal(max_position_value))
        object.__setattr__(self, "max_trade_loss", _decimal(max_trade_loss))
        object.__setattr__(self, "max_open_positions", None if max_open_positions is None else int(max_open_positions))
        object.__setattr__(self, "max_total_exposure", _decimal(max_total_exposure))

    def to_record(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "reason": self.reason,
            "max_position_value": None if self.max_position_value is None else str(self.max_position_value),
            "max_trade_loss": None if self.max_trade_loss is None else str(self.max_trade_loss),
            "max_open_positions": self.max_open_positions,
            "max_total_exposure": None if self.max_total_exposure is None else str(self.max_total_exposure),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "RiskProfile":
        return cls(
            version=int(record["version"]),
            created_at=datetime.fromisoformat(str(record["created_at"])),
            reason=str(record["reason"]),
            max_position_value=record.get("max_position_value"),
            max_trade_loss=record.get("max_trade_loss"),
            max_open_positions=record.get("max_open_positions"),
            max_total_exposure=record.get("max_total_exposure"),
        )


@dataclass(frozen=True)
class EntryRiskProposal:
    """Concrete risk facts for one proposed entry.

    This is not an ExecutionRequest. Quantity/price are supplied here because
    Risk Management must evaluate the exposure that would be created.
    """

    entry_intent_id: str
    requested_at: datetime
    planned_qty: int
    planned_entry_price: Decimal
    planned_max_loss: Decimal | None = None

    def __init__(
        self,
        *,
        entry_intent_id: str,
        requested_at: datetime,
        planned_qty: int,
        planned_entry_price,
        planned_max_loss=None,
    ) -> None:
        if requested_at.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware")
        if int(planned_qty) <= 0:
            raise ValueError("planned_qty must be > 0")
        price = _decimal(planned_entry_price)
        if price is None or price <= 0:
            raise ValueError("planned_entry_price must be > 0")
        loss = _decimal(planned_max_loss)
        if loss is not None and loss < 0:
            raise ValueError("planned_max_loss cannot be negative")
        object.__setattr__(self, "entry_intent_id", str(entry_intent_id))
        object.__setattr__(self, "requested_at", requested_at)
        object.__setattr__(self, "planned_qty", int(planned_qty))
        object.__setattr__(self, "planned_entry_price", price)
        object.__setattr__(self, "planned_max_loss", loss)

    @property
    def planned_position_value(self) -> Decimal:
        return self.planned_entry_price * self.planned_qty

    def to_record(self) -> dict[str, Any]:
        return {
            "entry_intent_id": self.entry_intent_id,
            "requested_at": self.requested_at.isoformat(),
            "planned_qty": self.planned_qty,
            "planned_entry_price": str(self.planned_entry_price),
            "planned_max_loss": None if self.planned_max_loss is None else str(self.planned_max_loss),
            "planned_position_value": str(self.planned_position_value),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "EntryRiskProposal":
        return cls(
            entry_intent_id=str(record["entry_intent_id"]),
            requested_at=datetime.fromisoformat(str(record["requested_at"])),
            planned_qty=int(record["planned_qty"]),
            planned_entry_price=record["planned_entry_price"],
            planned_max_loss=record.get("planned_max_loss"),
        )


@dataclass(frozen=True)
class RiskDecisionRecord:
    """Durable authoritative Risk Management decision."""

    decision_id: str
    entry_intent_id: str
    profile_version: int
    decision: "RiskDecision"
    evaluated_at: datetime
    reasons: tuple[str, ...]
    metrics: Mapping[str, Any]
    proposal: EntryRiskProposal

    def to_record(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "entry_intent_id": self.entry_intent_id,
            "profile_version": self.profile_version,
            "decision": self.decision.value,
            "evaluated_at": self.evaluated_at.isoformat(),
            "reasons": list(self.reasons),
            "metrics": dict(self.metrics),
            "proposal": self.proposal.to_record(),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "RiskDecisionRecord":
        from trademonitor.domain.enums import RiskDecision
        return cls(
            decision_id=str(record["decision_id"]),
            entry_intent_id=str(record["entry_intent_id"]),
            profile_version=int(record["profile_version"]),
            decision=RiskDecision(record["decision"]),
            evaluated_at=datetime.fromisoformat(str(record["evaluated_at"])),
            reasons=tuple(str(x) for x in record.get("reasons", ())),
            metrics=dict(record.get("metrics", {})),
            proposal=EntryRiskProposal.from_record(record["proposal"]),
        )


@dataclass(frozen=True)
class RiskProfileChange:
    """Pending/confirmed Setup/Admin risk-profile change request."""

    change_id: str
    status: "RiskChangeStatus"
    proposed: Mapping[str, Any]
    reason: str
    requested_at: datetime
    confirmed_at: datetime | None = None
    resulting_profile_version: int | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "change_id": self.change_id,
            "status": self.status.value,
            "proposed": dict(self.proposed),
            "reason": self.reason,
            "requested_at": self.requested_at.isoformat(),
            "confirmed_at": None if self.confirmed_at is None else self.confirmed_at.isoformat(),
            "resulting_profile_version": self.resulting_profile_version,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "RiskProfileChange":
        from trademonitor.domain.enums import RiskChangeStatus
        return cls(
            change_id=str(record["change_id"]),
            status=RiskChangeStatus(record["status"]),
            proposed=dict(record.get("proposed", {})),
            reason=str(record["reason"]),
            requested_at=datetime.fromisoformat(str(record["requested_at"])),
            confirmed_at=None if record.get("confirmed_at") is None else datetime.fromisoformat(str(record["confirmed_at"])),
            resulting_profile_version=record.get("resulting_profile_version"),
        )


@dataclass(frozen=True)
class ManagementRuleSpec:
    """User/policy supplied deterministic rule specification.

    `parameters` is intentionally typed as a mapping so the rule engine can evolve
    rule families without coupling the Position record to rule-specific fields.
    Every rule is still validated by its specialist engine before activation.
    """

    rule_type: ManagementRuleType
    parameters: Mapping[str, Any]
    created_by: str
    reason: str
    policy_name: str | None = None

    def __post_init__(self) -> None:
        if not self.created_by.strip():
            raise ValueError("created_by is required")
        if not self.reason.strip():
            raise ValueError("reason is required")
        object.__setattr__(self, "rule_type", ManagementRuleType(self.rule_type))
        object.__setattr__(self, "parameters", dict(self.parameters))


@dataclass(frozen=True)
class PositionManagementRule:
    """Durable deterministic rule attached to exactly one MANAGED position."""

    rule_id: str
    position_id: str
    rule_type: ManagementRuleType
    parameters: Mapping[str, Any]
    status: ManagementRuleStatus
    runtime_state: Mapping[str, Any]
    created_at: datetime
    updated_at: datetime
    created_by: str
    reason: str
    policy_name: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "position_id": self.position_id,
            "rule_type": self.rule_type.value,
            "parameters": dict(self.parameters),
            "status": self.status.value,
            "runtime_state": dict(self.runtime_state),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "reason": self.reason,
            "policy_name": self.policy_name,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "PositionManagementRule":
        return cls(
            rule_id=str(record["rule_id"]),
            position_id=str(record["position_id"]),
            rule_type=ManagementRuleType(str(record["rule_type"])),
            parameters=dict(record.get("parameters", {})),
            status=ManagementRuleStatus(str(record["status"])),
            runtime_state=dict(record.get("runtime_state", {})),
            created_at=datetime.fromisoformat(str(record["created_at"])),
            updated_at=datetime.fromisoformat(str(record["updated_at"])),
            created_by=str(record["created_by"]),
            reason=str(record["reason"]),
            policy_name=record.get("policy_name"),
        )


@dataclass(frozen=True)
class PositionManagementSnapshot:
    """Current facts supplied to the deterministic management-rule engine."""

    observed_at: datetime
    premium: Decimal | None = None
    underlying_price: Decimal | None = None
    pnl: Decimal | None = None

    @classmethod
    def create(
        cls,
        *,
        observed_at: datetime,
        premium: Decimal | str | int | float | None = None,
        underlying_price: Decimal | str | int | float | None = None,
        pnl: Decimal | str | int | float | None = None,
    ) -> "PositionManagementSnapshot":
        return cls(
            observed_at=observed_at,
            premium=_decimal(premium),
            underlying_price=_decimal(underlying_price),
            pnl=_decimal(pnl),
        )


@dataclass(frozen=True)
class ManagementRuleEvaluation:
    """One deterministic rule result; not an execution request."""

    rule_id: str
    position_id: str
    rule_type: ManagementRuleType
    triggered: bool
    signal: ManagementSignal
    reason: str
    evaluated_at: datetime
    effective_value: Decimal | None = None



@dataclass(frozen=True)
class ExitProposal:
    """Durable proposed reduction of one MANAGED broker-confirmed position.

    This is a decision object only. TM3/TGT3 intentionally has no ExecutionRequest
    or broker write path. Multiple triggers may be coalesced into one proposal.
    """

    proposal_id: str
    position_id: str
    proposal_class: ExitProposalClass
    action: ExitAction
    requested_quantity: int | None
    requested_percent: Decimal | None
    status: ExitProposalStatus
    reasons: tuple[str, ...]
    trigger_rule_ids: tuple[str, ...]
    created_at: datetime
    updated_at: datetime
    created_by: str

    def to_record(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "position_id": self.position_id,
            "proposal_class": self.proposal_class.value,
            "action": self.action.value,
            "requested_quantity": self.requested_quantity,
            "requested_percent": None if self.requested_percent is None else str(self.requested_percent),
            "status": self.status.value,
            "reasons": list(self.reasons),
            "trigger_rule_ids": list(self.trigger_rule_ids),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ExitProposal":
        return cls(
            proposal_id=str(record["proposal_id"]),
            position_id=str(record["position_id"]),
            proposal_class=ExitProposalClass(str(record["proposal_class"])),
            action=ExitAction(str(record["action"])),
            requested_quantity=(None if record.get("requested_quantity") is None else int(record["requested_quantity"])),
            requested_percent=_decimal(record.get("requested_percent")),
            status=ExitProposalStatus(str(record["status"])),
            reasons=tuple(str(x) for x in record.get("reasons", [])),
            trigger_rule_ids=tuple(str(x) for x in record.get("trigger_rule_ids", [])),
            created_at=datetime.fromisoformat(str(record["created_at"])),
            updated_at=datetime.fromisoformat(str(record["updated_at"])),
            created_by=str(record["created_by"]),
        )


@dataclass(frozen=True)
class PositionConversionRequest:
    """Explicit User request to change holding intent without broker execution."""

    position_id: str
    new_trade_type: TradeType
    new_horizon_at: datetime
    requested_at: datetime
    requested_by: str
    reason: str

    def __post_init__(self) -> None:
        if not self.requested_by.strip():
            raise ValueError("requested_by is required")
        if not self.reason.strip():
            raise ValueError("reason is required")
        if self.new_horizon_at < self.requested_at:
            raise ValueError("new_horizon_at cannot be earlier than request time")


# ---------------------------------------------------------------------------
# TM4/TGT1 execution-deployment models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BrokerInstrument:
    broker: str
    exchange: str
    symbol: str
    product: str
    instrument_token: str


@dataclass(frozen=True)
class BrokerOrderRequest:
    """Normalized broker-facing order produced by Module M."""

    broker: str
    client_order_id: str
    instrument: BrokerInstrument
    side: "OrderSide"
    quantity: int
    order_type: "OrderType"
    limit_price: Decimal | None = None

    def __post_init__(self) -> None:
        from trademonitor.domain.enums import OrderType
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("LIMIT order requires limit_price")
        if self.order_type == OrderType.MARKET and self.limit_price is not None:
            raise ValueError("MARKET order must not carry limit_price")


@dataclass(frozen=True)
class BrokerOrderSnapshot:
    """Normalized broker order truth used to reconcile Module M state."""

    broker: str
    broker_order_id: str
    client_order_id: str
    status: "BrokerOrderStatus"
    requested_quantity: int
    filled_quantity: int
    average_fill_price: Decimal | None
    observed_at: datetime
    rejection_reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "average_fill_price", _decimal(self.average_fill_price))
        if self.requested_quantity <= 0:
            raise ValueError("requested_quantity must be positive")
        if self.filled_quantity < 0 or self.filled_quantity > self.requested_quantity:
            raise ValueError("filled_quantity is outside valid range")


@dataclass(frozen=True)
class ExecutionRequest:
    """Durable, authorized instruction handed to Module M.

    The request deliberately contains deployment facts only.  It is immutable in
    intent: status/fill fields evolve by replacing the durable record, while the
    broker, instrument, side, quantity and source authority remain unchanged.
    """

    request_id: str
    idempotency_key: str
    purpose: "ExecutionPurpose"
    source_id: str
    broker: str
    exchange: str
    symbol: str
    product: str
    side: "OrderSide"
    quantity: int
    order_type: "OrderType"
    limit_price: Decimal | None
    status: "ExecutionRequestStatus"
    created_at: datetime
    updated_at: datetime
    risk_decision_id: str | None = None
    risk_profile_version: int | None = None
    broker_order_id: str | None = None
    filled_quantity: int = 0
    average_fill_price: Decimal | None = None
    rejection_reason: str | None = None
    last_broker_observed_at: datetime | None = None
    instrument_token: str | None = None

    def __post_init__(self) -> None:
        from trademonitor.domain.enums import ExecutionPurpose, OrderType
        object.__setattr__(self, "limit_price", _decimal(self.limit_price))
        object.__setattr__(self, "average_fill_price", _decimal(self.average_fill_price))
        if not self.request_id.strip() or not self.idempotency_key.strip():
            raise ValueError("request_id and idempotency_key are required")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.filled_quantity < 0 or self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity is outside valid range")
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError("LIMIT request requires limit_price")
        if self.order_type == OrderType.MARKET and self.limit_price is not None:
            raise ValueError("MARKET request must not carry limit_price")
        if self.purpose == ExecutionPurpose.ENTRY:
            if not self.risk_decision_id or self.risk_profile_version is None:
                raise ValueError("ENTRY execution requires current Risk authorization")

    def to_record(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "idempotency_key": self.idempotency_key,
            "purpose": self.purpose.value,
            "source_id": self.source_id,
            "broker": self.broker,
            "exchange": self.exchange,
            "symbol": self.symbol,
            "product": self.product,
            "side": self.side.value,
            "quantity": self.quantity,
            "order_type": self.order_type.value,
            "limit_price": None if self.limit_price is None else str(self.limit_price),
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "risk_decision_id": self.risk_decision_id,
            "risk_profile_version": self.risk_profile_version,
            "broker_order_id": self.broker_order_id,
            "filled_quantity": self.filled_quantity,
            "average_fill_price": None if self.average_fill_price is None else str(self.average_fill_price),
            "rejection_reason": self.rejection_reason,
            "last_broker_observed_at": None if self.last_broker_observed_at is None else self.last_broker_observed_at.isoformat(),
            "instrument_token": self.instrument_token,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "ExecutionRequest":
        from trademonitor.domain.enums import ExecutionPurpose, ExecutionRequestStatus, OrderSide, OrderType
        return cls(
            request_id=str(record["request_id"]),
            idempotency_key=str(record["idempotency_key"]),
            purpose=ExecutionPurpose(str(record["purpose"])),
            source_id=str(record["source_id"]),
            broker=str(record["broker"]),
            exchange=str(record["exchange"]),
            symbol=str(record["symbol"]),
            product=str(record["product"]),
            side=OrderSide(str(record["side"])),
            quantity=int(record["quantity"]),
            order_type=OrderType(str(record["order_type"])),
            limit_price=record.get("limit_price"),
            status=ExecutionRequestStatus(str(record["status"])),
            created_at=datetime.fromisoformat(str(record["created_at"])),
            updated_at=datetime.fromisoformat(str(record["updated_at"])),
            risk_decision_id=record.get("risk_decision_id"),
            risk_profile_version=record.get("risk_profile_version"),
            broker_order_id=record.get("broker_order_id"),
            filled_quantity=int(record.get("filled_quantity", 0)),
            average_fill_price=record.get("average_fill_price"),
            rejection_reason=record.get("rejection_reason"),
            last_broker_observed_at=(None if record.get("last_broker_observed_at") is None else datetime.fromisoformat(str(record["last_broker_observed_at"]))),
            instrument_token=record.get("instrument_token"),
        )
