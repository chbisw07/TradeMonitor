"""Durable repository contracts and SQLite implementation for TM1."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from trademonitor.domain.models import EntryIntentRecord, EpisodeRecord, OutcomeRecord, PositionRecord, SourceObservation
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
        terminal = ("INVALIDATED", "EXPIRED", "CANCELLED")
        with self._database.connect() as connection:
            row = connection.execute(
                """SELECT * FROM entry_intents WHERE episode_id = ?
                   AND state NOT IN (?, ?, ?) ORDER BY updated_at DESC LIMIT 1""",
                (episode_id, *terminal),
            ).fetchone()
        return self._entry_intent_from_row(row)

    def list_entry_intents(self, *, active_only: bool = False) -> list[EntryIntentRecord]:
        sql = "SELECT * FROM entry_intents"
        params = ()
        if active_only:
            sql += " WHERE state NOT IN (?, ?, ?)"
            params = ("INVALIDATED", "EXPIRED", "CANCELLED")
        sql += " ORDER BY updated_at, entry_intent_id"
        with self._database.connect() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [self._entry_intent_from_row(row) for row in rows]

