"""Optional Google Sheets intake adapter.

This module is deliberately outside TradeMonitor core domains.  It knows about
Google Sheets and a convenient "Top Picks" style source, then converts rows into
the source-neutral :class:`CanonicalTradeObservation` contract.

The core Intake/Entry/Risk/Position domains never import this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from trademonitor.adapters.intake import CanonicalTradeObservation
from trademonitor.domain.models import NormalizedTradeIntent


class GoogleSheetConfigurationError(ValueError):
    """Raised when the optional Google Sheet adapter is not configured."""


class GoogleSheetDependencyError(RuntimeError):
    """Raised when optional Google packages have not been installed."""


def load_dotenv_file(path: str | Path = ".env", *, override: bool = False) -> bool:
    """Load a small .env file without making python-dotenv a core dependency.

    Only KEY=VALUE lines are supported.  Quotes around values are stripped.  The
    function intentionally does not attempt shell expansion or advanced dotenv
    syntax because this adapter only needs a few simple settings.
    """

    env_path = Path(path)
    if not env_path.exists():
        return False
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key and (override or key not in os.environ):
            os.environ[key] = value
    return True


@dataclass(frozen=True)
class GoogleSheetConfig:
    spreadsheet_id: str
    service_account_file: Path
    sheet_name: str = "Top Picks"
    header_row: int = 1
    source_name: str = "GOOGLE_TOP_PICKS"
    default_setup: str = "TOP_PICK"
    default_trade_type: str = "DAY"
    default_instrument_type: str = "OPTION"
    state_file: Path = Path("data/google_top_picks_state.json")

    @classmethod
    def from_env(cls) -> "GoogleSheetConfig":
        spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
        service_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip()
        if not spreadsheet_id:
            raise GoogleSheetConfigurationError("GOOGLE_SPREADSHEET_ID is required")
        if not service_file:
            raise GoogleSheetConfigurationError("GOOGLE_SERVICE_ACCOUNT_FILE is required")
        header = os.getenv("GOOGLE_SHEET_HEADER_ROW", "1").strip() or "1"
        return cls(
            spreadsheet_id=spreadsheet_id,
            service_account_file=Path(service_file).expanduser(),
            sheet_name=os.getenv("GOOGLE_SHEET_NAME", "Top Picks").strip() or "Top Picks",
            header_row=int(header),
            source_name=os.getenv("GOOGLE_SOURCE_NAME", "GOOGLE_TOP_PICKS").strip() or "GOOGLE_TOP_PICKS",
            default_setup=os.getenv("GOOGLE_TOP_PICKS_DEFAULT_SETUP", "TOP_PICK").strip() or "TOP_PICK",
            default_trade_type=os.getenv("GOOGLE_TOP_PICKS_DEFAULT_TRADE_TYPE", "DAY").strip() or "DAY",
            default_instrument_type=os.getenv("GOOGLE_TOP_PICKS_DEFAULT_INSTRUMENT_TYPE", "OPTION").strip() or "OPTION",
            state_file=Path(os.getenv("GOOGLE_FEEDER_STATE_FILE", "data/google_top_picks_state.json")).expanduser(),
        )


@dataclass(frozen=True)
class GoogleSheetRow:
    row_number: int
    values: Mapping[str, Any]


@dataclass(frozen=True)
class PreparedGoogleObservation:
    observation: CanonicalTradeObservation
    row_number: int
    fingerprint: str
    skipped_reason: str | None = None


class GoogleSheetReader:
    """Read-only Google Sheets client using optional gspread dependency."""

    def __init__(self, config: GoogleSheetConfig) -> None:
        self._config = config

    def read_rows(self) -> list[GoogleSheetRow]:
        if not self._config.service_account_file.exists():
            raise GoogleSheetConfigurationError(
                f"Google service-account file not found: {self._config.service_account_file}"
            )
        try:
            import gspread  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise GoogleSheetDependencyError(
                "Google Sheet support is optional. Install it with: pip install -e '.[google]'"
            ) from exc

        client = gspread.service_account(filename=str(self._config.service_account_file))
        workbook = client.open_by_key(self._config.spreadsheet_id)
        worksheet = workbook.worksheet(self._config.sheet_name)
        records = worksheet.get_all_records(head=self._config.header_row, default_blank="")
        first_data_row = self._config.header_row + 1
        return [
            GoogleSheetRow(row_number=first_data_row + idx, values=dict(row))
            for idx, row in enumerate(records)
            if any(str(value).strip() for value in row.values())
        ]


class FeederState:
    """Adapter-local state used only to avoid re-feeding unchanged Sheet rows."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._fingerprints: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        rows = payload.get("rows", {}) if isinstance(payload, dict) else {}
        if isinstance(rows, dict):
            self._fingerprints = {str(k): str(v) for k, v in rows.items()}

    def unchanged(self, key: str, fingerprint: str) -> bool:
        return self._fingerprints.get(key) == fingerprint

    def remember(self, key: str, fingerprint: str) -> None:
        self._fingerprints[key] = fingerprint

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "updated_at": datetime.now(UTC).isoformat(),
            "rows": dict(sorted(self._fingerprints.items())),
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


