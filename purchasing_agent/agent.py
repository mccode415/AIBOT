"""
Autonomous Purchasing Agent with Visual Reasoning

This agent uses vision-language models to:
1. See and understand any webpage dynamically
2. Reason about what actions to take
3. Execute actions through browser automation
4. Handle unexpected situations gracefully

No hard-coded page knowledge required!
"""

import asyncio
import base64
import json
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Page, Browser, ElementHandle
import anthropic


class ActionType(Enum):
    CLICK = "click"
    TYPE = "type"
    SCROLL = "scroll"
    SELECT = "select"
    WAIT = "wait"
    NAVIGATE = "navigate"
    DONE = "done"
    ASK_USER = "ask_user"


@dataclass
class Action:
    """Represents an action the agent decides to take"""
    action_type: ActionType
    target: Optional[str] = None  # CSS selector, XPath, or description
    value: Optional[str] = None   # Text to type, option to select, etc.
    reasoning: str = ""           # Why the agent chose this action
    confidence: float = 0.0       # How confident (0-1)


@dataclass
class PurchaseTask:
    """Defines what the agent should purchase"""
    product_description: str
    max_price: float
    quantity: int = 1
    preferred_options: Dict[str, str] = None  # e.g., {"size": "Large", "color": "Blue"}
    shipping_address: Dict[str, str] = None
    payment_method: str = "saved_card"  # or provide card details


class AutonomousPurchasingAgent:
    """
    A true reasoning agent that can navigate any e-commerce site.

    Key capabilities:
    - Visual understanding of page structure
    - Semantic reasoning about what to do next
    - Dynamic element location (no hardcoded selectors)
    - Error recovery and adaptation
    - Multi-step planning
    """

    def __init__(self, api_key: str = None):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.action_history: List[Action] = []
        self.max_actions = 50  # Safety limit
        self.model = "claude-sonnet-4-20250514"  # Vision-capable model

    async def start(self, headless: bool = False):
        """Initialize the browser"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=headless)
        context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        self.page = await context.new_page()

    async def stop(self):
        """Clean up browser resources"""
        if self.browser:
            await self.browser.close()

    async def capture_page_state(self) -> Dict[str, Any]:
        """
        Capture complete page state for the LLM to analyze.
        Returns screenshot + accessibility tree + visible text.
        """
        # Take screenshot
        screenshot_bytes = await self.page.screenshot(full_page=False)
        screenshot_b64 = base64.standard_b64encode(screenshot_bytes).decode("utf-8")

        # Get page URL and title
        url = self.page.url
        title = await self.page.title()

        # Get accessibility tree (semantic structure)
        accessibility_tree = await self._get_accessibility_snapshot()

        # Get all interactive elements with their locations
        interactive_elements = await self._get_interactive_elements()

        return {
            "screenshot_b64": screenshot_b64,
            "url": url,
            "title": title,
            "accessibility_tree": accessibility_tree,
            "interactive_elements": interactive_elements
        }

    async def _get_accessibility_snapshot(self) -> str:
        """Get a semantic representation of the page structure"""
        try:
            snapshot = await self.page.accessibility.snapshot()
            return self._format_accessibility_tree(snapshot, max_depth=4)
        except Exception:
            return "Accessibility tree unavailable"

    def _format_accessibility_tree(self, node: dict, depth: int = 0, max_depth: int = 4) -> str:
        """Format accessibility tree as readable text"""
        if not node or depth > max_depth:
            return ""

        indent = "  " * depth
        role = node.get("role", "unknown")
        name = node.get("name", "")

        # Filter to important elements
        important_roles = {"button", "link", "textbox", "combobox", "checkbox",
                          "radio", "heading", "img", "listitem", "menuitem"}

        result = ""
        if role in important_roles or name:
            result = f"{indent}[{role}] {name}\n"

        for child in node.get("children", []):
            result += self._format_accessibility_tree(child, depth + 1, max_depth)

        return result

    async def _get_interactive_elements(self) -> List[Dict]:
        """Get all clickable/interactive elements with bounding boxes"""
        elements = await self.page.evaluate("""
            () => {
                const interactive = [];
                const selectors = 'a, button, input, select, textarea, [role="button"], [onclick], [tabindex]';

                document.querySelectorAll(selectors).forEach((el, index) => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0 && rect.top < window.innerHeight) {
                        interactive.push({
                            index: index,
                            tag: el.tagName.toLowerCase(),
                            type: el.type || null,
                            text: (el.innerText || el.value || el.placeholder || el.ariaLabel || '').slice(0, 100),
                            id: el.id || null,
                            name: el.name || null,
                            href: el.href || null,
                            bounds: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            }
                        });
                    }
                });
                return interactive;
            }
        """)
        return elements

    async def reason_about_action(self, task: PurchaseTask, page_state: Dict) -> Action:
        """
        Use Claude to reason about what action to take next.
        This is the core "thinking" part of the agent.
        """

        # Build the prompt with all context
        system_prompt = """You are an autonomous web purchasing agent. Your job is to navigate e-commerce websites and complete purchases.

