"""Runtime settings for TradeMonitor TM1."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from trademonitor.domain.enums import ExecutionMode


@dataclass(frozen=True)
class Settings:
    """Runtime settings. Defaults remain deliberately safe/PAPER-only."""

    database_path: Path = Path("data/trademonitor.db")
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    allow_real_broker_writes: bool = False
    semi_auto_approval_ttl_seconds: int = 60
    allow_auto_execution: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        raw_mode = os.getenv("TM_EXECUTION_MODE", "PAPER").strip().upper()
        mode = ExecutionMode(raw_mode)
        allow = os.getenv("TM_ALLOW_REAL_BROKER_WRITES", "false").strip().lower() in {"1", "true", "yes", "on"}
        auto = os.getenv("TM_ALLOW_AUTO_EXECUTION", "false").strip().lower() in {"1", "true", "yes", "on"}
        ttl = int(os.getenv("TM_SEMI_AUTO_APPROVAL_TTL_SECONDS", "60"))
        if ttl <= 0:
            raise ValueError("TM_SEMI_AUTO_APPROVAL_TTL_SECONDS must be positive")
        return cls(
            database_path=Path(os.getenv("TM_DATABASE_PATH", "data/trademonitor.db")),
            execution_mode=mode,
            allow_real_broker_writes=allow,
            semi_auto_approval_ttl_seconds=ttl,
            allow_auto_execution=auto,
        )
