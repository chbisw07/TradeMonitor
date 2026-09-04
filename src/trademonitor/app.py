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
    )


def main() -> None:
    """Start the TM4/TGT3 control-room runtime.

    Defaults remain PAPER-only. SEMI_AUTO real writes require explicit settings,
    a non-simulation broker adapter, current Risk permission, and per-request User approval.
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
