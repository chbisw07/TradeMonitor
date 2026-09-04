"""Read the scanner's Google Sheet ``Top Picks`` layout and feed TM Intake.

This is a PAPER-only integration harness.  It deliberately absorbs the workbook-
specific layout (title rows, row-4 headers, side-by-side CE/PE tables, blank
separator columns) at the adapter boundary.  TradeMonitor core never sees or
depends on those worksheet details.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
from pathlib import Path
import re
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from trademonitor.adapters import (  # noqa: E402
    FeederState,
    GoogleSheetConfig,
    GoogleSheetConfigurationError,
    GoogleSheetDependencyError,
    GoogleSheetRow,
    GoogleTopPicksAdapter,
    load_dotenv_file,
)
from trademonitor.app import build_manager  # noqa: E402


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Feed Google Top Picks into TradeMonitor Intake")
    parser.add_argument("--env-file", default=".env", help="dotenv file to load (default: .env)")
    parser.add_argument("--sheet-name", help="override GOOGLE_SHEET_NAME")
    parser.add_argument("--limit", type=int, default=0, help="maximum candidates to process; 0 = all")
    parser.add_argument("--dry-run", action="store_true", help="read/map/print only; do not write TM or feeder state")
    parser.add_argument("--force", action="store_true", help="feed candidates even when unchanged since last successful run")
    parser.add_argument("--show-raw", action="store_true", help="print complete source candidate for diagnostics")
    return parser.parse_args()


def _short(value: object, width: int = 34) -> str:
    text = "-" if value in (None, "") else str(value)
    return text if len(text) <= width else text[: width - 1] + "…"


def _norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower()).strip()


def _unique_headers(values: list[Any], *, prefix: str) -> list[str]:
    """Make a block's headers usable without changing the source worksheet."""
    result: list[str] = []
    seen: dict[str, int] = {}
    for idx, raw in enumerate(values, start=1):
        base = str(raw or "").strip() or f"__COL_{idx}"
        key = _norm(base) or f"col {idx}"
        seen[key] = seen.get(key, 0) + 1
        suffix = f"__{seen[key]}" if seen[key] > 1 else ""
        result.append(f"{prefix}_{base}{suffix}")
    return result


def _value_by_header(payload: dict[str, Any], wanted: str) -> Any:
    wanted_n = _norm(wanted)
    for key, value in payload.items():
        # Remove CE_/PE_ namespace before comparing the source heading.
        heading = key.split("_", 1)[1] if "_" in key else key
        heading = re.sub(r"__\d+$", "", heading)
        if _norm(heading) == wanted_n:
            return value
    return None


def _find_header_row(values: list[list[Any]]) -> tuple[int, int]:
    """Return (zero-based row index, zero-based PE-table start column)."""
    for row_idx, row in enumerate(values[:20]):
        normalized = [_norm(cell) for cell in row]
        if "ce rank" in normalized and "pe rank" in normalized:
            return row_idx, normalized.index("pe rank")
    raise GoogleSheetConfigurationError(
        "Top Picks layout not recognized: could not find a header row containing both 'CE Rank' and 'PE Rank'"
    )


def _read_top_picks_rows(config: GoogleSheetConfig) -> tuple[list[GoogleSheetRow], int, int, int]:
    """Read the real side-by-side Top Picks layout into virtual TM source rows.

    One physical worksheet row may produce two virtual rows: one CE candidate and
    one PE candidate.  Each receives a side-specific src_id so the two ideas can
    never collide merely because they share the same Google row number.
    """
    if not config.service_account_file.exists():
        raise GoogleSheetConfigurationError(
            f"Google service-account file not found: {config.service_account_file}"
        )
    try:
        import gspread  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise GoogleSheetDependencyError(
            "Google Sheet support is optional. Install it with: pip install -e '.[google]'"
        ) from exc

    client = gspread.service_account(filename=str(config.service_account_file))
    workbook = client.open_by_key(config.spreadsheet_id)
    worksheet = workbook.worksheet(config.sheet_name)
    matrix = worksheet.get_all_values()
    if not matrix:
        return [], 0, 0, 0

    header_idx, pe_start = _find_header_row(matrix)
    header = matrix[header_idx]

    # CE is everything before PE Rank.  Blank separator columns are harmless and
    # ignored later.  PE begins exactly at the detected PE Rank column.
    ce_headers_raw = header[:pe_start]
    pe_headers_raw = header[pe_start:]
    ce_headers = _unique_headers(ce_headers_raw, prefix="CE")
    pe_headers = _unique_headers(pe_headers_raw, prefix="PE")

    sheet_token = hashlib.sha256(
        f"{config.spreadsheet_id}:{config.sheet_name}".encode()
    ).hexdigest()[:10].upper()

    virtual_rows: list[GoogleSheetRow] = []
    ce_count = 0
    pe_count = 0

    for physical_idx in range(header_idx + 1, len(matrix)):
        row = list(matrix[physical_idx])
        if len(row) < len(header):
            row.extend([""] * (len(header) - len(row)))
        physical_row_number = physical_idx + 1

        for side, start, raw_headers, headers in (
            ("CE", 0, ce_headers_raw, ce_headers),
            ("PE", pe_start, pe_headers_raw, pe_headers),
        ):
            width = len(raw_headers)
            cells = row[start : start + width]
            if len(cells) < width:
                cells.extend([""] * (width - len(cells)))
            payload = dict(zip(headers, cells, strict=False))

            stock = _value_by_header(payload, "Stock")
            rank = _value_by_header(payload, f"{side} Rank")
            suggested = _value_by_header(payload, "Suggested Option")
            if not str(stock or "").strip():
                continue

            # Canonical aliases consumed by GoogleTopPicksAdapter.  All original
            # source columns remain in payload for provenance/audit.
            payload.update(
                {
                    "src_id": f"GS-{sheet_token}-R{physical_row_number}-{side}",
                    "underlying": str(stock).strip(),
                    "direction": "BULLISH" if side == "CE" else "BEARISH",
                    "option_type": side,
                    "setup": config.default_setup,
                    "trade_type": config.default_trade_type,
                    "instrument_type": config.default_instrument_type,
                    "contract_symbol": str(suggested).strip() if suggested is not None else "",
                    "premium": str(_value_by_header(payload, "Premium Entry Zone") or "").strip(),
                    "reference_price": str(_value_by_header(payload, "Spot Entry Zone") or "").strip(),
                    "context_key": f"{config.sheet_name}:R{physical_row_number}:{side}:rank={rank or '-'}",
                    # Extra source intelligence stays adapter-local/raw for now.
                    "entry_status": _value_by_header(payload, "Entry Status"),
                    "confirmation": _value_by_header(payload, "Confirmation"),
                    "invalidation": _value_by_header(payload, "Invalidation"),
                    "score": _value_by_header(payload, f"{side} Score"),
                    "option_quality": _value_by_header(payload, "Option Quality"),
                    "atr_pct": _value_by_header(payload, "ATR%"),
                    "move_atr": _value_by_header(payload, "Move/ATR"),
                    "rank": rank,
                }
            )

            virtual_rows.append(GoogleSheetRow(row_number=physical_row_number, values=payload))
            if side == "CE":
                ce_count += 1
            else:
                pe_count += 1

    return virtual_rows, header_idx + 1, ce_count, pe_count


