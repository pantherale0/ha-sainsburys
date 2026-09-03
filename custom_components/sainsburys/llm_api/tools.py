"""LLM tools for Sainsbury's catalogue search and basket changes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm

from custom_components.sainsburys.const import (
    SERVICE_ADD_BASKET_ITEM,
    SERVICE_CLEAR_BASKET,
    SERVICE_GET_PRODUCT,
    SERVICE_REMOVE_BASKET_ITEM,
    SERVICE_SEARCH_PRODUCTS,
    SERVICE_SET_BASKET_ITEM,
)
from custom_components.sainsburys.services import (
    ATTR_PAGE_NUMBER,
    ATTR_PAGE_SIZE,
    ATTR_PRODUCT_UID,
    ATTR_QUANTITY,
    ATTR_QUERY,
    async_add_basket_item,
    async_clear_basket,
    async_get_product,
    async_remove_basket_item,
    async_search_products,
    async_set_basket_item,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.llm import LLMContext, ToolInput
    from homeassistant.util.json import JsonObjectType
    from pysainsburys import Price, Product

    from custom_components.sainsburys.coordinator import SainsburysData
    from custom_components.sainsburys.data import SainsburysConfigEntry

SERVICE_GET_BASKET = "get_basket"

LLM_SEARCH_PAGE_SIZE = 8

API_PROMPT = (
    "You can search the Sainsbury's grocery catalogue and manage this "
    "account's basket.\n"
    "- Call search_products to find items. Use the returned product_uid "
    "values; never invent them.\n"
    "- Call get_product when you need more detail for one product_uid.\n"
    "- Call get_basket to inspect current lines, totals and whether "
    "minimum spend is met.\n"
    "- add_basket_item increases quantity (default 1). set_basket_item "
    "sets an absolute quantity; 0 removes that line.\n"
    "- remove_basket_item removes one product. clear_basket empties the "
    "whole basket; only do this when the user asks.\n"
    "- Checkout, payment and booking a delivery or collection slot are "
    "not supported.\n"
    "Prices are in GBP."
)


def _serialize_price(price: Price | None) -> dict[str, Any] | None:
    """Serialize a pysainsburys Price, if present."""
    if price is None:
        return None
    return price.to_dict()


def _serialize_product(product: Product, *, include_nutrition: bool) -> dict[str, Any]:
    """Serialize a catalogue product for an LLM tool response."""
    payload: dict[str, Any] = {
        "product_uid": product.product_uid,
        "name": product.name,
        "retail_price": _serialize_price(product.retail_price),
        "unit_price": _serialize_price(product.unit_price),
        "is_available": product.is_available,
        "is_alcoholic": product.is_alcoholic,
        "average_rating": (
            product.reviews.average_rating if product.reviews is not None else None
        ),
    }
    if include_nutrition:
        payload["nutrition_summary"] = (
            [item.to_dict() for item in product.nutrition.summary]
            if product.nutrition is not None
            else None
        )
    return payload


def serialize_basket(data: SainsburysData) -> dict[str, Any]:
    """Serialize coordinator basket data for an LLM tool response."""
    basket = data.basket
    return {
        "item_count": basket.item_count,
        "subtotal_price": basket.subtotal_price,
        "total_price": basket.total_price,
        "slot_price": basket.slot_price,
        "savings": basket.savings,
        "nectar_savings": basket.nectar_savings,
        "minimum_spend": basket.minimum_spend,
        "has_exceeded_minimum_spend": basket.has_exceeded_minimum_spend,
        "is_in_amend_mode": basket.is_in_amend_mode,
        "items": [
            {
                "product_uid": item.product_uid,
                "name": item.name,
                "quantity": item.quantity,
                "subtotal": item.subtotal,
            }
            for item in basket.items
        ],
    }


class SainsburysTool(llm.Tool):
    """LLM tool bound to one Sainsbury's config entry."""

    def __init__(self, entry: SainsburysConfigEntry) -> None:
        """Initialize the tool."""
        self._entry = entry

    @override
    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: ToolInput,
        llm_context: LLMContext,
    ) -> JsonObjectType:
        """Validate arguments and run the tool."""
        del hass, llm_context
        return await self.async_run(self.parameters(tool_input.tool_args))

    async def async_run(self, args: dict[str, Any]) -> JsonObjectType:
        """Execute the tool with validated arguments."""
        raise NotImplementedError


