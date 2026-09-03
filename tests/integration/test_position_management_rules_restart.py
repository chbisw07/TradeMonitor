"""TM3/TGT2 restart persistence for management rules and runtime state."""

from datetime import UTC, date, datetime, timedelta

from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import AssetClass, InstrumentType, ManagementRuleStatus, ManagementRuleType, TradeType
from trademonitor.domain.models import BrokerAccountSnapshot, BrokerPositionSnapshot, ManagementRuleSpec, PositionAdoptionRequest, PositionManagementSnapshot
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def _core(path):
    c = CoreTMManager(SQLiteRuntimeRepository(Database(path)))
    c.start(); return c


def test_rule_and_trailing_runtime_state_survive_restart(tmp_path):
    db = tmp_path / "tm.db"
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    snapshot = BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=at,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:X", exchange="NFO", symbol="X26SEP100CE",
            product="NRML", quantity=100, average_price="100", last_price="100", observed_at=at,
        )],
    )
    core = _core(db)
    positions = core.reconcile_broker_truth(MockBroker(snapshot=snapshot))
    pos = positions[0]
    core.adopt_position(PositionAdoptionRequest(
        position_id=pos.position_id, asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION, trade_type=TradeType.POS,
        horizon_at=at+timedelta(days=7), expiry_date=date(2026,9,29),
        requested_at=at+timedelta(minutes=1), requested_by="USER", reason="manage",
    ))
    rule = core.add_position_management_rule(pos.position_id, ManagementRuleSpec(
        rule_type=ManagementRuleType.TRAILING_SL,
        parameters={"trail_pct":"10", "activate_at_premium":"110"},
        created_by="USER", reason="trail",
    ), created_at=at+timedelta(minutes=2))
    core.evaluate_position_management(pos.position_id, PositionManagementSnapshot.create(
        observed_at=at+timedelta(minutes=3), premium="120"
    ))
    before = core.position_management_rules_snapshot(position_id=pos.position_id)[0]
    assert before.status == ManagementRuleStatus.ARMED
    assert before.runtime_state["effective_stop"] == "108.0"
    core.stop()

    restored = _core(db)
    after = restored.position_management_rules_snapshot(position_id=pos.position_id)[0]
    assert after.rule_id == rule.rule_id
    assert after.status == ManagementRuleStatus.ARMED
    assert after.runtime_state["effective_stop"] == "108.0"
    ctx = restored.status_snapshot()["position"]["data"]["management_rules"]
    assert ctx["active"] == 1
