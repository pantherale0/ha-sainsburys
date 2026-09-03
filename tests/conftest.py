"""Shared fixtures for Sainsbury's integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pysainsburys import (
    Basket,
    BasketItem,
    Customer,
    DeliverySlot,
    OrderStatus,
    OrderSummary,
    SlotReservation,
)

from custom_components.sainsburys.coordinator import SainsburysData

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations) -> None:
    """Enable loading custom integrations in all tests."""
    return


@pytest.fixture
def session_data() -> dict[str, object]:
    """Return stored pysainsburys authentication data."""
    return {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "wc_auth_token": "wc-token",
        "user_id": "user-123",
        "wc_trusted_token": "trusted-token",
        "cookies": {"session": "cookie"},
        "app_version": "3.65.0",
        "login_hint": "person@example.com",
        "personalization_id": "personalization",
        "next_refresh": datetime.now(UTC).isoformat(),
    }


@pytest.fixture
def sainsburys_data() -> SainsburysData:
    """Return representative coordinator data."""
    customer = Customer(
        user_id="user-123",
        email="person@example.com",
        given_name="Test",
        family_name="Shopper",
        delivery_pass_expiry_date="2027-01-01",
        has_nectar_associated=True,
        has_nectar_linked=True,
        is_digital_nectar=True,
    )
    basket = Basket(
        subtotal_price=9.5,
        total_price=11.0,
        slot_price=1.5,
        savings=2.0,
        nectar_savings=1.0,
        item_count=1,
        minimum_spend=25,
        has_exceeded_minimum_spend=True,
        items=[
            BasketItem(
                product_uid="123",
                quantity=1,
                name="Milk",
                item_uid="line-1",
                subtotal=2.0,
            )
        ],
    )
    order = OrderSummary(
        order_id="order-1",
        status="confirmed",
        total=11.0,
        slot_type="delivery",
    )
    status = OrderStatus(
        order_uid="order-1",
        is_in_amend_mode=True,
        cutoff_time="2026-09-04T12:00:00+00:00",
        total=11.0,
    )
    reservation = SlotReservation(
        reservation_type="delivery",
        is_expired=False,
        slot=DeliverySlot(
            slot_uid="slot-1",
            start_time="2026-09-05T10:00:00+00:00",
            end_time="2026-09-05T11:00:00+00:00",
        ),
    )
    return SainsburysData(customer, basket, order, status, reservation)
