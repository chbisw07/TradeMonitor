from datetime import UTC, datetime, timedelta

from trademonitor.candidates.manager import TradeIntakeManager
from trademonitor.candidates.relevance import EpisodeRelevancePolicy
from trademonitor.domain.enums import EpisodeDecision, ExposureRelation, IntakeDisposition
from trademonitor.domain.models import NormalizedTradeIntent
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def make_manager(tmp_path, *, resolver=None):
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db"))
    repo.initialize()
    return TradeIntakeManager(repo, ambiguity_resolver=resolver), repo


def intent(*, underlying="KAYNES", direction="BULLISH", setup="BREAKOUT", contract="KAYNES26SEP4200CE", strike="4200", premium="145", context_key=None):
    return NormalizedTradeIntent(
        underlying=underlying,
        direction=direction,
        setup=setup,
        trade_type="DAY",
        instrument_type="OPTION",
        option_type="CE",
        contract_symbol=contract,
        expiry="2026-09-29",
        strike=strike,
        premium=premium,
        context_key=context_key,
    )


def test_different_sources_same_outcome_share_outcome_and_episode(tmp_path):
    manager, repo = make_manager(tmp_path)
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    first, _ = manager.ingest(src_id="DS-1", source="DAYSCANNER", observed_at=t, intent=intent())
    second, _ = manager.ingest(src_id="USER-9", source="USER", observed_at=t + timedelta(minutes=5), intent=intent())

    assert first.outcome.outcome_id == second.outcome.outcome_id
    assert first.episode.episode_id == second.episode.episode_id
    assert second.disposition == IntakeDisposition.UPDATED_EPISODE
    assert repo.intake_counts() == {"observations": 2, "outcomes": 1, "episodes": 1, "active_episodes": 1}


def test_same_src_id_different_outcomes_remain_distinct(tmp_path):
    manager, repo = make_manager(tmp_path)
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    first, _ = manager.ingest(src_id="DS-RUN-1", source="DAYSCANNER", observed_at=t, intent=intent(setup="BREAKOUT"))
    second, _ = manager.ingest(src_id="DS-RUN-1", source="DAYSCANNER", observed_at=t, intent=intent(setup="PULLBACK"))

    assert first.outcome.outcome_id != second.outcome.outcome_id
    assert repo.intake_counts()["outcomes"] == 2


def test_exact_observation_replay_is_idempotent(tmp_path):
    manager, repo = make_manager(tmp_path)
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    kwargs = dict(src_id="DS-1", source="DAYSCANNER", observed_at=t, intent=intent(), raw_payload={"rank": 1})
    first, _ = manager.ingest(**kwargs)
    replay, _ = manager.ingest(**kwargs)

    assert replay.disposition == IntakeDisposition.DUPLICATE_OBSERVATION
    assert replay.observation.observation_id == first.observation.observation_id
    assert repo.intake_counts()["observations"] == 1


def test_same_outcome_different_contract_creates_new_episode_without_resolver(tmp_path):
    manager, repo = make_manager(tmp_path)
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    first, _ = manager.ingest(src_id="DS-1", source="DAYSCANNER", observed_at=t, intent=intent())
    second, _ = manager.ingest(
        src_id="DS-2", source="DAYSCANNER", observed_at=t + timedelta(minutes=20),
        intent=intent(contract="KAYNES26SEP4300CE", strike="4300", premium="92"),
    )

    assert first.outcome.outcome_id == second.outcome.outcome_id
    assert first.episode.episode_id != second.episode.episode_id
    assert second.disposition == IntakeDisposition.NEW_EPISODE
    assert repo.intake_counts()["episodes"] == 2
    assert repo.intake_counts()["active_episodes"] == 1


def test_same_contract_after_relevance_window_creates_new_episode(tmp_path):
    policy = EpisodeRelevancePolicy(max_gap=timedelta(minutes=30))
    repo = SQLiteRuntimeRepository(Database(tmp_path / "tm.db")); repo.initialize()
    manager = TradeIntakeManager(repo, relevance_policy=policy)
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    first, _ = manager.ingest(src_id="DS-1", source="DAYSCANNER", observed_at=t, intent=intent())
    second, _ = manager.ingest(src_id="DS-2", source="DAYSCANNER", observed_at=t + timedelta(hours=2), intent=intent())

    assert first.outcome.outcome_id == second.outcome.outcome_id
    assert first.episode.episode_id != second.episode.episode_id
    assert second.disposition == IntakeDisposition.NEW_EPISODE


class SameEpisodeResolver:
    def __init__(self):
        self.calls = 0
    def resolve(self, request):
        self.calls += 1
        return EpisodeDecision.SAME_EPISODE


def test_ambiguous_contract_change_can_be_delegated_to_external_resolver(tmp_path):
    resolver = SameEpisodeResolver()
    manager, repo = make_manager(tmp_path, resolver=resolver)
    t = datetime(2026, 9, 3, 10, 15, tzinfo=UTC)
    first, _ = manager.ingest(src_id="DS-1", source="DAYSCANNER", observed_at=t, intent=intent())
    second, _ = manager.ingest(
        src_id="AG-1", source="AGENT_SUGGESTION", observed_at=t + timedelta(minutes=5),
        intent=intent(contract="KAYNES26SEP4100CE", strike="4100", premium="168"),
    )

    assert resolver.calls == 1
    assert first.episode.episode_id == second.episode.episode_id
    assert second.disposition == IntakeDisposition.UPDATED_EPISODE
    assert repo.intake_counts()["episodes"] == 1


def test_stale_observation_is_recorded_without_replacing_active_episode(tmp_path):
    manager, repo = make_manager(tmp_path)
    t = datetime(2026, 9, 3, 12, 15, tzinfo=UTC)
    current, _ = manager.ingest(src_id="DS-NEW", source="DAYSCANNER", observed_at=t, intent=intent())
    stale, _ = manager.ingest(
        src_id="DS-OLD", source="DAYSCANNER", observed_at=t - timedelta(hours=1),
        intent=intent(contract="KAYNES26SEP4100CE", strike="4100"),
    )

    assert stale.disposition == IntakeDisposition.STALE_OBSERVATION
    assert stale.episode.episode_id == current.episode.episode_id
    active = repo.get_active_episode_for_outcome(current.outcome.outcome_id)
    assert active.episode_id == current.episode.episode_id
    assert active.last_observed_at == t
    assert repo.intake_counts()["observations"] == 2
