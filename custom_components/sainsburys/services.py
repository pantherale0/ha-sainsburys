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
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
    from pysainsburys import Product

    from .data import SainsburysConfigEntry

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_PAGE_NUMBER = "page_number"
ATTR_PAGE_SIZE = "page_size"
ATTR_PRODUCT_UID = "product_uid"
ATTR_QUANTITY = "quantity"
ATTR_QUERY = "query"

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


@callback
def async_setup_services(hass: HomeAssistant) -> None:  # noqa: PLR0915
    """Register Sainsbury's service actions."""

    async def async_search_products(call: ServiceCall) -> ServiceResponse:
        entry = _entry_for_call(hass, call)
        try:
            result = await entry.runtime_data.client.search_products(
                call.data[ATTR_QUERY],
                page_number=call.data[ATTR_PAGE_NUMBER],
                page_size=call.data[ATTR_PAGE_SIZE],
            )
        except (AuthError, ClientError, HttpException, TimeoutError) as err:
            raise _action_error() from err
        return {
            "products": [_serialize_product(product) for product in result.products],
            "controls": result.controls.to_dict(),
        }

    async def async_get_product(call: ServiceCall) -> ServiceResponse:
        entry = _entry_for_call(hass, call)
        try:
            product = await entry.runtime_data.client.get_product(
                call.data[ATTR_PRODUCT_UID]
            )
        except (AuthError, ClientError, HttpException, TimeoutError) as err:
            raise _action_error() from err
        return {"product": _serialize_product(product)}

    async def async_add_basket_item(call: ServiceCall) -> None:
        entry = _entry_for_call(hass, call)
        try:
            customer = entry.runtime_data.coordinator.data.customer
            await customer.basket.add(
                call.data[ATTR_PRODUCT_UID],
                call.data[ATTR_QUANTITY],
            )
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_basket_item",
            ) from err
        except (AuthError, ClientError, HttpException, TimeoutError) as err:
            raise _action_error() from err
        await entry.runtime_data.coordinator.async_request_refresh()

    async def async_set_basket_item(call: ServiceCall) -> None:
        entry = _entry_for_call(hass, call)
        try:
            customer = entry.runtime_data.coordinator.data.customer
            await customer.basket.set_quantity(
                call.data[ATTR_PRODUCT_UID],
                call.data[ATTR_QUANTITY],
            )
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_basket_item",
            ) from err
        except (AuthError, ClientError, HttpException, TimeoutError) as err:
            raise _action_error() from err
        await entry.runtime_data.coordinator.async_request_refresh()

    async def async_remove_basket_item(call: ServiceCall) -> None:
        entry = _entry_for_call(hass, call)
        try:
            customer = entry.runtime_data.coordinator.data.customer
            await customer.basket.remove(call.data[ATTR_PRODUCT_UID])
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_basket_item",
            ) from err
        except (AuthError, ClientError, HttpException, TimeoutError) as err:
            raise _action_error() from err
        await entry.runtime_data.coordinator.async_request_refresh()

    async def async_clear_basket(call: ServiceCall) -> None:
        entry = _entry_for_call(hass, call)
        try:
            customer = entry.runtime_data.coordinator.data.customer
            await customer.basket.clear()
        except (AuthError, ClientError, HttpException, TimeoutError) as err:
            raise _action_error() from err
        await entry.runtime_data.coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_PRODUCTS,
        async_search_products,
        SEARCH_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRODUCT,
        async_get_product,
        GET_PRODUCT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_BASKET_ITEM,
        async_add_basket_item,
        ADD_BASKET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_BASKET_ITEM,
        async_set_basket_item,
        SET_BASKET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_BASKET_ITEM,
        async_remove_basket_item,
        REMOVE_BASKET_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_BASKET,
        async_clear_basket,
        CLEAR_BASKET_SCHEMA,
    )
