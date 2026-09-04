from datetime import UTC, datetime

import pytest

from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import ExecutionMode
from trademonitor.execution.readiness import AutoReadinessEvidence, AutoReadinessError, AutoReadinessGate
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def _manager(tmp_path, *, mode=ExecutionMode.PAPER, real=False, auto=False):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    tm = CoreTMManager(
        repo,
        execution_mode=mode,
        allow_real_broker_writes=real,
        allow_auto_execution=auto,
    )
    return tm


def _complete_evidence():
    return AutoReadinessEvidence(
        semi_auto_sessions=3,
        semi_auto_real_executions=3,
        unresolved_reconciliation_defects=0,
        duplicate_execution_defects=0,
        restart_recovery_validated=True,
        risk_management_validated=True,
        position_exit_validated=True,
        agent_degradation_validated=True,
        operating_safeguards_validated=True,
        note="reviewed evidence pack",
    )


def test_default_auto_readiness_is_not_ready(tmp_path):
    tm = _manager(tmp_path); tm.start()
    report = tm.auto_readiness_snapshot()
    assert report["assessment"]["ready"] is False
    assert "sufficient_semi_auto_sessions" in report["assessment"]["blockers"]


def test_complete_evidence_becomes_ready_but_does_not_enable_auto(tmp_path):
    tm = _manager(tmp_path); tm.start()
    report = tm.record_auto_readiness_evidence(
        _complete_evidence(), recorded_by="USER", at=datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    )
    assert report["assessment"]["ready"] is True
    assert report["decision"]["enabled"] is False


def test_auto_enable_requires_ready_evidence_and_exact_confirmation(tmp_path):
    tm = _manager(tmp_path); tm.start()
    with pytest.raises(AutoReadinessError, match="not READY"):
        tm.decide_auto_enable(
            enable=True, decided_by="USER", reason="go", confirmation="ENABLE AUTO"
        )
    tm.record_auto_readiness_evidence(_complete_evidence(), recorded_by="USER")
    with pytest.raises(AutoReadinessError, match="exactly ENABLE AUTO"):
        tm.decide_auto_enable(enable=True, decided_by="USER", reason="go", confirmation="YES")
    result = tm.decide_auto_enable(
        enable=True, decided_by="USER", reason="evidence reviewed", confirmation="ENABLE AUTO"
    )
    assert result["decision"]["enabled"] is True


def test_changed_evidence_revokes_prior_auto_decision(tmp_path):
    tm = _manager(tmp_path); tm.start()
    tm.record_auto_readiness_evidence(_complete_evidence(), recorded_by="USER")
    tm.decide_auto_enable(enable=True, decided_by="USER", reason="ok", confirmation="ENABLE AUTO")
    degraded = AutoReadinessEvidence(**{
        **_complete_evidence().to_record(),
        "unresolved_reconciliation_defects": 1,
    })
    report = tm.record_auto_readiness_evidence(degraded, recorded_by="SYSTEM")
    assert report["assessment"]["ready"] is False
    assert report["decision"]["enabled"] is False


def test_auto_mode_start_requires_persisted_decision_and_both_arms(tmp_path):
    tm = _manager(tmp_path); tm.start()
    tm.record_auto_readiness_evidence(_complete_evidence(), recorded_by="USER")
    tm.decide_auto_enable(enable=True, decided_by="USER", reason="accepted", confirmation="ENABLE AUTO")
    tm.stop()

    blocked = _manager(tmp_path, mode=ExecutionMode.AUTO, real=True, auto=False)
    with pytest.raises(AutoReadinessError, match="TM_ALLOW_AUTO_EXECUTION"):
        blocked.start()

    allowed = _manager(tmp_path, mode=ExecutionMode.AUTO, real=True, auto=True)
    allowed.start()
    assert allowed.status_snapshot()["health"]["data"]["execution_mode"] == "AUTO"


def test_auto_evidence_decision_survives_restart(tmp_path):
    tm = _manager(tmp_path); tm.start()
    tm.record_auto_readiness_evidence(_complete_evidence(), recorded_by="USER")
    tm.decide_auto_enable(enable=True, decided_by="USER", reason="accepted", confirmation="ENABLE AUTO")
    tm.stop()
    restarted = _manager(tmp_path); restarted.start()
    report = restarted.auto_readiness_snapshot()
    assert report["assessment"]["ready"] is True
    assert report["decision"]["enabled"] is True


def test_gate_minimums_are_repetition_floors():
    evidence = _complete_evidence()
    assert AutoReadinessGate.assess(evidence).ready
    too_few = AutoReadinessEvidence(**{**evidence.to_record(), "semi_auto_real_executions": 2})
    assert not AutoReadinessGate.assess(too_few).ready
