"""Recovery/replay helpers for TM1/TGT4.

These helpers deliberately stay free of trading logic. They provide stable
state comparison and freshness classification so PAPER recovery/replay tests
can prove that the coordinating core converges to the same coherent state.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Mapping, Sequence

from trademonitor.domain.models import PositionRecord


class FreshnessRelation(StrEnum):
    """Relation of an incoming observation to the last accepted observation."""

    FIRST = "FIRST"
    NEWER = "NEWER"
    REPLAY = "REPLAY"
    STALE = "STALE"


def compare_observation_time(
    incoming: datetime, previous: datetime | None
) -> FreshnessRelation:
    if previous is None:
        return FreshnessRelation.FIRST
    if incoming > previous:
        return FreshnessRelation.NEWER
    if incoming == previous:
        return FreshnessRelation.REPLAY
    return FreshnessRelation.STALE


def runtime_fingerprint(
    contexts: Mapping[str, Mapping[str, Any]], positions: Sequence[PositionRecord]
) -> str:
    """Return a stable fingerprint of business-relevant TM1 runtime state.

    Context versions/update timestamps are intentionally excluded: replay may
    legitimately create additional audit activity while still converging to the
    exact same business state. Position update timestamps are excluded for the
    same reason. Position identity/provenance/management boundaries are kept.
    """

    context_data = {
        name: _stable_value(record.get("data", {}))
        for name, record in sorted(contexts.items())
    }
    position_data = [
        {
            "position_id": p.position_id,
            "broker": p.broker,
            "broker_position_key": p.broker_position_key,
            "exchange": p.exchange,
            "symbol": p.symbol,
            "product": p.product,
            "quantity": p.quantity,
            "average_price": str(p.average_price),
            "state": p.state.value,
            "management_status": p.management_status.value,
            "origin": p.origin.value,
            "last_price": None if p.last_price is None else str(p.last_price),
            "realized_pnl": None if p.realized_pnl is None else str(p.realized_pnl),
            "unrealized_pnl": None if p.unrealized_pnl is None else str(p.unrealized_pnl),
            "instrument_token": p.instrument_token,
        }
        for p in sorted(positions, key=lambda p: (p.broker, p.broker_position_key))
    ]
    payload = {"contexts": context_data, "positions": position_data}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _stable_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        # Runtime bookkeeping fields that are expected to change on restart or
        # repeated reconciliation are not business-state identity.
        ignored = {"observed_at"}
        return {
            str(key): _stable_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in ignored
        }
    if isinstance(value, (list, tuple)):
        return [_stable_value(item) for item in value]
    return value
