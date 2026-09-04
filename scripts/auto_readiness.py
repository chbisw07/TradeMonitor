#!/usr/bin/env python3
"""TM4/TGT4 AUTO-readiness operator utility.

This utility records/reviews evidence and the explicit AUTO enable decision.
It never talks to a broker and never places/modifies/cancels an order.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from trademonitor.core.manager import CoreTMManager
from trademonitor.execution.readiness import AutoReadinessEvidence, AutoReadinessError
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def _manager(db: Path) -> CoreTMManager:
    tm = CoreTMManager(SQLiteRuntimeRepository(Database(db)))
    tm.start()
    return tm


def _print_report(report: dict) -> None:
    evidence = report.get("evidence", {})
    assessment = report.get("assessment", {})
    decision = report.get("decision", {})
    print("TRADEMONITOR TM4/TGT4 — AUTO READINESS")
    print("=" * 78)
    print(f"Readiness : {'READY' if assessment.get('ready') else 'NOT READY'}")
    print(f"Decision  : {decision.get('status', 'NOT_DECIDED')}")
    print(f"Enabled   : {bool(decision.get('enabled'))}")
    print()
    print("Evidence")
    print("-" * 78)
    for key in (
        "semi_auto_sessions", "semi_auto_real_executions",
        "unresolved_reconciliation_defects", "duplicate_execution_defects",
        "restart_recovery_validated", "risk_management_validated",
        "position_exit_validated", "agent_degradation_validated",
        "operating_safeguards_validated", "recorded_by", "recorded_at", "note",
    ):
        print(f"{key:<38} {evidence.get(key, '')}")
    print()
    print("Checks")
    print("-" * 78)
    for name, passed in assessment.get("checks", {}).items():
        print(f"{'PASS' if passed else 'BLOCK':<6} {name}")
    if assessment.get("blockers"):
        print("\nAUTO remains blocked by: " + ", ".join(assessment["blockers"]))
    else:
        print("\nReadiness checks pass. AUTO still requires an explicit ENABLE AUTO decision and runtime arming.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect/record TradeMonitor AUTO-readiness evidence")
    parser.add_argument("--db", default="data/trademonitor.db")
    parser.add_argument("--record", metavar="JSON_FILE", help="Record evidence from a JSON file")
    parser.add_argument("--recorded-by", default="USER")
    parser.add_argument("--enable", action="store_true", help="Record explicit AUTO enable decision")
    parser.add_argument("--disable", action="store_true", help="Record explicit AUTO disabled decision")
    parser.add_argument("--reason", default="")
    parser.add_argument("--confirmation", default="", help='Must be exactly "ENABLE AUTO" or "KEEP AUTO DISABLED"')
    args = parser.parse_args()
    if args.enable and args.disable:
        parser.error("choose only one of --enable or --disable")

    tm = _manager(Path(args.db))
    try:
        if args.record:
            raw = json.loads(Path(args.record).read_text(encoding="utf-8"))
            evidence = AutoReadinessEvidence.from_mapping(raw)
            tm.record_auto_readiness_evidence(evidence, recorded_by=args.recorded_by)
        if args.enable or args.disable:
            tm.decide_auto_enable(
                enable=args.enable,
                decided_by=args.recorded_by,
                reason=args.reason,
                confirmation=args.confirmation,
            )
        _print_report(tm.auto_readiness_snapshot())
        return 0
    except (AutoReadinessError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 2
    finally:
        tm.stop()


if __name__ == "__main__":
    raise SystemExit(main())
