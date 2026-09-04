"""Durable repository contracts and SQLite implementation for TM1."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from trademonitor.domain.models import (
    EntryIntentRecord,
    EntryReviewRecord,
    EpisodeRecord,
    OutcomeRecord,
    PositionRecord,
    PositionManagementProfile,
    SourceObservation,
    RiskProfile,
    RiskDecisionRecord,
    RiskProfileChange,
    PositionManagementRule,
    ExitProposal,
    ExitReviewRecord,
)
from trademonitor.persistence.database import Database


class RuntimeRepository(ABC):
    """Persistence contract required by the Core TM Manager."""

    @abstractmethod
    def initialize(self) -> None: ...

    @abstractmethod
    def save_context(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def load_contexts(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def append_event(self, record: Mapping[str, Any]) -> bool: ...

    @abstractmethod
    def list_events(self, *, limit: int | None = None) -> list[dict[str, Any]]: ...

    @abstractmethod
    def save_position(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def list_positions(self, *, broker: str | None = None) -> list[PositionRecord]: ...

    @abstractmethod
    def get_position(self, position_id: str) -> PositionRecord | None: ...

    @abstractmethod
    def save_position_management_profile(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_position_management_profile(self, position_id: str) -> PositionManagementProfile | None: ...


    @abstractmethod
    def save_management_rule(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_management_rule(self, rule_id: str) -> PositionManagementRule | None: ...

    @abstractmethod
    def list_management_rules(
        self, *, position_id: str | None = None, active_only: bool = False
    ) -> list[PositionManagementRule]: ...


    @abstractmethod
    def save_exit_proposal(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_exit_proposal(self, proposal_id: str) -> ExitProposal | None: ...

    @abstractmethod
    def list_exit_proposals(
        self, *, position_id: str | None = None, active_only: bool = False
    ) -> list[ExitProposal]: ...

    @abstractmethod
    def save_exit_review(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_exit_review(self, review_id: str) -> ExitReviewRecord | None: ...

    @abstractmethod
    def get_latest_exit_review(self, exit_proposal_id: str) -> ExitReviewRecord | None: ...

    @abstractmethod
    def list_exit_reviews(
        self, *, exit_proposal_id: str | None = None
    ) -> list[ExitReviewRecord]: ...

    @abstractmethod
    def save_source_observation(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_source_observation_by_dedupe_key(self, dedupe_key: str) -> SourceObservation | None: ...

    @abstractmethod
    def save_outcome(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_outcome(self, outcome_id: str) -> OutcomeRecord | None: ...

    @abstractmethod
    def get_outcome_by_key(self, outcome_key: str) -> OutcomeRecord | None: ...

    @abstractmethod
    def save_episode(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_episode(self, episode_id: str) -> EpisodeRecord | None: ...

    @abstractmethod
    def get_active_episode_for_outcome(self, outcome_id: str) -> EpisodeRecord | None: ...

    @abstractmethod
    def intake_counts(self) -> dict[str, int]: ...

    @abstractmethod
    def save_entry_intent(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_entry_intent(self, entry_intent_id: str) -> EntryIntentRecord | None: ...

    @abstractmethod
    def get_active_entry_intent_for_episode(self, episode_id: str) -> EntryIntentRecord | None: ...

    @abstractmethod
    def list_entry_intents(self, *, active_only: bool = False) -> list[EntryIntentRecord]: ...

    @abstractmethod
    def save_entry_review(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_entry_review(self, review_id: str) -> EntryReviewRecord | None: ...

    @abstractmethod
    def get_latest_entry_review(self, entry_intent_id: str) -> EntryReviewRecord | None: ...

    @abstractmethod
    def list_entry_reviews(self, *, entry_intent_id: str | None = None) -> list[EntryReviewRecord]: ...

    @abstractmethod
    def save_risk_profile(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_active_risk_profile(self) -> RiskProfile | None: ...

    @abstractmethod
    def save_risk_decision(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def list_risk_decisions(self, *, entry_intent_id: str | None = None) -> list[RiskDecisionRecord]: ...

    @abstractmethod
    def save_risk_profile_change(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def get_risk_profile_change(self, change_id: str) -> RiskProfileChange | None: ...


# Backward-compatible name retained from TM0 skeleton.
Repository = RuntimeRepository


class SQLiteRuntimeRepository(RuntimeRepository):
    """SQLite-backed implementation of the TM1 runtime repository."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def initialize(self) -> None:
        self._database.initialize()

    def save_context(self, record: Mapping[str, Any]) -> None:
        data_json = json.dumps(record.get("data", {}), sort_keys=True, default=str)
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_contexts(name, version, updated_at, data_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    version = excluded.version,
                    updated_at = excluded.updated_at,
                    data_json = excluded.data_json
                """,
                (
                    str(record["name"]),
                    int(record.get("version", 0)),
                    str(record["updated_at"]),
                    data_json,
                ),
            )

    def load_contexts(self) -> list[dict[str, Any]]:
        with self._database.connect() as connection:
            rows = connection.execute(
                "SELECT name, version, updated_at, data_json FROM runtime_contexts ORDER BY name"
            ).fetchall()
        return [
            {
                "name": row["name"],
                "version": row["version"],
                "updated_at": row["updated_at"],
                "data": json.loads(row["data_json"]),
            }
            for row in rows
        ]

    def append_event(self, record: Mapping[str, Any]) -> bool:
        """Append once by event_id; duplicate/replayed events are harmless."""
        payload_json = json.dumps(record.get("payload", {}), sort_keys=True, default=str)
        with self._database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO event_log(event_id, name, occurred_at, source, payload_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(record["event_id"]),
                    str(record["name"]),
                    str(record["occurred_at"]),
                    str(record["source"]),
                    payload_json,
                ),
            )
        return cursor.rowcount == 1

    def list_events(self, *, limit: int | None = None) -> list[dict[str, Any]]:
        query = (
            "SELECT sequence, event_id, name, occurred_at, source, payload_json "
            "FROM event_log ORDER BY sequence"
        )
        params: tuple[Any, ...] = ()
        if limit is not None:
            query += " LIMIT ?"
            params = (int(limit),)
        with self._database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "event_id": row["event_id"],
                "name": row["name"],
                "occurred_at": row["occurred_at"],
                "source": row["source"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def save_position(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO positions(
                    position_id, broker, broker_position_key, exchange, symbol, product,
                    quantity, average_price, state, management_status, origin, last_price,
                    realized_pnl, unrealized_pnl, instrument_token, first_seen_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(broker, broker_position_key) DO UPDATE SET
                    position_id = excluded.position_id,
                    exchange = excluded.exchange,
                    symbol = excluded.symbol,
                    product = excluded.product,
                    quantity = excluded.quantity,
                    average_price = excluded.average_price,
                    state = excluded.state,
                    management_status = excluded.management_status,
                    origin = excluded.origin,
                    last_price = excluded.last_price,
                    realized_pnl = excluded.realized_pnl,
                    unrealized_pnl = excluded.unrealized_pnl,
                    instrument_token = excluded.instrument_token,
                    first_seen_at = excluded.first_seen_at,
                    updated_at = excluded.updated_at
                """,
                (
                    str(record["position_id"]),
                    str(record["broker"]),
                    str(record["broker_position_key"]),
                    str(record["exchange"]),
                    str(record["symbol"]),
                    str(record["product"]),
                    int(record["quantity"]),
                    str(record["average_price"]),
                    str(record["state"]),
                    str(record["management_status"]),
                    str(record["origin"]),
                    record.get("last_price"),
                    record.get("realized_pnl"),
                    record.get("unrealized_pnl"),
                    record.get("instrument_token"),
                    str(record["first_seen_at"]),
                    str(record["updated_at"]),
                ),
            )

    def list_positions(self, *, broker: str | None = None) -> list[PositionRecord]:
        query = "SELECT * FROM positions"
        params: tuple[Any, ...] = ()
        if broker is not None:
            query += " WHERE broker = ?"
            params = (broker,)
        query += " ORDER BY broker, symbol, product, broker_position_key"
        with self._database.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [
            PositionRecord.from_record(
                {
                    "position_id": row["position_id"],
                    "broker": row["broker"],
                    "broker_position_key": row["broker_position_key"],
                    "exchange": row["exchange"],
                    "symbol": row["symbol"],
                    "product": row["product"],
                    "quantity": row["quantity"],
                    "average_price": row["average_price"],
                    "state": row["state"],
                    "management_status": row["management_status"],
                    "origin": row["origin"],
                    "last_price": row["last_price"],
                    "realized_pnl": row["realized_pnl"],
                    "unrealized_pnl": row["unrealized_pnl"],
                    "instrument_token": row["instrument_token"],
                    "first_seen_at": row["first_seen_at"],
                    "updated_at": row["updated_at"],
                }
            )
            for row in rows
        ]

    def get_position(self, position_id: str) -> PositionRecord | None:
        with self._database.connect() as connection:
            row = connection.execute("SELECT * FROM positions WHERE position_id = ?", (position_id,)).fetchone()
        if row is None:
            return None
        return PositionRecord.from_record(dict(row))

    def save_position_management_profile(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO position_management_profiles(
                    position_id, asset_class, instrument_type, trade_type, horizon_at,
                    expiry_date, activated_at, activated_by, activation_reason, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(position_id) DO UPDATE SET
                    asset_class=excluded.asset_class,
                    instrument_type=excluded.instrument_type,
                    trade_type=excluded.trade_type,
                    horizon_at=excluded.horizon_at,
                    expiry_date=excluded.expiry_date,
                    activated_at=excluded.activated_at,
                    activated_by=excluded.activated_by,
                    activation_reason=excluded.activation_reason,
                    notes=excluded.notes
                """,
                (
                    str(record["position_id"]), str(record["asset_class"]),
                    str(record["instrument_type"]), str(record["trade_type"]),
                    str(record["horizon_at"]), record.get("expiry_date"),
                    str(record["activated_at"]), str(record["activated_by"]),
                    str(record["activation_reason"]), record.get("notes"),
                ),
            )

    def get_position_management_profile(self, position_id: str) -> PositionManagementProfile | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM position_management_profiles WHERE position_id = ?",
                (position_id,),
            ).fetchone()
        if row is None:
            return None
        return PositionManagementProfile.from_record(dict(row))


    def save_management_rule(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO position_management_rules(
                    rule_id, position_id, rule_type, parameters_json, status,
                    runtime_state_json, created_at, updated_at, created_by, reason, policy_name
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(rule_id) DO UPDATE SET
                    rule_type=excluded.rule_type,
                    parameters_json=excluded.parameters_json,
                    status=excluded.status,
                    runtime_state_json=excluded.runtime_state_json,
                    updated_at=excluded.updated_at,
                    created_by=excluded.created_by,
                    reason=excluded.reason,
                    policy_name=excluded.policy_name
                """,
                (
                    str(record["rule_id"]), str(record["position_id"]), str(record["rule_type"]),
                    json.dumps(record.get("parameters", {}), sort_keys=True, default=str),
                    str(record["status"]),
                    json.dumps(record.get("runtime_state", {}), sort_keys=True, default=str),
                    str(record["created_at"]), str(record["updated_at"]),
                    str(record["created_by"]), str(record["reason"]), record.get("policy_name"),
                ),
            )

    def get_management_rule(self, rule_id: str) -> PositionManagementRule | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM position_management_rules WHERE rule_id = ?", (rule_id,)
            ).fetchone()
        return self._management_rule_from_row(row)

    def list_management_rules(
        self, *, position_id: str | None = None, active_only: bool = False
    ) -> list[PositionManagementRule]:
        query = "SELECT * FROM position_management_rules"
        clauses: list[str] = []
        params: list[Any] = []
        if position_id is not None:
            clauses.append("position_id = ?")
            params.append(position_id)
        if active_only:
            clauses.append("status NOT IN ('TRIGGERED', 'CANCELLED')")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, rule_id"
        with self._database.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [self._management_rule_from_row(row) for row in rows if row is not None]

    @staticmethod
    def _management_rule_from_row(row) -> PositionManagementRule | None:
        if row is None:
            return None
        return PositionManagementRule.from_record({
            "rule_id": row["rule_id"],
            "position_id": row["position_id"],
            "rule_type": row["rule_type"],
            "parameters": json.loads(row["parameters_json"]),
            "status": row["status"],
            "runtime_state": json.loads(row["runtime_state_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "created_by": row["created_by"],
            "reason": row["reason"],
            "policy_name": row["policy_name"],
        })


    def save_exit_proposal(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO exit_proposals(proposal_id, position_id, record_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(proposal_id) DO UPDATE SET
                    record_json=excluded.record_json,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (
                    str(record["proposal_id"]), str(record["position_id"]),
                    json.dumps(dict(record), sort_keys=True, default=str), str(record["status"]),
                    str(record["created_at"]), str(record["updated_at"]),
                ),
            )

    def list_exit_proposals(
        self, *, position_id: str | None = None, active_only: bool = False
    ) -> list[ExitProposal]:
        query = "SELECT record_json FROM exit_proposals"
        clauses: list[str] = []
        params: list[Any] = []
        if position_id is not None:
            clauses.append("position_id = ?")
            params.append(position_id)
        if active_only:
            clauses.append("status IN ('PENDING', 'APPROVED')")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY created_at, proposal_id"
        with self._database.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [ExitProposal.from_record(json.loads(row["record_json"])) for row in rows]

    def get_exit_proposal(self, proposal_id: str) -> ExitProposal | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM exit_proposals WHERE proposal_id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return ExitProposal.from_record(json.loads(row["record_json"]))

    def save_exit_review(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO exit_reviews(review_id, exit_proposal_id, record_json, status, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(review_id) DO UPDATE SET
                    record_json=excluded.record_json,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (
                    str(record["review_id"]), str(record["exit_proposal_id"]),
                    json.dumps(dict(record), sort_keys=True, default=str),
                    str(record["status"]), str(record["updated_at"]),
                ),
            )

    @staticmethod
    def _exit_review_from_row(row) -> ExitReviewRecord | None:
        if row is None:
            return None
        return ExitReviewRecord.from_record(json.loads(row["record_json"]))

    def get_exit_review(self, review_id: str) -> ExitReviewRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT record_json FROM exit_reviews WHERE review_id = ?", (review_id,)
            ).fetchone()
        return self._exit_review_from_row(row)

    def get_latest_exit_review(self, exit_proposal_id: str) -> ExitReviewRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """SELECT record_json FROM exit_reviews WHERE exit_proposal_id = ?
                   ORDER BY updated_at DESC, review_id DESC LIMIT 1""",
                (exit_proposal_id,),
            ).fetchone()
        return self._exit_review_from_row(row)

    def list_exit_reviews(self, *, exit_proposal_id: str | None = None) -> list[ExitReviewRecord]:
        sql = "SELECT record_json FROM exit_reviews"
        params: tuple[Any, ...] = ()
        if exit_proposal_id is not None:
            sql += " WHERE exit_proposal_id = ?"
            params = (exit_proposal_id,)
        sql += " ORDER BY updated_at, review_id"
        with self._database.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [ExitReviewRecord.from_record(json.loads(row["record_json"])) for row in rows]


    def save_source_observation(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO source_observations(
                    observation_id, dedupe_key, src_id, source, observed_at, intent_json,
                    raw_payload_json, outcome_id, episode_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record["observation_id"]), str(record["dedupe_key"]),
                    str(record["src_id"]), str(record["source"]), str(record["observed_at"]),
                    json.dumps(record["intent"], sort_keys=True, default=str),
                    json.dumps(record.get("raw_payload", {}), sort_keys=True, default=str),
                    str(record["outcome_id"]), str(record["episode_id"]),
                ),
            )

    def get_source_observation_by_dedupe_key(self, dedupe_key: str) -> SourceObservation | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM source_observations WHERE dedupe_key = ?", (dedupe_key,)
            ).fetchone()
        if row is None:
            return None
        return SourceObservation.from_record({
            "observation_id": row["observation_id"], "dedupe_key": row["dedupe_key"],
            "src_id": row["src_id"], "source": row["source"], "observed_at": row["observed_at"],
            "intent": json.loads(row["intent_json"]), "raw_payload": json.loads(row["raw_payload_json"]),
            "outcome_id": row["outcome_id"], "episode_id": row["episode_id"],
        })

    def save_outcome(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO intake_outcomes(outcome_id, outcome_key, identity_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(outcome_id) DO UPDATE SET
                    outcome_key=excluded.outcome_key, identity_json=excluded.identity_json,
                    created_at=excluded.created_at, updated_at=excluded.updated_at
                """,
                (str(record["outcome_id"]), str(record["outcome_key"]),
                 json.dumps(record["identity"], sort_keys=True, default=str),
                 str(record["created_at"]), str(record["updated_at"])),
            )

    def _outcome_from_row(self, row) -> OutcomeRecord | None:
        if row is None:
            return None
        return OutcomeRecord.from_record({
            "outcome_id": row["outcome_id"], "outcome_key": row["outcome_key"],
            "identity": json.loads(row["identity_json"]), "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })

    def get_outcome(self, outcome_id: str) -> OutcomeRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM intake_outcomes WHERE outcome_id = ?", (outcome_id,)
            ).fetchone()
        return self._outcome_from_row(row)

    def get_outcome_by_key(self, outcome_key: str) -> OutcomeRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM intake_outcomes WHERE outcome_key = ?", (outcome_key,)
            ).fetchone()
        return self._outcome_from_row(row)

    def save_episode(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO intake_episodes(
                    episode_id, outcome_id, signature_json, status, started_at,
                    last_observed_at, latest_observation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(episode_id) DO UPDATE SET
                    outcome_id=excluded.outcome_id, signature_json=excluded.signature_json,
                    status=excluded.status, started_at=excluded.started_at,
                    last_observed_at=excluded.last_observed_at,
                    latest_observation_id=excluded.latest_observation_id
                """,
                (str(record["episode_id"]), str(record["outcome_id"]),
                 json.dumps(record.get("signature", {}), sort_keys=True, default=str),
                 str(record["status"]), str(record["started_at"]),
                 str(record["last_observed_at"]), str(record["latest_observation_id"])),
            )

    def _episode_from_row(self, row) -> EpisodeRecord | None:
        if row is None:
            return None
        return EpisodeRecord.from_record({
            "episode_id": row["episode_id"], "outcome_id": row["outcome_id"],
            "signature": json.loads(row["signature_json"]), "status": row["status"],
            "started_at": row["started_at"], "last_observed_at": row["last_observed_at"],
            "latest_observation_id": row["latest_observation_id"],
        })

    def get_episode(self, episode_id: str) -> EpisodeRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM intake_episodes WHERE episode_id = ?", (episode_id,)
            ).fetchone()
        return self._episode_from_row(row)

    def get_active_episode_for_outcome(self, outcome_id: str) -> EpisodeRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """SELECT * FROM intake_episodes
                   WHERE outcome_id = ? AND status = 'ACTIVE'
                   ORDER BY last_observed_at DESC LIMIT 1""", (outcome_id,)
            ).fetchone()
        return self._episode_from_row(row)

    def intake_counts(self) -> dict[str, int]:
        with self._database.connect() as connection:
            observations = connection.execute("SELECT COUNT(*) AS n FROM source_observations").fetchone()["n"]
            outcomes = connection.execute("SELECT COUNT(*) AS n FROM intake_outcomes").fetchone()["n"]
            episodes = connection.execute("SELECT COUNT(*) AS n FROM intake_episodes").fetchone()["n"]
            active = connection.execute("SELECT COUNT(*) AS n FROM intake_episodes WHERE status='ACTIVE'").fetchone()["n"]
        return {"observations": observations, "outcomes": outcomes, "episodes": episodes, "active_episodes": active}
    def save_entry_intent(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO entry_intents(entry_intent_id, episode_id, record_json, state, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entry_intent_id) DO UPDATE SET
                    episode_id=excluded.episode_id, record_json=excluded.record_json,
                    state=excluded.state, updated_at=excluded.updated_at
                """,
                (str(record["entry_intent_id"]), str(record["episode_id"]),
                 json.dumps(dict(record), sort_keys=True, default=str),
                 str(record["state"]), str(record["updated_at"])),
            )

    @staticmethod
    def _entry_intent_from_row(row) -> EntryIntentRecord | None:
        if row is None:
            return None
        return EntryIntentRecord.from_record(json.loads(row["record_json"]))

    def get_entry_intent(self, entry_intent_id: str) -> EntryIntentRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM entry_intents WHERE entry_intent_id = ?", (entry_intent_id,)
            ).fetchone()
        return self._entry_intent_from_row(row)

    def get_active_entry_intent_for_episode(self, episode_id: str) -> EntryIntentRecord | None:
        terminal = ("REJECTED", "INVALIDATED", "EXPIRED", "CANCELLED")
        with self._database.connect() as connection:
            row = connection.execute(
                """SELECT * FROM entry_intents WHERE episode_id = ?
                   AND state NOT IN (?, ?, ?, ?) ORDER BY updated_at DESC LIMIT 1""",
                (episode_id, *terminal),
            ).fetchone()
        return self._entry_intent_from_row(row)

    def list_entry_intents(self, *, active_only: bool = False) -> list[EntryIntentRecord]:
        sql = "SELECT * FROM entry_intents"
        params = ()
        if active_only:
            sql += " WHERE state NOT IN (?, ?, ?, ?)"
            params = ("REJECTED", "INVALIDATED", "EXPIRED", "CANCELLED")
        sql += " ORDER BY updated_at, entry_intent_id"
        with self._database.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._entry_intent_from_row(row) for row in rows]

    def save_entry_review(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO entry_reviews(review_id, entry_intent_id, record_json, status, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(review_id) DO UPDATE SET
                    entry_intent_id=excluded.entry_intent_id,
                    record_json=excluded.record_json,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (
                    str(record["review_id"]),
                    str(record["entry_intent_id"]),
                    json.dumps(dict(record), sort_keys=True, default=str),
                    str(record["status"]),
                    str(record["updated_at"]),
                ),
            )

    @staticmethod
    def _entry_review_from_row(row) -> EntryReviewRecord | None:
        if row is None:
            return None
        return EntryReviewRecord.from_record(json.loads(row["record_json"]))

    def get_entry_review(self, review_id: str) -> EntryReviewRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM entry_reviews WHERE review_id = ?", (review_id,)
            ).fetchone()
        return self._entry_review_from_row(row)

    def get_latest_entry_review(self, entry_intent_id: str) -> EntryReviewRecord | None:
        with self._database.connect() as connection:
            row = connection.execute(
                """SELECT * FROM entry_reviews WHERE entry_intent_id = ?
                   ORDER BY updated_at DESC, review_id DESC LIMIT 1""",
                (entry_intent_id,),
            ).fetchone()
        return self._entry_review_from_row(row)

    def list_entry_reviews(self, *, entry_intent_id: str | None = None) -> list[EntryReviewRecord]:
        sql = "SELECT * FROM entry_reviews"
        params: tuple[str, ...] = ()
        if entry_intent_id is not None:
            sql += " WHERE entry_intent_id = ?"
            params = (entry_intent_id,)
        sql += " ORDER BY updated_at, review_id"
        with self._database.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._entry_review_from_row(row) for row in rows]

    def save_risk_profile(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """INSERT INTO risk_profiles(version, record_json, created_at) VALUES (?, ?, ?)
                   ON CONFLICT(version) DO UPDATE SET record_json=excluded.record_json, created_at=excluded.created_at""",
                (int(record["version"]), json.dumps(dict(record), sort_keys=True, default=str), str(record["created_at"])),
            )

    def get_active_risk_profile(self) -> RiskProfile | None:
        with self._database.connect() as connection:
            row = connection.execute("SELECT * FROM risk_profiles ORDER BY version DESC LIMIT 1").fetchone()
        if row is None:
            return None
        return RiskProfile.from_record(json.loads(row["record_json"]))

    def save_risk_decision(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """INSERT INTO risk_decisions(decision_id, entry_intent_id, record_json, decision, evaluated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(decision_id) DO UPDATE SET record_json=excluded.record_json, decision=excluded.decision, evaluated_at=excluded.evaluated_at""",
                (str(record["decision_id"]), str(record["entry_intent_id"]), json.dumps(dict(record), sort_keys=True, default=str), str(record["decision"]), str(record["evaluated_at"])),
            )

    def list_risk_decisions(self, *, entry_intent_id: str | None = None) -> list[RiskDecisionRecord]:
        sql = "SELECT * FROM risk_decisions"
        params: tuple[str, ...] = ()
        if entry_intent_id is not None:
            sql += " WHERE entry_intent_id = ?"
            params = (entry_intent_id,)
        sql += " ORDER BY evaluated_at, decision_id"
        with self._database.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [RiskDecisionRecord.from_record(json.loads(row["record_json"])) for row in rows]

    def save_risk_profile_change(self, record: Mapping[str, Any]) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """INSERT INTO risk_profile_changes(change_id, record_json, status, requested_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(change_id) DO UPDATE SET record_json=excluded.record_json, status=excluded.status, requested_at=excluded.requested_at""",
                (str(record["change_id"]), json.dumps(dict(record), sort_keys=True, default=str), str(record["status"]), str(record["requested_at"])),
            )

    def get_risk_profile_change(self, change_id: str) -> RiskProfileChange | None:
        with self._database.connect() as connection:
            row = connection.execute("SELECT * FROM risk_profile_changes WHERE change_id = ?", (change_id,)).fetchone()
        if row is None:
            return None
        return RiskProfileChange.from_record(json.loads(row["record_json"]))

