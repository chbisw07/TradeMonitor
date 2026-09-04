"""Generic intake-adapter primitives.

This module deliberately knows nothing about Google Sheets, DayScanner,
Positional Scanner, or any other concrete producer. A concrete adapter maps its
own payload into :class:`CanonicalTradeObservation`, then hands that object to
TradeMonitor's public intake boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from trademonitor.domain.models import NormalizedTradeIntent


@dataclass(frozen=True)
class CanonicalTradeObservation:
    """Source-neutral observation accepted by TradeMonitor intake."""

    src_id: str
    source: str
    observed_at: datetime
    intent: NormalizedTradeIntent
    raw_payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.src_id.strip():
            raise ValueError("src_id is required")
        if not self.source.strip():
            raise ValueError("source is required")

    def submit_kwargs(self) -> dict[str, Any]:
        """Return kwargs compatible with CoreTMManager.ingest_trade_observation."""
        return {
            "src_id": self.src_id,
            "source": self.source,
            "observed_at": self.observed_at,
            "intent": self.intent,
            "raw_payload": dict(self.raw_payload),
        }


class MappingTradeAdapter:
    """Translate an arbitrary mapping into the canonical TM intake contract.

    ``field_map`` maps canonical intent field names to external payload keys.
    This intentionally small adapter demonstrates the architectural boundary:
    source-specific naming is resolved here, never inside TM core domains.
    """

    _INTENT_FIELDS = (
        "underlying",
        "direction",
        "setup",
        "trade_type",
        "instrument_type",
        "option_type",
        "contract_symbol",
        "expiry",
        "strike",
        "premium",
        "reference_price",
        "context_key",
    )

    def __init__(self, field_map: Mapping[str, str] | None = None) -> None:
        mapping = dict(field_map or {})
        unknown = sorted(set(mapping) - set(self._INTENT_FIELDS))
        if unknown:
            raise ValueError(f"Unsupported canonical field(s): {', '.join(unknown)}")
        self._field_map = mapping

    def from_mapping(
        self,
        payload: Mapping[str, Any],
        *,
        src_id: str,
        source: str,
        observed_at: datetime,
    ) -> CanonicalTradeObservation:
        intent_values: dict[str, Any] = {}
        for canonical in self._INTENT_FIELDS:
            external_key = self._field_map.get(canonical, canonical)
            if external_key in payload:
                intent_values[canonical] = payload.get(external_key)

        intent = NormalizedTradeIntent(**intent_values)
        return CanonicalTradeObservation(
            src_id=src_id,
            source=source,
            observed_at=observed_at,
            intent=intent,
            raw_payload=dict(payload),
        )
