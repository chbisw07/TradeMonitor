"""Tests for the TM1 console status rendering."""

from trademonitor.console.ui import ConsoleUI


def test_console_makes_live_execution_disabled_explicit() -> None:
    rendered = ConsoleUI().render_status(
        {
            "health": {
                "version": 1,
                "updated_at": "now",
                "data": {
                    "core": "HEALTHY",
                    "runtime": "STARTED",
                    "live_execution_enabled": False,
                },
            }
        }
    )

    assert "Live execution: DISABLED" in rendered
    assert "NO LIVE TRADING CAPABILITY" in rendered
