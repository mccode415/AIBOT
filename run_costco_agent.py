#!/usr/bin/env python3
"""
Costco Shopping Automation Agent - Entry Point

This script provides a command-line interface for the Costco shopping agent.

Usage:
    # Set credentials first
    export COSTCO_EMAIL="your_email@example.com"
    export COSTCO_PASSWORD="your_password"

    # Run the agent
    python run_costco_agent.py --items "kirkland olive oil" "toilet paper"
    python run_costco_agent.py --items "paper towels" --promo "SAVE10"
    python run_costco_agent.py --interactive
"""

import asyncio
import argparse
import os
import sys
from typing import List, Optional

from costco_agent import CostcoShoppingAgent, CostcoConfig


def print_banner():
    """Print the agent banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║         COSTCO SHOPPING AUTOMATION AGENT v1.0             ║
    ║                                                           ║
    ║  Automate your Costco shopping with AI                    ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_message(msg_type: str, content: str):
    """Print a formatted message."""
    colors = {
        "thinking": "\033[94m",  # Blue
        "action": "\033[93m",    # Yellow
        "result": "\033[92m",    # Green
        "error": "\033[91m",     # Red
    }
    reset = "\033[0m"

    icons = {
        "thinking": "🤔",
        "action": "⚡",
        "result": "✅",
        "error": "❌",
    }

    color = colors.get(msg_type, "")
    icon = icons.get(msg_type, "ℹ️")

    print(f"{color}{icon} {content}{reset}")


async def run_shopping(
    items: List[str],
    promo_code: Optional[str] = None,
    auto_checkout: bool = False,
    headless: bool = False,
    browse_only: bool = False
):
    """
    Run the shopping agent with specified items.

    Args:
        items: List of items to shop for
        promo_code: Optional promo code to apply
        auto_checkout: Whether to proceed to checkout automatically
        headless: Run browser in headless mode
        browse_only: Just search/browse, don't login or add to cart
    """
    # Set headless mode
    os.environ["HEADLESS"] = str(headless).lower()

    config = CostcoConfig.from_env()

    if not browse_only and (not config.email or not config.password):
        print_message("error", "Credentials not configured!")
        print("\nPlease set environment variables:")
        print("  export COSTCO_EMAIL='your_email@example.com'")
        print("  export COSTCO_PASSWORD='your_password'")
        print("\nOr use --browse for browse-only mode (no login needed)")
        return

    print(f"\n📋 Shopping list: {', '.join(items)}")
    if promo_code:
        print(f"🏷️  Promo code: {promo_code}")
    print(f"🔍 Mode: {'Browse-only' if browse_only else 'Full shopping'}")
    if not browse_only:
        print(f"💳 Auto-checkout: {'Yes' if auto_checkout else 'No'}")
    print("-" * 50)

    try:
        async with CostcoShoppingAgent(config, browse_only=browse_only) as agent:
            async for message in agent.shop(
                items=items,
                promo_code=promo_code,
                auto_checkout=auto_checkout
            ):
                print_message(message.type, message.content)

                # Show product results
                if message.data and message.type == "result":
                    if "products" in message.data:
                        print("\n   Top results:")
                        for i, p in enumerate(message.data["products"][:5]):
                            title = p.get("title", "Unknown")[:45]
                            price = p.get("price", "N/A")
                            print(f"   {i+1}. {title}... - {price}")
                        print()

                    if "items" in message.data:
                        print("\n   Cart contents:")
                        for item in message.data["items"]:
                            name = item.get("name", "Unknown")[:40]
                            qty = item.get("quantity", "1")
                            price = item.get("price", "N/A")
                            print(f"   • {name}... x{qty} - {price}")
                        print()

    except KeyboardInterrupt:
        print("\n\n⚠️  Shopping cancelled by user")
    except Exception as e:
        print_message("error", f"Agent error: {str(e)}")
        raise


async def run_interactive():
    """Run an interactive shopping session."""
    config = CostcoConfig.from_env()

    if not config.email or not config.password:
        print_message("error", "Credentials not configured!")
        return

    print("\n🎯 Interactive Mode")
    print("Commands: search <query>, add, cart, checkout, quit")
    print("-" * 50)

    async with CostcoShoppingAgent(config) as agent:
        # Login first
        print_message("thinking", "Logging in...")
        result = await agent.execute_tool("costco_login", {})
        import json
        data = json.loads(result["content"][0]["text"])

        if data.get("success"):
            print_message("result", "Logged in successfully!")
        else:
            print_message("error", f"Login failed: {data.get('error')}")
            return

        while True:
            try:
                cmd = input("\n> ").strip().lower()

                if cmd.startswith("quit") or cmd.startswith("exit"):
                    print("👋 Goodbye!")
                    break

                elif cmd.startswith("search "):
                    query = cmd[7:].strip()
                    print_message("thinking", f"Searching for: {query}")
                    result = await agent.execute_tool("costco_search", {"query": query})
                    data = json.loads(result["content"][0]["text"])

                    if data.get("success"):
                        print_message("result", f"Found {data['result_count']} results")
                        for i, p in enumerate(data.get("products", [])[:5]):
                            print(f"   {i+1}. {p['title'][:45]}... - {p['price']}")
                    else:
                        print_message("error", data.get("error", "Search failed"))

                elif cmd.startswith("view "):
                    url = cmd[5:].strip()
                    print_message("thinking", "Viewing product...")
                    result = await agent.execute_tool("costco_view_product", {"product_url": url})
                    data = json.loads(result["content"][0]["text"])
                    print_message("result" if data.get("success") else "error", json.dumps(data, indent=2))

                elif cmd == "add":
                    print_message("action", "Adding to cart...")
                    result = await agent.execute_tool("costco_add_to_cart", {"quantity": 1})
                    data = json.loads(result["content"][0]["text"])
                    print_message("result" if data.get("success") else "error", data.get("message") or data.get("error"))

                elif cmd == "cart":
                    print_message("thinking", "Viewing cart...")
                    result = await agent.execute_tool("costco_view_cart", {})
                    data = json.loads(result["content"][0]["text"])

                    if data.get("success"):
                        print_message("result", f"Cart: {data.get('item_count', 0)} items, Subtotal: {data.get('subtotal', 'N/A')}")
                        for item in data.get("items", []):
                            print(f"   • {item.get('name', 'Unknown')[:40]}...")
                    else:
                        print_message("error", data.get("error"))

                elif cmd == "checkout":
                    print_message("action", "Proceeding to checkout...")
                    result = await agent.execute_tool("costco_checkout", {})
                    data = json.loads(result["content"][0]["text"])
                    print_message("result" if data.get("success") else "error", data.get("message") or data.get("error"))

                elif cmd.startswith("promo "):
                    code = cmd[6:].strip()
                    print_message("action", f"Applying promo: {code}")
                    result = await agent.execute_tool("costco_apply_promo", {"code": code})
                    data = json.loads(result["content"][0]["text"])
                    print_message("result" if data.get("success") else "error", data.get("message") or data.get("error"))

                elif cmd == "screenshot":
                    result = await agent.execute_tool("costco_screenshot", {"name": "interactive"})
                    print_message("result", "Screenshot saved")

                elif cmd == "help":
                    print("""