class GoogleTopPicksAdapter:
    """Map a flexible Top Picks-style row into TM canonical intake.

    Header aliases are intentionally adapter-local.  Users with a different sheet
    can either configure another adapter or reuse the generic MappingTradeAdapter.
    """

    _ALIASES: dict[str, tuple[str, ...]] = {
        "src_id": ("src_id", "source id", "source_id", "src", "id"),
        "underlying": ("underlying", "symbol", "stock", "instrument", "ticker"),
        "direction": ("direction", "bias", "side", "view", "trade direction"),
        "setup": ("setup", "entry setup", "entry style", "signal", "strategy"),
        "trade_type": ("trade type", "trade_type", "holding", "holding type"),
        "instrument_type": ("instrument type", "instrument_type", "security type"),
        "option_type": ("option type", "option_type", "right", "ce/pe", "ce pe"),
        "contract_symbol": (
            "suggested option", "option contract", "contract", "contract symbol",
            "option", "suggested contract",
        ),
        "expiry": ("expiry", "expiry date", "contract expiry"),
        "strike": ("strike", "strike price"),
        "premium": ("premium", "option premium", "premium entry", "premium entry zone"),
        "reference_price": ("spot", "spot price", "underlying ltp", "ltp", "reference price"),
        "context_key": ("context key", "context_key", "scan id", "run id", "batch id"),
        "observed_at": (
            "timestamp", "observed at", "observed_at", "datetime", "date time",
            "generated at", "scan time", "run time",
        ),
        "enabled": ("enabled", "active", "include", "monitor", "selected"),
    }

    def __init__(self, config: GoogleSheetConfig) -> None:
        self.config = config

    @staticmethod
    def _norm_header(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()

    def _index(self, row: Mapping[str, Any]) -> dict[str, Any]:
        return {self._norm_header(key): value for key, value in row.items()}

    def _get(self, index: Mapping[str, Any], field: str) -> Any:
        for alias in self._ALIASES[field]:
            key = self._norm_header(alias)
            if key in index and str(index[key]).strip():
                return index[key]
        return None

    @staticmethod
    def _option_type(text: Any) -> str | None:
        if text is None:
            return None
        value = str(text).upper()
        match = re.search(r"(?:^|\s)(CE|PE)(?:\s|$)", value)
        if match:
            return match.group(1)
        if value.strip() in {"CALL", "C"}:
            return "CE"
        if value.strip() in {"PUT", "P"}:
            return "PE"
        return None

    @staticmethod
    def _direction(value: Any, option_type: str | None) -> str | None:
        if value is not None:
            text = str(value).strip().upper()
            if text in {"BULLISH", "BUY", "LONG", "UP", "CE", "CALL"}:
                return "BULLISH"
            if text in {"BEARISH", "SELL", "SHORT", "DOWN", "PE", "PUT"}:
                return "BEARISH"
            if text:
                return text
        if option_type == "CE":
            return "BULLISH"
        if option_type == "PE":
            return "BEARISH"
        return None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if value is None or not str(value).strip():
            return None
        text = str(value).strip()
        # ISO first, including trailing Z.
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            pass
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d-%b-%Y %I:%M:%S %p",
            "%d-%b-%Y %I:%M %p",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
        ):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
        return None

    @staticmethod
    def _truthy_selected(value: Any) -> bool:
        if value is None or str(value).strip() == "":
            return True
        return str(value).strip().upper() not in {"0", "NO", "N", "FALSE", "OFF", "DISABLED", "SKIP"}

    @staticmethod
    def _extract_strike(contract: str | None) -> str | None:
        if not contract:
            return None
        match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:CE|PE)\b", contract.upper())
        return match.group(1) if match else None

    def _src_id(self, index: Mapping[str, Any], row_number: int) -> str:
        explicit = self._get(index, "src_id")
        if explicit is not None:
            return str(explicit).strip()
        sheet_token = hashlib.sha256(
            f"{self.config.spreadsheet_id}:{self.config.sheet_name}".encode()
        ).hexdigest()[:10].upper()
        return f"GS-{sheet_token}-R{row_number}"

    def prepare_row(
        self,
        row: GoogleSheetRow,
        *,
        fallback_observed_at: datetime | None = None,
    ) -> PreparedGoogleObservation | None:
        index = self._index(row.values)
        if not self._truthy_selected(self._get(index, "enabled")):
            return None

        underlying = self._get(index, "underlying")
        contract = self._get(index, "contract_symbol")
        option_type = self._option_type(self._get(index, "option_type")) or self._option_type(contract)
        direction = self._direction(self._get(index, "direction"), option_type)
        if underlying is None:
            raise ValueError(f"Row {row.row_number}: underlying/symbol is required")
        if direction is None:
            raise ValueError(
                f"Row {row.row_number}: direction is required and could not be inferred from CE/PE"
            )

        setup = self._get(index, "setup") or self.config.default_setup
        observed_at = self._parse_datetime(self._get(index, "observed_at")) or fallback_observed_at or datetime.now(UTC)
        strike = self._get(index, "strike") or self._extract_strike(str(contract) if contract is not None else None)

        intent = NormalizedTradeIntent(
            underlying=str(underlying),
            direction=str(direction),
            setup=str(setup),
            trade_type=str(self._get(index, "trade_type") or self.config.default_trade_type),
            instrument_type=str(self._get(index, "instrument_type") or self.config.default_instrument_type),
            option_type=str(option_type) if option_type else None,
            contract_symbol=str(contract).strip() if contract is not None else None,
            expiry=str(self._get(index, "expiry")).strip() if self._get(index, "expiry") is not None else None,
            strike=str(strike).strip() if strike is not None else None,
            premium=str(self._get(index, "premium")).strip() if self._get(index, "premium") is not None else None,
            reference_price=str(self._get(index, "reference_price")).strip() if self._get(index, "reference_price") is not None else None,
            context_key=str(self._get(index, "context_key")).strip() if self._get(index, "context_key") is not None else None,
        )
        src_id = self._src_id(index, row.row_number)
        observation = CanonicalTradeObservation(
            src_id=src_id,
            source=self.config.source_name,
            observed_at=observed_at,
            intent=intent,
            raw_payload=dict(row.values),
        )
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "src_id": src_id,
                    "intent": intent.to_record(),
                    "raw_payload": dict(row.values),
                },
                sort_keys=True,
                default=str,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return PreparedGoogleObservation(
            observation=observation,
            row_number=row.row_number,
            fingerprint=fingerprint,
        )

    def prepare_rows(
        self,
        rows: Iterable[GoogleSheetRow],
        *,
        fallback_observed_at: datetime | None = None,
    ) -> list[PreparedGoogleObservation]:
        prepared: list[PreparedGoogleObservation] = []
        for row in rows:
            item = self.prepare_row(row, fallback_observed_at=fallback_observed_at)
            if item is not None:
                prepared.append(item)
        return prepared
