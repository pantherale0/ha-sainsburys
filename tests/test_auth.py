"""Tests for Sainsbury's authentication helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.sainsburys.auth import create_auth


def test_create_auth(session_data: dict[str, object]) -> None:
    """Test stored session data is restored into a library authenticator."""
    session = MagicMock()
    auth = create_auth(session_data, session)

    assert auth.access_token == "access-token"
    assert auth.refresh_token == "refresh-token"
    assert auth.user_id == "user-123"
    assert auth.cookies == {"session": "cookie"}
    assert auth.personalization_id == "personalization"
    assert auth.next_refresh is not None


def test_create_auth_minimal() -> None:
    """Test missing optional session values are supported."""
    auth = create_auth({"cookies": "invalid"}, MagicMock())

    assert auth.access_token is None
    assert auth.cookies == {}
    assert auth.next_refresh is None
