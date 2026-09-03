"""TradeMonitor TM1/TGT2 development application."""

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
    """Start the PAPER-only TM1/TGT2 runtime and display durable known state.

    No broker adapter is auto-connected here. Real broker credentials/connectivity
    are intentionally outside TGT2; broker reconciliation is invoked explicitly
    through the read-only Broker contract.
    """
    manager = build_manager()
    manager.start()
    ui = ConsoleUI()
    try:
        print(ui.render_status(manager.status_snapshot()))
        print()
        print(ui.render_positions(manager.positions_snapshot(open_only=True)))
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
