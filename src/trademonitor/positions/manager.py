"""Broker-truth position reconciliation for TM1/TGT2."""

from __future__ import annotations

from uuid import uuid4

from trademonitor.domain.enums import ManagementStatus, PositionOrigin, PositionState
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import (
    BrokerAccountSnapshot,
    BrokerPositionSnapshot,
    PositionAdoptionRequest,
    PositionManagementProfile,
    PositionRecord,
)
from trademonitor.persistence.repository import RuntimeRepository


class UnmanagedPositionError(PermissionError):
    """Raised when a management operation is attempted across the UM boundary."""


class PositionAdoptionError(ValueError):
    """Raised when an explicit adoption request is invalid for current broker truth."""


class AlreadyManagedPositionError(PositionAdoptionError):
    """Raised when adoption is requested for a position already under TM management."""


class PositionManager:
    """Own canonical position reconciliation and the MANAGED/UNMANAGED boundary."""

    def __init__(self, repository: RuntimeRepository) -> None:
        self._repository = repository

    def reconcile(self, snapshot: BrokerAccountSnapshot) -> tuple[list[PositionRecord], list[DomainEvent]]:
        """Reconcile persisted positions to one broker snapshot.

        Broker-reported quantity/state always wins. Existing management status and
        provenance are preserved. Newly discovered broker positions are always
        UNMANAGED / BROKER_EXTERNAL until a later explicit adoption workflow.
        """
        existing = {
            (p.broker, p.broker_position_key): p
            for p in self._repository.list_positions(broker=snapshot.broker)
        }
        seen: set[tuple[str, str]] = set()
        events: list[DomainEvent] = []

        for broker_position in snapshot.positions:
            key = (snapshot.broker, broker_position.broker_position_key)
            seen.add(key)
            current = existing.get(key)
            state = PositionState.OPEN if broker_position.quantity != 0 else PositionState.CLOSED

            if current is None:
                record = self._new_external_position(broker_position, state=state)
                self._repository.save_position(record.to_record())
                events.append(
                    DomainEvent.create(
                        "BROKER_POSITION_DISCOVERED",
                        source="POSITION",
                        payload=self._event_payload(record),
                        occurred_at=snapshot.observed_at,
                    )
                )
                existing[key] = record
                continue

            updated = PositionRecord(
                position_id=current.position_id,
                broker=current.broker,
                broker_position_key=current.broker_position_key,
                exchange=broker_position.exchange,
                symbol=broker_position.symbol,
                product=broker_position.product,
                quantity=broker_position.quantity,
                average_price=broker_position.average_price,
                state=state,
                management_status=current.management_status,
                origin=current.origin,
                last_price=broker_position.last_price,
                realized_pnl=broker_position.realized_pnl,
                unrealized_pnl=broker_position.unrealized_pnl,
                instrument_token=broker_position.instrument_token,
                first_seen_at=current.first_seen_at,
                updated_at=snapshot.observed_at,
            )
            # Persist current broker truth on every coherent snapshot. Emit a
            # structural event only when exposure/identity materially changes;
            # price/P&L refreshes are snapshot data, not lifecycle transitions.
            self._repository.save_position(updated.to_record())
            if self._materially_changed(current, updated):
                event_name = self._change_event_name(current, updated)
                events.append(
                    DomainEvent.create(
                        event_name,
                        source="POSITION",
                        payload={
                            **self._event_payload(updated),
                            "previous_quantity": current.quantity,
                            "previous_state": current.state.value,
                        },
                        occurred_at=snapshot.observed_at,
                    )
                )
            existing[key] = updated

        # A previously open position omitted by a coherent broker snapshot is closed.
        for key, current in list(existing.items()):
            if key in seen or current.state == PositionState.CLOSED:
                continue
            closed = PositionRecord(
                position_id=current.position_id,
                broker=current.broker,
                broker_position_key=current.broker_position_key,
                exchange=current.exchange,
                symbol=current.symbol,
                product=current.product,
                quantity=0,
                average_price=current.average_price,
                state=PositionState.CLOSED,
                management_status=current.management_status,
                origin=current.origin,
                last_price=current.last_price,
                realized_pnl=current.realized_pnl,
                unrealized_pnl=current.unrealized_pnl,
                instrument_token=current.instrument_token,
                first_seen_at=current.first_seen_at,
                updated_at=snapshot.observed_at,
            )
            self._repository.save_position(closed.to_record())
            events.append(
                DomainEvent.create(
                    "BROKER_POSITION_CLOSED",
                    source="POSITION",
                    payload={
                        **self._event_payload(closed),
                        "previous_quantity": current.quantity,
                        "closure_basis": "ABSENT_FROM_BROKER_SNAPSHOT",
                    },
                    occurred_at=snapshot.observed_at,
                )
            )
            existing[key] = closed

        return self._repository.list_positions(broker=snapshot.broker), events

    def list_positions(self, *, broker: str | None = None, open_only: bool = False) -> list[PositionRecord]:
        positions = self._repository.list_positions(broker=broker)
        if open_only:
            return [position for position in positions if position.is_open]
        return positions

    def get_position(self, position_id: str) -> PositionRecord | None:
        return self._repository.get_position(position_id)

    def management_profile(self, position_id: str) -> PositionManagementProfile | None:
        return self._repository.get_position_management_profile(position_id)

    def adopt(
        self, request: PositionAdoptionRequest
    ) -> tuple[PositionRecord, PositionManagementProfile, list[DomainEvent]]:
        """Explicitly adopt one open external broker position into TM management.

        Adoption changes only TradeMonitor authority/metadata. It performs no broker
        write. Broker quantity, average price, state and identity remain broker truth.
        """
        current = self._repository.get_position(request.position_id)
        if current is None:
            raise PositionAdoptionError(f"Unknown position: {request.position_id}")
        if current.management_status == ManagementStatus.MANAGED:
            raise AlreadyManagedPositionError(
                f"Position {current.position_id} is already MANAGED"
            )
        if not current.is_open:
            raise PositionAdoptionError(
                f"Position {current.position_id} is not open at broker and cannot be adopted"
            )

        profile = request.to_profile()
        adopted = PositionRecord(
            position_id=current.position_id,
            broker=current.broker,
            broker_position_key=current.broker_position_key,
            exchange=current.exchange,
            symbol=current.symbol,
            product=current.product,
            quantity=current.quantity,
            average_price=current.average_price,
            state=current.state,
            management_status=ManagementStatus.MANAGED,
            origin=(
                PositionOrigin.BROKER_ADOPTED
                if current.origin == PositionOrigin.BROKER_EXTERNAL
                else current.origin
            ),
            last_price=current.last_price,
            realized_pnl=current.realized_pnl,
            unrealized_pnl=current.unrealized_pnl,
            instrument_token=current.instrument_token,
            first_seen_at=current.first_seen_at,
            updated_at=request.requested_at,
        )
        self._repository.save_position(adopted.to_record())
        self._repository.save_position_management_profile(profile.to_record())
        event = DomainEvent.create(
            "POSITION_ADOPTED",
            source="POSITION",
            payload={
                **self._event_payload(adopted),
                "trade_type": profile.trade_type.value,
                "instrument_type": profile.instrument_type.value,
                "asset_class": profile.asset_class.value,
                "horizon_at": profile.horizon_at.isoformat(),
                "expiry_date": None if profile.expiry_date is None else profile.expiry_date.isoformat(),
                "adopted_by": profile.activated_by,
                "reason": profile.activation_reason,
            },
            occurred_at=request.requested_at,
        )
        return adopted, profile, [event]

    @staticmethod
    def require_managed(position: PositionRecord) -> None:
        """Enforce the hard read-only boundary for external/unadopted positions."""
        if position.management_status != ManagementStatus.MANAGED:
            raise UnmanagedPositionError(
                f"Position {position.position_id} is UNMANAGED and read-only until explicitly adopted"
            )

    @staticmethod
    def _new_external_position(
        broker_position: BrokerPositionSnapshot, *, state: PositionState
    ) -> PositionRecord:
        return PositionRecord(
            position_id=str(uuid4()),
            broker=broker_position.broker,
            broker_position_key=broker_position.broker_position_key,
            exchange=broker_position.exchange,
            symbol=broker_position.symbol,
            product=broker_position.product,
            quantity=broker_position.quantity,
            average_price=broker_position.average_price,
            state=state,
            management_status=ManagementStatus.UNMANAGED,
            origin=PositionOrigin.BROKER_EXTERNAL,
            last_price=broker_position.last_price,
            realized_pnl=broker_position.realized_pnl,
            unrealized_pnl=broker_position.unrealized_pnl,
            instrument_token=broker_position.instrument_token,
            first_seen_at=broker_position.observed_at,
            updated_at=broker_position.observed_at,
        )

    @staticmethod
    def _materially_changed(previous: PositionRecord, current: PositionRecord) -> bool:
        return (
            previous.exchange,
            previous.symbol,
            previous.product,
            previous.quantity,
            previous.average_price,
            previous.state,
            previous.instrument_token,
        ) != (
            current.exchange,
            current.symbol,
            current.product,
            current.quantity,
            current.average_price,
            current.state,
            current.instrument_token,
        )

    @staticmethod
    def _change_event_name(previous: PositionRecord, current: PositionRecord) -> str:
        if previous.state == PositionState.OPEN and current.state == PositionState.CLOSED:
            return "BROKER_POSITION_CLOSED"
        if previous.state == PositionState.CLOSED and current.state == PositionState.OPEN:
            return "BROKER_POSITION_REOPENED"
        return "BROKER_POSITION_CHANGED"

    @staticmethod
    def _event_payload(position: PositionRecord) -> dict[str, object]:
        return {
            "position_id": position.position_id,
            "broker": position.broker,
            "broker_position_key": position.broker_position_key,
            "symbol": position.symbol,
            "product": position.product,
            "quantity": position.quantity,
            "state": position.state.value,
            "management_status": position.management_status.value,
            "origin": position.origin.value,
        }
