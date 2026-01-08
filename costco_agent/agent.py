"""
Costco Shopping Agent - Main Orchestrator

This module provides the main CostcoShoppingAgent class that orchestrates
the shopping workflow using Claude as the AI backbone.
"""

import asyncio
import json
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass

from .config import CostcoConfig
from .browser import CostcoBrowser
from .tools import CostcoTools, get_tool_definitions, TOOL_HANDLERS


@dataclass
class ShoppingTask:
    """Represents a shopping task to be completed."""
    items: List[str]  # Items to search for and purchase
    promo_code: Optional[str] = None  # Optional promo code
    max_price_per_item: Optional[float] = None  # Optional price limit
    auto_checkout: bool = False  # Whether to automatically checkout


@dataclass
class AgentMessage:
    """Message from the agent during execution."""
    type: str  # "thinking", "action", "result", "error"
    content: str
    data: Optional[Dict[str, Any]] = None


class CostcoShoppingAgent:
    """
    AI-powered shopping agent for Costco.com

    This agent can:
    - Search for products
    - Add items to cart
    - Apply promotional codes
    - Complete checkout (with user confirmation)

    Usage:
        config = CostcoConfig.from_env()
        agent = CostcoShoppingAgent(config)

        async with agent:
            result = await agent.shop(["kirkland olive oil", "toilet paper"])
    """

    def __init__(self, config: Optional[CostcoConfig] = None):
        self.config = config or CostcoConfig.from_env()
        self.browser: Optional[CostcoBrowser] = None
        self.tools: Optional[CostcoTools] = None
        self._is_running = False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()

    async def start(self) -> None:
        """Initialize the agent and browser."""
        self.browser = CostcoBrowser(self.config)
        await self.browser.start()
        self.tools = CostcoTools(self.browser)
        self._is_running = True

    async def stop(self) -> None:
        """Shutdown the agent and browser."""
        if self.browser:
            await self.browser.stop()
        self._is_running = False

    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single tool by name.

        Args:
            tool_name: Name of the tool to execute
            args: Arguments for the tool

        Returns:
            Tool execution result
        """
        if tool_name not in TOOL_HANDLERS:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}

        method_name = TOOL_HANDLERS[tool_name]
        method = getattr(self.tools, method_name)
        return await method(args)

    async def shop(
        self,
        items: List[str],
        promo_code: Optional[str] = None,
        auto_checkout: bool = False
    ) -> AsyncGenerator[AgentMessage, None]:
        """
        Execute a shopping workflow.

        Args:
            items: List of items to search for and add to cart
            promo_code: Optional promotional code to apply
            auto_checkout: Whether to automatically proceed to checkout

        Yields:
            AgentMessage objects with progress updates
        """
        if not self._is_running:
            yield AgentMessage(
                type="error",
                content="Agent not started. Use 'async with' or call start() first."
            )
            return

        # Step 1: Login
        yield AgentMessage(type="thinking", content="Logging into Costco...")
        login_result = await self.execute_tool("costco_login", {})
        login_data = json.loads(login_result["content"][0]["text"])

        if not login_data.get("success"):
            yield AgentMessage(
                type="error",
                content=f"Login failed: {login_data.get('error', 'Unknown error')}",
                data=login_data
            )
            return

        yield AgentMessage(type="result", content="Successfully logged in", data=login_data)

        # Step 2: Search and add each item
        for item in items:
            yield AgentMessage(type="thinking", content=f"Searching for: {item}")

            # Search for the item
            search_result = await self.execute_tool("costco_search", {"query": item})
            search_data = json.loads(search_result["content"][0]["text"])

            if not search_data.get("success") or not search_data.get("products"):
                yield AgentMessage(
                    type="error",
                    content=f"No results found for: {item}",
                    data=search_data
                )
                continue

            yield AgentMessage(
                type="result",
                content=f"Found {search_data['result_count']} results for '{item}'",
                data=search_data
            )

            # Select the first product
            first_product = search_data["products"][0]
            yield AgentMessage(
                type="thinking",
                content=f"Selecting: {first_product['title'][:50]}... ({first_product['price']})"
            )

            # View the product
            view_result = await self.execute_tool(
                "costco_view_product",
                {"product_url": first_product["url"]}
            )
            view_data = json.loads(view_result["content"][0]["text"])

            if not view_data.get("success"):
                yield AgentMessage(
                    type="error",
                    content=f"Failed to view product: {view_data.get('error')}",
                    data=view_data
                )
                continue

            # Add to cart
            if view_data.get("can_add_to_cart"):
                yield AgentMessage(type="action", content="Adding to cart...")
                add_result = await self.execute_tool("costco_add_to_cart", {"quantity": 1})
                add_data = json.loads(add_result["content"][0]["text"])

                if add_data.get("success"):
                    yield AgentMessage(
                        type="result",
                        content=f"Added to cart: {first_product['title'][:50]}...",
                        data=add_data
                    )
                else:
                    yield AgentMessage(
                        type="error",
                        content=f"Failed to add to cart: {add_data.get('error')}",
                        data=add_data
                    )
            else:
                yield AgentMessage(
                    type="error",
                    content=f"Product cannot be added to cart (may be out of stock)"
                )

        # Step 3: View cart
        yield AgentMessage(type="thinking", content="Viewing cart...")
        cart_result = await self.execute_tool("costco_view_cart", {})
        cart_data = json.loads(cart_result["content"][0]["text"])

        yield AgentMessage(
            type="result",
            content=f"Cart has {cart_data.get('item_count', 0)} items. Subtotal: {cart_data.get('subtotal', 'N/A')}",
            data=cart_data
        )

        # Step 4: Apply promo code if provided
        if promo_code:
            yield AgentMessage(type="action", content=f"Applying promo code: {promo_code}")
            promo_result = await self.execute_tool("costco_apply_promo", {"code": promo_code})
            promo_data = json.loads(promo_result["content"][0]["text"])

            if promo_data.get("success"):
                yield AgentMessage(
                    type="result",
                    content=f"Promo code applied successfully",
                    data=promo_data
                )
            else:
                yield AgentMessage(
                    type="error",
                    content=f"Promo code failed: {promo_data.get('error')}",
                    data=promo_data
                )

        # Step 5: Checkout (if auto_checkout enabled)
        if auto_checkout:
            yield AgentMessage(type="action", content="Proceeding to checkout...")
            checkout_result = await self.execute_tool("costco_checkout", {})
            checkout_data = json.loads(checkout_result["content"][0]["text"])

            if checkout_data.get("success"):
                yield AgentMessage(
                    type="result",
                    content="At checkout page",
                    data=checkout_data
                )

                # Get order summary
                summary_result = await self.execute_tool("costco_order_summary", {})
                summary_data = json.loads(summary_result["content"][0]["text"])

                yield AgentMessage(
                    type="result",
                    content=f"Order total: {summary_data.get('total', 'N/A')}",
                    data=summary_data
                )

                # Note: We don't automatically place the order for safety
                yield AgentMessage(
                    type="thinking",
                    content="Ready to place order. Call place_order(confirm=True) to complete purchase."
                )
            else:
                yield AgentMessage(
                    type="error",
                    content=f"Checkout failed: {checkout_data.get('error')}",
                    data=checkout_data
                )
        else:
            yield AgentMessage(
                type="result",
                content="Shopping complete! Items are in cart. Set auto_checkout=True to proceed to checkout."
            )

    async def place_order(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Place the order (final step).

        Args:
            confirm: Must be True to actually place the order

        Returns:
            Order result
        """
        result = await self.execute_tool("costco_place_order", {"confirm": confirm})
        return json.loads(result["content"][0]["text"])

    async def interactive_session(self) -> AsyncGenerator[AgentMessage, None]:
        """
        Start an interactive shopping session.

        Yields status messages and waits for user commands.
        """
        yield AgentMessage(
            type="thinking",
            content="Starting interactive Costco shopping session..."
        )

        # Login
        login_result = await self.execute_tool("costco_login", {})
        login_data = json.loads(login_result["content"][0]["text"])

        if login_data.get("success"):
            yield AgentMessage(
                type="result",
                content="Logged in! Ready for commands.",
                data={"available_commands": list(TOOL_HANDLERS.keys())}
            )
        else:
            yield AgentMessage(
                type="error",
                content=f"Login failed: {login_data.get('error')}"
            )


async def run_shopping_demo():
    """Demo function showing agent usage."""
    print("=" * 60)
    print("Costco Shopping Agent Demo")
    print("=" * 60)

    config = CostcoConfig.from_env()

    if not config.email or not config.password:
        print("\nError: Please set environment variables:")
        print("  export COSTCO_EMAIL='your_email@example.com'")
        print("  export COSTCO_PASSWORD='your_password'")
        return

    async with CostcoShoppingAgent(config) as agent:
        # Example: Search for items and add to cart
        items_to_buy = ["kirkland olive oil"]

        async for message in agent.shop(items_to_buy, auto_checkout=False):
            prefix = {
                "thinking": "[THINKING]",
                "action": "[ACTION]  ",
                "result": "[RESULT]  ",
                "error": "[ERROR]   "
            }.get(message.type, "[INFO]    ")

            print(f"{prefix} {message.content}")

            if message.data and message.type == "result":
                if "products" in message.data:
                    for i, p in enumerate(message.data["products"][:3]):
                        print(f"           {i+1}. {p['title'][:40]}... - {p['price']}")


if __name__ == "__main__":
    asyncio.run(run_shopping_demo())
