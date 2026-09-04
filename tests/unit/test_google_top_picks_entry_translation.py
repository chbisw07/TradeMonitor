from datetime import datetime, timezone

from trademonitor.adapters import CanonicalTradeObservation, translate_top_pick_to_entry
from trademonitor.domain.enums import ConditionOperator
from trademonitor.domain.models import NormalizedTradeIntent


def obs(*, direction="BULLISH", status="BUY ON CONFIRM", spot="544.28–545.34", premium="₹12.42–₹14.35", invalid="541.86"):
    return CanonicalTradeObservation(
        src_id="SRC1",
        source="GOOGLE_TOP_PICKS",
        observed_at=datetime(2026, 9, 4, 6, 0, tzinfo=timezone.utc),
        intent=NormalizedTradeIntent(
            underlying="HDFCLIFE",
            direction=direction,
            setup="TOP_PICK",
            trade_type="DAY",
            instrument_type="OPTION",
            option_type="CE" if direction == "BULLISH" else "PE",
            contract_symbol="2026-09-29 545 CE @ 13.50 | Δ 0.561",
            expiry="2026-09-29",
            strike="545",
            premium=premium,
            reference_price=spot,
        ),
        raw_payload={
            "entry_status": status,
            "confirmation": "15m bullish hold/reversal",
            "invalidation": invalid,
        },
    )


def test_buy_on_confirm_bullish_maps_to_directional_entry_conditions():
    result = translate_top_pick_to_entry(obs())
    assert result.arm
    kw = dict(result.kwargs or {})
    assert kw["trigger"].operator == ConditionOperator.AT_OR_ABOVE
    assert str(kw["trigger"].value) == "544.28"
    assert kw["confirmation"].operator == ConditionOperator.AT_OR_ABOVE
    assert kw["invalidation"].operator == ConditionOperator.AT_OR_BELOW
    assert str(kw["premium_min"]) == "12.42"
    assert str(kw["premium_max"]) == "14.35"
    assert kw["expiry_date"] == "2026-09-29"
    assert kw["contract_symbol"] == "2026-09-29 545 CE"


def test_wait_for_pullback_bullish_waits_for_upper_zone_then_holds_lower_zone():
    result = translate_top_pick_to_entry(obs(status="WAIT FOR PULLBACK", spot="3408.65–3430.32", invalid="3381.55"))
    assert result.arm
    kw = dict(result.kwargs or {})
    assert kw["trigger"].operator == ConditionOperator.AT_OR_BELOW
    assert str(kw["trigger"].value) == "3430.32"
    assert kw["confirmation"].operator == ConditionOperator.AT_OR_ABOVE
    assert str(kw["confirmation"].value) == "3408.65"


def test_buy_on_confirm_bearish_maps_inverse_conditions():
    result = translate_top_pick_to_entry(obs(direction="BEARISH", spot="14139.11–14179.03", invalid="14269.75"))
    assert result.arm
    kw = dict(result.kwargs or {})
    assert kw["trigger"].operator == ConditionOperator.AT_OR_BELOW
    assert str(kw["trigger"].value) == "14179.03"
    assert kw["confirmation"].operator == ConditionOperator.AT_OR_BELOW
    assert kw["invalidation"].operator == ConditionOperator.AT_OR_ABOVE


def test_avoid_chase_is_kept_in_intake_but_not_armed():
    result = translate_top_pick_to_entry(obs(status="AVOID CHASE"))
    assert not result.arm
    assert result.kwargs is None


def test_unknown_status_is_not_guessed():
    result = translate_top_pick_to_entry(obs(status="MAYBE"))
    assert not result.arm
    assert "no verified deterministic mapping" in result.reason
