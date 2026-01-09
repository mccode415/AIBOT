"""
Visual Element Locator

Uses vision models to locate UI elements when traditional selectors fail.
This enables truly dynamic page understanding without any hardcoded selectors.
"""

import base64
import json
from dataclasses import dataclass
from typing import List, Optional, Tuple
import anthropic
import os


@dataclass
class ElementLocation:
    """A located element with its bounding box"""
    description: str
    x: int  # Center x coordinate
    y: int  # Center y coordinate
    width: int
    height: int
    confidence: float
    element_type: str  # button, input, link, etc.

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x, self.y)

    @property
    def click_point(self) -> Tuple[int, int]:
        """Return the best point to click"""
        return self.center


class VisualElementLocator:
    """
    Uses vision models to find UI elements in screenshots.

    This is the fallback when CSS/XPath selectors don't work.
    It can find elements by:
    - Visual description ("the blue Add to Cart button")
    - Semantic meaning ("the quantity input field")
    - Relative position ("the button below the price")
    """

    def __init__(self, api_key: str = None):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"

    async def locate_element(
        self,
        screenshot_b64: str,
        element_description: str,
        viewport_size: Tuple[int, int] = (1280, 800)
    ) -> Optional[ElementLocation]:
        """
        Find an element in the screenshot by description.

        Args:
            screenshot_b64: Base64 encoded PNG screenshot
            element_description: Natural language description of what to find
            viewport_size: Width and height of the viewport

        Returns:
            ElementLocation with coordinates, or None if not found
        """

        prompt = f"""Find the UI element matching this description: "{element_description}"

The screenshot is {viewport_size[0]}x{viewport_size[1]} pixels.

If you find the element, respond with JSON:
{{
    "found": true,
    "element": {{
        "description": "what you found",
        "x": <center x coordinate in pixels>,
        "y": <center y coordinate in pixels>,
        "width": <approximate width>,
        "height": <approximate height>,
        "element_type": "button|input|link|image|text|other",
        "confidence": 0.0-1.0
    }}
}}

If you cannot find it:
{{
    "found": false,
    "reason": "why not found",
    "suggestions": ["alternative elements that might work"]
}}

Be precise with coordinates - they must be accurate for clicking to work."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        try:
            text = response.content[0].text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)

            if data.get("found"):
                elem = data["element"]
                return ElementLocation(
                    description=elem.get("description", element_description),
                    x=int(elem.get("x", 0)),
                    y=int(elem.get("y", 0)),
                    width=int(elem.get("width", 100)),
                    height=int(elem.get("height", 30)),
                    confidence=float(elem.get("confidence", 0.5)),
                    element_type=elem.get("element_type", "unknown")
                )
            else:
                print(f"Element not found: {data.get('reason')}")
                return None

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to parse element location: {e}")
            return None

    async def locate_all_interactive(
        self,
        screenshot_b64: str,
        viewport_size: Tuple[int, int] = (1280, 800)
    ) -> List[ElementLocation]:
        """
        Find all interactive elements in the screenshot.
        Useful for understanding page structure.
        """

        prompt = f"""Identify ALL interactive elements in this screenshot.
The screenshot is {viewport_size[0]}x{viewport_size[1]} pixels.

For each element, provide:
- Type (button, link, input, dropdown, checkbox, etc.)
- Purpose (what it does or is for)
- Position (x, y coordinates of center)
- Size (approximate width and height)

Respond with JSON:
{{
    "elements": [
        {{
            "description": "what this element is/does",
            "element_type": "button|input|link|dropdown|checkbox|other",
            "x": <center x>,
            "y": <center y>,
            "width": <width>,
            "height": <height>,
            "importance": "high|medium|low"
        }}
    ],
    "page_summary": "brief description of what this page is for"
}}

