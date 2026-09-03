"""Trade Intake domain for TM2/TGT1.

Candidate remains an operational UI notion. Internally intake keeps source
observations, broad Outcomes, and time-relevant Episodes separate so identity,
provenance, and market-time relevance do not collapse into one object.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime
from typing import Callable, Iterable
from uuid import uuid4

from trademonitor.candidates.relevance import EpisodeAmbiguityResolver, EpisodeRelevancePolicy
from trademonitor.domain.enums import (
    EpisodeDecision,
    EpisodeStatus,
    ExposureRelation,
    IntakeDisposition,
)
from trademonitor.domain.events import DomainEvent
from trademonitor.domain.models import (
    EpisodeRecord,
    ExistingExposure,
    IntakeResult,
    NormalizedTradeIntent,
    OutcomeRecord,
    PositionRecord,
    SourceObservation,
)
from trademonitor.persistence.repository import RuntimeRepository


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(raw).hexdigest()


class TradeIntakeManager:
    """Own source/outcome/episode reconciliation; never executes or scales a trade."""

    def __init__(
        self,
        repository: RuntimeRepository,
        *,
        positions_provider: Callable[[], Iterable[PositionRecord]] | None = None,
        relevance_policy: EpisodeRelevancePolicy | None = None,
        ambiguity_resolver: EpisodeAmbiguityResolver | None = None,
    ) -> None:
        self._repository = repository
        self._positions_provider = positions_provider or (lambda: ())
        self._relevance = relevance_policy or EpisodeRelevancePolicy()
        self._resolver = ambiguity_resolver

    def ingest(
        self,
        *,
        src_id: str,
        source: str,
        observed_at: datetime,
        intent: NormalizedTradeIntent,
        raw_payload: dict | None = None,
    ) -> tuple[IntakeResult, list[DomainEvent]]:
        if not src_id.strip():
            raise ValueError("src_id is required")
        if not source.strip():
            raise ValueError("source is required")

        dedupe_key = _stable_hash(
            {
                "src_id": src_id,
                "source": source.upper(),
                "observed_at": observed_at.isoformat(),
                "intent": intent.to_record(),
                "raw_payload": raw_payload or {},
            }
        )
        duplicate = self._repository.get_source_observation_by_dedupe_key(dedupe_key)
        if duplicate is not None:
            outcome = self._repository.get_outcome(str(duplicate.outcome_id))
            episode = self._repository.get_episode(str(duplicate.episode_id))
            if outcome is None or episode is None:
                raise RuntimeError("Persisted intake observation references missing outcome/episode")
            exposure = self._existing_exposure(intent)
            result = IntakeResult(
                disposition=IntakeDisposition.DUPLICATE_OBSERVATION,
                observation=duplicate,
                outcome=outcome,
                episode=episode,
                existing_exposure=exposure,
                reason="Exact source observation already ingested",
            )
            return result, [self._event("INTAKE_OBSERVATION_DUPLICATE", result)]

        outcome_key = _stable_hash(intent.outcome_identity())
        outcome = self._repository.get_outcome_by_key(outcome_key)
        new_outcome = outcome is None
        now = observed_at
        if outcome is None:
            outcome = OutcomeRecord(
                outcome_id=f"OUT-{uuid4()}",
                outcome_key=outcome_key,
                identity=intent.outcome_identity(),
                created_at=now,
                updated_at=now,
            )
            self._repository.save_outcome(outcome.to_record())

        provisional_observation = SourceObservation(
            observation_id=f"OBS-{uuid4()}",
            src_id=src_id,
            source=source.upper(),
            observed_at=observed_at,
            intent=intent,
            raw_payload=dict(raw_payload or {}),
            dedupe_key=dedupe_key,
            outcome_id=outcome.outcome_id,
        )

        current = self._repository.get_active_episode_for_outcome(outcome.outcome_id)
        if current is None:
            episode = self._new_episode(outcome, provisional_observation)
            disposition = IntakeDisposition.NEW_OUTCOME if new_outcome else IntakeDisposition.NEW_EPISODE
            reason = "Created first time-relevant Episode for Outcome"
        else:
            decision = self._relevance.decide(provisional_observation, current, self._resolver)
            if decision == EpisodeDecision.SAME_EPISODE:
                episode = replace(
                    current,
                    last_observed_at=max(current.last_observed_at, observed_at),
                    latest_observation_id=provisional_observation.observation_id,
                    signature=intent.episode_identity(),
                )
                self._repository.save_episode(episode.to_record())
                disposition = IntakeDisposition.UPDATED_EPISODE
                reason = "Observation reconciled to current time-relevant Episode"
            elif decision == EpisodeDecision.STALE_OBSERVATION:
                episode = current
                disposition = IntakeDisposition.STALE_OBSERVATION
                reason = "Older observation recorded for provenance without changing current Episode"
            else:
                self._repository.save_episode(
                    replace(current, status=EpisodeStatus.SUPERSEDED).to_record()
                )
                episode = self._new_episode(outcome, provisional_observation)
                disposition = IntakeDisposition.NEW_EPISODE
                reason = "Market-time/contract context requires a fresh Episode"

        observation = replace(provisional_observation, episode_id=episode.episode_id)
        self._repository.save_source_observation(observation.to_record())
        self._repository.save_outcome(replace(outcome, updated_at=observed_at).to_record())

        exposure = self._existing_exposure(intent)
        if exposure.relation != ExposureRelation.NONE:
            disposition = IntakeDisposition.REDISCOVERED_EXISTING_EXPOSURE
            reason = (
                "Related broker-confirmed exposure already exists; observation is recorded "
                "but creates no scale-in/execution permission"
            )

        result = IntakeResult(
            disposition=disposition,
            observation=observation,
            outcome=replace(outcome, updated_at=observed_at),
            episode=episode,
            existing_exposure=exposure,
            reason=reason,
        )
        events = [self._event("INTAKE_OBSERVATION_ACCEPTED", result)]
        if new_outcome:
            events.append(self._event("OUTCOME_CREATED", result))
        if new_outcome or disposition == IntakeDisposition.NEW_EPISODE:
            events.append(self._event("EPISODE_CREATED", result))
        if exposure.relation != ExposureRelation.NONE:
            events.append(self._event("EXISTING_EXPOSURE_REDISCOVERED", result))
        return result, events

    def snapshot(self) -> dict[str, int]:
        return self._repository.intake_counts()

    def _new_episode(self, outcome: OutcomeRecord, observation: SourceObservation) -> EpisodeRecord:
        episode = EpisodeRecord(
            episode_id=f"EP-{uuid4()}",
            outcome_id=outcome.outcome_id,
            signature=observation.intent.episode_identity(),
            status=EpisodeStatus.ACTIVE,
            started_at=observation.observed_at,
            last_observed_at=observation.observed_at,
            latest_observation_id=observation.observation_id,
        )
        self._repository.save_episode(episode.to_record())
        return episode

    def _existing_exposure(self, intent: NormalizedTradeIntent) -> ExistingExposure:
        exact: list[str] = []
        same_underlying: list[str] = []
        contract = (intent.contract_symbol or "").upper()
        underlying = intent.underlying.upper()
        for position in self._positions_provider():
            if not position.is_open:
                continue
            symbol = position.symbol.upper()
            if contract and symbol == contract:
                exact.append(position.position_id)
            elif underlying and symbol.startswith(underlying):
                same_underlying.append(position.position_id)
        if exact:
            return ExistingExposure(ExposureRelation.EXACT_CONTRACT, tuple(sorted(exact)))
        if same_underlying:
            return ExistingExposure(ExposureRelation.SAME_UNDERLYING, tuple(sorted(same_underlying)))
        return ExistingExposure(ExposureRelation.NONE, ())

    @staticmethod
    def _event(name: str, result: IntakeResult) -> DomainEvent:
        return DomainEvent.create(
            name,
            source="INTAKE",
            occurred_at=result.observation.observed_at,
            payload={
                "observation_id": result.observation.observation_id,
                "src_id": result.observation.src_id,
                "source": result.observation.source,
                "outcome_id": result.outcome.outcome_id,
                "episode_id": result.episode.episode_id,
                "disposition": result.disposition.value,
                "exposure_relation": result.existing_exposure.relation.value,
                "position_ids": list(result.existing_exposure.position_ids),
                "reason": result.reason,
            },
        )


# Compatibility with the original skeleton name; Candidate remains an operational notion.
CandidateManager = TradeIntakeManager
