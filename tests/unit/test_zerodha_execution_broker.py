from trademonitor.brokers.zerodha import ZerodhaExecutionBroker
from trademonitor.domain.enums import BrokerOrderStatus, OrderSide, OrderType
from trademonitor.domain.models import BrokerInstrument, BrokerOrderRequest


class FakeKite:
    def __init__(self):
        self._orders = []
        self._next = 1
        self.placed = []

    def positions(self):
        return {"net": [{
            "exchange": "NFO", "tradingsymbol": "KAYNES26SEP4200CE", "product": "NRML",
            "quantity": 125, "average_price": 150.0, "last_price": 155.0,
            "realised": 0, "unrealised": 625.0, "instrument_token": 12345,
        }]}

    def margins(self, segment):
        assert segment == "equity"
        return {"available": {"cash": 100000}, "utilised": {"debits": 25000}, "net": 75000}

    def trades(self):
        return []

    def instruments(self, exchange):
        return [{"tradingsymbol": "KAYNES26SEP4200CE", "instrument_token": 12345}]

    def place_order(self, **kwargs):
        self.placed.append(kwargs)
        oid = str(self._next); self._next += 1
        self._orders.append({
            "order_id": oid, "tag": kwargs.get("tag"), "quantity": kwargs["quantity"],
            "filled_quantity": 0, "average_price": 0, "status": "OPEN",
        })
        return oid

    def orders(self):
        return list(self._orders)

    def order_history(self, order_id):
        return [x for x in self._orders if x["order_id"] == str(order_id)]

    def cancel_order(self, **kwargs):
        oid = str(kwargs["order_id"])
        for row in self._orders:
            if row["order_id"] == oid:
                row["status"] = "CANCELLED"
        return oid


def _order(broker):
    instrument = BrokerInstrument(
        broker=broker.name, exchange="NFO", symbol="KAYNES26SEP4200CE",
        product="NRML", instrument_token="12345",
    )
    return BrokerOrderRequest(
        broker=broker.name, client_order_id="ENTRY:very-long-idempotency-key:RD1",
        instrument=instrument, side=OrderSide.BUY, quantity=125,
        order_type=OrderType.LIMIT, limit_price="150",
    )


def test_zerodha_account_snapshot_maps_positions_and_funds():
    broker = ZerodhaExecutionBroker(kite=FakeKite())
    snap = broker.fetch_account_snapshot()
    assert snap.broker == "ZERODHA"
    assert len(snap.positions) == 1
    assert snap.positions[0].quantity == 125
    assert snap.positions[0].symbol == "KAYNES26SEP4200CE"
    assert snap.funds.available_cash == 100000


def test_zerodha_submit_and_restart_safe_lookup_by_client_id():
    kite = FakeKite()
    broker = ZerodhaExecutionBroker(kite=kite)
    order = _order(broker)
    submitted = broker.submit_order(order)
    assert submitted.status == BrokerOrderStatus.ACKNOWLEDGED
    assert submitted.client_order_id == order.client_order_id
    assert len(kite.placed[0]["tag"]) <= 20

    # New adapter instance simulates restart: lookup uses deterministic broker tag.
    restarted = ZerodhaExecutionBroker(kite=kite)
    found = restarted.fetch_order_by_client_id(order.client_order_id)
    assert found is not None
    assert found.client_order_id == order.client_order_id
    assert found.broker_order_id == submitted.broker_order_id


def test_zerodha_cancel_maps_broker_truth():
    kite = FakeKite(); broker = ZerodhaExecutionBroker(kite=kite)
    submitted = broker.submit_order(_order(broker))
    cancelled = broker.cancel_order(submitted.broker_order_id)
    assert cancelled.status == BrokerOrderStatus.CANCELLED
