"""Sainsbury's dedicated LLM API registration."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from homeassistant.helpers import llm
from homeassistant.helpers.llm import APIInstance, LLMContext

from custom_components.sainsburys.const import DOMAIN
from custom_components.sainsburys.llm_api.tools import (
    API_PROMPT,
    build_sainsburys_tools,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from custom_components.sainsburys.data import SainsburysConfigEntry


def llm_api_id(entry_id: str) -> str:
    """Return the LLM API identifier for a config entry."""
    return f"{DOMAIN}-{entry_id}"


class SainsburysAPI(llm.API):
    """LLM API for one Sainsbury's Groceries account."""

    def __init__(self, hass: HomeAssistant, entry: SainsburysConfigEntry) -> None:
        """Initialize the API for a config entry."""
        super().__init__(
            hass=hass,
            id=llm_api_id(entry.entry_id),
            name=f"Sainsbury's ({entry.title})",
        )
        self.entry = entry

    @override
    async def async_get_api_instance(self, llm_context: LLMContext) -> APIInstance:
        """Return tools for this account."""
        return APIInstance(
            api=self,
            api_prompt=API_PROMPT,
            llm_context=llm_context,
            tools=build_sainsburys_tools(self.entry),
        )


def async_register_llm_api(hass: HomeAssistant, entry: SainsburysConfigEntry) -> None:
    """Register the account LLM API and unregister it when the entry unloads."""
    entry.async_on_unload(
        llm.async_register_api(hass, SainsburysAPI(hass=hass, entry=entry))
    )
