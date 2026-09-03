"""SQLite persistence foundation for TradeMonitor TM1."""

from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    """Own a small SQLite database used for durable runtime state and events."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runtime_contexts (
                    name TEXT PRIMARY KEY,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    data_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS event_log (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_event_log_occurred_at
                    ON event_log(occurred_at);
                CREATE INDEX IF NOT EXISTS idx_event_log_name
                    ON event_log(name);

                CREATE TABLE IF NOT EXISTS positions (
                    position_id TEXT PRIMARY KEY,
                    broker TEXT NOT NULL,
                    broker_position_key TEXT NOT NULL,
                    exchange TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    product TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    average_price TEXT NOT NULL,
                    state TEXT NOT NULL,
                    management_status TEXT NOT NULL,
                    origin TEXT NOT NULL,
                    last_price TEXT,
                    realized_pnl TEXT,
                    unrealized_pnl TEXT,
                    instrument_token TEXT,
                    first_seen_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(broker, broker_position_key)
                );

                CREATE INDEX IF NOT EXISTS idx_positions_broker
                    ON positions(broker);
                CREATE INDEX IF NOT EXISTS idx_positions_state
                    ON positions(state);
                CREATE INDEX IF NOT EXISTS idx_positions_management_status
                    ON positions(management_status);
                """
            )
