from datetime import UTC, datetime

from trademonitor.brokers.mock import MockBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.domain.enums import ExposureRelation, IntakeDisposition
from trademonitor.domain.models import BrokerAccountSnapshot, BrokerPositionSnapshot, NormalizedTradeIntent
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def test_existing_broker_exposure_is_rediscovery_not_scale_in(tmp_path):
    manager = CoreTMManager(SQLiteRuntimeRepository(Database(tmp_path / "tm.db")))
    manager.start()
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    broker = MockBroker(BrokerAccountSnapshot.create(
        broker="MOCK", observed_at=t,
        positions=[BrokerPositionSnapshot(
            broker="MOCK", broker_position_key="NFO:KAYNES26SEP4200CE:NRML",
            exchange="NFO", symbol="KAYNES26SEP4200CE", product="NRML",
            quantity=125, average_price="145", observed_at=t,
        )],
    ))
    manager.reconcile_broker_truth(broker)

    result = manager.ingest_trade_observation(
        src_id="DS-55", source="DAYSCANNER", observed_at=t,
        intent=NormalizedTradeIntent(
            underlying="KAYNES", direction="BULLISH", setup="BREAKOUT", trade_type="DAY",
            instrument_type="OPTION", option_type="CE", contract_symbol="KAYNES26SEP4200CE",
            expiry="2026-09-29", strike="4200", premium="150",
        ),
    )

    assert result.disposition == IntakeDisposition.REDISCOVERED_EXISTING_EXPOSURE
    assert result.existing_exposure.relation == ExposureRelation.EXACT_CONTRACT
    assert result.creates_new_operational_path is False
    assert manager.intake_snapshot()["observations"] == 1
    manager.stop()
