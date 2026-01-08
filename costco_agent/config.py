"""
Configuration for Costco Shopping Agent
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CostcoConfig:
    """Configuration for the Costco shopping agent."""

    # Costco credentials (from environment variables for security)
    email: str = field(default_factory=lambda: os.getenv("COSTCO_EMAIL", ""))
    password: str = field(default_factory=lambda: os.getenv("COSTCO_PASSWORD", ""))

    # Browser settings
    headless: bool = field(default_factory=lambda: os.getenv("HEADLESS", "false").lower() == "true")
    browser_timeout: int = 30000  # 30 seconds
    slow_mo: int = 100  # milliseconds between actions for stability

    # Costco URLs
    base_url: str = "https://www.costco.com"
    login_url: str = "https://www.costco.com/LogonForm"
    cart_url: str = "https://www.costco.com/CheckoutCartView"
    checkout_url: str = "https://www.costco.com/CheckoutPaymentView"

    # Shopping preferences
    default_quantity: int = 1
    auto_apply_coupons: bool = True

    # Shipping address (from environment or set programmatically)
    shipping_address: Optional[dict] = None

    # Payment info (from environment - NEVER hardcode)
    payment_method: str = field(default_factory=lambda: os.getenv("COSTCO_PAYMENT_METHOD", "saved"))

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 2.0

    # Screenshot settings for debugging
    save_screenshots: bool = True
    screenshot_dir: str = "screenshots"

    def __post_init__(self):
        """Validate configuration after initialization."""
        if not self.email or not self.password:
            print("Warning: Costco credentials not set. Set COSTCO_EMAIL and COSTCO_PASSWORD environment variables.")

        # Create screenshot directory if needed
        if self.save_screenshots:
            os.makedirs(self.screenshot_dir, exist_ok=True)

    @classmethod
    def from_env(cls) -> "CostcoConfig":
        """Create configuration from environment variables."""
        shipping_address = None
        if os.getenv("COSTCO_SHIPPING_ADDRESS"):
            import json
            try:
                shipping_address = json.loads(os.getenv("COSTCO_SHIPPING_ADDRESS", "{}"))
            except json.JSONDecodeError:
                pass

        return cls(
            email=os.getenv("COSTCO_EMAIL", ""),
            password=os.getenv("COSTCO_PASSWORD", ""),
            headless=os.getenv("HEADLESS", "false").lower() == "true",
            shipping_address=shipping_address
        )


# Default selectors for Costco website elements
COSTCO_SELECTORS = {
    # Login page
    "login_email": "#logonId",
    "login_password": "#logonPassword",
    "login_button": "input[type='submit'][value='Sign In']",
    "login_remember_me": "#rememberMe",

    # Search
    "search_input": "#search-field",
    "search_button": "button[aria-label='Search']",
    "search_results": ".product-tile-set",
    "product_card": ".product-tile",
    "product_title": ".description a",
    "product_price": ".price",

    # Product page
    "add_to_cart_button": "#add-to-cart-btn",
    "quantity_input": "#quantity",
    "product_options": ".product-options select",

    # Cart page
    "cart_items": ".cart-item",
    "cart_item_name": ".item-name",
    "cart_item_price": ".item-price",
    "cart_item_quantity": ".quantity-input",
    "cart_subtotal": ".order-subtotal",
    "proceed_to_checkout": "#shopCartCheckoutSubmitButton",
    "promo_code_input": "#promoCode",
    "apply_promo_button": "#applyPromoCodeButton",

    # Checkout page
    "checkout_continue": ".checkout-continue-btn",
    "place_order_button": "#placeOrderButton",
    "shipping_address_section": ".shipping-address",
    "payment_section": ".payment-method",
    "order_summary": ".order-summary",
    "order_total": ".order-total",

    # General
    "modal_close": ".modal-close, .close-button, [aria-label='Close']",
    "loading_spinner": ".loading, .spinner",
    "error_message": ".error-message, .alert-error",
}
