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


                CREATE TABLE IF NOT EXISTS position_management_profiles (
                    position_id TEXT PRIMARY KEY,
                    asset_class TEXT NOT NULL,
                    instrument_type TEXT NOT NULL,
                    trade_type TEXT NOT NULL,
                    horizon_at TEXT NOT NULL,
                    expiry_date TEXT,
                    activated_at TEXT NOT NULL,
                    activated_by TEXT NOT NULL,
                    activation_reason TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY(position_id) REFERENCES positions(position_id)
                );



                CREATE TABLE IF NOT EXISTS position_management_rules (
                    rule_id TEXT PRIMARY KEY,
                    position_id TEXT NOT NULL,
                    rule_type TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    runtime_state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    policy_name TEXT,
                    FOREIGN KEY(position_id) REFERENCES positions(position_id)
                );

                CREATE INDEX IF NOT EXISTS idx_management_rules_position_status
                    ON position_management_rules(position_id, status);

                CREATE TABLE IF NOT EXISTS exit_proposals (
                    proposal_id TEXT PRIMARY KEY,
                    position_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(position_id) REFERENCES positions(position_id)
                );

                CREATE INDEX IF NOT EXISTS idx_exit_proposals_position_status
                    ON exit_proposals(position_id, status);

                CREATE TABLE IF NOT EXISTS exit_reviews (
                    review_id TEXT PRIMARY KEY,
                    exit_proposal_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(exit_proposal_id) REFERENCES exit_proposals(proposal_id)
                );

                CREATE INDEX IF NOT EXISTS idx_exit_reviews_proposal_updated
                    ON exit_reviews(exit_proposal_id, updated_at);

                                CREATE TABLE IF NOT EXISTS intake_outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    outcome_key TEXT NOT NULL UNIQUE,
                    identity_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS intake_episodes (
                    episode_id TEXT PRIMARY KEY,
                    outcome_id TEXT NOT NULL,
                    signature_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    last_observed_at TEXT NOT NULL,
                    latest_observation_id TEXT NOT NULL,
                    FOREIGN KEY(outcome_id) REFERENCES intake_outcomes(outcome_id)
                );

                CREATE INDEX IF NOT EXISTS idx_intake_episodes_outcome_status
                    ON intake_episodes(outcome_id, status);

                CREATE TABLE IF NOT EXISTS source_observations (
                    observation_id TEXT PRIMARY KEY,
                    dedupe_key TEXT NOT NULL UNIQUE,
                    src_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    intent_json TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL,
                    outcome_id TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    FOREIGN KEY(outcome_id) REFERENCES intake_outcomes(outcome_id),
                    FOREIGN KEY(episode_id) REFERENCES intake_episodes(episode_id)
                );

                CREATE INDEX IF NOT EXISTS idx_source_observations_src_id
                    ON source_observations(src_id);
                CREATE INDEX IF NOT EXISTS idx_source_observations_outcome
                    ON source_observations(outcome_id, observed_at);

                CREATE TABLE IF NOT EXISTS entry_intents (
                    entry_intent_id TEXT PRIMARY KEY,
                    episode_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(episode_id) REFERENCES intake_episodes(episode_id)
                );

                CREATE INDEX IF NOT EXISTS idx_entry_intents_episode_state
                    ON entry_intents(episode_id, state);

                CREATE TABLE IF NOT EXISTS entry_reviews (
                    review_id TEXT PRIMARY KEY,
                    entry_intent_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(entry_intent_id) REFERENCES entry_intents(entry_intent_id)
                );

                CREATE INDEX IF NOT EXISTS idx_entry_reviews_intent_updated
                    ON entry_reviews(entry_intent_id, updated_at);

                CREATE TABLE IF NOT EXISTS risk_profiles (
                    version INTEGER PRIMARY KEY,
                    record_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS risk_decisions (
                    decision_id TEXT PRIMARY KEY,
                    entry_intent_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL,
                    FOREIGN KEY(entry_intent_id) REFERENCES entry_intents(entry_intent_id)
                );

                CREATE INDEX IF NOT EXISTS idx_risk_decisions_intent_time
                    ON risk_decisions(entry_intent_id, evaluated_at);

                CREATE TABLE IF NOT EXISTS risk_profile_changes (
                    change_id TEXT PRIMARY KEY,
                    record_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requested_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS execution_requests (
                    request_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    record_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_execution_requests_status
                    ON execution_requests(status);

                CREATE TABLE IF NOT EXISTS execution_approvals (
                    approval_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(request_id) REFERENCES execution_requests(request_id)
                );

                CREATE INDEX IF NOT EXISTS idx_execution_approvals_request
                    ON execution_approvals(request_id, updated_at);
                """
            )