CAPABILITIES:
- You can SEE the current webpage (screenshot provided)
- You can understand page structure (accessibility tree provided)
- You can identify interactive elements (list provided)

ACTIONS YOU CAN TAKE:
1. CLICK - Click on an element (provide CSS selector or element description)
2. TYPE - Type text into a field (provide selector and text)
3. SCROLL - Scroll the page (provide direction: up/down)
4. SELECT - Select an option from dropdown (provide selector and option)
5. WAIT - Wait for page to load
6. NAVIGATE - Go to a specific URL
7. DONE - Task is complete (purchase confirmed)
8. ASK_USER - Need human input (for captchas, 2FA, critical decisions)

DECISION PROCESS:
1. Analyze what's currently on screen
2. Determine where we are in the purchase flow
3. Identify the next logical step toward completing the purchase
4. Choose the most appropriate action
5. Provide clear reasoning for your choice

SAFETY RULES:
- Never share payment details in responses
- Verify prices before confirming purchase
- Ask user if price exceeds max_price
- Be cautious with irreversible actions (final purchase confirmation)

OUTPUT FORMAT (JSON):
{
    "current_state": "Brief description of what you see on the page",
    "purchase_stage": "browsing|product_page|cart|checkout|payment|confirmation",
    "action": {
        "type": "CLICK|TYPE|SCROLL|SELECT|WAIT|NAVIGATE|DONE|ASK_USER",
        "target": "CSS selector or description of element",
        "value": "text to type or option to select (if applicable)",
        "reasoning": "Why this action moves us toward the goal",
        "confidence": 0.0-1.0
    },
    "next_steps": ["What we'll likely need to do after this action"]
}"""

        # Format the task and current state
        user_prompt = f"""## CURRENT TASK
Product to purchase: {task.product_description}
Maximum price: ${task.max_price}
Quantity: {task.quantity}
Preferred options: {json.dumps(task.preferred_options or {})}

## CURRENT PAGE
URL: {page_state['url']}
Title: {page_state['title']}

## PAGE STRUCTURE (Accessibility Tree)
{page_state['accessibility_tree'][:3000]}

## INTERACTIVE ELEMENTS
{json.dumps(page_state['interactive_elements'][:30], indent=2)}

## ACTION HISTORY (last 5 actions)
{self._format_action_history()}