def main() -> int:
    args = _args()
    load_dotenv_file(args.env_file)

    try:
        config = GoogleSheetConfig.from_env()
    except GoogleSheetConfigurationError as exc:
        print(f"CONFIG ERROR: {exc}", file=sys.stderr)
        return 2
    if args.sheet_name:
        from dataclasses import replace
        config = replace(config, sheet_name=args.sheet_name)

    print("TradeMonitor Google Top Picks feeder")
    print("------------------------------------")
    print(f"Sheet      : {config.sheet_name}")
    print(f"Source     : {config.source_name}")
    print(f"Mode       : {'DRY RUN' if args.dry_run else 'PAPER INTAKE'}")
    print("Broker write: DISABLED (this feeder has no broker path)")

    try:
        rows, detected_header_row, ce_count, pe_count = _read_top_picks_rows(config)
    except (GoogleSheetConfigurationError, GoogleSheetDependencyError) as exc:
        print(f"GOOGLE ERROR: {exc}", file=sys.stderr)
        return 3
    except Exception as exc:  # external service errors should be concise at CLI boundary
        print(f"GOOGLE READ FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    print(f"Layout     : header row {detected_header_row}; side-by-side CE/PE tables")
    print(f"Candidates : CE={ce_count}  PE={pe_count}  Total={len(rows)}")

    adapter = GoogleTopPicksAdapter(config)
    fallback = datetime.now(UTC)
    try:
        prepared = adapter.prepare_rows(rows, fallback_observed_at=fallback)
    except ValueError as exc:
        print(f"MAPPING ERROR: {exc}", file=sys.stderr)
        return 5

    if args.limit > 0:
        prepared = prepared[: args.limit]

    state = FeederState(config.state_file)
    selected = []
    unchanged = 0
    for item in prepared:
        state_key = (
            f"{config.spreadsheet_id}:{config.sheet_name}:"
            f"{item.row_number}:{item.observation.src_id}"
        )
        if not args.force and state.unchanged(state_key, item.fingerprint):
            unchanged += 1
            continue
        selected.append((item, state_key))

    print(f"Rows mapped : {len(prepared)}")
    print(f"Unchanged   : {unchanged}")
    print(f"To process  : {len(selected)}")
    print()

    for item, _state_key in selected:
        intent = item.observation.intent
        raw = dict(item.observation.raw_payload)
        print(
            f"R{item.row_number:<4} {_short(intent.underlying,12):<12} "
            f"{_short(intent.direction,8):<8} {_short(intent.trade_type,5):<5} "
            f"{_short(intent.option_type,3):<3} {_short(intent.contract_symbol)}"
        )
        print(
            f"      src={item.observation.src_id}  setup={intent.setup}  "
            f"observed={item.observation.observed_at.isoformat()}"
        )
        print(
            f"      status={_short(raw.get('entry_status'),18)}  "
            f"spot-zone={_short(intent.reference_price,18)}  "
            f"premium-zone={_short(intent.premium,18)}  "
            f"invalid={_short(raw.get('invalidation'),14)}"
        )
        print(f"      confirm={_short(raw.get('confirmation'),76)}")
        if args.show_raw:
            print(f"      raw={raw}")

    if args.dry_run:
        print("\nDRY RUN complete — TradeMonitor state was not changed.")
        return 0

    manager = build_manager()
    manager.start()
    try:
        accepted = 0
        for item, state_key in selected:
            result = manager.ingest_trade_observation(**item.observation.submit_kwargs())
            accepted += 1
            print(
                f"INGEST R{item.row_number}: {result.disposition.value} | "
                f"outcome={result.outcome.outcome_id} | episode={result.episode.episode_id}"
            )
            state.remember(state_key, item.fingerprint)
        state.save()
        counts = manager.intake_snapshot()
        print("\nTM Intake totals:")
        print(
            f"  observations={counts.get('observations', 0)}  "
            f"outcomes={counts.get('outcomes', 0)}  "
            f"active_episodes={counts.get('active_episodes', 0)}"
        )
        print(f"Successfully processed: {accepted}")
    finally:
        manager.stop()

    print("\nPAPER intake complete. No broker operation was possible from this feeder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
