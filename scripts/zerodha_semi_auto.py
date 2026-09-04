"""Operator-controlled Zerodha SEMI_AUTO console for TM4/TGT3.

This script is deliberately not a daemon and never auto-selects a trade. It only
operates on durable ExecutionRequests already produced by TradeMonitor.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from trademonitor.app import build_manager
from trademonitor.brokers.zerodha import ZerodhaExecutionBroker
from trademonitor.config.settings import Settings
from trademonitor.domain.enums import ExecutionRequestStatus


def load_env(path: str = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def args():
    p = argparse.ArgumentParser(description="TradeMonitor Zerodha SEMI_AUTO operator console")
    p.add_argument("--env-file", default=".env")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--list", action="store_true")
    g.add_argument("--request-approval", metavar="REQUEST_ID")
    g.add_argument("--approve", metavar="REQUEST_ID")
    g.add_argument("--reject", metavar="REQUEST_ID")
    g.add_argument("--deploy", metavar="REQUEST_ID")
    g.add_argument("--reconcile-order", metavar="REQUEST_ID")
    g.add_argument("--cancel", metavar="REQUEST_ID")
    p.add_argument("--reason", default="controlled SEMI_AUTO forward test")
    p.add_argument("--confirm", help="APPROVE or REJECT for User decision")
    p.add_argument("--confirm-deploy", help="must equal: DEPLOY <REQUEST_ID>")
    p.add_argument("--confirm-cancel", help="must equal: CANCEL <REQUEST_ID>")
    return p.parse_args()


def show(tm):
    rows = tm.execution_snapshot()
    approvals = {a.request_id: a for a in tm.execution_approval_snapshot()}
    print("\nExecution Requests")
    print("-" * 110)
    if not rows:
        print("No execution requests.")
        return
    for r in rows:
        a = approvals.get(r.request_id)
        print(
            f"{r.request_id} | {r.purpose.value:<5} | {r.symbol:<28} | {r.side.value:<4} "
            f"| qty={r.quantity:<6} | {r.status.value:<17} | approval={a.status.value if a else '-'}"
        )


def main() -> int:
    a = args(); load_env(a.env_file)
    settings = Settings.from_env()
    tm = build_manager(settings); tm.start()
    try:
        broker = ZerodhaExecutionBroker.from_env()
        # Read-only current broker truth is refreshed on every invocation.
        tm.reconcile_broker_truth(broker)

        if not any([a.request_approval, a.approve, a.reject, a.deploy, a.reconcile_order, a.cancel]):
            show(tm); return 0
        if a.request_approval:
            item = tm.request_semi_auto_execution_approval(
                a.request_approval, requested_by="USER", reason=a.reason
            )
            print(f"Approval requested: {item.approval_id} status={item.status.value}")
            return 0
        if a.approve or a.reject:
            request_id = a.approve or a.reject
            approve = bool(a.approve)
            expected = "APPROVE" if approve else "REJECT"
            if (a.confirm or "").strip().upper() != expected:
                print(f"REFUSED: --confirm must be exactly {expected}", file=sys.stderr); return 2
            item = tm.resolve_semi_auto_execution_approval(
                request_id, approve=approve, decided_by="USER", reason=a.reason,
                confirmation=expected,
            )
            print(f"User decision: {item.status.value} for {request_id}")
            return 0
        if a.deploy:
            if a.confirm_deploy != f"DEPLOY {a.deploy}":
                print(f"REFUSED: --confirm-deploy must be exactly 'DEPLOY {a.deploy}'", file=sys.stderr); return 2
            request = tm.deploy_execution_request(a.deploy, broker)
            print(f"Broker deployment result: {request.status.value} order={request.broker_order_id or '-'}")
            return 0
        if a.reconcile_order:
            request = tm.reconcile_execution_request(a.reconcile_order, broker)
            print(f"Broker truth: {request.status.value} filled={request.filled_quantity}/{request.quantity}")
            return 0
        if a.cancel:
            if a.confirm_cancel != f"CANCEL {a.cancel}":
                print(f"REFUSED: --confirm-cancel must be exactly 'CANCEL {a.cancel}'", file=sys.stderr); return 2
            request = tm.cancel_execution_request(a.cancel, broker)
            print(f"Cancel result: {request.status.value}")
            return 0
        show(tm); return 0
    finally:
        tm.stop()


if __name__ == "__main__":
    raise SystemExit(main())