class SearchProductsTool(SainsburysTool):
    """Search the Sainsbury's grocery catalogue."""

    name = SERVICE_SEARCH_PRODUCTS
    description = (
        "Search the Sainsbury's grocery catalogue. Returns matching products "
        "with product_uid, name, prices and availability. Use product_uid "
        "with basket tools. Do not guess product UIDs."
    )
    parameters = vol.Schema(
        {
            vol.Required(
                ATTR_QUERY, description="Product name or search terms"
            ): vol.All(cv.string, vol.Length(min=1)),
            vol.Optional(
                ATTR_PAGE_NUMBER, default=1, description="Results page to return"
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Optional(
                ATTR_PAGE_SIZE,
                default=LLM_SEARCH_PAGE_SIZE,
                description="Maximum number of products to return",
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        }
    )

    @override
    async def async_run(self, args: dict[str, Any]) -> JsonObjectType:
        """Search the catalogue."""
        result = await async_search_products(
            self._entry,
            args[ATTR_QUERY],
            page_number=args[ATTR_PAGE_NUMBER],
            page_size=args[ATTR_PAGE_SIZE],
        )
        return {
            "products": [
                _serialize_product(product, include_nutrition=False)
                for product in result.products
            ],
            "controls": result.controls.to_dict(),
        }


class GetProductTool(SainsburysTool):
    """Get details for one catalogue product."""

    name = SERVICE_GET_PRODUCT
    description = (
        "Get details for one Sainsbury's product by product_uid, including "
        "prices, availability and a nutrition summary when available."
    )
    parameters = vol.Schema(
        {
            vol.Required(
                ATTR_PRODUCT_UID, description="Sainsbury's product identifier"
            ): cv.string
        }
    )

    @override
    async def async_run(self, args: dict[str, Any]) -> JsonObjectType:
        """Fetch one product."""
        product = await async_get_product(self._entry, args[ATTR_PRODUCT_UID])
        return {"product": _serialize_product(product, include_nutrition=True)}


class GetBasketTool(SainsburysTool):
    """Read the current Sainsbury's basket."""

    name = SERVICE_GET_BASKET
    description = (
        "Get the current Sainsbury's basket, including line items, totals "
        "and whether the minimum spend is met."
    )

    @override
    async def async_run(self, args: dict[str, Any]) -> JsonObjectType:
        """Return the cached basket."""
        del args
        return {"basket": serialize_basket(self._entry.runtime_data.coordinator.data)}


class AddBasketItemTool(SainsburysTool):
    """Add a product to the basket."""

    name = SERVICE_ADD_BASKET_ITEM
    description = (
        "Add a product to the Sainsbury's basket by product_uid. Quantity "
        "defaults to 1 and is added to any existing quantity for that product."
    )
    parameters = vol.Schema(
        {
            vol.Required(
                ATTR_PRODUCT_UID,
                description="Product identifier returned by product search",
            ): cv.string,
            vol.Optional(
                ATTR_QUANTITY, default=1.0, description="Quantity to add"
            ): vol.All(vol.Coerce(float), vol.Range(min=0, min_included=False)),
        }
    )

    @override
    async def async_run(self, args: dict[str, Any]) -> JsonObjectType:
        """Add a basket line and return the refreshed basket."""
        await async_add_basket_item(
            self._entry,
            args[ATTR_PRODUCT_UID],
            args[ATTR_QUANTITY],
        )
        return {
            "success": True,
            "basket": serialize_basket(self._entry.runtime_data.coordinator.data),
        }


class SetBasketItemTool(SainsburysTool):
    """Set the absolute quantity of a basket line."""

    name = SERVICE_SET_BASKET_ITEM
    description = (
        "Set the absolute quantity of a product already identified by "
        "product_uid. Use 0 to remove that line."
    )
    parameters = vol.Schema(
        {
            vol.Required(
                ATTR_PRODUCT_UID, description="Sainsbury's product identifier"
            ): cv.string,
            vol.Required(
                ATTR_QUANTITY,
                description="Absolute quantity. Use zero to remove the product.",
            ): vol.All(vol.Coerce(float), vol.Range(min=0)),
        }
    )

    @override
    async def async_run(self, args: dict[str, Any]) -> JsonObjectType:
        """Set a basket quantity and return the refreshed basket."""
        await async_set_basket_item(
            self._entry,
            args[ATTR_PRODUCT_UID],
            args[ATTR_QUANTITY],
        )
        return {
            "success": True,
            "basket": serialize_basket(self._entry.runtime_data.coordinator.data),
        }


class RemoveBasketItemTool(SainsburysTool):
    """Remove a product from the basket."""

    name = SERVICE_REMOVE_BASKET_ITEM
    description = "Remove a product from the Sainsbury's basket by product_uid."
    parameters = vol.Schema(
        {
            vol.Required(
                ATTR_PRODUCT_UID, description="Sainsbury's product identifier"
            ): cv.string
        }
    )

    @override
    async def async_run(self, args: dict[str, Any]) -> JsonObjectType:
        """Remove a basket line and return the refreshed basket."""
        await async_remove_basket_item(self._entry, args[ATTR_PRODUCT_UID])
        return {
            "success": True,
            "basket": serialize_basket(self._entry.runtime_data.coordinator.data),
        }


class ClearBasketTool(SainsburysTool):
    """Empty the basket."""

    name = SERVICE_CLEAR_BASKET
    description = (
        "Remove all products from the Sainsbury's basket. Only use this when "
        "the user asks to empty or clear the basket."
    )

    @override
    async def async_run(self, args: dict[str, Any]) -> JsonObjectType:
        """Clear the basket and return the refreshed basket."""
        del args
        await async_clear_basket(self._entry)
        return {
            "success": True,
            "basket": serialize_basket(self._entry.runtime_data.coordinator.data),
        }


def build_sainsburys_tools(entry: SainsburysConfigEntry) -> list[llm.Tool]:
    """Build the LLM tool list for a config entry."""
    return [
        SearchProductsTool(entry),
        GetProductTool(entry),
        GetBasketTool(entry),
        AddBasketItemTool(entry),
        SetBasketItemTool(entry),
        RemoveBasketItemTool(entry),
        ClearBasketTool(entry),
    ]
