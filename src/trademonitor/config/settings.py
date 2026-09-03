"""Runtime settings for TradeMonitor TM1/TGT1."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Small TM1 settings object. Later milestones can extend validation/config sources."""

    database_path: Path = Path("data/trademonitor.db")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(database_path=Path(os.getenv("TM_DATABASE_PATH", "data/trademonitor.db")))
