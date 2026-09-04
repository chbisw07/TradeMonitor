"""Top Picks -> canonical EntryIntent translation.

This module is intentionally source-specific and lives at the adapter boundary.
It understands the scanner's human-facing Top Picks fields and translates only
semantics that have been explicitly verified into TradeMonitor's generic entry
contract.  Core Entry code remains unaware of Google Sheets or workbook columns.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
import re
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from trademonitor.adapters.intake import CanonicalTradeObservation
from trademonitor.domain.enums import ConditionOperator
from trademonitor.domain.models import PriceCondition


IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class TopPicksEntryTranslation:
    """Result of translating one source observation into entry-intent kwargs."""

    arm: bool
    reason: str
    kwargs: Mapping[str, Any] | None = None


def _norm(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("₹", "")
    if not text:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def parse_price_range(value: object) -> tuple[Decimal | None, Decimal | None]:
    """Parse scanner ranges such as ``₹12.42–₹14.35`` or ``544.28-545.34``."""
    if value is None:
        return None, None
    text = str(value).strip().replace(",", "").replace("₹", "")
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    if not numbers:
        return None, None
    vals = [Decimal(n) for n in numbers[:2]]
    if len(vals) == 1:
        return vals[0], vals[0]
    return min(vals[0], vals[1]), max(vals[0], vals[1])


def extract_expiry(value: object) -> str | None:
    if value is None:
        return None
    match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", str(value))
    return match.group(1) if match else None


def clean_contract_symbol(value: object) -> str | None:
    """Keep the contract identity and discard display-only premium/greek suffixes."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Top Picks display is commonly: YYYY-MM-DD 545 CE @ 13.50 | Δ ...
    return re.split(r"\s+@\s+|\s*\|\s*", text, maxsplit=1)[0].strip()


def _asset_class(underlying: str) -> str:
    indexes = {
        "NIFTY", "NIFTY50", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "BANKEX"
    }
    return "INDEX" if underlying.upper().replace(" ", "") in indexes else "EQUITY"


def _day_horizon(observed_at: datetime) -> datetime:
    local = observed_at.astimezone(IST)
    return datetime.combine(local.date(), time(15, 30), tzinfo=IST)


def translate_top_pick_to_entry(
    observation: CanonicalTradeObservation,
) -> TopPicksEntryTranslation:
    """Translate verified Top Picks semantics into generic EntryIntent kwargs.

    Current conservative mapping:
      * BUY ON CONFIRM -> arm in the spot zone and require a directionally
        supportive completed-candle close.
      * WAIT FOR PULLBACK -> wait for price to return to the zone, then require a
        directionally supportive completed-candle close.
      * AVOID CHASE / unknown statuses -> retain Intake opportunity only; do not arm.

    The original natural-language Confirmation remains in source provenance.  We
    intentionally do not attempt broad NLP interpretation inside the core.
    """

    raw = dict(observation.raw_payload)
    status = _norm(raw.get("entry_status"))
    if status == "AVOID CHASE":
        return TopPicksEntryTranslation(False, "AVOID CHASE remains an Intake opportunity; entry is not armed")
    if status not in {"BUY ON CONFIRM", "WAIT FOR PULLBACK"}:
        label = status or "EMPTY"
        return TopPicksEntryTranslation(False, f"Entry Status {label!r} has no verified deterministic mapping")

    intent = observation.intent
    direction = intent.direction.upper()
    if direction not in {"BULLISH", "BEARISH"}:
        return TopPicksEntryTranslation(False, f"Unsupported direction for Top Picks entry mapping: {direction}")

    spot_min, spot_max = parse_price_range(intent.reference_price)
    if spot_min is None or spot_max is None:
        return TopPicksEntryTranslation(False, "Spot Entry Zone is required to arm this Top Picks entry")

    premium_min, premium_max = parse_price_range(intent.premium)
    invalidation_value = _decimal(raw.get("invalidation"))
    if invalidation_value is None:
        return TopPicksEntryTranslation(False, "Invalidation is required to arm this Top Picks entry")

    if status == "BUY ON CONFIRM":
        if direction == "BULLISH":
            trigger = PriceCondition(ConditionOperator.AT_OR_ABOVE, spot_min)
            confirmation = PriceCondition(ConditionOperator.AT_OR_ABOVE, spot_min)
        else:
            trigger = PriceCondition(ConditionOperator.AT_OR_BELOW, spot_max)
            confirmation = PriceCondition(ConditionOperator.AT_OR_BELOW, spot_max)
    else:  # WAIT FOR PULLBACK
        if direction == "BULLISH":
            trigger = PriceCondition(ConditionOperator.AT_OR_BELOW, spot_max)
            confirmation = PriceCondition(ConditionOperator.AT_OR_ABOVE, spot_min)
        else:
            trigger = PriceCondition(ConditionOperator.AT_OR_ABOVE, spot_min)
            confirmation = PriceCondition(ConditionOperator.AT_OR_BELOW, spot_max)

    invalidation = (
        PriceCondition(ConditionOperator.AT_OR_BELOW, invalidation_value)
        if direction == "BULLISH"
        else PriceCondition(ConditionOperator.AT_OR_ABOVE, invalidation_value)
    )

    expiry = intent.expiry or extract_expiry(intent.contract_symbol)
    if (intent.instrument_type or "OPTION").upper() in {"OPTION", "FUTURE"} and not expiry:
        return TopPicksEntryTranslation(False, "F&O contract expiry could not be derived from Suggested Option")

    trade_type = (intent.trade_type or "DAY").upper()
    if trade_type != "DAY":
        # This feeder currently targets the DayScanner Top Picks sheet. Other
        # horizons should come from a source that explicitly supplies them.
        return TopPicksEntryTranslation(False, f"This Top Picks entry translator currently supports DAY, got {trade_type}")

    kwargs = {
        "underlying": intent.underlying,
        "direction": direction,
        "trade_type": trade_type,
        "asset_class": _asset_class(intent.underlying),
        "instrument_type": (intent.instrument_type or "OPTION").upper(),
        "horizon_at": _day_horizon(observation.observed_at),
        "trigger": trigger,
        "confirmation": confirmation,
        "invalidation": invalidation,
        "expiry_date": expiry,
        "contract_symbol": clean_contract_symbol(intent.contract_symbol),
        "option_type": intent.option_type,
        "strike": intent.strike,
        "premium_min": premium_min,
        "premium_max": premium_max,
        "last_reason": (
            f"Top Picks {status}; source confirmation: "
            f"{str(raw.get('confirmation') or '').strip() or 'not supplied'}"
        ),
    }
    return TopPicksEntryTranslation(True, f"Armed from Top Picks status {status}", kwargs)
