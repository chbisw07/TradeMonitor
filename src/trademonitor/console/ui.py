"""Professional console views for the TM1 runtime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from trademonitor.domain.models import PositionRecord


class ConsoleUI:
    """Render concise runtime/position status without owning business logic."""

    def render_status(self, snapshot: Mapping[str, Mapping[str, Any]]) -> str:
        lines = ["TradeMonitor TM1/TGT2", "=" * 48]
        health = snapshot.get("health", {}).get("data", {})
        broker = snapshot.get("broker", {}).get("data", {})
        positions = snapshot.get("position", {}).get("data", {})
        lines.append(
            "Core: {core} | Runtime: {runtime} | Live execution: {live}".format(
                core=health.get("core", "UNKNOWN"),
                runtime=health.get("runtime", "UNKNOWN"),
                live="ENABLED" if health.get("live_execution_enabled") else "DISABLED",
            )
        )
        lines.append(
            "Broker: {status} | Open positions: {open} | Managed: {managed} | Unmanaged: {unmanaged}".format(
                status=broker.get("status", "NOT_RECONCILED"),
                open=positions.get("open", 0),
                managed=positions.get("managed_open", 0),
                unmanaged=positions.get("unmanaged_open", 0),
            )
        )
        lines.append("")
        lines.append("Runtime Contexts")
        for name in sorted(snapshot):
            ctx = snapshot[name]
            lines.append(
                f"- {name:<9} v{ctx.get('version', 0):<3} "
                f"updated={ctx.get('updated_at', 'n/a')}"
            )
        lines.append("")
        lines.append("BROKER ACCESS IS READ-ONLY — NO LIVE TRADING CAPABILITY")
        return "\n".join(lines)

    def render_positions(self, positions: Sequence[PositionRecord]) -> str:
        lines = ["Positions", "=" * 86]
        if not positions:
            lines.append("No broker positions known to TradeMonitor.")
            return "\n".join(lines)

        lines.append(
            f"{'SYMBOL':<28} {'BROKER':<9} {'QTY':>8} {'AVG':>10} {'MGMT':<10} {'STATE':<8}"
        )
        lines.append("-" * 86)
        for position in positions:
            lines.append(
                f"{position.symbol:<28} {position.broker:<9} {position.quantity:>8} "
                f"{str(position.average_price):>10} {position.management_status.value:<10} "
                f"{position.state.value:<8}"
            )
        return "\n".join(lines)
