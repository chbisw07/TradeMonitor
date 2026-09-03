"""Settings placeholder."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """TODO: expand settings when integrations are introduced."""

    environment: str = "development"
