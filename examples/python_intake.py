"""Example: feed a custom Python payload into TradeMonitor's canonical intake.

This example is documentation only; it does not place or simulate a broker order.
"""

from datetime import datetime, timezone

from trademonitor.adapters import MappingTradeAdapter


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

payload = {
    "ticker": "KAYNES",
    "bias": "BULLISH",
    "entry_style": "BREAKOUT",
    "holding": "DAY",
    "instrument": "OPTION",
    "right": "CE",
    "contract": "KAYNES26SEP4200CE",
    "contract_expiry": "2026-09-29",
    "strike_px": "4200",
    "ltp": "145.50",
}

observation = adapter.from_mapping(
    payload,
    src_id="MYAPP-001",
    source="MY_CUSTOM_APP",
    observed_at=datetime.now(timezone.utc),
)

# With a started CoreTMManager named `tm`:
# result = tm.ingest_trade_observation(**observation.submit_kwargs())
print(observation)
