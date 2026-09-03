"""
Contribute Sainsbury's tools to Home Assistant LLM APIs when supported.

Home Assistant discovers this platform from the ``llm`` integration and calls
``async_get_tools`` per request. On older cores without the contributor API,
this module is unused; the dedicated Sainsbury's LLM API is still registered via
``llm_api``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback

from .const import DOMAIN
from .llm_api.tools import API_PROMPT, build_sainsburys_tools

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.llm import LLMContext


def _llm_tools_class() -> type[Any] | None:
    """Return LLMTools when the llm integration is available."""
    try:
        from homeassistant.components.llm import LLMTools  # noqa: PLC0415
    except ImportError:
        return None
    return LLMTools


@callback
def async_get_tools(
    hass: HomeAssistant,
    llm_context: LLMContext,
    api_id: str,
) -> Any | None:
    """Return Sainsbury's tools for Assist and other selected LLM APIs."""
    del llm_context
    if api_id.startswith(f"{DOMAIN}-"):
        return None

    llm_tools_cls = _llm_tools_class()
    if llm_tools_cls is None:
        return None

    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if getattr(entry, "runtime_data", None) is not None
    ]
    if not entries:
        return None

    tools: list[Any] = []
    for entry in entries:
        tools.extend(build_sainsburys_tools(entry))
    return llm_tools_cls(tools=tools, prompt=API_PROMPT)
