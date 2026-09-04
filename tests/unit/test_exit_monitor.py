"""TM3/TGT3 Exit Monitor and position-evolution tests."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from trademonitor.domain.enums import (
    AssetClass,
    ConditionOperator,
    ExitAction,
    ExitProposalClass,
    ExitProposalStatus,
    InstrumentType,
    ManagementRuleType,
    TradeType,
)
from trademonitor.domain.models import (
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
    ManagementRuleSpec,
    PositionAdoptionRequest,
    PositionConversionRequest,
    PositionManagementSnapshot,
)
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository
from trademonitor.positions.exit import ExitMonitor, ExitMonitorError
from trademonitor.positions.manager import PositionManager, UnmanagedPositionError
from trademonitor.positions.rules import ManagementRuleEngine


def _setup(tmp_path, *, trade_type=TradeType.DAY):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db")); repo.initialize()
    pm = PositionManager(repo); rules = ManagementRuleEngine(repo, pm); exits = ExitMonitor(repo, pm)
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    snap = BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=at,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:X", exchange="NFO",
            symbol="X26SEP100CE", product="NRML", quantity=100,
            average_price="100", last_price="100", observed_at=at,
        )],
    )
    pos = pm.reconcile(snap)[0][0]
    pos, profile, _ = pm.adopt(PositionAdoptionRequest(
        position_id=pos.position_id, asset_class=AssetClass.EQUITY,
        instrument_type=InstrumentType.OPTION, trade_type=trade_type,
        horizon_at=at+timedelta(days=7), expiry_date=date(2026,9,29),
        requested_at=at+timedelta(minutes=1), requested_by="USER", reason="manage",
    ))
    return repo, pm, rules, exits, pos, profile, at


def test_triggered_rule_becomes_exit_proposal(tmp_path):
    _, _, rules, exits, pos, _, at = _setup(tmp_path)
    rule, _ = rules.add_rule(pos.position_id, ManagementRuleSpec(
        rule_type=ManagementRuleType.HARD_SL,
        parameters={"operator": ConditionOperator.AT_OR_BELOW.value, "value": "90"},
        created_by="USER", reason="protect",
    ), created_at=at+timedelta(minutes=2))
    evaluations, _ = rules.evaluate(pos.position_id, PositionManagementSnapshot.create(
        observed_at=at+timedelta(minutes=3), premium="85"
    ))
    proposals, events = exits.consume_rule_evaluations(
        pos.position_id, evaluations, at=at+timedelta(minutes=3)
    )
    assert len(proposals) == 1
    assert proposals[0].proposal_class == ExitProposalClass.PROTECTIVE
    assert proposals[0].action == ExitAction.EXIT_ALL
    assert rule.rule_id in proposals[0].trigger_rule_ids
    assert any(e.name == "EXIT_PROPOSAL_CREATED" for e in events)


def test_duplicate_full_exit_triggers_coalesce(tmp_path):
    _, _, _, exits, pos, _, at = _setup(tmp_path)
    first, _ = exits.propose_exit(
        pos.position_id, proposal_class=ExitProposalClass.DETERMINISTIC,
        action=ExitAction.EXIT_ALL, at=at+timedelta(minutes=2),
        created_by="POLICY", reason="target reached",
    )
    second, events = exits.propose_exit(
        pos.position_id, proposal_class=ExitProposalClass.STRATEGIC,
        action=ExitAction.EXIT_ALL, at=at+timedelta(minutes=3),
        created_by="USER", reason="exit now",
    )
    assert second.proposal_id == first.proposal_id
    assert set(second.reasons) == {"target reached", "exit now"}
    assert [e.name for e in events] == ["EXIT_TRIGGER_COALESCED"]
    assert len(exits.list_proposals(active_only=True)) == 1


def test_partial_exit_shapes_are_native_and_validated(tmp_path):
    _, _, _, exits, pos, _, at = _setup(tmp_path)
    q, _ = exits.propose_exit(
        pos.position_id, proposal_class=ExitProposalClass.STRATEGIC,
        action=ExitAction.EXIT_QTY, requested_quantity=40,
        at=at+timedelta(minutes=2), created_by="USER", reason="book partial",
    )
    p, _ = exits.propose_exit(
        pos.position_id, proposal_class=ExitProposalClass.STRATEGIC,
        action=ExitAction.EXIT_PERCENT, requested_percent=Decimal("25"),
        at=at+timedelta(minutes=3), created_by="USER", reason="book more",
    )
    assert q.requested_quantity == 40
    assert p.requested_percent == Decimal("25")
    with pytest.raises(ExitMonitorError):
        exits.propose_exit(
            pos.position_id, proposal_class=ExitProposalClass.STRATEGIC,
            action=ExitAction.EXIT_QTY, requested_quantity=101,
            at=at+timedelta(minutes=4), created_by="USER", reason="bad",
        )


def test_day_end_protection_and_deliberate_conversion(tmp_path):
    _, _, _, exits, pos, profile, at = _setup(tmp_path, trade_type=TradeType.DAY)
    cutoff = at + timedelta(hours=8)
    assert exits.day_end_review(pos.position_id, at=cutoff-timedelta(seconds=1), cutoff_at=cutoff)[0] is None
    proposal, _ = exits.day_end_review(pos.position_id, at=cutoff, cutoff_at=cutoff)
    assert proposal is not None
    assert "DAY end-of-day" in proposal.reasons[0]

    converted, events = exits.convert_position(PositionConversionRequest(
        position_id=pos.position_id, new_trade_type=TradeType.POS,
        new_horizon_at=at+timedelta(days=10), requested_at=at+timedelta(hours=1),
        requested_by="USER", reason="carry positionally",
    ))
    assert converted.trade_type == TradeType.POS
    assert converted.horizon_at > profile.horizon_at
    assert [e.name for e in events] == ["POSITION_TRADE_TYPE_CONVERTED"]


def test_unmanaged_position_cannot_get_exit_proposal(tmp_path):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db")); repo.initialize()
    pm = PositionManager(repo); exits = ExitMonitor(repo, pm)
    at = datetime(2026, 9, 4, 5, 0, tzinfo=UTC)
    pos = pm.reconcile(BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=at,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:U", exchange="NFO", symbol="U",
            product="NRML", quantity=1, average_price="10", observed_at=at,
        )],
    ))[0][0]
    with pytest.raises(UnmanagedPositionError):
        exits.propose_exit(
            pos.position_id, proposal_class=ExitProposalClass.STRATEGIC,
            action=ExitAction.EXIT_ALL, at=at, created_by="USER", reason="try",
        )


def test_full_exit_suppresses_competing_partial_paths(tmp_path):
    _, _, _, exits, pos, _, at = _setup(tmp_path)
    partial, _ = exits.propose_exit(
        pos.position_id, proposal_class=ExitProposalClass.STRATEGIC,
        action=ExitAction.EXIT_PERCENT, requested_percent="50",
        at=at+timedelta(minutes=2), created_by="USER", reason="partial first",
    )
    full, _ = exits.propose_exit(
        pos.position_id, proposal_class=ExitProposalClass.PROTECTIVE,
        action=ExitAction.EXIT_ALL,
        at=at+timedelta(minutes=3), created_by="POSITION_RULE", reason="hard stop",
    )
    all_items = exits.list_proposals(position_id=pos.position_id)
    old = next(p for p in all_items if p.proposal_id == partial.proposal_id)
    assert old.status == ExitProposalStatus.SUPERSEDED
    returned, events = exits.propose_exit(
        pos.position_id, proposal_class=ExitProposalClass.STRATEGIC,
        action=ExitAction.EXIT_QTY, requested_quantity=10,
        at=at+timedelta(minutes=4), created_by="USER", reason="late partial",
    )
    assert returned.proposal_id == full.proposal_id
    assert [e.name for e in events] == ["EXIT_TRIGGER_SUPPRESSED"]
