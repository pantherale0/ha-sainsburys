"""Authentication helpers for the Sainsbury's Groceries integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any

from pysainsburys import GOLAuth

if TYPE_CHECKING:
    from aiohttp import ClientSession


def create_auth(
    data: Mapping[str, Any],
    session: ClientSession,
) -> GOLAuth:
    """Create a pysainsburys authenticator using Home Assistant's session."""
    cookies = data.get("cookies")
    auth = GOLAuth(
        access_token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        wc_auth_token=data.get("wc_auth_token"),
        user_id=data.get("user_id"),
        wc_trusted_token=data.get("wc_trusted_token"),
        cookies=(
            {str(key): str(value) for key, value in cookies.items()}
            if isinstance(cookies, Mapping)
            else None
        ),
        app_version=data.get("app_version"),
        login_hint=data.get("login_hint"),
        session=session,
    )
    auth.personalization_id = data.get("personalization_id")
    if isinstance(next_refresh := data.get("next_refresh"), str):
        auth.next_refresh = datetime.fromisoformat(next_refresh)
    return auth
