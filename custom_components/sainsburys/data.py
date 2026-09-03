"""Runtime data types for the Sainsbury's Groceries integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiohttp import ClientSession
    from homeassistant.config_entries import ConfigEntry
    from pysainsburys import Sainsburys

    from .coordinator import SainsburysDataUpdateCoordinator

type SainsburysConfigEntry = ConfigEntry[SainsburysRuntimeData]


@dataclass(slots=True)
class SainsburysRuntimeData:
    """Store runtime objects for a Sainsbury's account."""

    client: Sainsburys
    coordinator: SainsburysDataUpdateCoordinator
    session: ClientSession
