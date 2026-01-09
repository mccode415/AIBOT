"""
Enhanced Autonomous Purchasing Agent

This is the full-featured agent that combines:
- Visual reasoning (understanding any page dynamically)
- Strategic planning (multi-step goal tracking)
- Visual element location (find elements without selectors)
- Memory (remember information across pages)
- Error recovery (adapt when things go wrong)

This is a TRUE reasoning agent - no hardcoded page knowledge!
"""

import asyncio
import base64
import json
import os
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Page, Browser
import anthropic

from planner import StrategicPlanner, PurchaseStage, PurchasePlan
from visual_locator import VisualElementLocator, SetOfMarksLocator


@dataclass
class PurchaseTask:
    """What the agent should purchase"""
    product_description: str
    max_price: float
    quantity: int = 1
    preferred_options: Dict[str, str] = None
    require_confirmation: bool = True  # Ask before final purchase


class EnhancedPurchasingAgent:
    """
    A sophisticated autonomous agent that can navigate any e-commerce website.

    Architecture:
    ┌─────────────────────────────────────────────────────┐
    │                  AGENT CONTROL LOOP                 │
    │  ┌───────────┐   ┌───────────┐   ┌───────────┐     │
    │  │  OBSERVE  │ → │   THINK   │ → │    ACT    │     │
    │  │ (Vision)  │   │ (Reason)  │   │ (Execute) │     │
    │  └───────────┘   └───────────┘   └───────────┘     │
    │        ↑                               │            │
    │        └───────────────────────────────┘            │
    │                                                     │
    │  Supporting Systems:                                │
    │  • Strategic Planner (goal tracking)               │
    │  • Visual Locator (find elements visually)         │
    │  • Memory (persist info across pages)              │
    │  • Error Recovery (handle failures)                │
    └─────────────────────────────────────────────────────┘
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"

        # Browser
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

        # Supporting systems
        self.planner = StrategicPlanner(api_key=self.api_key)
        self.visual_locator = VisualElementLocator(api_key=self.api_key)
        self.som_locator = SetOfMarksLocator(api_key=self.api_key)

        # State
        self.action_history: List[Dict] = []
        self.current_task: Optional[PurchaseTask] = None
        self.max_actions = 100

    async def start(self, headless: bool = False):
        """Initialize browser"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=headless,
            slow_mo=100  # Slow down for visibility
        )
        context = await self.browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        self.page = await context.new_page()

    async def stop(self):
        """Cleanup"""
        if self.browser:
            await self.browser.close()

    # =========================================================
    # OBSERVE: Capture complete page state
    # =========================================================

    async def observe(self) -> Dict[str, Any]:
        """
        Capture everything we can about the current page.
        This forms the agent's "perception" of the world.
        """
        # Take screenshot
        screenshot = await self.page.screenshot()
        screenshot_b64 = base64.standard_b64encode(screenshot).decode()

        # Get page metadata
        url = self.page.url
        title = await self.page.title()

        # Get accessibility tree (semantic structure)
        try:
            a11y = await self.page.accessibility.snapshot()
            a11y_text = self._format_a11y(a11y)
        except:
            a11y_text = ""

        # Get interactive elements with positions
        elements = await self.page.evaluate("""
            () => {
                const results = [];
                const selectors = 'a, button, input, select, textarea, [role="button"], [onclick], [tabindex]:not([tabindex="-1"])';

                document.querySelectorAll(selectors).forEach((el, i) => {
                    const rect = el.getBoundingClientRect();
                    const styles = window.getComputedStyle(el);

                    if (rect.width > 0 && rect.height > 0 &&
                        styles.visibility !== 'hidden' &&
                        styles.display !== 'none' &&
                        rect.top < window.innerHeight &&
                        rect.bottom > 0) {

                        results.push({
                            index: i,
                            tag: el.tagName.toLowerCase(),
                            type: el.type || null,
                            text: (el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || '').trim().slice(0, 100),
                            id: el.id || null,
                            name: el.name || null,
                            class: el.className?.slice?.(0, 50) || null,
                            href: el.href || null,
                            bounds: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height),
                                centerX: Math.round(rect.x + rect.width/2),
                                centerY: Math.round(rect.y + rect.height/2)
                            }
                        });
                    }
                });
                return results.slice(0, 50);  // Limit to 50 elements
            }
        """)

        # Get visible text content
        visible_text = await self.page.evaluate("""
            () => {
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                let text = '';
                let node;
                while (node = walker.nextNode()) {
                    const content = node.textContent.trim();
                    if (content.length > 2) {
                        text += content + ' ';
                    }
                }
                return text.slice(0, 5000);
            }
        """)

        # Update memory
        self.planner.update_memory_from_page({"url": url})

        return {
            "screenshot_b64": screenshot_b64,
            "url": url,
            "title": title,
            "accessibility_tree": a11y_text,
            "interactive_elements": elements,
            "visible_text": visible_text,
            "viewport": {"width": 1280, "height": 800}
        }

    def _format_a11y(self, node: dict, depth: int = 0) -> str:
        """Format accessibility tree as text"""
        if not node or depth > 3:
            return ""

        important_roles = {"button", "link", "textbox", "combobox", "heading",
                          "img", "listitem", "checkbox", "radio", "menuitem"}

        role = node.get("role", "")
        name = node.get("name", "")

        result = ""
        if role in important_roles or name:
            indent = "  " * depth
            result = f"{indent}[{role}] {name}\n"

        for child in node.get("children", []):
            result += self._format_a11y(child, depth + 1)

        return result

    # =========================================================
    # THINK: Reason about what action to take
    # =========================================================

    async def think(self, observation: Dict) -> Dict:
        """
        The agent's reasoning process.
        Uses the LLM to analyze the situation and decide what to do.
        """

        # Get strategic context from planner
        strategic_context = self.planner.get_strategic_context()
        memory_context = self.planner.memory.to_context()

        # Build the reasoning prompt
        system_prompt = """You are an autonomous e-commerce purchasing agent. You can SEE webpages (via screenshots) and INTERACT with them (click, type, scroll).

YOUR CAPABILITIES:
1. CLICK - Click on any element (button, link, image, etc.)
2. TYPE - Type text into input fields
3. SCROLL - Scroll the page up or down
4. SELECT - Choose an option from a dropdown
5. WAIT - Wait for page to load
6. NAVIGATE - Go to a URL
7. DONE - Purchase is complete
8. NEED_HELP - Ask the human for assistance

DECISION FRAMEWORK:
1. Analyze what you see in the screenshot
2. Identify where you are in the purchase flow
3. Determine the next logical action
4. Be specific about which element to interact with
5. Explain your reasoning clearly

ELEMENT IDENTIFICATION:
When specifying which element to interact with, you can use:
- Element index from the list (e.g., "element[5]")
- Text content (e.g., "Add to Cart button")
- Visual description (e.g., "the blue button on the right")

OUTPUT FORMAT (JSON):
{
    "observation": "What I see on this page",
    "current_stage": "searching|browsing|product|cart|checkout|payment|confirmation",
    "reasoning": "Step by step thinking about what to do",
    "action": {
        "type": "CLICK|TYPE|SCROLL|SELECT|WAIT|NAVIGATE|DONE|NEED_HELP",
        "target": "element identifier or description",
        "value": "text to type or option to select (if applicable)"
    },
    "confidence": 0.0-1.0,
    "potential_issues": ["any concerns or things that could go wrong"]
}"""

        # Format task info
        task_info = ""
        if self.current_task:
            task_info = f"""
## YOUR MISSION
Find and purchase: {self.current_task.product_description}
Maximum price: ${self.current_task.max_price}
Quantity: {self.current_task.quantity}
Options: {json.dumps(self.current_task.preferred_options or {})}
"""

        # Format recent actions
        recent_actions = "\n".join([
            f"- {a['action']['type']}: {a['action'].get('target', 'N/A')}"
            for a in self.action_history[-5:]
        ]) or "No actions yet"

        user_prompt = f"""{task_info}

{strategic_context}

{memory_context}

## CURRENT PAGE
URL: {observation['url']}
Title: {observation['title']}

## PAGE STRUCTURE
{observation['accessibility_tree'][:2000]}

## INTERACTIVE ELEMENTS (index: [tag] text)
{self._format_elements(observation['interactive_elements'])}

## RECENT ACTIONS
{recent_actions}

## YOUR TASK
Look at the screenshot and page data. Decide the single best next action to take toward completing the purchase. Be specific and precise."""

        # Call the model with vision
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
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
                                "data": observation["screenshot_b64"]
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

        # Parse response
        return self._parse_thought(response.content[0].text)

    def _format_elements(self, elements: List[dict]) -> str:
        """Format elements list for the prompt"""
        lines = []
        for e in elements[:30]:
            text = e.get("text", "")[:40] or e.get("id", "") or e.get("name", "")
            tag = e.get("tag", "?")
            idx = e.get("index", "?")
            bounds = e.get("bounds", {})
            pos = f"({bounds.get('centerX', '?')},{bounds.get('centerY', '?')})"
            lines.append(f"  [{idx}] <{tag}> {text} {pos}")
        return "\n".join(lines) or "No interactive elements found"

    def _parse_thought(self, response_text: str) -> Dict:
        """Parse the model's reasoning response"""
        try:
            text = response_text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            return json.loads(text)
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Parse error: {e}")
            print(f"Raw: {response_text[:500]}")
            return {
                "observation": "Failed to parse response",
                "action": {"type": "WAIT"},
                "confidence": 0.1
            }

    # =========================================================
    # ACT: Execute the decided action
    # =========================================================

    async def act(self, thought: Dict, observation: Dict) -> bool:
        """
        Execute the action decided by the thinking step.
        Returns True if the task is complete.
        """
        action = thought.get("action", {})
        action_type = action.get("type", "WAIT").upper()
        target = action.get("target", "")
        value = action.get("value", "")

        print(f"  Action: {action_type} -> {target}")

        try:
            if action_type == "CLICK":
                await self._execute_click(target, observation)

            elif action_type == "TYPE":
                await self._execute_type(target, value, observation)

            elif action_type == "SCROLL":
                direction = -400 if value.lower() == "up" else 400
                await self.page.mouse.wheel(0, direction)

            elif action_type == "SELECT":
                await self._execute_select(target, value, observation)

            elif action_type == "WAIT":
                await asyncio.sleep(2)

            elif action_type == "NAVIGATE":
                await self.page.goto(target, wait_until="domcontentloaded", timeout=30000)

            elif action_type == "DONE":
                return True

            elif action_type == "NEED_HELP":
                print(f"\n🆘 AGENT NEEDS HELP: {thought.get('reasoning', 'Unknown reason')}")
                user_input = input("Please provide guidance: ")
                self.planner.memory.remember("user_guidance", user_input)

            # Wait for page to settle
            await asyncio.sleep(0.5)
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=5000)
            except:
                pass

            # Record action in history
            self.action_history.append(thought)
            return False

        except Exception as e:
            print(f"  Action failed: {e}")
            self.planner.record_error(str(e))
            return False

    async def _execute_click(self, target: str, observation: Dict):
        """
        Smart click that tries multiple strategies.
        Falls back to visual location if selectors fail.
        """
        elements = observation.get("interactive_elements", [])

        # Strategy 1: If target is an element index like "element[5]" or "[5]"
        if "[" in target and "]" in target:
            try:
                idx = int(target.split("[")[1].split("]")[0])
                for elem in elements:
                    if elem.get("index") == idx:
                        bounds = elem.get("bounds", {})
                        x, y = bounds.get("centerX", 0), bounds.get("centerY", 0)
                        if x and y:
                            await self.page.mouse.click(x, y)
                            return
            except (ValueError, IndexError):
                pass

        # Strategy 2: Try text-based locators
        text_strategies = [
            lambda: self.page.get_by_text(target, exact=False).first.click(timeout=2000),
            lambda: self.page.get_by_role("button", name=target).click(timeout=2000),
            lambda: self.page.get_by_role("link", name=target).click(timeout=2000),
            lambda: self.page.locator(f"text=/{target}/i").first.click(timeout=2000),
        ]

        for strategy in text_strategies:
            try:
                await strategy()
                return
            except:
                continue

        # Strategy 3: Try CSS selector
        try:
            await self.page.click(target, timeout=2000)
            return
        except:
            pass

        # Strategy 4: Use visual locator as fallback
        print("  Using visual locator...")
        location = await self.visual_locator.locate_element(
            observation["screenshot_b64"],
            target,
            (1280, 800)
        )
        if location and location.confidence > 0.5:
            await self.page.mouse.click(location.x, location.y)
            return

        raise Exception(f"Could not find element: {target}")

    async def _execute_type(self, target: str, value: str, observation: Dict):
        """Type text into a field"""
        elements = observation.get("interactive_elements", [])

        # Try to find input by various methods
        strategies = [
            lambda: self.page.get_by_placeholder(target).fill(value),
            lambda: self.page.get_by_label(target).fill(value),
            lambda: self.page.locator(f"input[name*='{target}' i]").fill(value),
            lambda: self.page.locator(f"input[id*='{target}' i]").fill(value),
        ]

        for strategy in strategies:
            try:
                await strategy()
                return
            except:
                continue

        # Find by element index
        if "[" in target and "]" in target:
            try:
                idx = int(target.split("[")[1].split("]")[0])
                for elem in elements:
                    if elem.get("index") == idx and elem.get("tag") in ["input", "textarea"]:
                        bounds = elem.get("bounds", {})
                        await self.page.mouse.click(bounds.get("centerX"), bounds.get("centerY"))
                        await self.page.keyboard.type(value)
                        return
            except:
                pass

        raise Exception(f"Could not find input: {target}")

    async def _execute_select(self, target: str, value: str, observation: Dict):
        """Select an option from a dropdown"""
        try:
            await self.page.select_option(target, label=value, timeout=3000)
        except:
            await self.page.get_by_label(target).select_option(label=value)

    # =========================================================
    # MAIN LOOP: The Agent's Lifecycle
    # =========================================================

    async def run(self, task: PurchaseTask, start_url: str) -> bool:
        """
        Main agent loop: OBSERVE → THINK → ACT → REPEAT

        This is the core "agentic" behavior - a continuous loop of
        perception, reasoning, and action until the goal is achieved.
        """
        self.current_task = task

        # Create strategic plan
        self.planner.create_initial_plan(task.product_description, start_url)

        # Navigate to starting point
        print(f"🌐 Navigating to {start_url}...")
        await self.page.goto(start_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        action_count = 0
        consecutive_failures = 0

        print("\n" + "="*60)
        print("🤖 AUTONOMOUS PURCHASING AGENT STARTED")
        print("="*60)

        while action_count < self.max_actions:
            action_count += 1
            print(f"\n--- Step {action_count} ---")

            # 1. OBSERVE
            print("👁️  Observing page...")
            observation = await self.observe()
            print(f"    URL: {observation['url'][:60]}...")

            # 2. THINK
            print("🧠 Reasoning...")
            thought = await self.think(observation)
            print(f"    Stage: {thought.get('current_stage', '?')}")
            print(f"    Reasoning: {thought.get('reasoning', '?')[:80]}...")
            print(f"    Confidence: {thought.get('confidence', 0):.2f}")

            # Check if done
            if thought.get("action", {}).get("type", "").upper() == "DONE":
                print("\n" + "="*60)
                print("✅ PURCHASE COMPLETE!")
                print("="*60)
                return True

            # Confirm before final purchase if required
            if task.require_confirmation:
                stage = thought.get("current_stage", "").lower()
                action_type = thought.get("action", {}).get("type", "").upper()
                if stage in ["payment", "confirmation"] and action_type == "CLICK":
                    target = thought.get("action", {}).get("target", "").lower()
                    if any(word in target for word in ["place order", "confirm", "buy", "purchase", "pay"]):
                        print("\n⚠️  CONFIRMATION REQUIRED:")
                        print(f"    About to: {target}")
                        confirm = input("    Proceed with purchase? (yes/no): ")
                        if confirm.lower() != "yes":
                            print("    Purchase cancelled by user")
                            return False

            # 3. ACT
            print("🎯 Executing action...")
            done = await self.act(thought, observation)

            if done:
                return True

            # Track failures
            if thought.get("confidence", 0) < 0.3:
                consecutive_failures += 1
                if consecutive_failures >= 5:
                    print("\n❌ Too many low-confidence actions. Stopping.")
                    return False
            else:
                consecutive_failures = 0

        print("\n⚠️  Maximum actions reached")
        return False


# ============================================================
# RUN THE AGENT
# ============================================================

async def main():
    """Example usage of the enhanced agent"""

    agent = EnhancedPurchasingAgent()

    try:
        # Start browser (visible mode for demo)
        await agent.start(headless=False)

        # Define the purchase task
        task = PurchaseTask(
            product_description="Wireless Bluetooth headphones with noise cancellation",
            max_price=150.00,
            quantity=1,
            preferred_options={"color": "black"},
            require_confirmation=True  # Will ask before final purchase
        )

        # Run the agent
        success = await agent.run(
            task=task,
            start_url="https://www.amazon.com"
        )

        if success:
            print("\n🎉 Mission accomplished!")
        else:
            print("\n😕 Mission incomplete")

    except KeyboardInterrupt:
        print("\n\n⏹️  Agent stopped by user")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
