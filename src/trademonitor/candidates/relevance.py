"""Temporal relevance and bounded ambiguity delegation for TM2/TGT1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from trademonitor.domain.enums import EpisodeDecision
from trademonitor.domain.models import EpisodeRecord, SourceObservation


@dataclass(frozen=True)
class EpisodeAmbiguityRequest:
    """Bounded question that may be delegated to the external Agents service."""

    observation: SourceObservation
    current_episode: EpisodeRecord
    reason: str


class EpisodeAmbiguityResolver(Protocol):
    """Port implemented by an external ambiguity/Agents service, never by TM core."""

    def resolve(self, request: EpisodeAmbiguityRequest) -> EpisodeDecision: ...


@dataclass(frozen=True)
class EpisodeRelevancePolicy:
    """Small deterministic policy for clear intake cases.

    Contract/context changes inside the relevance window are the deliberately fuzzy
    case. If an external resolver is connected, TM delegates that bounded question;
    otherwise it conservatively creates a new Episode.
    """

    max_gap: timedelta = timedelta(minutes=90)

    def decide(
        self,
        observation: SourceObservation,
        current_episode: EpisodeRecord,
        resolver: EpisodeAmbiguityResolver | None = None,
    ) -> EpisodeDecision:
        gap = observation.observed_at - current_episode.last_observed_at
        if gap.total_seconds() < 0:
            # Older observations are recorded for provenance but never rewrite current relevance.
            return EpisodeDecision.STALE_OBSERVATION
        if gap > self.max_gap:
            return EpisodeDecision.NEW_EPISODE

        incoming = observation.intent.episode_identity()
        current = dict(current_episode.signature)
        if incoming == current:
            return EpisodeDecision.SAME_EPISODE

        incoming_context = incoming.get("context_key")
        current_context = current.get("context_key")
        if incoming_context and current_context and incoming_context == current_context:
            return EpisodeDecision.SAME_EPISODE

        if resolver is not None:
            return EpisodeDecision(
                resolver.resolve(
                    EpisodeAmbiguityRequest(
                        observation=observation,
                        current_episode=current_episode,
                        reason="Material Episode signature changed inside relevance window",
                    )
                )
            )
        return EpisodeDecision.NEW_EPISODE