## YOUR TASK
Analyze the screenshot and page data. Decide the next action to take toward purchasing the specified product.
Remember: Reason step-by-step about what you see and what action makes sense."""

        # Call Claude with vision
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": page_state["screenshot_b64"]
                            }
                        },
                        {
                            "type": "text",
                            "text": user_prompt
                        }
                    ]
                }
            ]
        )

        # Parse the response
        return self._parse_action_response(response.content[0].text)

    def _format_action_history(self) -> str:
        """Format recent actions for context"""
        recent = self.action_history[-5:]
        if not recent:
            return "No previous actions"

        lines = []
        for i, action in enumerate(recent):
            lines.append(f"{i+1}. {action.action_type.value}: {action.target} -> {action.reasoning[:50]}")
        return "\n".join(lines)

    def _parse_action_response(self, response_text: str) -> Action:
        """Parse Claude's response into an Action object"""
        try:
            # Extract JSON from response (handle markdown code blocks)
            json_str = response_text
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]

            data = json.loads(json_str)
            action_data = data.get("action", {})

            return Action(
                action_type=ActionType(action_data.get("type", "WAIT").upper()),
                target=action_data.get("target"),
                value=action_data.get("value"),
                reasoning=action_data.get("reasoning", ""),
                confidence=action_data.get("confidence", 0.5)
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Failed to parse response: {e}")
            print(f"Raw response: {response_text[:500]}")
            # Default to waiting if parsing fails
            return Action(
                action_type=ActionType.WAIT,
                reasoning=f"Failed to parse response: {e}"
            )

    async def execute_action(self, action: Action) -> bool:
        """Execute the decided action in the browser"""
        try:
            if action.action_type == ActionType.CLICK:
                await self._smart_click(action.target)

            elif action.action_type == ActionType.TYPE:
                element = await self._find_element(action.target)
                if element:
                    await element.fill(action.value or "")

            elif action.action_type == ActionType.SCROLL:
                direction = -300 if action.value == "up" else 300
                await self.page.mouse.wheel(0, direction)

            elif action.action_type == ActionType.SELECT:
                element = await self._find_element(action.target)
                if element:
                    await element.select_option(label=action.value)

            elif action.action_type == ActionType.WAIT:
                await asyncio.sleep(2)

            elif action.action_type == ActionType.NAVIGATE:
                await self.page.goto(action.target, wait_until="networkidle")

            elif action.action_type == ActionType.ASK_USER:
                print(f"\n🤖 AGENT NEEDS HELP: {action.reasoning}")
                user_input = input("Your response: ")
                # Agent can use this input in next iteration

            elif action.action_type == ActionType.DONE:
                print("✅ Purchase complete!")
                return True

            # Wait for page to settle after action
            await asyncio.sleep(1)
            await self.page.wait_for_load_state("domcontentloaded")

            self.action_history.append(action)
            return action.action_type == ActionType.DONE

        except Exception as e:
            print(f"Action execution failed: {e}")
            return False

    async def _smart_click(self, target: str):
        """
        Intelligently find and click an element.
        Tries multiple strategies to locate the element.
        """
        strategies = [
            # 1. Try as CSS selector
            lambda: self.page.click(target, timeout=3000),
            # 2. Try as text content
            lambda: self.page.get_by_text(target, exact=False).first.click(timeout=3000),
            # 3. Try as button/link with text
            lambda: self.page.get_by_role("button", name=target).click(timeout=3000),
            lambda: self.page.get_by_role("link", name=target).click(timeout=3000),
            # 4. Try as label
            lambda: self.page.get_by_label(target).click(timeout=3000),
            # 5. Try partial text match
            lambda: self.page.locator(f"text=/{target}/i").first.click(timeout=3000),
        ]

        for strategy in strategies:
            try:
                await strategy()
                return
            except Exception:
                continue

        raise Exception(f"Could not find clickable element: {target}")

    async def _find_element(self, target: str) -> Optional[ElementHandle]:
        """Find an element using multiple strategies"""
        try:
            # Try CSS selector first
            element = await self.page.query_selector(target)
            if element:
                return element
        except Exception:
            pass

        try:
            # Try by placeholder
            locator = self.page.get_by_placeholder(target)
            if await locator.count() > 0:
                return await locator.first.element_handle()
        except Exception:
            pass

        try:
            # Try by label
            locator = self.page.get_by_label(target)
            if await locator.count() > 0:
                return await locator.first.element_handle()
        except Exception:
            pass

        return None

    async def purchase(self, task: PurchaseTask, start_url: str) -> bool:
        """
        Main agent loop: observe -> reason -> act -> repeat

        This is the core agent architecture:
        1. Capture current page state (vision)
        2. Send to LLM for reasoning (thinking)
        3. Execute decided action (acting)
        4. Repeat until done or stuck
        """
        await self.page.goto(start_url, wait_until="networkidle")

        action_count = 0
        consecutive_failures = 0

        while action_count < self.max_actions:
            action_count += 1
            print(f"\n--- Action {action_count} ---")

            # 1. OBSERVE: Capture current page state
            print("📸 Capturing page state...")
            page_state = await self.capture_page_state()

            # 2. REASON: Ask LLM what to do
            print("🧠 Reasoning about next action...")
            action = await self.reason_about_action(task, page_state)

            print(f"📋 Decided: {action.action_type.value}")
            print(f"   Target: {action.target}")
            print(f"   Reasoning: {action.reasoning}")
            print(f"   Confidence: {action.confidence:.2f}")

            # 3. ACT: Execute the action
            print("🎯 Executing action...")
            success = await self.execute_action(action)

            if action.action_type == ActionType.DONE:
                return True

            if action.action_type == ActionType.ASK_USER:
                consecutive_failures = 0
                continue

            if not success:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    print("❌ Too many consecutive failures. Stopping.")
                    return False
            else:
                consecutive_failures = 0

        print("⚠️ Reached maximum action limit")
        return False


# ============================================================
# EXAMPLE USAGE
# ============================================================

async def main():
    """Example: Purchase an item from Amazon"""

    agent = AutonomousPurchasingAgent()

    try:
        await agent.start(headless=False)  # Set True for headless mode

        # Define what to purchase
        task = PurchaseTask(
            product_description="Wireless Bluetooth headphones, noise cancelling",
            max_price=100.00,
            quantity=1,
            preferred_options={
                "color": "Black"
            }
        )

        # Start the agent
        success = await agent.purchase(
            task=task,
            start_url="https://www.amazon.com"
        )

        if success:
            print("\n🎉 Purchase completed successfully!")
        else:
            print("\n😕 Purchase was not completed")

    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
