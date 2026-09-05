"""Tests for the Sainsbury's LLM API."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol
from aiohttp import ClientConnectionError
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import llm
from pysainsburys import (
    DeliverySlot,
    Product,
    SlotDay,
    SlotReservation,
    SlotType,
    SlotWeek,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry
from voluptuous_openapi import convert

from custom_components.sainsburys.const import (
    DOMAIN,
    SERVICE_ADD_BASKET_ITEM,
    SERVICE_CLEAR_BASKET,
    SERVICE_GET_PRODUCT,
    SERVICE_REMOVE_BASKET_ITEM,
    SERVICE_RESERVE_SLOT,
    SERVICE_SEARCH_PRODUCTS,
    SERVICE_SEARCH_SLOTS,
    SERVICE_SET_BASKET_ITEM,
)
from custom_components.sainsburys.llm import _llm_tools_class, async_get_tools
from custom_components.sainsburys.llm_api import (
    SainsburysAPI,
    async_register_llm_api,
    llm_api_id,
)
from custom_components.sainsburys.llm_api.tools import (
    SERVICE_GET_BASKET,
    SainsburysTool,
    build_sainsburys_tools,
)
from custom_components.sainsburys.services import (
    ATTR_PRODUCT_UID,
    ATTR_QUERY,
    ATTR_SLOT_TYPE,
    ATTR_SLOT_UID,
)

TOOL_NAMES = [
    SERVICE_SEARCH_PRODUCTS,
    SERVICE_GET_PRODUCT,
    SERVICE_GET_BASKET,
    SERVICE_ADD_BASKET_ITEM,
    SERVICE_SET_BASKET_ITEM,
    SERVICE_REMOVE_BASKET_ITEM,
    SERVICE_CLEAR_BASKET,
    SERVICE_SEARCH_SLOTS,
    SERVICE_RESERVE_SLOT,
]


class FakeLLMTools:
    """Stand-in for homeassistant.components.llm.LLMTools."""

    def __init__(self, tools: list[object], prompt: str | None = None) -> None:
        """Store contributed tools and prompt."""
        self.tools = tools
        self.prompt = prompt


def _llm_context() -> llm.LLMContext:
    """Build an LLM context for tool calls."""
    return llm.LLMContext(
        platform="test",
        context=None,
        language="en",
        assistant="conversation",
        device_id=None,
    )


def _entry(sainsburys_data) -> MockConfigEntry:
    """Build a loaded account runtime mock."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test Shopper")
    entry.runtime_data = MagicMock()
    entry.runtime_data.client.search_products = AsyncMock()
    entry.runtime_data.client.get_product = AsyncMock()
    entry.runtime_data.coordinator.async_request_refresh = AsyncMock()
    coordinator_data = MagicMock()
    coordinator_data.basket = sainsburys_data.basket
    basket = coordinator_data.customer.basket
    basket.add = AsyncMock()
    basket.set_quantity = AsyncMock()
    basket.remove = AsyncMock()
    basket.clear = AsyncMock()
    slots = coordinator_data.customer.slots
    slots.list = AsyncMock()
    slots.reserve = AsyncMock()
    entry.runtime_data.coordinator.data = coordinator_data
    return entry


async def _call_tool(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    name: str,
    tool_args: dict[str, object],
) -> dict[str, object]:
    """Call a named tool from the account API."""
    api = SainsburysAPI(hass, entry)
    instance = await api.async_get_api_instance(_llm_context())
    tool = next(item for item in instance.tools if item.name == name)
    return await tool.async_call(
        hass,
        llm.ToolInput(tool_name=name, tool_args=tool_args),
        _llm_context(),
    )


def test_llm_platform_skips_own_api(hass: HomeAssistant) -> None:
    """Test the platform does not duplicate tools onto the dedicated API."""
    assert async_get_tools(hass, _llm_context(), f"{DOMAIN}-entry") is None


def test_llm_platform_contributes_to_assist(
    hass: HomeAssistant, sainsburys_data
) -> None:
    """Test Assist receives Sainsbury's tools from loaded accounts."""
    entry = _entry(sainsburys_data)
    entry.add_to_hass(hass)

    with patch(
        "custom_components.sainsburys.llm._llm_tools_class",
        return_value=FakeLLMTools,
    ):
        result = async_get_tools(hass, _llm_context(), "assist")

    assert result is not None
    assert [tool.name for tool in result.tools] == TOOL_NAMES
    assert "search the Sainsbury's grocery catalogue" in result.prompt
    assert "never assume a slot type" in result.prompt
    assert "ask them" in result.prompt


