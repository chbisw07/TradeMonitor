"""TM1/TGT3 health and fault-containment tests."""

from pathlib import Path

from trademonitor.core.health import DomainHealthReport, FaultReport
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import HealthStatus
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def _manager(tmp_path: Path) -> CoreTMManager:
    return CoreTMManager(SQLiteRuntimeRepository(Database(tmp_path / "tm.db")))


def test_horizontal_domain_health_is_reported_without_collapsing_core(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    manager.start()
    manager.report_domain_health(
        DomainHealthReport.create(
            "AGENTS",
            HealthStatus.UNAVAILABLE,
            "Agent service unavailable",
            impact=("agent-assisted review unavailable",),
            capabilities={"agent_review": "UNAVAILABLE"},
        )
    )

    health = manager.contexts.get("health").data
    assert health["domains"]["AGENTS"]["status"] == "UNAVAILABLE"
    assert health["domains"]["CORE"]["status"] == "HEALTHY"
    manager.stop()


def test_vertical_fault_is_contained_at_nearest_owner_when_resolved(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    manager.start()
    manager.report_fault(
        FaultReport.create(
            component="OPTION_CHAIN_CLIENT",
            owner_domain="ENTRY",
            summary="Transient option-chain timeout",
            local_action="Use cached snapshot and retry later",
            resolved_locally=True,
            impact=("one refresh skipped",),
        )
    )

    events = manager.events_snapshot()
    contained = [e for e in events if e["name"] == "DOMAIN_FAULT_CONTAINED"]
    assert contained[-1]["payload"]["owner_domain"] == "ENTRY"
    assert contained[-1]["payload"]["resolved_locally"] is True
    manager.stop()


def test_unresolved_vertical_fault_escalates_summary_upward(tmp_path: Path) -> None:
    manager = _manager(tmp_path)
    manager.start()
    manager.report_fault(
        FaultReport.create(
            component="ENTRY_CHILD",
            owner_domain="ENTRY",
            summary="Entry child cannot continue safely",
            local_action="Suspend affected entry capability",
            resolved_locally=False,
            impact=("new entries unavailable",),
            escalate_to="CORE",
        )
    )

    report = manager.contexts.get("health").data["domains"]["ENTRY"]
    assert report["status"] == "DEGRADED"
    assert report["parent"] == "CORE"
    assert report["escalated_from"] == "ENTRY_CHILD"
    manager.stop()
