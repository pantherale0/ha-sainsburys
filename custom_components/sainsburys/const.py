"""Constants for the Sainsbury's Groceries integration."""

from datetime import timedelta
from logging import Logger, getLogger

DOMAIN = "sainsburys"
LOGGER: Logger = getLogger(__package__)

ATTRIBUTION = "Data provided by Sainsbury's Groceries"
CONF_SESSION = "session"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=15)

SERVICE_ADD_BASKET_ITEM = "add_basket_item"
SERVICE_CLEAR_BASKET = "clear_basket"
SERVICE_GET_PRODUCT = "get_product"
SERVICE_REMOVE_BASKET_ITEM = "remove_basket_item"
SERVICE_SEARCH_PRODUCTS = "search_products"
SERVICE_SET_BASKET_ITEM = "set_basket_item"
