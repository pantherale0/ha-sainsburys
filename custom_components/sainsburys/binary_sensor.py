"""Binary sensor platform for the Sainsbury's Groceries integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory

from .entity import SainsburysEntity

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

    from .coordinator import SainsburysData, SainsburysDataUpdateCoordinator
    from .data import SainsburysConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SainsburysBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a Sainsbury's binary sensor."""

    value_fn: Callable[[SainsburysData], bool]


BINARY_SENSOR_DESCRIPTIONS: tuple[SainsburysBinarySensorEntityDescription, ...] = (
    SainsburysBinarySensorEntityDescription(
        key="minimum_spend_met",
        translation_key="minimum_spend_met",
        value_fn=lambda data: data.basket.has_exceeded_minimum_spend,
    ),
    SainsburysBinarySensorEntityDescription(
        key="order_amendable",
        translation_key="order_amendable",
        value_fn=lambda data: (
            data.latest_order_status.is_in_amend_mode
            if data.latest_order_status is not None
            else False
        ),
    ),
    SainsburysBinarySensorEntityDescription(
        key="nectar_linked",
        translation_key="nectar_linked",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.customer.has_nectar_linked,
    ),
    SainsburysBinarySensorEntityDescription(
        key="slot_reserved",
        translation_key="slot_reserved",
        value_fn=lambda data: (
            data.slot_reservation.slot is not None
            and not data.slot_reservation.is_expired
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SainsburysConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sainsbury's binary sensors."""
    async_add_entities(
        SainsburysBinarySensor(entry.runtime_data.coordinator, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class SainsburysBinarySensor(SainsburysEntity, BinarySensorEntity):
    """Represent Sainsbury's account state as a binary sensor."""

    entity_description: SainsburysBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SainsburysDataUpdateCoordinator,
        entity_description: SainsburysBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.data.customer.user_id}_{entity_description.key}"
        )

    @property
    @override
    def is_on(self) -> bool:
        """Return whether the condition is true."""
        return self.entity_description.value_fn(self.coordinator.data)
