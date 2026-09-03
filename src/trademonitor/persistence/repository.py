"""Durable repository contracts and SQLite implementation for TM1."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any

from trademonitor.domain.models import PositionRecord
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

    @abstractmethod
    def save_position(self, record: Mapping[str, Any]) -> None: ...

    @abstractmethod
    def list_positions(self, *, broker: str | None = None) -> list[PositionRecord]: ...


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

