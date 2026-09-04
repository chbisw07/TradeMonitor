from datetime import UTC, datetime

from trademonitor.brokers.execution_mock import MockExecutionBroker
from trademonitor.core.manager import CoreTMManager
from trademonitor.execution.engine import ExecutionEngine
from trademonitor.domain.enums import (
    ExecutionPurpose,
    ExecutionRequestStatus,
    OrderSide,
    OrderType,
)
from trademonitor.domain.models import ExecutionRequest
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def test_execution_request_survives_restart_and_duplicate_deploy_does_not_resubmit(tmp_path):
    db = Database(tmp_path / "tm.db")
    repo = SQLiteRuntimeRepository(db)
    tm = CoreTMManager(repo); tm.start()
    t = datetime(2026, 9, 4, 10, 0, tzinfo=UTC)
    req = ExecutionRequest(
        request_id="ER-RESTART-1",
        idempotency_key="ENTRY:E1:RD1",
        purpose=ExecutionPurpose.ENTRY,
        source_id="E1",
        broker="MOCK",
        exchange="NFO",
        symbol="KAYNES26SEP4200CE",
        product="NRML",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price="150",
        status=ExecutionRequestStatus.READY,
        created_at=t,
        updated_at=t,
        risk_decision_id="RD1",
        risk_profile_version=1,
    )
    repo.save_execution_request(req.to_record())
    broker = MockExecutionBroker(name="MOCK")
    submitted, _ = ExecutionEngine(repo).deploy(req.request_id, broker)
    assert submitted.status == ExecutionRequestStatus.SUBMITTED
    assert broker.submit_count == 1
    tm.stop()

    repo2 = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    tm2 = CoreTMManager(repo2); tm2.start()
    restored = tm2.execution_snapshot()[0]
    assert restored.status == ExecutionRequestStatus.SUBMITTED
    again = tm2.deploy_execution_request(restored.request_id, broker)
    assert again.request_id == restored.request_id
    assert broker.submit_count == 1
