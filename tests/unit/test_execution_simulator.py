from datetime import UTC, datetime

import pytest

from trademonitor.brokers.execution_simulator import SimulatedExecutionBroker, SubmitFault
from trademonitor.domain.enums import BrokerOrderStatus, OrderSide, OrderType
from trademonitor.domain.models import BrokerInstrument, BrokerOrderRequest


def _order(client_id="C1"):
    return BrokerOrderRequest(
        broker="SIM",
        client_order_id=client_id,
        instrument=BrokerInstrument(
            broker="SIM", exchange="NFO", symbol="KAYNES26SEP4200CE",
            product="NRML", instrument_token="NFO:KAYNES26SEP4200CE"
        ),
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price="150",
    )


def test_accept_then_timeout_preserves_broker_order_for_reconciliation():
    broker = SimulatedExecutionBroker(name="SIM")
    broker.queue_submit_fault(SubmitFault.ACCEPT_THEN_TIMEOUT)
    with pytest.raises(TimeoutError):
        broker.submit_order(_order())
    assert broker.submit_count == 1
    truth = broker.fetch_order_by_client_id("C1")
    assert truth is not None
    assert truth.status == BrokerOrderStatus.ACKNOWLEDGED


def test_disconnect_before_accept_creates_no_broker_order():
    broker = SimulatedExecutionBroker(name="SIM")
    broker.queue_submit_fault(SubmitFault.DISCONNECT_BEFORE_ACCEPT)
    with pytest.raises(ConnectionError):
        broker.submit_order(_order())
    assert broker.submit_count == 1
    assert broker.fetch_order_by_client_id("C1") is None


def test_client_visibility_can_be_delayed_deterministically():
    broker = SimulatedExecutionBroker(name="SIM")
    snap = broker.submit_order(_order())
    broker.delay_client_visibility("C1", fetches=2)
    assert broker.fetch_order_by_client_id("C1") is None
    assert broker.fetch_order_by_client_id("C1") is None
    assert broker.fetch_order_by_client_id("C1").broker_order_id == snap.broker_order_id


def test_reconciliation_fetch_disconnect_is_scriptable():
    broker = SimulatedExecutionBroker(name="SIM")
    broker.submit_order(_order())
    broker.fail_next_fetches(1)
    with pytest.raises(ConnectionError):
        broker.fetch_order_by_client_id("C1")
    assert broker.fetch_order_by_client_id("C1") is not None


def test_order_truth_transition_supports_partial_fill_reject_and_fill():
    broker = SimulatedExecutionBroker(name="SIM")
    snap = broker.submit_order(_order())
    partial = broker.set_order_truth(
        snap.broker_order_id, status=BrokerOrderStatus.PARTIALLY_FILLED,
        filled_quantity=40, average_fill_price="149.5"
    )
    assert partial.filled_quantity == 40
    rejected = broker.set_order_truth(
        snap.broker_order_id, status=BrokerOrderStatus.REJECTED,
        filled_quantity=40, rejection_reason="remaining quantity rejected"
    )
    assert rejected.status == BrokerOrderStatus.REJECTED
    assert rejected.filled_quantity == 40
