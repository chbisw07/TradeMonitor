"""Minimal professional console view for TM1/TGT1."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class ConsoleUI:
    """Render a concise runtime status view without owning business logic."""

    def render_status(self, snapshot: Mapping[str, Mapping[str, Any]]) -> str:
        lines = ["TradeMonitor TM1/TGT1", "=" * 42]
        health = snapshot.get("health", {}).get("data", {})
        lines.append(
            "Core: {core} | Runtime: {runtime} | Live execution: {live}".format(
                core=health.get("core", "UNKNOWN"),
                runtime=health.get("runtime", "UNKNOWN"),
                live="ENABLED" if health.get("live_execution_enabled") else "DISABLED",
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
        lines.append("NO LIVE TRADING CAPABILITY")
        return "\n".join(lines)
