"""Professional console/control-room views for the TM1 runtime."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from trademonitor.domain.models import AttentionItem, PositionRecord


class ConsoleUI:
    """Render concise runtime state without owning business logic."""

    def render_status(self, snapshot: Mapping[str, Mapping[str, Any]]) -> str:
        lines = ["TradeMonitor TM2/TGT3", "=" * 72]
        health = snapshot.get("health", {}).get("data", {})
        broker = snapshot.get("broker", {}).get("data", {})
        positions = snapshot.get("position", {}).get("data", {})
        lines.append(
            "Core: {core} | Runtime: {runtime} | Mode: {mode} | Live execution: {live}".format(
                core=health.get("core", "UNKNOWN"),
                runtime=health.get("runtime", "UNKNOWN"),
                mode=health.get("execution_mode", "PAPER"),
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
        intake = snapshot.get("trade", {}).get("data", {}).get("intake", {})
        lines.append(
            "Intake: Observations {observations} | Outcomes {outcomes} | Active Episodes {episodes}".format(
                observations=intake.get("observations", 0),
                outcomes=intake.get("outcomes", 0),
                episodes=intake.get("active_episodes", 0),
            )
        )
        entry = snapshot.get("trade", {}).get("data", {}).get("entry_monitoring", {})
        states = entry.get("by_state", {})
        state_text = ", ".join(f"{name}={count}" for name, count in sorted(states.items())) or "none"
        lines.append(f"Entry: Active {entry.get('active', 0)} | States: {state_text}")
        reviews = snapshot.get("trade", {}).get("data", {}).get("entry_agent_reviews", {})
        review_states = reviews.get("by_status", {})
        review_text = ", ".join(
            f"{name}={count}" for name, count in sorted(review_states.items())
        ) or "none"
        lines.append(
            f"Agent Reviews: Total {reviews.get('total', 0)} | Status: {review_text}"
        )
        lines.append("")
        lines.append("Domain Health")
        domains = health.get("domains", {})
        if not domains:
            lines.append("- no domain health reports")
        else:
            for name in sorted(domains):
                report = domains[name]
                lines.append(
                    f"- {name:<12} {report.get('status', 'UNKNOWN'):<11} "
                    f"{report.get('summary', '')}"
                )
                for impact in report.get("impact", []):
                    lines.append(f"    impact: {impact}")
                for capability, state in sorted(report.get("capabilities", {}).items()):
                    lines.append(f"    {capability}: {state}")
        lines.append("")
        lines.append("Runtime Contexts")
        for name in sorted(snapshot):
            ctx = snapshot[name]
            lines.append(
                f"- {name:<9} v{ctx.get('version', 0):<3} updated={ctx.get('updated_at', 'n/a')}"
            )
        lines.append("")
        lines.append("BROKER ACCESS IS READ-ONLY — NO LIVE TRADING CAPABILITY")
        return "\n".join(lines)

    def render_positions(self, positions: Sequence[PositionRecord]) -> str:
        lines = ["Positions", "=" * 96]
        if not positions:
            lines.append("No broker positions known to TradeMonitor.")
            return "\n".join(lines)

        lines.append(
            f"{'SYMBOL':<30} {'BROKER':<10} {'QTY':>8} {'AVG':>11} {'LTP':>11} {'MGMT':<10} {'STATE':<8}"
        )
        lines.append("-" * 96)
        for position in positions:
            ltp = "-" if position.last_price is None else str(position.last_price)
            lines.append(
                f"{position.symbol:<30} {position.broker:<10} {position.quantity:>8} "
                f"{str(position.average_price):>11} {ltp:>11} "
                f"{position.management_status.value:<10} {position.state.value:<8}"
            )
        return "\n".join(lines)

    def render_attention(self, items: Sequence[AttentionItem]) -> str:
        lines = ["Attention", "=" * 96]
        if not items:
            lines.append("No open attention items.")
            return "\n".join(lines)
        lines.append(f"{'LEVEL':<10} {'SOURCE':<12} {'TITLE':<34} DETAIL")
        lines.append("-" * 96)
        for item in items:
            lines.append(
                f"{item.level:<10} {item.source:<12} {item.title:<34} {item.detail}"
            )
        return "\n".join(lines)

    def render_control_room(self, snapshot: Mapping[str, Any]) -> str:
        """Render one coherent operator view: health, positions, attention."""
        return "\n\n".join(
            [
                self.render_status(snapshot.get("contexts", {})),
                self.render_positions(snapshot.get("positions", [])),
                self.render_attention(snapshot.get("attention", [])),
            ]
        )