Available commands:
  search <query>  - Search for products
  view <url>      - View a product page
  add             - Add current product to cart
  cart            - View cart contents
  promo <code>    - Apply promo code
  checkout        - Proceed to checkout
  screenshot      - Take screenshot
  quit            - Exit
                    """)

                else:
                    print("Unknown command. Type 'help' for available commands.")

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print_message("error", str(e))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Costco Shopping Automation Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --items "kirkland olive oil" "paper towels"
  %(prog)s --items "toilet paper" --promo "SAVE10"
  %(prog)s --browse --items "coffee"        # Browse-only (no login)
  %(prog)s --gui                            # Launch web GUI
  %(prog)s --interactive

Environment Variables:
  COSTCO_EMAIL     Your Costco account email
  COSTCO_PASSWORD  Your Costco account password
  HEADLESS         Run browser in headless mode (true/false)
        """
    )

    parser.add_argument(
        "--items", "-i",
        nargs="+",
        help="Items to search for and add to cart"
    )
    parser.add_argument(
        "--promo", "-p",
        help="Promotional code to apply"
    )
    parser.add_argument(
        "--checkout", "-c",
        action="store_true",
        help="Automatically proceed to checkout"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--browse", "-b",
        action="store_true",
        help="Browse-only mode: search products without logging in"
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the Streamlit web GUI"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run in interactive mode"
    )

    args = parser.parse_args()

    print_banner()

    if args.gui:
        import subprocess
        print("🚀 Launching Streamlit GUI...")
        print("   Open http://localhost:8501 in your browser")
        subprocess.run(["streamlit", "run", "costco_app.py"])
    elif args.interactive:
        asyncio.run(run_interactive())
    elif args.items:
        asyncio.run(run_shopping(
            items=args.items,
            promo_code=args.promo,
            auto_checkout=args.checkout,
            headless=args.headless,
            browse_only=args.browse
        ))
    else:
        parser.print_help()
        print("\n⚠️  Please specify --items, --gui, or --interactive")


if __name__ == "__main__":
    main()
