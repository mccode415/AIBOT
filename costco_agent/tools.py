"""
Costco Shopping Tools for Claude Agent SDK

This module provides tool definitions that can be used with the Claude Agent SDK
to automate Costco shopping workflows.
"""

import json
from typing import Dict, Any, Callable, List
from functools import wraps

from .browser import CostcoBrowser
from .config import CostcoConfig


class CostcoTools:
    """
    Collection of shopping tools for Costco automation.
    These tools wrap browser automation into agent-callable functions.
    """

    def __init__(self, browser: CostcoBrowser):
        self.browser = browser

    def _format_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Format response for Claude agent consumption."""
        return {
            "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
        }

    async def login(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Log into Costco.com

        Tool name: costco_login
        Description: Log into Costco.com with configured credentials
        Parameters: None required (uses environment credentials)
        """
        result = await self.browser.login()
        return self._format_response(result)

    async def search_products(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search for products on Costco

        Tool name: costco_search
        Description: Search for products on Costco.com
        Parameters:
            - query (str, required): Search term for products
            - max_results (int, optional): Maximum results to return (default: 10)
        """
        query = args.get("query", "")
        if not query:
            return self._format_response({
                "success": False,
                "error": "Query parameter is required"
            })

        result = await self.browser.search_products(query)

        # Limit results if specified
        max_results = args.get("max_results", 10)
        if result.get("success") and result.get("products"):
            result["products"] = result["products"][:max_results]
            result["result_count"] = len(result["products"])

        return self._format_response(result)

    async def view_product(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        View a specific product page

        Tool name: costco_view_product
        Description: Navigate to and view a product page to see details
        Parameters:
            - product_url (str, required): Full URL of the product
            - product_index (int, optional): Index from search results to view
        """
        product_url = args.get("product_url", "")
        if not product_url:
            return self._format_response({
                "success": False,
                "error": "product_url parameter is required"
            })

        result = await self.browser.view_product(product_url)
        return self._format_response(result)

    async def add_to_cart(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add the current product to cart

        Tool name: costco_add_to_cart
        Description: Add the currently viewed product to the shopping cart
        Parameters:
            - quantity (int, optional): Number of items to add (default: 1)
        """
        quantity = args.get("quantity", 1)
        result = await self.browser.add_to_cart(quantity=quantity)
        return self._format_response(result)

    async def view_cart(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        View the shopping cart contents

        Tool name: costco_view_cart
        Description: View all items currently in the shopping cart
        Parameters: None
        """
        result = await self.browser.view_cart()
        return self._format_response(result)

    async def apply_promo_code(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply a promotional code

        Tool name: costco_apply_promo
        Description: Apply a promotional/coupon code to the cart
        Parameters:
            - code (str, required): The promotional code to apply
        """
        code = args.get("code", "")
        if not code:
            return self._format_response({
                "success": False,
                "error": "code parameter is required"
            })

        result = await self.browser.apply_promo_code(code)
        return self._format_response(result)

    async def proceed_to_checkout(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Proceed from cart to checkout

        Tool name: costco_checkout
        Description: Move from the shopping cart to the checkout page
        Parameters: None
        """
        result = await self.browser.proceed_to_checkout()
        return self._format_response(result)

    async def get_order_summary(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get the order summary

        Tool name: costco_order_summary
        Description: Get the current order summary including total price
        Parameters: None
        """
        result = await self.browser.get_order_summary()
        return self._format_response(result)

    async def place_order(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Place the order (final step)

        Tool name: costco_place_order
        Description: Complete the purchase and place the order
        Parameters:
            - confirm (bool, required): Must be True to actually place order (safety check)
        """
        confirm = args.get("confirm", False)
        result = await self.browser.place_order(confirm=confirm)
        return self._format_response(result)

    async def take_screenshot(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Take a screenshot of current page

        Tool name: costco_screenshot
        Description: Take a screenshot for debugging or verification
        Parameters:
            - name (str, optional): Name for the screenshot file
        """
        name = args.get("name", "manual_screenshot")
        filepath = await self.browser.screenshot(name)
        return self._format_response({
            "success": True,
            "screenshot_path": filepath
        })


def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Get tool definitions for Claude Agent SDK registration.

    Returns:
        List of tool definition dictionaries
    """
    return [
        {
            "name": "costco_login",
            "description": "Log into Costco.com with configured credentials. Credentials should be set via COSTCO_EMAIL and COSTCO_PASSWORD environment variables.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "costco_search",
            "description": "Search for products on Costco.com. Returns a list of products matching the search query with titles, prices, and URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term for products (e.g., 'kirkland olive oil', 'toilet paper')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        },
        {
            "name": "costco_view_product",
            "description": "Navigate to a specific product page to view its details and check if it can be added to cart.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_url": {
                        "type": "string",
                        "description": "Full URL of the Costco product page"
                    }
                },
                "required": ["product_url"]
            }
        },
        {
            "name": "costco_add_to_cart",
            "description": "Add the currently viewed product to the shopping cart. Must be on a product page first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "quantity": {
                        "type": "integer",
                        "description": "Number of items to add (default: 1)",
                        "default": 1
                    }
                },
                "required": []
            }
        },
        {
            "name": "costco_view_cart",
            "description": "View all items currently in the shopping cart, including item names, prices, quantities, and subtotal.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "costco_apply_promo",
            "description": "Apply a promotional or coupon code to the shopping cart for discounts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "The promotional code to apply"
                    }
                },
                "required": ["code"]
            }
        },
        {
            "name": "costco_checkout",
            "description": "Proceed from the shopping cart to the checkout page to begin the purchase process.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "costco_order_summary",
            "description": "Get the current order summary at checkout, including itemized costs and total price.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        },
        {
            "name": "costco_place_order",
            "description": "Complete the purchase and place the order. IMPORTANT: This will charge your payment method. Requires confirm=True as a safety check.",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirm": {
                        "type": "boolean",
                        "description": "Must be True to actually place the order. This is a safety check to prevent accidental purchases."
                    }
                },
                "required": ["confirm"]
            }
        },
        {
            "name": "costco_screenshot",
            "description": "Take a screenshot of the current browser page for debugging or verification purposes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name for the screenshot file",
                        "default": "screenshot"
                    }
                },
                "required": []
            }
        }
    ]


# Tool name to method mapping
TOOL_HANDLERS = {
    "costco_login": "login",
    "costco_search": "search_products",
    "costco_view_product": "view_product",
    "costco_add_to_cart": "add_to_cart",
    "costco_view_cart": "view_cart",
    "costco_apply_promo": "apply_promo_code",
    "costco_checkout": "proceed_to_checkout",
    "costco_order_summary": "get_order_summary",
    "costco_place_order": "place_order",
    "costco_screenshot": "take_screenshot"
}
