from trademonitor.brokers.base import Broker
from trademonitor.brokers.execution import ExecutionBroker
from trademonitor.brokers.zerodha import ZerodhaReadOnlyBroker


class FakeReadOnlyKite:
    def __init__(self):
        self.calls = []

    def positions(self):
        self.calls.append("positions")
        return {
            "net": [
                {
                    "exchange": "NFO",
                    "tradingsymbol": "KAYNES26SEP4200CE",
                    "product": "NRML",
                    "quantity": 125,
                    "average_price": 150.0,
                    "last_price": 155.0,
                    "realised": 0,
                    "unrealised": 625.0,
                    "instrument_token": 12345,
                },
                {
                    # Zerodha can retain a closed row in the day net book.
                    "exchange": "NFO",
                    "tradingsymbol": "OLD26SEP100CE",
                    "product": "NRML",
                    "quantity": 0,
                    "average_price": 0,
                    "last_price": 1.0,
                    "realised": 100,
                    "unrealised": 0,
                    "instrument_token": 999,
                },
            ]
        }

    def margins(self, segment):
        self.calls.append(f"margins:{segment}")
        return {
            "available": {"cash": 100000},
            "utilised": {"debits": 25000},
            "net": 75000,
        }

    def orders(self):
        self.calls.append("orders")
        return [{"order_id": "1"}, {"order_id": "2"}]

    def trades(self):
        self.calls.append("trades")
        return [{"trade_id": "T1"}]

    # If code accidentally reaches a broker mutation method, the test should fail.
    def place_order(self, **kwargs):
        raise AssertionError("read-only adapter must never place orders")

    def modify_order(self, **kwargs):
        raise AssertionError("read-only adapter must never modify orders")

    def cancel_order(self, **kwargs):
        raise AssertionError("read-only adapter must never cancel orders")


def test_read_only_adapter_implements_only_broker_truth_contract():
    broker = ZerodhaReadOnlyBroker(kite=FakeReadOnlyKite())
    assert isinstance(broker, Broker)
    assert not isinstance(broker, ExecutionBroker)
    assert not hasattr(broker, "submit_order")
    assert not hasattr(broker, "cancel_order")
    assert not hasattr(broker, "resolve_instrument")


def test_read_only_snapshot_uses_only_read_endpoints_and_filters_zero_qty_rows():
    kite = FakeReadOnlyKite()
    broker = ZerodhaReadOnlyBroker(kite=kite)

    snapshot = broker.fetch_account_snapshot()

    assert snapshot.broker == "ZERODHA"
    assert len(snapshot.positions) == 1
    assert snapshot.positions[0].symbol == "KAYNES26SEP4200CE"
    assert snapshot.positions[0].quantity == 125
    assert snapshot.funds.available_cash == 100000
    assert snapshot.order_count == 2
    assert snapshot.fill_count == 1
    assert kite.calls == ["positions", "margins:equity", "orders", "trades"]
