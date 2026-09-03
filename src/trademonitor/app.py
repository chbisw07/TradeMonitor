"""TradeMonitor TM2/TGT1 development application."""

from __future__ import annotations

from trademonitor.config.settings import Settings
from trademonitor.console.ui import ConsoleUI
from trademonitor.core.manager import CoreTMManager
from trademonitor.persistence.database import Database
from trademonitor.persistence.repository import SQLiteRuntimeRepository


def build_manager(settings: Settings | None = None) -> CoreTMManager:
    settings = settings or Settings.from_env()
    repository = SQLiteRuntimeRepository(Database(settings.database_path))
    return CoreTMManager(repository)


def main() -> None:
    """Start the PAPER-only TM2/TGT1 control-room runtime.

    No broker adapter is auto-connected. Real broker credentials/connectivity and
    all broker writes remain outside TM2/TGT1.
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
