"""Tests for Sainsbury's service actions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientConnectionError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pysainsburys import Product
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sainsburys.const import (
    DOMAIN,
    SERVICE_ADD_BASKET_ITEM,
    SERVICE_CLEAR_BASKET,
    SERVICE_GET_PRODUCT,
    SERVICE_REMOVE_BASKET_ITEM,
    SERVICE_SEARCH_PRODUCTS,
    SERVICE_SET_BASKET_ITEM,
)
from custom_components.sainsburys.services import _entry_for_call, async_setup_services


def _entry() -> MockConfigEntry:
    """Build a loaded account runtime mock."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.runtime_data = MagicMock()
    entry.runtime_data.client.search_products = AsyncMock()
    entry.runtime_data.client.get_product = AsyncMock()
    entry.runtime_data.coordinator.async_request_refresh = AsyncMock()
    basket = entry.runtime_data.coordinator.data.customer.basket
    basket.add = AsyncMock()
    basket.set_quantity = AsyncMock()
    basket.remove = AsyncMock()
    basket.clear = AsyncMock()
    return entry


def test_entry_for_call(hass: HomeAssistant) -> None:
    """Test service calls resolve their selected config entry."""
    call = MagicMock()
    call.data = {"config_entry_id": "entry-id"}
    with patch(
        "custom_components.sainsburys.services.service.async_get_config_entry",
        return_value="entry",
    ) as get_entry:
        assert _entry_for_call(hass, call) == "entry"
    get_entry.assert_called_once_with(hass, DOMAIN, "entry-id")


async def test_catalogue_services(hass: HomeAssistant) -> None:
    """Test search and product detail response actions."""
    entry = _entry()
    product = Product(product_uid="123", name="Milk", image_url="milk.jpg")
    controls = MagicMock()
    controls.to_dict.return_value = {"active_page": 1}
    entry.runtime_data.client.search_products.return_value = MagicMock(
        products=[product],
        controls=controls,
    )
    entry.runtime_data.client.get_product.return_value = product
    async_setup_services(hass)

    with patch(
        "custom_components.sainsburys.services._entry_for_call",
        return_value=entry,
    ):
        search = await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH_PRODUCTS,
            {"query": "milk"},
            blocking=True,
            return_response=True,
        )
        detail = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRODUCT,
            {"product_uid": "123"},
            blocking=True,
            return_response=True,
        )

    assert search["products"][0]["name"] == "Milk"
    assert search["controls"] == {"active_page": 1}
    assert detail["product"]["product_uid"] == "123"


@pytest.mark.parametrize(
    ("service_name", "service_data", "method"),
    [
        (SERVICE_ADD_BASKET_ITEM, {"product_uid": "123"}, "add"),
        (
            SERVICE_SET_BASKET_ITEM,
            {"product_uid": "123", "quantity": 2},
            "set_quantity",
        ),
        (SERVICE_REMOVE_BASKET_ITEM, {"product_uid": "123"}, "remove"),
        (SERVICE_CLEAR_BASKET, {}, "clear"),
    ],
)
async def test_basket_services(
    hass: HomeAssistant,
    service_name: str,
    service_data: dict[str, object],
    method: str,
) -> None:
    """Test basket mutation actions and refresh."""
    entry = _entry()
    async_setup_services(hass)

    with patch(
        "custom_components.sainsburys.services._entry_for_call",
        return_value=entry,
    ):
        await hass.services.async_call(
            DOMAIN,
            service_name,
            service_data,
            blocking=True,
        )

    getattr(
        entry.runtime_data.coordinator.data.customer.basket,
        method,
    ).assert_awaited_once()
    entry.runtime_data.coordinator.async_request_refresh.assert_awaited_once()


async def test_invalid_basket_item(hass: HomeAssistant) -> None:
    """Test a missing basket line raises a validation error."""
    entry = _entry()
    entry.runtime_data.coordinator.data.customer.basket.remove.side_effect = ValueError
    async_setup_services(hass)

    with (
        patch(
            "custom_components.sainsburys.services._entry_for_call",
            return_value=entry,
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_REMOVE_BASKET_ITEM,
            {"product_uid": "missing"},
            blocking=True,
        )


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test a client failure raises a translated action error."""
    entry = _entry()
    entry.runtime_data.client.get_product.side_effect = ClientConnectionError
    async_setup_services(hass)

    with (
        patch(
            "custom_components.sainsburys.services._entry_for_call",
            return_value=entry,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_PRODUCT,
            {"product_uid": "123"},
            blocking=True,
            return_response=True,
        )


async def test_search_connection_error(hass: HomeAssistant) -> None:
    """Test product search maps a client error."""
    entry = _entry()
    entry.runtime_data.client.search_products.side_effect = ClientConnectionError
    async_setup_services(hass)

    with (
        patch(
            "custom_components.sainsburys.services._entry_for_call",
            return_value=entry,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SEARCH_PRODUCTS,
            {"query": "milk"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.parametrize(
    ("service_name", "service_data", "method"),
    [
        (SERVICE_ADD_BASKET_ITEM, {"product_uid": "123"}, "add"),
        (
            SERVICE_SET_BASKET_ITEM,
            {"product_uid": "123", "quantity": 2},
            "set_quantity",
        ),
    ],
)
async def test_invalid_basket_mutation(
    hass: HomeAssistant,
    service_name: str,
    service_data: dict[str, object],
    method: str,
) -> None:
    """Test invalid add and set operations."""
    entry = _entry()
    getattr(
        entry.runtime_data.coordinator.data.customer.basket, method
    ).side_effect = ValueError
    async_setup_services(hass)

    with (
        patch(
            "custom_components.sainsburys.services._entry_for_call",
            return_value=entry,
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            service_name,
            service_data,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service_name", "service_data", "method"),
    [
        (SERVICE_ADD_BASKET_ITEM, {"product_uid": "123"}, "add"),
        (
            SERVICE_SET_BASKET_ITEM,
            {"product_uid": "123", "quantity": 2},
            "set_quantity",
        ),
        (SERVICE_REMOVE_BASKET_ITEM, {"product_uid": "123"}, "remove"),
        (SERVICE_CLEAR_BASKET, {}, "clear"),
    ],
)
async def test_basket_connection_errors(
    hass: HomeAssistant,
    service_name: str,
    service_data: dict[str, object],
    method: str,
) -> None:
    """Test basket client errors map to Home Assistant errors."""
    entry = _entry()
    getattr(
        entry.runtime_data.coordinator.data.customer.basket, method
    ).side_effect = ClientConnectionError
    async_setup_services(hass)

    with (
        patch(
            "custom_components.sainsburys.services._entry_for_call",
            return_value=entry,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            service_name,
            service_data,
            blocking=True,
        )
