"""Service actions for the Sainsbury's Groceries integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from aiohttp import ClientError
from homeassistant.core import SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from pysainsburys.exceptions import AuthError, HttpException

from .const import (
    DOMAIN,
    SERVICE_ADD_BASKET_ITEM,
    SERVICE_CLEAR_BASKET,
    SERVICE_GET_PRODUCT,
    SERVICE_REMOVE_BASKET_ITEM,
    SERVICE_SEARCH_PRODUCTS,
    SERVICE_SET_BASKET_ITEM,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
    from pysainsburys import Product, ProductList

    from .data import SainsburysConfigEntry

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_PAGE_NUMBER = "page_number"
ATTR_PAGE_SIZE = "page_size"
ATTR_PRODUCT_UID = "product_uid"
ATTR_QUANTITY = "quantity"
ATTR_QUERY = "query"

CLIENT_ERRORS = (AuthError, ClientError, HttpException, TimeoutError)

CONFIG_ENTRY_FIELD = {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}
PRODUCT_FIELD = {vol.Required(ATTR_PRODUCT_UID): cv.string}

SEARCH_SCHEMA = vol.Schema(
    {
        **CONFIG_ENTRY_FIELD,
        vol.Required(ATTR_QUERY): vol.All(cv.string, vol.Length(min=1)),
        vol.Optional(ATTR_PAGE_NUMBER, default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1)
        ),
        vol.Optional(ATTR_PAGE_SIZE, default=24): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
    }
)
GET_PRODUCT_SCHEMA = vol.Schema({**CONFIG_ENTRY_FIELD, **PRODUCT_FIELD})
ADD_BASKET_SCHEMA = vol.Schema(
    {
        **CONFIG_ENTRY_FIELD,
        **PRODUCT_FIELD,
        vol.Optional(ATTR_QUANTITY, default=1.0): vol.All(
            vol.Coerce(float), vol.Range(min=0, min_included=False)
        ),
    }
)
SET_BASKET_SCHEMA = vol.Schema(
    {
        **CONFIG_ENTRY_FIELD,
        **PRODUCT_FIELD,
        vol.Required(ATTR_QUANTITY): vol.All(vol.Coerce(float), vol.Range(min=0)),
    }
)
REMOVE_BASKET_SCHEMA = vol.Schema({**CONFIG_ENTRY_FIELD, **PRODUCT_FIELD})
CLEAR_BASKET_SCHEMA = vol.Schema(CONFIG_ENTRY_FIELD)


def _entry_for_call(hass: HomeAssistant, call: ServiceCall) -> SainsburysConfigEntry:
    """Return the loaded account selected by a service call."""
    return service.async_get_config_entry(
        hass,
        DOMAIN,
        call.data.get(ATTR_CONFIG_ENTRY_ID),
    )


def _serialize_product(product: Product) -> dict[str, Any]:
    """Serialize a product into service-response data."""
    return product.to_dict()


def _action_error() -> HomeAssistantError:
    """Create a translated Home Assistant action error."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="action_failed",
    )


def _invalid_basket_item() -> ServiceValidationError:
    """Create a translated invalid basket-item error."""
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="invalid_basket_item",
    )


async def _await_client[T](awaitable: Awaitable[T]) -> T:
    """Await a Sainsbury's client call and map transport errors."""
    try:
        return await awaitable
    except CLIENT_ERRORS as err:
        raise _action_error() from err


async def async_search_products(
    entry: SainsburysConfigEntry,
    query: str,
    *,
    page_number: int = 1,
    page_size: int = 24,
) -> ProductList:
    """Search the grocery catalogue for the selected account."""
    return await _await_client(
        entry.runtime_data.client.search_products(
            query,
            page_number=page_number,
            page_size=page_size,
        )
    )


async def async_get_product(
    entry: SainsburysConfigEntry,
    product_uid: str,
) -> Product:
    """Fetch one catalogue product for the selected account."""
    return await _await_client(entry.runtime_data.client.get_product(product_uid))


