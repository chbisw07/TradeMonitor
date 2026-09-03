"""TM0 smoke tests."""

import importlib


def test_trademonitor_package_imports() -> None:
    """The package should import without initializing trading behavior."""
    package = importlib.import_module("trademonitor")

    assert package.__name__ == "trademonitor"


def test_app_module_imports() -> None:
    """The app module should import without running trading behavior."""
    app = importlib.import_module("trademonitor.app")

    assert callable(app.main)
