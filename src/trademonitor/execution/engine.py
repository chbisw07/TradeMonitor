"""TM4/TGT1 Module M — controlled broker deployment and order reconciliation."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from trademonitor.brokers.execution import ExecutionBroker
from trademonitor.domain.enums import BrokerOrderStatus, ExecutionRequestStatus
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import BrokerOrderRequest, BrokerOrderSnapshot, ExecutionRequest, utc_now
from trademonitor.persistence.repository import RuntimeRepository


_TERMINAL = {
    ExecutionRequestStatus.FILLED,
    ExecutionRequestStatus.REJECTED,
    ExecutionRequestStatus.CANCELLED,
}


class ExecutionDeploymentError(RuntimeError):
    pass


class ExecutionEngine:
    """Module M.

    Module M knows deployment mechanics only. It neither judges trade quality nor
    grants Risk permission. A durable ExecutionRequest must already exist before
    this module is called.
    """

    def __init__(self, repository: RuntimeRepository) -> None:
        self._repository = repository

    def deploy(
        self, request_id: str, broker: ExecutionBroker, *, at: datetime | None = None
    ) -> tuple[ExecutionRequest, list[DomainEvent]]:
        request = self._require_request(request_id)
        self._validate_broker(request, broker)

        # Retry/restart safety: once submission started, never submit again merely
        # because the caller repeats deploy(). Reconcile broker truth instead.
        if request.status != ExecutionRequestStatus.READY:
            return self.reconcile(request_id, broker, at=at)

        when = at or utc_now()
        instrument = broker.resolve_instrument(
            exchange=request.exchange,
            symbol=request.symbol,
            product=request.product,
            instrument_token=request.instrument_token,
        )
        submitting = replace(
            request,
            status=ExecutionRequestStatus.SUBMITTING,
            instrument_token=instrument.instrument_token,
            updated_at=when,
        )
        self._repository.save_execution_request(submitting.to_record())
        events = [
            DomainEvent.create(
                "EXECUTION_SUBMISSION_STARTED",
                source="MODULE_M",
                occurred_at=when,
                payload={
                    "request_id": request_id,
                    "idempotency_key": request.idempotency_key,
                    "purpose": request.purpose.value,
                    "broker": request.broker,
                    "symbol": request.symbol,
                    "quantity": request.quantity,
                },
            )
        ]

        order = BrokerOrderRequest(
            broker=request.broker,
            client_order_id=request.idempotency_key,
            instrument=instrument,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
        )
        try:
            snapshot = broker.submit_order(order)
        except Exception as exc:
            uncertain = replace(
                submitting,
                status=ExecutionRequestStatus.UNCERTAIN,
                updated_at=utc_now(),
                rejection_reason=f"submission outcome unknown: {type(exc).__name__}",
            )
            self._repository.save_execution_request(uncertain.to_record())
            events.append(
                DomainEvent.create(
                    "EXECUTION_OUTCOME_UNCERTAIN",
                    source="MODULE_M",
                    payload={
                        "request_id": request_id,
                        "idempotency_key": request.idempotency_key,
                        "error_type": type(exc).__name__,
                        "rule": "do not blind-retry; reconcile broker truth",
                    },
                )
            )
            return uncertain, events

        updated = self._apply_broker_truth(submitting, snapshot)
        self._repository.save_execution_request(updated.to_record())
        events.append(self._broker_event(updated, snapshot))
        return updated, events

    def reconcile(
        self, request_id: str, broker: ExecutionBroker, *, at: datetime | None = None
    ) -> tuple[ExecutionRequest, list[DomainEvent]]:
        request = self._require_request(request_id)
        self._validate_broker(request, broker)
        if request.status in _TERMINAL:
            return request, []

        snapshot = broker.fetch_order_by_client_id(request.idempotency_key)
        if snapshot is None and request.broker_order_id:
            snapshot = broker.fetch_order(request.broker_order_id)
        if snapshot is None:
            when = at or utc_now()
            uncertain = replace(
                request,
                status=ExecutionRequestStatus.UNCERTAIN,
                updated_at=when,
                rejection_reason="broker order truth not currently resolvable",
            )
            self._repository.save_execution_request(uncertain.to_record())
            return uncertain, [
                DomainEvent.create(
                    "EXECUTION_RECONCILIATION_UNCERTAIN",
                    source="MODULE_M",
                    occurred_at=when,
                    payload={
                        "request_id": request_id,
                        "idempotency_key": request.idempotency_key,
                    },
                )
            ]

        updated = self._apply_broker_truth(request, snapshot)
        self._repository.save_execution_request(updated.to_record())
        return updated, [self._broker_event(updated, snapshot)]

    def cancel(
        self, request_id: str, broker: ExecutionBroker, *, at: datetime | None = None
    ) -> tuple[ExecutionRequest, list[DomainEvent]]:
        request = self._require_request(request_id)
        self._validate_broker(request, broker)
        if not request.broker_order_id:
            raise ExecutionDeploymentError("Cannot cancel before broker order identity is known")
        if request.status in _TERMINAL:
            return request, []
        snapshot = broker.cancel_order(request.broker_order_id)
        updated = self._apply_broker_truth(request, snapshot)
        self._repository.save_execution_request(updated.to_record())
        return updated, [self._broker_event(updated, snapshot)]

    def list_requests(self) -> list[ExecutionRequest]:
        return self._repository.list_execution_requests()

    def get_request(self, request_id: str) -> ExecutionRequest | None:
        return self._repository.get_execution_request(request_id)

    def _require_request(self, request_id: str) -> ExecutionRequest:
        request = self._repository.get_execution_request(request_id)
        if request is None:
            raise KeyError(f"Unknown execution request: {request_id}")
        return request

    @staticmethod
    def _validate_broker(request: ExecutionRequest, broker: ExecutionBroker) -> None:
        if broker.name != request.broker:
            raise ExecutionDeploymentError("ExecutionRequest broker does not match adapter")

    @staticmethod
    def _apply_broker_truth(
        request: ExecutionRequest, snapshot: BrokerOrderSnapshot
    ) -> ExecutionRequest:
        if snapshot.broker != request.broker:
            raise ExecutionDeploymentError("Broker order truth identity mismatch")
        if snapshot.client_order_id != request.idempotency_key:
            raise ExecutionDeploymentError("Broker client-order correlation mismatch")
        if snapshot.requested_quantity != request.quantity:
            raise ExecutionDeploymentError("Broker requested quantity differs from ExecutionRequest")

        mapping = {
            BrokerOrderStatus.ACKNOWLEDGED: ExecutionRequestStatus.SUBMITTED,
            BrokerOrderStatus.PARTIALLY_FILLED: ExecutionRequestStatus.PARTIALLY_FILLED,
            BrokerOrderStatus.FILLED: ExecutionRequestStatus.FILLED,
            BrokerOrderStatus.REJECTED: ExecutionRequestStatus.REJECTED,
            BrokerOrderStatus.CANCELLED: ExecutionRequestStatus.CANCELLED,
            BrokerOrderStatus.UNKNOWN: ExecutionRequestStatus.UNCERTAIN,
        }
        return replace(
            request,
            status=mapping[snapshot.status],
            broker_order_id=snapshot.broker_order_id,
            filled_quantity=snapshot.filled_quantity,
            average_fill_price=snapshot.average_fill_price,
            rejection_reason=snapshot.rejection_reason,
            last_broker_observed_at=snapshot.observed_at,
            updated_at=snapshot.observed_at,
        )

    @staticmethod
    def _broker_event(request: ExecutionRequest, snapshot: BrokerOrderSnapshot) -> DomainEvent:
        return DomainEvent.create(
            "EXECUTION_BROKER_TRUTH_UPDATED",
            source="MODULE_M",
            occurred_at=snapshot.observed_at,
            payload={
                "request_id": request.request_id,
                "idempotency_key": request.idempotency_key,
                "broker_order_id": snapshot.broker_order_id,
                "status": request.status.value,
                "filled_quantity": request.filled_quantity,
                "average_fill_price": None if request.average_fill_price is None else str(request.average_fill_price),
                "rejection_reason": request.rejection_reason,
            },
        )
