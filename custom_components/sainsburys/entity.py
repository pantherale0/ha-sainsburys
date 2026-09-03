"""Base entities for the Sainsbury's Groceries integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN
from .coordinator import SainsburysDataUpdateCoordinator


class SainsburysEntity(CoordinatorEntity[SainsburysDataUpdateCoordinator]):
    """Base class for Sainsbury's account entities."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, coordinator: SainsburysDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        customer = coordinator.data.customer
        self._attr_device_info = DeviceInfo(
            configuration_url="https://www.sainsburys.co.uk/gol-ui/",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, customer.user_id)},
            manufacturer="Sainsbury's",
            name=customer.display_name,
        )
