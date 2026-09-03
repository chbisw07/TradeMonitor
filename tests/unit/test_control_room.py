"""Control-room rendering tests for TM1/TGT3."""

from trademonitor.console.ui import ConsoleUI
from trademonitor.domain.models import AttentionItem
from datetime import UTC, datetime


def test_control_room_shows_health_positions_and_attention() -> None:
    item = AttentionItem(
        attention_id="a1",
        level="CRITICAL",
        source="BROKER",
        title="Broker unavailable",
        detail="New broker-dependent actions suspended",
        status="OPEN",
        created_at=datetime.now(UTC),
    )
    rendered = ConsoleUI().render_control_room(
        {
            "contexts": {
                "health": {
                    "version": 1,
                    "updated_at": "now",
                    "data": {
                        "core": "HEALTHY",
                        "runtime": "STARTED",
                        "execution_mode": "PAPER",
                        "live_execution_enabled": False,
                        "domains": {
                            "CORE": {"status": "HEALTHY", "summary": "operational", "impact": [], "capabilities": {}},
                            "BROKER": {"status": "UNAVAILABLE", "summary": "down", "impact": ["reads stale"], "capabilities": {"broker_reads": "UNAVAILABLE"}},
                        },
                    },
                }
            },
            "positions": [],
            "attention": [item],
        }
    )
    assert "Mode: PAPER" in rendered
    assert "BROKER       UNAVAILABLE" in rendered
    assert "Positions" in rendered
    assert "Attention" in rendered
    assert "Broker unavailable" in rendered
