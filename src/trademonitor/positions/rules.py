"""Deterministic managed-position rule engine for TM3/TGT2.

This module evaluates explicit management rules only. It never writes to a broker,
never creates an ExecutionRequest, and never bypasses the Position Manager's hard
MANAGED/UNMANAGED authority boundary. Triggered rules emit auditable management
signals for the later TM3/TGT3 Exit Monitor.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

from trademonitor.domain.enums import (
    ConditionOperator,
    ManagementRuleStatus,
    ManagementRuleType,
    ManagementSignal,
    PositionState,
)
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import (
    ManagementRuleEvaluation,
    ManagementRuleSpec,
    PositionManagementRule,
    PositionManagementSnapshot,
    PositionRecord,
)
from trademonitor.persistence.repository import RuntimeRepository
from trademonitor.positions.manager import PositionManager


class ManagementRuleError(ValueError):
    """Raised when a management rule cannot be safely created/evaluated."""


class ManagementRuleEngine:
    """Own deterministic rule validation, state, and evaluation for managed positions."""

    def __init__(self, repository: RuntimeRepository, position_manager: PositionManager) -> None:
        self._repository = repository
        self._positions = position_manager

    def add_rule(
        self,
        position_id: str,
        spec: ManagementRuleSpec,
        *,
        created_at: datetime,
    ) -> tuple[PositionManagementRule, list[DomainEvent]]:
        position = self._require_open_managed(position_id)
        self._validate_spec(spec)
        rule = PositionManagementRule(
            rule_id=str(uuid4()),
            position_id=position.position_id,
            rule_type=spec.rule_type,
            parameters=dict(spec.parameters),
            status=ManagementRuleStatus.ACTIVE,
            runtime_state={},
            created_at=created_at,
            updated_at=created_at,
            created_by=spec.created_by,
            reason=spec.reason,
            policy_name=spec.policy_name,
        )
        self._repository.save_management_rule(rule.to_record())
        return rule, [
            DomainEvent.create(
                "POSITION_MANAGEMENT_RULE_ADDED",
                source="POSITION",
                occurred_at=created_at,
                payload={
                    "position_id": position_id,
                    "rule_id": rule.rule_id,
                    "rule_type": rule.rule_type.value,
                    "policy_name": rule.policy_name,
                    "created_by": rule.created_by,
                    "reason": rule.reason,
                },
            )
        ]

    def install_policy(
        self,
        position_id: str,
        policy_name: str,
        specs: list[ManagementRuleSpec],
        *,
        created_at: datetime,
    ) -> tuple[list[PositionManagementRule], list[DomainEvent]]:
        """Install a named batch of explicit rules after validating the full batch."""
        if not policy_name.strip():
            raise ManagementRuleError("policy_name is required")
        self._require_open_managed(position_id)
        if not specs:
            raise ManagementRuleError("policy must contain at least one rule")
        for spec in specs:
            self._validate_spec(spec)

        rules: list[PositionManagementRule] = []
        events: list[DomainEvent] = []
        for spec in specs:
            normalized = ManagementRuleSpec(
                rule_type=spec.rule_type,
                parameters=spec.parameters,
                created_by=spec.created_by,
                reason=spec.reason,
                policy_name=policy_name,
            )
            rule, rule_events = self.add_rule(position_id, normalized, created_at=created_at)
            rules.append(rule)
            events.extend(rule_events)
        events.append(
            DomainEvent.create(
                "POSITION_MANAGEMENT_POLICY_INSTALLED",
                source="POSITION",
                occurred_at=created_at,
                payload={
                    "position_id": position_id,
                    "policy_name": policy_name,
                    "rule_ids": [r.rule_id for r in rules],
                },
            )
        )
        return rules, events

    def cancel_rule(
        self, rule_id: str, *, at: datetime, cancelled_by: str, reason: str
    ) -> tuple[PositionManagementRule, list[DomainEvent]]:
        rule = self._repository.get_management_rule(rule_id)
        if rule is None:
            raise KeyError(f"Unknown management rule: {rule_id}")
        self._require_open_managed(rule.position_id)
        if not cancelled_by.strip() or not reason.strip():
            raise ManagementRuleError("cancelled_by and reason are required")
        if rule.status == ManagementRuleStatus.CANCELLED:
            return rule, []
        updated = self._replace_rule(
            rule,
            status=ManagementRuleStatus.CANCELLED,
            runtime_state=rule.runtime_state,
            updated_at=at,
        )
        self._repository.save_management_rule(updated.to_record())
        return updated, [
            DomainEvent.create(
                "POSITION_MANAGEMENT_RULE_CANCELLED",
                source="POSITION",
                occurred_at=at,
                payload={
                    "position_id": rule.position_id,
                    "rule_id": rule.rule_id,
                    "rule_type": rule.rule_type.value,
                    "cancelled_by": cancelled_by,
                    "reason": reason,
                },
            )
        ]

    def evaluate(
        self, position_id: str, snapshot: PositionManagementSnapshot
    ) -> tuple[list[ManagementRuleEvaluation], list[DomainEvent]]:
        position = self._require_open_managed(position_id)
        rules = self._repository.list_management_rules(position_id=position_id, active_only=True)
        evaluations: list[ManagementRuleEvaluation] = []
        events: list[DomainEvent] = []
        for rule in rules:
            evaluation, updated_rule, rule_events = self._evaluate_rule(position, rule, snapshot)
            evaluations.append(evaluation)
            events.extend(rule_events)
            if updated_rule != rule:
                self._repository.save_management_rule(updated_rule.to_record())
        return evaluations, events

    def list_rules(
        self, *, position_id: str | None = None, active_only: bool = False
    ) -> list[PositionManagementRule]:
        return self._repository.list_management_rules(
            position_id=position_id, active_only=active_only
        )

    def _evaluate_rule(
        self,
        position: PositionRecord,
        rule: PositionManagementRule,
        snapshot: PositionManagementSnapshot,
    ) -> tuple[ManagementRuleEvaluation, PositionManagementRule, list[DomainEvent]]:
        if rule.status in {ManagementRuleStatus.TRIGGERED, ManagementRuleStatus.CANCELLED}:
            return self._evaluation(rule, False, "Rule is not active", snapshot.observed_at), rule, []

        if rule.rule_type == ManagementRuleType.TRAILING_SL:
            return self._evaluate_trailing(position, rule, snapshot)
        if rule.rule_type == ManagementRuleType.PROFIT_LOCK:
            return self._evaluate_profit_lock(position, rule, snapshot)
        if rule.rule_type == ManagementRuleType.HORIZON:
            profile = self._repository.get_position_management_profile(position.position_id)
            if profile is None:
                raise ManagementRuleError("Managed position has no management profile")
            triggered = snapshot.observed_at >= profile.horizon_at
            reason = (
                f"Trade horizon reached at {profile.horizon_at.isoformat()}"
                if triggered else "Trade horizon not yet reached"
            )
            return self._finalize_simple(rule, snapshot, triggered, reason, None)
        if rule.rule_type == ManagementRuleType.TIME_EXIT:
            threshold = datetime.fromisoformat(str(rule.parameters["at"]))
            triggered = snapshot.observed_at >= threshold
            return self._finalize_simple(
                rule, snapshot, triggered,
                f"Time exit {'reached' if triggered else 'not reached'}: {threshold.isoformat()}",
                None,
            )

        value, label = self._metric_value(position, rule, snapshot)
        operator = ConditionOperator(str(rule.parameters["operator"]))
        threshold = Decimal(str(rule.parameters["value"]))
        if value is None:
            return self._evaluation(
                rule, False, f"{label} unavailable for evaluation", snapshot.observed_at
            ), rule, []
        triggered = self._compare(value, operator, threshold)
        reason = (
            f"{label} {value} satisfied {operator.value} {threshold}"
            if triggered
            else f"{label} {value} did not satisfy {operator.value} {threshold}"
        )
        return self._finalize_simple(rule, snapshot, triggered, reason, threshold)

    def _evaluate_trailing(
        self, position: PositionRecord, rule: PositionManagementRule, snapshot: PositionManagementSnapshot
    ) -> tuple[ManagementRuleEvaluation, PositionManagementRule, list[DomainEvent]]:
        premium = snapshot.premium if snapshot.premium is not None else position.last_price
        if premium is None:
            return self._evaluation(rule, False, "Premium unavailable for trailing SL", snapshot.observed_at), rule, []
        pct = Decimal(str(rule.parameters["trail_pct"]))
        activation = rule.parameters.get("activate_at_premium")
        activation_value = None if activation is None else Decimal(str(activation))
        state = dict(rule.runtime_state)
        armed = bool(state.get("armed", False))
        events: list[DomainEvent] = []

        if not armed:
            activation_ok = True
            if activation_value is not None:
                activation_ok = premium >= activation_value if position.quantity > 0 else premium <= activation_value
            if not activation_ok:
                return self._evaluation(rule, False, "Trailing SL activation not reached", snapshot.observed_at), rule, []
            armed = True
            state["armed"] = True
            state["watermark"] = str(premium)
            events.append(self._state_event("POSITION_MANAGEMENT_RULE_ARMED", rule, snapshot.observed_at, {"premium": str(premium)}))

        watermark = Decimal(str(state.get("watermark", premium)))
        improved = premium > watermark if position.quantity > 0 else premium < watermark
        if improved:
            watermark = premium
            state["watermark"] = str(watermark)
            events.append(self._state_event("POSITION_MANAGEMENT_RULE_RATCHETED", rule, snapshot.observed_at, {"watermark": str(watermark)}))
        stop = watermark * (Decimal("1") - pct / Decimal("100")) if position.quantity > 0 else watermark * (Decimal("1") + pct / Decimal("100"))
        state["effective_stop"] = str(stop)
        triggered = premium <= stop if position.quantity > 0 else premium >= stop
        status = ManagementRuleStatus.TRIGGERED if triggered else ManagementRuleStatus.ARMED
        updated = self._replace_rule(rule, status=status, runtime_state=state, updated_at=snapshot.observed_at)
        if triggered:
            events.append(self._trigger_event(rule, snapshot.observed_at, f"Trailing SL hit at {premium}; stop={stop}"))
        evaluation = ManagementRuleEvaluation(
            rule_id=rule.rule_id,
            position_id=rule.position_id,
            rule_type=rule.rule_type,
            triggered=triggered,
            signal=ManagementSignal.EXIT_REVIEW if triggered else ManagementSignal.NONE,
            reason=(f"Trailing SL hit at {premium}; stop={stop}" if triggered else f"Trailing SL active; premium={premium}, stop={stop}"),
            evaluated_at=snapshot.observed_at,
            effective_value=stop,
        )
        return evaluation, updated, events

    def _evaluate_profit_lock(
        self, position: PositionRecord, rule: PositionManagementRule, snapshot: PositionManagementSnapshot
    ) -> tuple[ManagementRuleEvaluation, PositionManagementRule, list[DomainEvent]]:
        pnl = self._effective_pnl(position, snapshot)
        if pnl is None:
            return self._evaluation(rule, False, "P&L unavailable for profit lock", snapshot.observed_at), rule, []
        activate = Decimal(str(rule.parameters["activate_pnl"]))
        floor = Decimal(str(rule.parameters["floor_pnl"]))
        state = dict(rule.runtime_state)
        armed = bool(state.get("armed", False))
        events: list[DomainEvent] = []
        if not armed and pnl >= activate:
            armed = True
            state["armed"] = True
            state["activated_pnl"] = str(pnl)
            events.append(self._state_event("POSITION_MANAGEMENT_RULE_ARMED", rule, snapshot.observed_at, {"pnl": str(pnl)}))
        if not armed:
            return self._evaluation(rule, False, f"Profit lock waits for P&L >= {activate}", snapshot.observed_at), rule, []
        triggered = pnl <= floor
        status = ManagementRuleStatus.TRIGGERED if triggered else ManagementRuleStatus.ARMED
        updated = self._replace_rule(rule, status=status, runtime_state=state, updated_at=snapshot.observed_at)
        if triggered:
            events.append(self._trigger_event(rule, snapshot.observed_at, f"Profit lock floor reached: P&L={pnl}, floor={floor}"))
        evaluation = ManagementRuleEvaluation(
            rule_id=rule.rule_id,
            position_id=rule.position_id,
            rule_type=rule.rule_type,
            triggered=triggered,
            signal=ManagementSignal.EXIT_REVIEW if triggered else ManagementSignal.NONE,
            reason=(f"Profit lock floor reached: P&L={pnl}, floor={floor}" if triggered else f"Profit lock armed; P&L={pnl}, floor={floor}"),
            evaluated_at=snapshot.observed_at,
            effective_value=floor,
        )
        return evaluation, updated, events

    def _metric_value(
        self, position: PositionRecord, rule: PositionManagementRule, snapshot: PositionManagementSnapshot
    ) -> tuple[Decimal | None, str]:
        if rule.rule_type in {ManagementRuleType.HARD_SL, ManagementRuleType.TAKE_PROFIT, ManagementRuleType.PREMIUM_CONDITION}:
            return (snapshot.premium if snapshot.premium is not None else position.last_price), "premium"
        if rule.rule_type in {ManagementRuleType.SPOT_CONDITION, ManagementRuleType.UNDERLYING_INVALIDATION}:
            return snapshot.underlying_price, "underlying price"
        if rule.rule_type == ManagementRuleType.PNL_CONDITION:
            return self._effective_pnl(position, snapshot), "P&L"
        raise ManagementRuleError(f"Unsupported simple rule type: {rule.rule_type.value}")

    @staticmethod
    def _effective_pnl(position: PositionRecord, snapshot: PositionManagementSnapshot) -> Decimal | None:
        if snapshot.pnl is not None:
            return snapshot.pnl
        premium = snapshot.premium if snapshot.premium is not None else position.last_price
        if premium is None:
            return position.unrealized_pnl
        return (premium - position.average_price) * Decimal(position.quantity)

    def _finalize_simple(
        self,
        rule: PositionManagementRule,
        snapshot: PositionManagementSnapshot,
        triggered: bool,
        reason: str,
        effective_value: Decimal | None,
    ) -> tuple[ManagementRuleEvaluation, PositionManagementRule, list[DomainEvent]]:
        if not triggered:
            return self._evaluation(rule, False, reason, snapshot.observed_at, effective_value), rule, []
        updated = self._replace_rule(
            rule,
            status=ManagementRuleStatus.TRIGGERED,
            runtime_state=rule.runtime_state,
            updated_at=snapshot.observed_at,
        )
        event = self._trigger_event(rule, snapshot.observed_at, reason)
        return self._evaluation(rule, True, reason, snapshot.observed_at, effective_value), updated, [event]

    @staticmethod
    def _evaluation(
        rule: PositionManagementRule,
        triggered: bool,
        reason: str,
        at: datetime,
        effective_value: Decimal | None = None,
    ) -> ManagementRuleEvaluation:
        return ManagementRuleEvaluation(
            rule_id=rule.rule_id,
            position_id=rule.position_id,
            rule_type=rule.rule_type,
            triggered=triggered,
            signal=ManagementSignal.EXIT_REVIEW if triggered else ManagementSignal.NONE,
            reason=reason,
            evaluated_at=at,
            effective_value=effective_value,
        )

    @staticmethod
    def _compare(value: Decimal, operator: ConditionOperator, threshold: Decimal) -> bool:
        if operator == ConditionOperator.ABOVE:
            return value > threshold
        if operator == ConditionOperator.AT_OR_ABOVE:
            return value >= threshold
        if operator == ConditionOperator.BELOW:
            return value < threshold
        if operator == ConditionOperator.AT_OR_BELOW:
            return value <= threshold
        raise ManagementRuleError(f"Unsupported operator: {operator}")

    def _require_open_managed(self, position_id: str) -> PositionRecord:
        position = self._positions.get_position(position_id)
        if position is None:
            raise KeyError(f"Unknown position: {position_id}")
        self._positions.require_managed(position)
        if position.state != PositionState.OPEN or position.quantity == 0:
            raise ManagementRuleError(f"Position {position_id} is not open")
        if self._repository.get_position_management_profile(position_id) is None:
            raise ManagementRuleError(f"Position {position_id} has no management profile")
        return position

    @staticmethod
    def _validate_spec(spec: ManagementRuleSpec) -> None:
        p: Mapping[str, Any] = spec.parameters
        t = spec.rule_type
        if t in {
            ManagementRuleType.HARD_SL,
            ManagementRuleType.TAKE_PROFIT,
            ManagementRuleType.SPOT_CONDITION,
            ManagementRuleType.PREMIUM_CONDITION,
            ManagementRuleType.PNL_CONDITION,
            ManagementRuleType.UNDERLYING_INVALIDATION,
        }:
            if "operator" not in p or "value" not in p:
                raise ManagementRuleError(f"{t.value} requires operator and value")
            ConditionOperator(str(p["operator"]))
            Decimal(str(p["value"]))
            return
        if t == ManagementRuleType.TRAILING_SL:
            if "trail_pct" not in p:
                raise ManagementRuleError("TRAILING_SL requires trail_pct")
            pct = Decimal(str(p["trail_pct"]))
            if pct <= 0 or pct >= 100:
                raise ManagementRuleError("trail_pct must be > 0 and < 100")
            if p.get("activate_at_premium") is not None:
                Decimal(str(p["activate_at_premium"]))
            return
        if t == ManagementRuleType.PROFIT_LOCK:
            if "activate_pnl" not in p or "floor_pnl" not in p:
                raise ManagementRuleError("PROFIT_LOCK requires activate_pnl and floor_pnl")
            activate = Decimal(str(p["activate_pnl"]))
            floor = Decimal(str(p["floor_pnl"]))
            if floor >= activate:
                raise ManagementRuleError("profit-lock floor_pnl must be below activate_pnl")
            return
        if t == ManagementRuleType.TIME_EXIT:
            if "at" not in p:
                raise ManagementRuleError("TIME_EXIT requires at")
            datetime.fromisoformat(str(p["at"]))
            return
        if t == ManagementRuleType.HORIZON:
            return
        raise ManagementRuleError(f"Unsupported rule type: {t.value}")

    @staticmethod
    def _replace_rule(
        rule: PositionManagementRule,
        *,
        status: ManagementRuleStatus,
        runtime_state: Mapping[str, Any],
        updated_at: datetime,
    ) -> PositionManagementRule:
        return PositionManagementRule(
            rule_id=rule.rule_id,
            position_id=rule.position_id,
            rule_type=rule.rule_type,
            parameters=rule.parameters,
            status=status,
            runtime_state=dict(runtime_state),
            created_at=rule.created_at,
            updated_at=updated_at,
            created_by=rule.created_by,
            reason=rule.reason,
            policy_name=rule.policy_name,
        )

    @staticmethod
    def _state_event(name: str, rule: PositionManagementRule, at: datetime, extra: Mapping[str, Any]) -> DomainEvent:
        return DomainEvent.create(
            name,
            source="POSITION",
            occurred_at=at,
            payload={"position_id": rule.position_id, "rule_id": rule.rule_id, "rule_type": rule.rule_type.value, **dict(extra)},
        )

    @staticmethod
    def _trigger_event(rule: PositionManagementRule, at: datetime, reason: str) -> DomainEvent:
        return DomainEvent.create(
            "POSITION_MANAGEMENT_RULE_TRIGGERED",
            source="POSITION",
            occurred_at=at,
            payload={
                "position_id": rule.position_id,
                "rule_id": rule.rule_id,
                "rule_type": rule.rule_type.value,
                "signal": ManagementSignal.EXIT_REVIEW.value,
                "reason": reason,
            },
        )
