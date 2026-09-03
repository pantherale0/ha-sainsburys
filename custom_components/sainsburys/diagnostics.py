"""Diagnostics for the Sainsbury's Groceries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import SainsburysConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: SainsburysConfigEntry,
) -> dict[str, Any]:
    """Return privacy-conscious diagnostics for a config entry."""
    data = entry.runtime_data.coordinator.data
    return {
        "entry": {
            "version": entry.version,
            "state": entry.state.value,
        },
        "customer": {
            "has_nectar_associated": data.customer.has_nectar_associated,
            "has_nectar_linked": data.customer.has_nectar_linked,
            "is_digital_nectar": data.customer.is_digital_nectar,
            "has_delivery_pass": data.customer.delivery_pass_expiry_date is not None,
        },
        "basket": {
            "item_count": data.basket.item_count,
            "subtotal_price": data.basket.subtotal_price,
            "total_price": data.basket.total_price,
            "slot_price": data.basket.slot_price,
            "savings": data.basket.savings,
            "nectar_savings": data.basket.nectar_savings,
            "is_in_amend_mode": data.basket.is_in_amend_mode,
            "slot_type": data.basket.slot_type,
            "has_exceeded_minimum_spend": data.basket.has_exceeded_minimum_spend,
        },
        "latest_order": (
            {
                "status": data.latest_order.status,
                "slot_type": data.latest_order.slot_type,
                "has_total": data.latest_order.total is not None,
            }
            if data.latest_order is not None
            else None
        ),
        "slot_reservation": {
            "reservation_type": data.slot_reservation.reservation_type,
            "is_expired": data.slot_reservation.is_expired,
            "has_slot": data.slot_reservation.slot is not None,
        },
    }
