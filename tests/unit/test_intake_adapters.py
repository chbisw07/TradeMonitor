from datetime import datetime, timezone

from trademonitor.adapters import MappingTradeAdapter


def test_canonical_mapping_adapter_uses_source_neutral_contract():
    adapter = MappingTradeAdapter()
    obs = adapter.from_mapping(
        {
            "underlying": "KAYNES",
            "direction": "BULLISH",
            "setup": "BREAKOUT",
            "trade_type": "DAY",
            "instrument_type": "OPTION",
            "option_type": "CE",
            "contract_symbol": "KAYNES26SEP4200CE",
            "expiry": "2026-09-29",
            "strike": "4200",
            "premium": "145.50",
        },
        src_id="PY-1",
        source="PYTHON",
        observed_at=datetime(2026, 9, 4, 9, 30, tzinfo=timezone.utc),
    )

    assert obs.intent.underlying == "KAYNES"
    assert obs.intent.trade_type == "DAY"
    assert obs.intent.contract_symbol == "KAYNES26SEP4200CE"
    assert obs.submit_kwargs()["source"] == "PYTHON"


def test_arbitrary_external_schema_is_resolved_only_in_adapter():
    adapter = MappingTradeAdapter(
        {
            "underlying": "ticker",
            "direction": "bias",
            "setup": "entry_style",
            "trade_type": "holding",
            "instrument_type": "instrument",
            "option_type": "right",
            "contract_symbol": "contract",
            "expiry": "contract_expiry",
            "strike": "strike_px",
            "premium": "ltp",
        }
    )

    obs = adapter.from_mapping(
        {
            "ticker": "PNB",
            "bias": "bullish",
            "entry_style": "pullback",
            "holding": "btst",
            "instrument": "option",
            "right": "ce",
            "contract": "PNB26SEP117CE",
            "contract_expiry": "2026-09-29",
            "strike_px": "117",
            "ltp": "4.85",
            "whatever_else": "kept only as provenance",
        },
        src_id="FRIEND-SYSTEM-77",
        source="CUSTOM_APP",
        observed_at=datetime(2026, 9, 4, 10, 15, tzinfo=timezone.utc),
    )

    assert obs.intent.underlying == "PNB"
    assert obs.intent.direction == "BULLISH"
    assert obs.intent.setup == "PULLBACK"
    assert obs.intent.trade_type == "BTST"
    assert obs.intent.option_type == "CE"
    assert obs.raw_payload["whatever_else"] == "kept only as provenance"