async def _async_mutate_basket(
    entry: SainsburysConfigEntry,
    operation: Callable[[], Awaitable[object]],
    *,
    map_value_error: bool = False,
) -> None:
    """Run a basket mutation, map errors, and refresh account data."""
    try:
        await operation()
    except ValueError as err:
        if not map_value_error:
            raise
        raise _invalid_basket_item() from err
    except CLIENT_ERRORS as err:
        raise _action_error() from err
    await entry.runtime_data.coordinator.async_request_refresh()


async def async_add_basket_item(
    entry: SainsburysConfigEntry,
    product_uid: str,
    quantity: float = 1.0,
) -> None:
    """Add a product to the selected account's basket."""
    basket = entry.runtime_data.coordinator.data.customer.basket
    await _async_mutate_basket(
        entry,
        lambda: basket.add(product_uid, quantity),
        map_value_error=True,
    )


async def async_set_basket_item(
    entry: SainsburysConfigEntry,
    product_uid: str,
    quantity: float,
) -> None:
    """Set the absolute quantity of a basket line."""
    basket = entry.runtime_data.coordinator.data.customer.basket
    await _async_mutate_basket(
        entry,
        lambda: basket.set_quantity(product_uid, quantity),
        map_value_error=True,
    )


async def async_remove_basket_item(
    entry: SainsburysConfigEntry,
    product_uid: str,
) -> None:
    """Remove a product from the selected account's basket."""
    basket = entry.runtime_data.coordinator.data.customer.basket
    await _async_mutate_basket(
        entry,
        lambda: basket.remove(product_uid),
        map_value_error=True,
    )


async def async_clear_basket(entry: SainsburysConfigEntry) -> None:
    """Remove all products from the selected account's basket."""
    basket = entry.runtime_data.coordinator.data.customer.basket
    await _async_mutate_basket(entry, basket.clear)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register Sainsbury's service actions."""

    async def handle_search_products(call: ServiceCall) -> ServiceResponse:
        result = await async_search_products(
            _entry_for_call(hass, call),
            call.data[ATTR_QUERY],
            page_number=call.data[ATTR_PAGE_NUMBER],
            page_size=call.data[ATTR_PAGE_SIZE],
        )
        return {
            "products": [_serialize_product(product) for product in result.products],
            "controls": result.controls.to_dict(),
        }

    async def handle_get_product(call: ServiceCall) -> ServiceResponse:
        product = await async_get_product(
            _entry_for_call(hass, call),
            call.data[ATTR_PRODUCT_UID],
        )
        return {"product": _serialize_product(product)}

    async def handle_add_basket_item(call: ServiceCall) -> None:
        await async_add_basket_item(
            _entry_for_call(hass, call),
            call.data[ATTR_PRODUCT_UID],
            call.data[ATTR_QUANTITY],
        )

    async def handle_set_basket_item(call: ServiceCall) -> None:
        await async_set_basket_item(
            _entry_for_call(hass, call),
            call.data[ATTR_PRODUCT_UID],
            call.data[ATTR_QUANTITY],
        )

    async def handle_remove_basket_item(call: ServiceCall) -> None:
        await async_remove_basket_item(
            _entry_for_call(hass, call),
            call.data[ATTR_PRODUCT_UID],
        )

    async def handle_clear_basket(call: ServiceCall) -> None:
        await async_clear_basket(_entry_for_call(hass, call))

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_PRODUCTS,
        handle_search_products,
        SEARCH_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRODUCT,
        handle_get_product,
        GET_PRODUCT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BASKET_ITEM,
        handle_add_basket_item,
        ADD_BASKET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_BASKET_ITEM,
        handle_set_basket_item,
        SET_BASKET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_BASKET_ITEM,
        handle_remove_basket_item,
        REMOVE_BASKET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_BASKET,
        handle_clear_basket,
        CLEAR_BASKET_SCHEMA,
    )
