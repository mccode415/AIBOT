"""
Browser automation module using Playwright for Costco shopping.
"""

import asyncio
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeout

from .config import CostcoConfig, COSTCO_SELECTORS


class CostcoBrowser:
    """
    Browser automation class for interacting with Costco.com
    """

    def __init__(self, config: CostcoConfig):
        self.config = config
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._is_logged_in = False

    async def start(self) -> None:
        """Initialize the browser and create a new page."""
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=self.config.headless,
            slow_mo=self.config.slow_mo
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        self.page = await self.context.new_page()
        self.page.set_default_timeout(self.config.browser_timeout)

    async def stop(self) -> None:
        """Close the browser and cleanup resources."""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

    async def screenshot(self, name: str = "screenshot") -> str:
        """Take a screenshot for debugging purposes."""
        if not self.config.save_screenshots or not self.page:
            return ""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.config.screenshot_dir}/{name}_{timestamp}.png"
        await self.page.screenshot(path=filename)
        return filename

    async def wait_for_load(self) -> None:
        """Wait for page to finish loading."""
        await self.page.wait_for_load_state("networkidle")

    async def close_modals(self) -> None:
        """Close any popup modals that might be blocking."""
        try:
            modal_close = self.page.locator(COSTCO_SELECTORS["modal_close"])
            if await modal_close.count() > 0:
                await modal_close.first.click()
                await asyncio.sleep(0.5)
        except Exception:
            pass  # No modal to close

    async def navigate(self, url: str) -> bool:
        """Navigate to a URL and wait for load."""
        try:
            await self.page.goto(url)
            await self.wait_for_load()
            await self.close_modals()
            return True
        except PlaywrightTimeout:
            await self.screenshot("navigate_timeout")
            return False

    async def login(self) -> Dict[str, Any]:
        """
        Log into Costco.com with configured credentials.

        Returns:
            Dict with success status and message
        """
        if not self.config.email or not self.config.password:
            return {
                "success": False,
                "error": "Credentials not configured. Set COSTCO_EMAIL and COSTCO_PASSWORD."
            }

        try:
            # Navigate to login page
            await self.navigate(self.config.login_url)
            await self.screenshot("login_page")

            # Fill in credentials
            await self.page.fill(COSTCO_SELECTORS["login_email"], self.config.email)
            await self.page.fill(COSTCO_SELECTORS["login_password"], self.config.password)

            # Click login button
            await self.page.click(COSTCO_SELECTORS["login_button"])
            await self.wait_for_load()

            # Verify login success
            await asyncio.sleep(2)

            # Check for error messages
            error_locator = self.page.locator(COSTCO_SELECTORS["error_message"])
            if await error_locator.count() > 0:
                error_text = await error_locator.first.text_content()
                await self.screenshot("login_error")
                return {"success": False, "error": f"Login failed: {error_text}"}

            self._is_logged_in = True
            await self.screenshot("login_success")
            return {"success": True, "message": "Successfully logged into Costco"}

        except PlaywrightTimeout as e:
            await self.screenshot("login_timeout")
            return {"success": False, "error": f"Login timeout: {str(e)}"}
        except Exception as e:
            await self.screenshot("login_exception")
            return {"success": False, "error": f"Login failed: {str(e)}"}

    async def search_products(self, query: str) -> Dict[str, Any]:
        """
        Search for products on Costco.

        Args:
            query: Search term

        Returns:
            Dict with products found
        """
        try:
            # Navigate to homepage if not there
            if "costco.com" not in self.page.url:
                await self.navigate(self.config.base_url)

            await self.close_modals()

            # Enter search query
            search_input = self.page.locator(COSTCO_SELECTORS["search_input"])
            await search_input.fill(query)
            await search_input.press("Enter")

            await self.wait_for_load()
            await asyncio.sleep(2)
            await self.screenshot(f"search_{query.replace(' ', '_')}")

            # Parse search results
            products = []
            product_cards = self.page.locator(COSTCO_SELECTORS["product_card"])
            count = await product_cards.count()

            for i in range(min(count, 10)):  # Limit to first 10 results
                card = product_cards.nth(i)
                try:
                    title_elem = card.locator(COSTCO_SELECTORS["product_title"])
                    price_elem = card.locator(COSTCO_SELECTORS["product_price"])

                    title = await title_elem.text_content() if await title_elem.count() > 0 else "Unknown"
                    price = await price_elem.text_content() if await price_elem.count() > 0 else "N/A"
                    href = await title_elem.get_attribute("href") if await title_elem.count() > 0 else ""

                    products.append({
                        "index": i,
                        "title": title.strip() if title else "Unknown",
                        "price": price.strip() if price else "N/A",
                        "url": f"{self.config.base_url}{href}" if href and not href.startswith("http") else href
                    })
                except Exception:
                    continue

            return {
                "success": True,
                "query": query,
                "result_count": len(products),
                "products": products
            }

        except Exception as e:
            await self.screenshot("search_error")
            return {"success": False, "error": f"Search failed: {str(e)}"}

    async def view_product(self, product_url: str) -> Dict[str, Any]:
        """
        Navigate to and view a product page.

        Args:
            product_url: URL of the product

        Returns:
            Dict with product details
        """
        try:
            await self.navigate(product_url)
            await self.close_modals()
            await self.screenshot("product_page")

            # Extract product details
            title = await self.page.title()

            # Check if add to cart button exists
            add_to_cart = self.page.locator(COSTCO_SELECTORS["add_to_cart_button"])
            can_add_to_cart = await add_to_cart.count() > 0

            return {
                "success": True,
                "title": title,
                "url": product_url,
                "can_add_to_cart": can_add_to_cart
            }

        except Exception as e:
            await self.screenshot("product_view_error")
            return {"success": False, "error": f"Failed to view product: {str(e)}"}

    async def add_to_cart(self, quantity: int = 1) -> Dict[str, Any]:
        """
        Add the current product to cart.

        Args:
            quantity: Number of items to add

        Returns:
            Dict with success status
        """
        try:
            # Set quantity if different from default
            if quantity > 1:
                qty_input = self.page.locator(COSTCO_SELECTORS["quantity_input"])
                if await qty_input.count() > 0:
                    await qty_input.fill(str(quantity))

            # Click add to cart
            add_btn = self.page.locator(COSTCO_SELECTORS["add_to_cart_button"])
            if await add_btn.count() == 0:
                return {"success": False, "error": "Add to cart button not found"}

            await add_btn.click()
            await asyncio.sleep(2)
            await self.wait_for_load()
            await self.screenshot("added_to_cart")

            return {
                "success": True,
                "message": f"Added {quantity} item(s) to cart"
            }

        except Exception as e:
            await self.screenshot("add_to_cart_error")
            return {"success": False, "error": f"Failed to add to cart: {str(e)}"}

    async def view_cart(self) -> Dict[str, Any]:
        """
        Navigate to and view the shopping cart.

        Returns:
            Dict with cart contents
        """
        try:
            await self.navigate(self.config.cart_url)
            await self.close_modals()
            await asyncio.sleep(2)
            await self.screenshot("cart_page")

            # Parse cart items
            cart_items = []
            item_elements = self.page.locator(COSTCO_SELECTORS["cart_items"])
            count = await item_elements.count()

            for i in range(count):
                item = item_elements.nth(i)
                try:
                    name_elem = item.locator(COSTCO_SELECTORS["cart_item_name"])
                    price_elem = item.locator(COSTCO_SELECTORS["cart_item_price"])
                    qty_elem = item.locator(COSTCO_SELECTORS["cart_item_quantity"])

                    name = await name_elem.text_content() if await name_elem.count() > 0 else "Unknown"
                    price = await price_elem.text_content() if await price_elem.count() > 0 else "N/A"
                    qty = await qty_elem.input_value() if await qty_elem.count() > 0 else "1"

                    cart_items.append({
                        "name": name.strip() if name else "Unknown",
                        "price": price.strip() if price else "N/A",
                        "quantity": qty
                    })
                except Exception:
                    continue

            # Get subtotal
            subtotal_elem = self.page.locator(COSTCO_SELECTORS["cart_subtotal"])
            subtotal = await subtotal_elem.text_content() if await subtotal_elem.count() > 0 else "N/A"

            return {
                "success": True,
                "item_count": len(cart_items),
                "items": cart_items,
                "subtotal": subtotal.strip() if subtotal else "N/A"
            }

        except Exception as e:
            await self.screenshot("cart_error")
            return {"success": False, "error": f"Failed to view cart: {str(e)}"}

    async def apply_promo_code(self, code: str) -> Dict[str, Any]:
        """
        Apply a promotional code to the cart.

        Args:
            code: Promotional code

        Returns:
            Dict with success status
        """
        try:
            # Make sure we're on the cart page
            if "cart" not in self.page.url.lower():
                await self.navigate(self.config.cart_url)

            # Find and fill promo code input
            promo_input = self.page.locator(COSTCO_SELECTORS["promo_code_input"])
            if await promo_input.count() == 0:
                return {"success": False, "error": "Promo code input not found"}

            await promo_input.fill(code)

            # Click apply button
            apply_btn = self.page.locator(COSTCO_SELECTORS["apply_promo_button"])
            await apply_btn.click()

            await asyncio.sleep(2)
            await self.screenshot("promo_applied")

            # Check for error
            error_elem = self.page.locator(COSTCO_SELECTORS["error_message"])
            if await error_elem.count() > 0:
                error_text = await error_elem.text_content()
                return {"success": False, "error": f"Promo code failed: {error_text}"}

            return {"success": True, "message": f"Applied promo code: {code}"}

        except Exception as e:
            await self.screenshot("promo_error")
            return {"success": False, "error": f"Failed to apply promo: {str(e)}"}

    async def proceed_to_checkout(self) -> Dict[str, Any]:
        """
        Proceed from cart to checkout.

        Returns:
            Dict with success status
        """
        try:
            # Make sure we're on the cart page
            if "cart" not in self.page.url.lower():
                await self.navigate(self.config.cart_url)

            # Click proceed to checkout
            checkout_btn = self.page.locator(COSTCO_SELECTORS["proceed_to_checkout"])
            if await checkout_btn.count() == 0:
                return {"success": False, "error": "Checkout button not found"}

            await checkout_btn.click()
            await self.wait_for_load()
            await asyncio.sleep(2)
            await self.screenshot("checkout_page")

            return {"success": True, "message": "Proceeded to checkout"}

        except Exception as e:
            await self.screenshot("checkout_error")
            return {"success": False, "error": f"Failed to proceed to checkout: {str(e)}"}

    async def get_order_summary(self) -> Dict[str, Any]:
        """
        Get the order summary at checkout.

        Returns:
            Dict with order details
        """
        try:
            await self.screenshot("order_summary")

            summary_elem = self.page.locator(COSTCO_SELECTORS["order_summary"])
            total_elem = self.page.locator(COSTCO_SELECTORS["order_total"])

            summary = await summary_elem.text_content() if await summary_elem.count() > 0 else "N/A"
            total = await total_elem.text_content() if await total_elem.count() > 0 else "N/A"

            return {
                "success": True,
                "summary": summary.strip() if summary else "N/A",
                "total": total.strip() if total else "N/A"
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get order summary: {str(e)}"}

    async def place_order(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Place the order (final step).

        Args:
            confirm: Must be True to actually place the order (safety check)

        Returns:
            Dict with order status
        """
        if not confirm:
            return {
                "success": False,
                "error": "Order not placed. Set confirm=True to place order.",
                "message": "This is a safety check. Review order and call with confirm=True."
            }

        try:
            await self.screenshot("before_place_order")

            place_order_btn = self.page.locator(COSTCO_SELECTORS["place_order_button"])
            if await place_order_btn.count() == 0:
                return {"success": False, "error": "Place order button not found"}

            await place_order_btn.click()
            await self.wait_for_load()
            await asyncio.sleep(5)
            await self.screenshot("order_placed")

            return {
                "success": True,
                "message": "Order placed successfully!",
                "confirmation_url": self.page.url
            }

        except Exception as e:
            await self.screenshot("place_order_error")
            return {"success": False, "error": f"Failed to place order: {str(e)}"}

    @property
    def is_logged_in(self) -> bool:
        """Check if currently logged in."""
        return self._is_logged_in
