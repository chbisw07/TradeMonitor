"""TradeMonitor TM3/TGT4 development application."""

from __future__ import annotations

from trademonitor.config.settings import Settings
from trademonitor.console.ui import ConsoleUI
from trademonitor.core.manager import CoreTMManager
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def build_manager(settings: Settings | None = None) -> CoreTMManager:
    settings = settings or Settings.from_env()
    repository = SQLiteRuntimeRepository(Database(settings.database_path))
    return CoreTMManager(
        repository,
        execution_mode=settings.execution_mode,
        allow_real_broker_writes=settings.allow_real_broker_writes,
        semi_auto_approval_ttl_seconds=settings.semi_auto_approval_ttl_seconds,
        allow_auto_execution=settings.allow_auto_execution,
    )


def main() -> None:
    """Start the TM4/TGT4 control-room runtime.

    Defaults remain PAPER-only. SEMI_AUTO retains per-request approval. AUTO additionally
    requires persisted readiness evidence, an explicit enable decision, and dual arming.
    """
    manager = build_manager()
    manager.start()
    ui = ConsoleUI()
    try:
        print(ui.render_control_room(manager.control_room_snapshot()))
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