Focus on elements that can be clicked, typed into, or interacted with.
Order by importance (most important first)."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        try:
            text = response.content[0].text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]

            data = json.loads(text)
            elements = []

            for elem in data.get("elements", []):
                elements.append(ElementLocation(
                    description=elem.get("description", "Unknown"),
                    x=int(elem.get("x", 0)),
                    y=int(elem.get("y", 0)),
                    width=int(elem.get("width", 100)),
                    height=int(elem.get("height", 30)),
                    confidence=1.0 if elem.get("importance") == "high" else 0.7,
                    element_type=elem.get("element_type", "unknown")
                ))

            return elements

        except (json.JSONDecodeError, KeyError) as e:
            print(f"Failed to parse elements: {e}")
            return []

    async def find_best_match(
        self,
        screenshot_b64: str,
        intent: str,
        candidates: List[dict],
        viewport_size: Tuple[int, int] = (1280, 800)
    ) -> Optional[int]:
        """
        Given a list of candidate elements from the DOM, use vision
        to determine which one best matches the intent.

        Args:
            screenshot_b64: Screenshot of the page
            intent: What we're trying to do (e.g., "add item to cart")
            candidates: List of elements with their properties
            viewport_size: Viewport dimensions

        Returns:
            Index of the best matching candidate, or None
        """

        candidates_text = "\n".join([
            f"{i}. [{c.get('tag')}] {c.get('text', '')[:50]} (id={c.get('id')}, class={c.get('class', '')[:30]})"
            for i, c in enumerate(candidates[:15])
        ])

        prompt = f"""I want to: "{intent}"

Here are interactive elements found on the page:
{candidates_text}

Looking at the screenshot, which element (by index number) is the best choice to accomplish this intent?

Consider:
- Visual prominence
- Label/text match
- Position on page
- Element type appropriateness

Respond with JSON:
{{
    "best_index": <number or null if none suitable>,
    "reasoning": "why this element is the best choice",
    "confidence": 0.0-1.0
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": screenshot_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        try:
            text = response.content[0].text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]

            data = json.loads(text)
            idx = data.get("best_index")
            if idx is not None and 0 <= idx < len(candidates):
                return idx
            return None

        except (json.JSONDecodeError, KeyError):
            return None


class SetOfMarksLocator:
    """
    Alternative approach: Overlay numbered markers on the screenshot
    and let the model pick by number.

    This is more accurate because the model can directly associate
    visual elements with reference numbers.
    """

    def __init__(self, api_key: str = None):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    async def create_marked_screenshot(
        self,
        page,  # Playwright page
        elements: List[dict]
    ) -> Tuple[str, List[dict]]:
        """
        Create a screenshot with numbered markers overlaid on elements.

        Args:
            page: Playwright page object
            elements: List of elements with bounding box info

        Returns:
            Tuple of (base64 screenshot, list of numbered elements)
        """

        # Inject markers using JavaScript
        marked_elements = []
        for i, elem in enumerate(elements[:30]):  # Limit to 30 elements
            bounds = elem.get("bounds", {})
            if bounds.get("width", 0) > 0:
                # Add a numbered overlay
                await page.evaluate(f"""
                    (function() {{
                        const marker = document.createElement('div');
                        marker.id = 'ai-marker-{i}';
                        marker.style.cssText = `
                            position: fixed;
                            left: {bounds['x']}px;
                            top: {bounds['y']}px;
                            width: 20px;
                            height: 20px;
                            background: red;
                            color: white;
                            font-size: 12px;
                            font-weight: bold;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            border-radius: 50%;
                            z-index: 999999;
                            pointer-events: none;
                        `;
                        marker.textContent = '{i}';
                        document.body.appendChild(marker);
                    }})();
                """)
                marked_elements.append({**elem, "marker_id": i})

        # Take screenshot with markers
        screenshot_bytes = await page.screenshot()
        screenshot_b64 = base64.standard_b64encode(screenshot_bytes).decode()

        # Clean up markers
        for i in range(len(marked_elements)):
            await page.evaluate(f"""
                document.getElementById('ai-marker-{i}')?.remove();
            """)

        return screenshot_b64, marked_elements

    async def select_element(
        self,
        marked_screenshot_b64: str,
        marked_elements: List[dict],
        task_description: str
    ) -> Optional[dict]:
        """
        Show the marked screenshot to the model and let it pick an element.
        """

        elements_desc = "\n".join([
            f"[{e['marker_id']}] {e.get('tag', 'unknown')} - {e.get('text', '')[:40]}"
            for e in marked_elements
        ])

        prompt = f"""The screenshot has red numbered markers on interactive elements.

Task: {task_description}

Available elements:
{elements_desc}

Which numbered marker should I click to accomplish this task?

Respond with JSON:
{{
    "marker_id": <number>,
    "reasoning": "why this element"
}}"""

        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": marked_screenshot_b64
                            }
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ]
                }
            ]
        )

        try:
            text = response.content[0].text
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]

            data = json.loads(text)
            marker_id = data.get("marker_id")

            for elem in marked_elements:
                if elem.get("marker_id") == marker_id:
                    return elem

            return None

        except (json.JSONDecodeError, KeyError):
            return None