def test_llm_platform_without_loaded_account(hass: HomeAssistant) -> None:
    """Test Assist gets nothing when no Sainsbury's account is loaded."""
    with patch(
        "custom_components.sainsburys.llm._llm_tools_class",
        return_value=FakeLLMTools,
    ):
        assert async_get_tools(hass, _llm_context(), "assist") is None


def test_llm_platform_without_tools_class(hass: HomeAssistant, sainsburys_data) -> None:
    """Test Assist is skipped when the llm tools class is unavailable."""
    entry = _entry(sainsburys_data)
    entry.add_to_hass(hass)
    with patch(
        "custom_components.sainsburys.llm._llm_tools_class",
        return_value=None,
    ):
        assert async_get_tools(hass, _llm_context(), "assist") is None


def test_llm_tools_class_handles_missing_component() -> None:
    """Test older cores without the llm tools platform are tolerated."""
    result = _llm_tools_class()
    assert result is None or result.__name__ == "LLMTools"


async def test_register_and_unregister_llm_api(hass: HomeAssistant) -> None:
    """Test the account LLM API is registered and removed on unload."""
    entry = MockConfigEntry(domain=DOMAIN, title="Test Shopper")
    entry.add_to_hass(hass)
    async_register_llm_api(hass, entry)

    api_id = llm_api_id(entry.entry_id)
    apis = {api.id: api for api in llm.async_get_apis(hass)}
    assert api_id in apis
    assert apis[api_id].name == "Sainsbury's (Test Shopper)"

    await entry._async_process_on_unload(hass)
    assert api_id not in {api.id for api in llm.async_get_apis(hass)}


async def test_api_instance_tools(hass: HomeAssistant, sainsburys_data) -> None:
    """Test the API exposes catalogue and basket tools."""
    api = SainsburysAPI(hass, _entry(sainsburys_data))
    instance = await api.async_get_api_instance(_llm_context())

    assert instance.api_prompt.startswith("You can search the Sainsbury's")
    assert [tool.name for tool in instance.tools] == TOOL_NAMES


