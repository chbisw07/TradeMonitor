"""Strict Zerodha read-only connection and TradeMonitor reconciliation check.

This tool intentionally constructs ZerodhaReadOnlyBroker, which implements only
TM's Broker truth contract. It has no order placement/modification/cancellation
capability. Use this before enabling any SEMI_AUTO execution path.
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
from trademonitor.brokers.zerodha import ZerodhaReadOnlyBroker
from trademonitor.config.settings import Settings


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


def parse_args():
    p = argparse.ArgumentParser(
        description="TradeMonitor Zerodha strict read-only connection/reconciliation check"
    )
    p.add_argument("--env-file", default=".env")
    p.add_argument(
        "--no-persist",
        action="store_true",
        help="fetch/print Zerodha truth without reconciling it into TradeMonitor",
    )
    return p.parse_args()


def _money(value) -> str:
    return "-" if value is None else str(value)


def print_snapshot(snapshot) -> None:
    print("\nZERODHA READ-ONLY BROKER TRUTH")
    print("=" * 92)
    print(f"Observed at : {snapshot.observed_at.isoformat()}")
    print(f"Broker      : {snapshot.broker}")
    print(f"Open rows   : {len(snapshot.positions)}")
    print(f"Orders      : {_money(snapshot.order_count)}")
    print(f"Trades/fills: {_money(snapshot.fill_count)}")
    if snapshot.funds is not None:
        print(f"Available   : {_money(snapshot.funds.available_cash)}")
        print(f"Used margin : {_money(snapshot.funds.used_margin)}")
        print(f"Net value   : {_money(snapshot.funds.net_value)}")
    print("\nPositions")
    print("-" * 92)
    if not snapshot.positions:
        print("No open Zerodha net positions.")
    for p in snapshot.positions:
        print(
            f"{p.exchange:<5} {p.symbol:<32} {p.product:<6} "
            f"qty={p.quantity:<7} avg={p.average_price} ltp={_money(p.last_price)}"
        )


def main() -> int:
    a = parse_args()
    load_env(a.env_file)

    # Hard operational invariant for this stage: this command never arms writes.
    os.environ["TM_ALLOW_REAL_BROKER_WRITES"] = "false"

    broker = ZerodhaReadOnlyBroker.from_env()
    snapshot = broker.fetch_account_snapshot()
    print_snapshot(snapshot)

    if a.no_persist:
        print("\nREAD-ONLY CHECK PASSED: no broker-write capability was constructed.")
        return 0

    settings = Settings.from_env()
    tm = build_manager(settings)
    tm.start()
    try:
        positions = tm.reconcile_broker_truth(broker)
        open_positions = [p for p in positions if p.is_open]
        managed = [p for p in open_positions if p.is_managed]
        unmanaged = [p for p in open_positions if not p.is_managed]
        print("\nTRADEMONITOR RECONCILIATION")
        print("=" * 92)
        print(f"Open canonical positions : {len(open_positions)}")
        print(f"MANAGED                  : {len(managed)}")
        print(f"UNMANAGED                : {len(unmanaged)}")
        for p in unmanaged:
            print(f"UNMANAGED -> {p.broker_position_key} qty={p.quantity} origin={p.origin.value}")
        print("\nREAD-ONLY RECONCILIATION PASSED: broker writes remain disabled.")
        return 0
    finally:
        tm.stop()


if __name__ == "__main__":
    raise SystemExit(main())
