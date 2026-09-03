"""TM3/TGT2 deterministic managed-position rule tests."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from trademonitor.domain.enums import (
    AssetClass,
    ConditionOperator,
    InstrumentType,
    ManagementRuleStatus,
    ManagementRuleType,
    ManagementSignal,
    TradeType,
)
from trademonitor.domain.models import (
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
    ManagementRuleSpec,
    PositionAdoptionRequest,
    PositionManagementSnapshot,
)
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository
from trademonitor.positions.manager import PositionManager, UnmanagedPositionError
from trademonitor.positions.rules import ManagementRuleEngine, ManagementRuleError


def _managed(tmp_path, *, qty: int = 100, avg: str = "100"):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    repo.initialize()
    pm = PositionManager(repo)
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    snap = BrokerAccountSnapshot.create(
        broker="MOCK",
        observed_at=at,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:X:NRML", exchange="NFO",
            symbol="X26SEP100CE", product="NRML", quantity=qty, average_price=avg,
            last_price=avg, observed_at=at,
        )],
    )
    pos = pm.reconcile(snap)[0][0]
    pos, profile, _ = pm.adopt(PositionAdoptionRequest(
        position_id=pos.position_id, asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION, trade_type=TradeType.POS,
        horizon_at=at + timedelta(days=7), expiry_date=date(2026, 9, 29),
        requested_at=at + timedelta(minutes=1), requested_by="USER", reason="manage",
    ))
    return repo, pm, ManagementRuleEngine(repo, pm), pos, profile, at


def _simple(rule_type, operator, value):
    return ManagementRuleSpec(
        rule_type=rule_type,
        parameters={"operator": operator.value, "value": str(value)},
        created_by="USER", reason="test",
    )


def test_unmanaged_boundary_blocks_rule_creation(tmp_path):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db")); repo.initialize()
    pm = PositionManager(repo); engine = ManagementRuleEngine(repo, pm)
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    pos = pm.reconcile(BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=at,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:Y", exchange="NFO", symbol="Y",
            product="NRML", quantity=1, average_price="10", observed_at=at,
        )],
    ))[0][0]
    with pytest.raises(UnmanagedPositionError):
        engine.add_rule(pos.position_id, _simple(ManagementRuleType.HARD_SL, ConditionOperator.AT_OR_BELOW, 8), created_at=at)


def test_hard_sl_tp_spot_pnl_and_invalidation_are_deterministic(tmp_path):
    _, _, engine, pos, _, at = _managed(tmp_path)
    specs = [
        _simple(ManagementRuleType.HARD_SL, ConditionOperator.AT_OR_BELOW, 90),
        _simple(ManagementRuleType.TAKE_PROFIT, ConditionOperator.AT_OR_ABOVE, 130),
        _simple(ManagementRuleType.SPOT_CONDITION, ConditionOperator.AT_OR_ABOVE, 5100),
        _simple(ManagementRuleType.PNL_CONDITION, ConditionOperator.AT_OR_ABOVE, 2500),
        _simple(ManagementRuleType.UNDERLYING_INVALIDATION, ConditionOperator.AT_OR_BELOW, 4900),
    ]
    rules = [engine.add_rule(pos.position_id, s, created_at=at + timedelta(minutes=2))[0] for s in specs]

    evals, events = engine.evaluate(pos.position_id, PositionManagementSnapshot.create(
        observed_at=at + timedelta(minutes=3), premium="130", underlying_price="5105", pnl="3000"
    ))
    by_type = {e.rule_type: e for e in evals}
    assert not by_type[ManagementRuleType.HARD_SL].triggered
    assert by_type[ManagementRuleType.TAKE_PROFIT].triggered
    assert by_type[ManagementRuleType.SPOT_CONDITION].triggered
    assert by_type[ManagementRuleType.PNL_CONDITION].triggered
    assert not by_type[ManagementRuleType.UNDERLYING_INVALIDATION].triggered
    assert all(e.signal == (ManagementSignal.EXIT_REVIEW if e.triggered else ManagementSignal.NONE) for e in evals)
    assert len([e for e in events if e.name == "POSITION_MANAGEMENT_RULE_TRIGGERED"]) == 3


def test_trailing_sl_arms_ratchets_and_triggers_for_long(tmp_path):
    _, _, engine, pos, _, at = _managed(tmp_path)
    rule, _ = engine.add_rule(pos.position_id, ManagementRuleSpec(
        rule_type=ManagementRuleType.TRAILING_SL,
        parameters={"trail_pct": "10", "activate_at_premium": "110"},
        created_by="USER", reason="trail winners",
    ), created_at=at + timedelta(minutes=2))

    e1, _ = engine.evaluate(pos.position_id, PositionManagementSnapshot.create(observed_at=at+timedelta(minutes=3), premium="105"))
    assert not e1[0].triggered
    assert engine.list_rules(position_id=pos.position_id)[0].status == ManagementRuleStatus.ACTIVE

    engine.evaluate(pos.position_id, PositionManagementSnapshot.create(observed_at=at+timedelta(minutes=4), premium="120"))
    armed = engine.list_rules(position_id=pos.position_id)[0]
    assert armed.status == ManagementRuleStatus.ARMED
    assert Decimal(armed.runtime_state["effective_stop"]) == Decimal("108")

    engine.evaluate(pos.position_id, PositionManagementSnapshot.create(observed_at=at+timedelta(minutes=5), premium="140"))
    ratcheted = engine.list_rules(position_id=pos.position_id)[0]
    assert Decimal(ratcheted.runtime_state["effective_stop"]) == Decimal("126")

    final, _ = engine.evaluate(pos.position_id, PositionManagementSnapshot.create(observed_at=at+timedelta(minutes=6), premium="125"))
    assert final[0].triggered
    assert engine.list_rules(position_id=pos.position_id)[0].status == ManagementRuleStatus.TRIGGERED


def test_profit_lock_arms_then_triggers_on_giveback(tmp_path):
    _, _, engine, pos, _, at = _managed(tmp_path)
    engine.add_rule(pos.position_id, ManagementRuleSpec(
        rule_type=ManagementRuleType.PROFIT_LOCK,
        parameters={"activate_pnl": "2000", "floor_pnl": "1000"},
        created_by="USER", reason="protect profit",
    ), created_at=at+timedelta(minutes=2))
    engine.evaluate(pos.position_id, PositionManagementSnapshot.create(observed_at=at+timedelta(minutes=3), pnl="2200"))
    assert engine.list_rules(position_id=pos.position_id)[0].status == ManagementRuleStatus.ARMED
    ev, _ = engine.evaluate(pos.position_id, PositionManagementSnapshot.create(observed_at=at+timedelta(minutes=4), pnl="900"))
    assert ev[0].triggered


def test_horizon_time_exit_and_policy_installation(tmp_path):
    _, _, engine, pos, profile, at = _managed(tmp_path)
    specs = [
        ManagementRuleSpec(rule_type=ManagementRuleType.HORIZON, parameters={}, created_by="USER", reason="horizon"),
        ManagementRuleSpec(rule_type=ManagementRuleType.TIME_EXIT, parameters={"at": (at+timedelta(hours=2)).isoformat()}, created_by="USER", reason="time"),
    ]
    rules, events = engine.install_policy(pos.position_id, "POS_STANDARD", specs, created_at=at+timedelta(minutes=2))
    assert len(rules) == 2
    assert {r.policy_name for r in rules} == {"POS_STANDARD"}
    assert any(e.name == "POSITION_MANAGEMENT_POLICY_INSTALLED" for e in events)
    before, _ = engine.evaluate(pos.position_id, PositionManagementSnapshot.create(observed_at=at+timedelta(hours=1)))
    assert not any(e.triggered for e in before)
    after_time, _ = engine.evaluate(pos.position_id, PositionManagementSnapshot.create(observed_at=at+timedelta(hours=3)))
    assert any(e.rule_type == ManagementRuleType.TIME_EXIT and e.triggered for e in after_time)
    # horizon rule remains active until actual trade horizon
    horizon_rule = next(r for r in engine.list_rules(position_id=pos.position_id, active_only=True) if r.rule_type == ManagementRuleType.HORIZON)
    assert horizon_rule.status == ManagementRuleStatus.ACTIVE
    horizon_eval, _ = engine.evaluate(pos.position_id, PositionManagementSnapshot.create(observed_at=profile.horizon_at))
    assert any(e.rule_type == ManagementRuleType.HORIZON and e.triggered for e in horizon_eval)


def test_invalid_rule_specs_fail_before_activation(tmp_path):
    _, _, engine, pos, _, at = _managed(tmp_path)
    with pytest.raises(ManagementRuleError):
        engine.add_rule(pos.position_id, ManagementRuleSpec(
            rule_type=ManagementRuleType.TRAILING_SL, parameters={"trail_pct": "0"},
            created_by="USER", reason="bad",
        ), created_at=at)
    with pytest.raises(ManagementRuleError):
        engine.add_rule(pos.position_id, ManagementRuleSpec(
            rule_type=ManagementRuleType.PROFIT_LOCK,
            parameters={"activate_pnl": "1000", "floor_pnl": "1500"},
            created_by="USER", reason="bad",
        ), created_at=at)

def test_trailing_sl_handles_short_position_direction(tmp_path):
    _, _, engine, pos, _, at = _managed(tmp_path, qty=-100, avg="100")
    engine.add_rule(pos.position_id, ManagementRuleSpec(
        rule_type=ManagementRuleType.TRAILING_SL,
        parameters={"trail_pct": "10", "activate_at_premium": "90"},
        created_by="USER", reason="trail short",
    ), created_at=at+timedelta(minutes=2))
    engine.evaluate(pos.position_id, PositionManagementSnapshot.create(
        observed_at=at+timedelta(minutes=3), premium="90"
    ))
    armed = engine.list_rules(position_id=pos.position_id)[0]
    assert armed.status == ManagementRuleStatus.ARMED
    assert Decimal(armed.runtime_state["effective_stop"]) == Decimal("99")
    engine.evaluate(pos.position_id, PositionManagementSnapshot.create(
        observed_at=at+timedelta(minutes=4), premium="80"
    ))
    ratcheted = engine.list_rules(position_id=pos.position_id)[0]
    assert Decimal(ratcheted.runtime_state["effective_stop"]) == Decimal("88")
    final, _ = engine.evaluate(pos.position_id, PositionManagementSnapshot.create(
        observed_at=at+timedelta(minutes=5), premium="89"
    ))
    assert final[0].triggered


def test_rule_cancel_is_durable_and_removes_from_active_evaluation(tmp_path):
    _, _, engine, pos, _, at = _managed(tmp_path)
    rule, _ = engine.add_rule(pos.position_id, _simple(
        ManagementRuleType.HARD_SL, ConditionOperator.AT_OR_BELOW, 90
    ), created_at=at+timedelta(minutes=2))
    cancelled, events = engine.cancel_rule(
        rule.rule_id, at=at+timedelta(minutes=3), cancelled_by="USER", reason="replace SL"
    )
    assert cancelled.status == ManagementRuleStatus.CANCELLED
    assert [e.name for e in events] == ["POSITION_MANAGEMENT_RULE_CANCELLED"]
    evaluations, _ = engine.evaluate(pos.position_id, PositionManagementSnapshot.create(
        observed_at=at+timedelta(minutes=4), premium="80"
    ))
    assert evaluations == []