def test_tool_schemas_avoid_exclusive_bounds(sainsburys_data) -> None:
    """
    Exclusive bounds become exclusiveMinimum:true under HA 2026.9 Probatio.

    Providers that validate tool schemas as JSON Schema draft 2020-12 then
    reject the whole request with "True is not of type 'number'".
    """
    exclusive = ("exclusiveMinimum", "exclusiveMaximum")

    def _assert_no_exclusive(node: object, path: str) -> None:
        if isinstance(node, dict):
            for key in exclusive:
                assert key not in node, f"{path}.{key}"
            for key, value in node.items():
                _assert_no_exclusive(value, f"{path}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                _assert_no_exclusive(value, f"{path}[{index}]")

    for tool in build_sainsburys_tools(_entry(sainsburys_data)):
        _assert_no_exclusive(convert(tool.parameters), tool.name)


async def test_search_and_get_product_tools(
    hass: HomeAssistant, sainsburys_data
) -> None:
    """Test catalogue tools return compact product payloads."""
    entry = _entry(sainsburys_data)
    nutrition = MagicMock()
    nutrition.summary = [MagicMock()]
    nutrition.summary[0].to_dict.return_value = {"name": "Fat", "values": ["1g"]}
    retail_price = MagicMock()
    retail_price.to_dict.return_value = {
        "price": 1.85,
        "measure": "ea",
        "measure_amount": None,
    }
    product = Product(
        product_uid="123",
        name="Milk",
        image_url="milk.jpg",
        nutrition=nutrition,
        retail_price=retail_price,
    )
    controls = MagicMock()
    controls.to_dict.return_value = {"active_page": 1, "last_page": 3}
    entry.runtime_data.client.search_products.return_value = MagicMock(
        products=[product],
        controls=controls,
    )
    entry.runtime_data.client.get_product.return_value = product

    search = await _call_tool(
        hass, entry, SERVICE_SEARCH_PRODUCTS, {ATTR_QUERY: "milk"}
    )
    detail = await _call_tool(
        hass, entry, SERVICE_GET_PRODUCT, {ATTR_PRODUCT_UID: "123"}
    )

    assert search["products"][0]["retail_price"] == {
        "price": 1.85,
        "measure": "ea",
        "measure_amount": None,
    }
    assert search["products"][0]["product_uid"] == "123"
    assert "nutrition_summary" not in search["products"][0]
    assert "image_url" not in search["products"][0]
    assert search["controls"] == {"active_page": 1, "last_page": 3}
    assert detail["product"]["nutrition_summary"] == [{"name": "Fat", "values": ["1g"]}]
    entry.runtime_data.client.search_products.assert_awaited_once_with(
        "milk",
        page_number=1,
        page_size=8,
    )

    entry.runtime_data.client.get_product.return_value = Product(
        product_uid="123",
        name="Milk",
    )
    plain = await _call_tool(
        hass, entry, SERVICE_GET_PRODUCT, {ATTR_PRODUCT_UID: "123"}
    )
    assert plain["product"]["nutrition_summary"] is None


async def test_get_basket_tool(hass: HomeAssistant, sainsburys_data) -> None:
    """Test get_basket returns current coordinator basket lines."""
    result = await _call_tool(hass, _entry(sainsburys_data), SERVICE_GET_BASKET, {})

    assert result["basket"]["item_count"] == 1
    assert result["basket"]["items"][0]["name"] == "Milk"
    assert result["basket"]["has_exceeded_minimum_spend"] is True


@pytest.mark.parametrize(
    ("tool_name", "tool_args", "method"),
    [
        (SERVICE_ADD_BASKET_ITEM, {ATTR_PRODUCT_UID: "123"}, "add"),
        (
            SERVICE_SET_BASKET_ITEM,
            {ATTR_PRODUCT_UID: "123", "quantity": 2},
            "set_quantity",
        ),
        (SERVICE_REMOVE_BASKET_ITEM, {ATTR_PRODUCT_UID: "123"}, "remove"),
        (SERVICE_CLEAR_BASKET, {}, "clear"),
    ],
)
async def test_basket_mutation_tools(
    hass: HomeAssistant,
    sainsburys_data,
    tool_name: str,
    tool_args: dict[str, object],
    method: str,
) -> None:
    """Test basket mutation tools refresh and return the basket."""
    entry = _entry(sainsburys_data)
    result = await _call_tool(hass, entry, tool_name, tool_args)

    getattr(
        entry.runtime_data.coordinator.data.customer.basket,
        method,
    ).assert_awaited_once()
    entry.runtime_data.coordinator.async_request_refresh.assert_awaited_once()
    assert result["success"] is True
    assert result["basket"]["items"][0]["product_uid"] == "123"


async def test_invalid_basket_item_tool(hass: HomeAssistant, sainsburys_data) -> None:
    """Test a missing basket line raises a validation error."""
    entry = _entry(sainsburys_data)
    entry.runtime_data.coordinator.data.customer.basket.remove.side_effect = ValueError

    with pytest.raises(ServiceValidationError):
        await _call_tool(
            hass,
            entry,
            SERVICE_REMOVE_BASKET_ITEM,
            {ATTR_PRODUCT_UID: "missing"},
        )


async def test_search_connection_error(hass: HomeAssistant, sainsburys_data) -> None:
    """Test catalogue tool failures map to Home Assistant errors."""
    entry = _entry(sainsburys_data)
    entry.runtime_data.client.search_products.side_effect = ClientConnectionError

    with pytest.raises(HomeAssistantError):
        await _call_tool(hass, entry, SERVICE_SEARCH_PRODUCTS, {ATTR_QUERY: "milk"})


async def test_search_slots_tool(hass: HomeAssistant, sainsburys_data) -> None:
    """Test slot search returns compact available slots for both types."""
    entry = _entry(sainsburys_data)
    week = SlotWeek(
        slot_type=SlotType.COLLECTION,
        week_start_date="2026-09-07",
        days=[
            SlotDay(
                date="2026-09-07",
                day_label="Monday",
                slots=[
                    DeliverySlot(
                        slot_uid="slot-1",
                        start_time="2026-09-07T10:00:00+00:00",
                        end_time="2026-09-07T11:00:00+00:00",
                        price=1.5,
                        is_available=True,
                    ),
                    DeliverySlot(
                        slot_uid="slot-full",
                        start_time="2026-09-07T11:00:00+00:00",
                        end_time="2026-09-07T12:00:00+00:00",
                        is_available=False,
                    ),
                ],
            ),
            SlotDay(
                date="2026-09-08",
                day_label="Tuesday",
                slots=[
                    DeliverySlot(
                        slot_uid="slot-closed",
                        is_available=False,
                    )
                ],
            ),
        ],
    )
    entry.runtime_data.coordinator.data.customer.slots.list.return_value = week

    result = await _call_tool(
        hass,
        entry,
        SERVICE_SEARCH_SLOTS,
        {ATTR_SLOT_TYPE: SlotType.COLLECTION},
    )

    assert result["week"]["slot_type"] == "collection"
    assert result["week"]["days"][0]["slots"] == [
        {
            "slot_uid": "slot-1",
            "start_time": "2026-09-07T10:00:00+00:00",
            "end_time": "2026-09-07T11:00:00+00:00",
            "price": 1.5,
            "is_available": True,
        }
    ]
    entry.runtime_data.coordinator.data.customer.slots.list.assert_awaited_once_with(
        slot_type=SlotType.COLLECTION,
        week_start_date=None,
    )


async def test_search_slots_tool_requires_type(
    hass: HomeAssistant, sainsburys_data
) -> None:
    """Test the slot search tool does not assume a slot type."""
    with pytest.raises(vol.Invalid):
        await _call_tool(hass, _entry(sainsburys_data), SERVICE_SEARCH_SLOTS, {})


async def test_reserve_slot_tool(hass: HomeAssistant, sainsburys_data) -> None:
    """Test reserve_slot refreshes and returns a compact reservation."""
    entry = _entry(sainsburys_data)
    entry.runtime_data.coordinator.data.customer.slots.reserve.return_value = (
        SlotReservation(
            reservation_type="delivery",
            is_expired=False,
            reserved_until="2026-09-05T16:00:00+00:00",
            slot=DeliverySlot(
                slot_uid="slot-1",
                start_time="2026-09-07T10:00:00+00:00",
                end_time="2026-09-07T11:00:00+00:00",
                price=4.0,
            ),
        )
    )

    result = await _call_tool(
        hass,
        entry,
        SERVICE_RESERVE_SLOT,
        {ATTR_SLOT_TYPE: SlotType.DELIVERY, ATTR_SLOT_UID: "slot-1"},
    )

    entry.runtime_data.coordinator.data.customer.slots.reserve.assert_awaited_once()
    entry.runtime_data.coordinator.async_request_refresh.assert_awaited_once()
    assert result["success"] is True
    assert result["reservation"]["slot"]["slot_uid"] == "slot-1"


async def test_reserve_slot_tool_invalid(hass: HomeAssistant, sainsburys_data) -> None:
    """Test an invalid slot reservation raises a validation error."""
    entry = _entry(sainsburys_data)
    entry.runtime_data.coordinator.data.customer.slots.reserve.side_effect = ValueError

    with pytest.raises(ServiceValidationError):
        await _call_tool(
            hass,
            entry,
            SERVICE_RESERVE_SLOT,
            {ATTR_SLOT_TYPE: SlotType.DELIVERY, ATTR_SLOT_UID: "missing"},
        )


async def test_search_slots_tool_connection_error(
    hass: HomeAssistant, sainsburys_data
) -> None:
    """Test slot search tool failures map to Home Assistant errors."""
    entry = _entry(sainsburys_data)
    entry.runtime_data.coordinator.data.customer.slots.list.side_effect = (
        ClientConnectionError
    )

    with pytest.raises(HomeAssistantError):
        await _call_tool(
            hass,
            entry,
            SERVICE_SEARCH_SLOTS,
            {ATTR_SLOT_TYPE: SlotType.DELIVERY},
        )


async def test_base_tool_run(sainsburys_data) -> None:
    """Test the shared tool base requires a concrete implementation."""
    with pytest.raises(NotImplementedError):
        await SainsburysTool(_entry(sainsburys_data)).async_run({})
