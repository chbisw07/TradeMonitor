from trademonitor.brokers.zerodha import ZerodhaReadOnlyBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import ManagementStatus, PositionOrigin
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


class FakeKite:
    def positions(self):
        return {"net": [{
            "exchange": "NFO",
            "tradingsymbol": "KAYNES26SEP4200CE",
            "product": "NRML",
            "quantity": 125,
            "average_price": 150.0,
            "last_price": 155.0,
            "unrealised": 625.0,
            "instrument_token": 12345,
        }]}

    def margins(self, segment):
        return {"available": {"cash": 100000}, "utilised": {"debits": 25000}, "net": 75000}

    def orders(self):
        return []

    def trades(self):
        return []


def test_real_broker_shape_reconciles_external_position_as_unmanaged(tmp_path):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    tm = CoreTMManager(repo)
    tm.start()
    try:
        positions = tm.reconcile_broker_truth(ZerodhaReadOnlyBroker(kite=FakeKite()))
        assert len(positions) == 1
        p = positions[0]
        assert p.management_status == ManagementStatus.UNMANAGED
        assert p.origin == PositionOrigin.BROKER_EXTERNAL

        status = tm.status_snapshot()
        assert status["broker"]["data"]["broker"] == "ZERODHA"
        assert status["broker"]["data"]["read_only"] is True
        assert status["broker"]["data"]["runtime_reconciled"] is True
        assert status["position"]["data"]["unmanaged_open"] == 1
        assert status["position"]["data"]["managed_open"] == 0
    finally:
        tm.stop()
