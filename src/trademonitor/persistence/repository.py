"""Durable repository contracts and SQLite implementation for TM1/TGT1."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

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
    def append_event(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def list_events(self, *, limit: int | None = None) -> list[dict[str, Any]]: ...


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

    def append_event(self, record: Mapping[str, Any]) -> None:
        payload_json = json.dumps(record.get("payload", {}), sort_keys=True, default=str)
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO event_log(event_id, name, occurred_at, source, payload_json)
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
