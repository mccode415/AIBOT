"""
Strategic Planner for the Purchasing Agent

This module provides high-level planning capabilities:
- Breaks down complex purchases into sub-goals
- Tracks progress through checkout flow
- Adapts plans when unexpected situations occur
- Maintains memory across page transitions
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
import anthropic
import os


class PurchaseStage(Enum):
    """Stages in a typical e-commerce purchase flow"""
    SEARCHING = "searching"           # Looking for the product
    BROWSING = "browsing"             # Viewing search results
    PRODUCT_PAGE = "product_page"     # On product detail page
    SELECTING_OPTIONS = "selecting"   # Choosing size, color, etc.
    ADDING_TO_CART = "adding"         # Adding item to cart
    VIEWING_CART = "cart"             # Reviewing cart
    CHECKOUT_START = "checkout"       # Beginning checkout
    SHIPPING = "shipping"             # Entering shipping info
    PAYMENT = "payment"               # Entering payment info
    REVIEW = "review"                 # Final order review
    CONFIRMATION = "confirmation"     # Order confirmed
    FAILED = "failed"                 # Something went wrong
    BLOCKED = "blocked"               # Need human intervention


@dataclass
class Goal:
    """A sub-goal in the purchase process"""
    description: str
    stage: PurchaseStage
    success_indicators: List[str]  # What to look for to confirm completion
    failure_indicators: List[str]  # What indicates this goal failed
    completed: bool = False
    attempts: int = 0
    max_attempts: int = 5


@dataclass
class PurchasePlan:
    """A strategic plan for completing a purchase"""
    goals: List[Goal] = field(default_factory=list)
    current_goal_index: int = 0
    notes: List[str] = field(default_factory=list)  # Observations during execution

    @property
    def current_goal(self) -> Optional[Goal]:
        if 0 <= self.current_goal_index < len(self.goals):
            return self.goals[self.current_goal_index]
        return None

    def advance(self) -> bool:
        """Move to next goal. Returns True if there are more goals."""
        if self.current_goal:
            self.current_goal.completed = True
        self.current_goal_index += 1
        return self.current_goal_index < len(self.goals)


class AgentMemory:
    """
    Persistent memory for the agent to remember important information
    across page transitions and reasoning steps.
    """

    def __init__(self):
        self.product_info: Dict[str, Any] = {}  # Found product details
        self.prices_seen: List[float] = []       # Prices encountered
        self.urls_visited: List[str] = []        # Breadcrumb trail
        self.errors_encountered: List[str] = []  # Problems hit
        self.decisions_made: List[Dict] = []     # Key decisions
        self.form_data_entered: Dict[str, bool] = {}  # Track form progress
        self.cart_contents: List[Dict] = []      # Items in cart

    def remember(self, key: str, value: Any):
        """Store a piece of information"""
        self.decisions_made.append({"key": key, "value": value})

    def recall(self, key: str) -> Optional[Any]:
        """Retrieve stored information"""
        for decision in reversed(self.decisions_made):
            if decision["key"] == key:
                return decision["value"]
        return None

    def to_context(self) -> str:
        """Format memory as context for the LLM"""
        return f"""## AGENT MEMORY
Product Found: {json.dumps(self.product_info)}
Prices Seen: {self.prices_seen}
Recent URLs: {self.urls_visited[-5:]}
Errors: {self.errors_encountered[-3:]}
Cart: {self.cart_contents}
Forms Completed: {list(self.form_data_entered.keys())}
"""


class StrategicPlanner:
    """
    High-level planner that creates and adapts purchase strategies.

    Instead of just reacting to each page, the planner:
    1. Creates a multi-step plan upfront
    2. Tracks progress toward goals
    3. Detects when plans need adjustment
    4. Provides strategic context to the action-level agent
    """

    def __init__(self, api_key: str = None):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
        self.memory = AgentMemory()
        self.current_plan: Optional[PurchasePlan] = None

    def create_initial_plan(self, product_description: str, website: str) -> PurchasePlan:
        """
        Create a strategic plan for the purchase.
        This is called once at the start.
        """

        # Standard e-commerce plan (can be adapted per-site)
        plan = PurchasePlan(
            goals=[
                Goal(
                    description="Search for the product",
                    stage=PurchaseStage.SEARCHING,
                    success_indicators=["search results appear", "product listings visible"],
                    failure_indicators=["no results found", "error page"]
                ),
                Goal(
                    description="Find and select the right product",
                    stage=PurchaseStage.BROWSING,
                    success_indicators=["product page loaded", "product title matches"],
                    failure_indicators=["out of stock", "wrong product category"]
                ),
                Goal(
                    description="Configure product options and add to cart",
                    stage=PurchaseStage.ADDING_TO_CART,
                    success_indicators=["added to cart confirmation", "cart count increased"],
                    failure_indicators=["out of stock", "option unavailable"]
                ),
                Goal(
                    description="Proceed to checkout",
                    stage=PurchaseStage.CHECKOUT_START,
                    success_indicators=["checkout page loaded", "shipping form visible"],
                    failure_indicators=["login required", "cart expired"]
                ),
                Goal(
                    description="Enter shipping information",
                    stage=PurchaseStage.SHIPPING,
                    success_indicators=["shipping method selected", "proceed to payment available"],
                    failure_indicators=["address validation error", "shipping unavailable"]
                ),
                Goal(
                    description="Enter payment information",
                    stage=PurchaseStage.PAYMENT,
                    success_indicators=["payment accepted", "review order page"],
                    failure_indicators=["payment declined", "invalid card"]
                ),
                Goal(
                    description="Review and confirm order",
                    stage=PurchaseStage.REVIEW,
                    success_indicators=["order confirmed", "confirmation number received"],
                    failure_indicators=["price changed", "item unavailable"]
                )
            ]
        )

        self.current_plan = plan
        return plan

    async def analyze_situation(self, page_state: Dict, action_history: List) -> Dict:
        """
        High-level situation analysis.
        Determines where we are in the plan and if adjustments are needed.
        """

        prompt = f"""Analyze the current shopping situation and provide strategic guidance.

## CURRENT PLAN
{self._format_plan()}

## AGENT MEMORY
{self.memory.to_context()}

## CURRENT PAGE
URL: {page_state.get('url', 'Unknown')}
Title: {page_state.get('title', 'Unknown')}

## PAGE STRUCTURE
{page_state.get('accessibility_tree', '')[:2000]}

## RECENT ACTIONS
{self._format_actions(action_history)}

## ANALYSIS REQUIRED
1. What stage of the purchase flow are we currently in?
2. Is our current goal complete? What evidence supports this?
3. Are there any obstacles or unexpected situations?
4. Should we adjust our strategy?
5. What's the most important thing to focus on next?

Respond in JSON:
{{
    "current_stage": "stage name",
    "goal_status": "in_progress|completed|blocked|failed",
    "completion_evidence": "what indicates goal is done",
    "obstacles": ["list of problems noticed"],
    "strategy_adjustment": "none|skip_step|retry|ask_human|abort",
    "focus_next": "what to prioritize",
    "confidence": 0.0-1.0
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": page_state.get("screenshot_b64", "")
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
            return json.loads(text)
        except:
            return {"goal_status": "in_progress", "strategy_adjustment": "none"}

    def _format_plan(self) -> str:
        """Format the current plan for display"""
        if not self.current_plan:
            return "No plan created"

        lines = []
        for i, goal in enumerate(self.current_plan.goals):
            status = "✅" if goal.completed else ("👉" if i == self.current_plan.current_goal_index else "⬜")
            lines.append(f"{status} {i+1}. {goal.description} ({goal.stage.value})")

        return "\n".join(lines)

    def _format_actions(self, actions: List) -> str:
        """Format recent actions"""
        if not actions:
            return "No actions taken yet"
        return "\n".join([
            f"- {a.action_type.value}: {a.target}" for a in actions[-5:]
        ])

    def get_strategic_context(self) -> str:
        """
        Get strategic context to augment the action-level agent's decisions.
        This helps the agent make better decisions by knowing the bigger picture.
        """

        if not self.current_plan:
            return ""

        current = self.current_plan.current_goal

        return f"""
## STRATEGIC CONTEXT
Current Goal: {current.description if current else 'None'}
Goal Stage: {current.stage.value if current else 'Unknown'}
Look For: {', '.join(current.success_indicators) if current else 'N/A'}
Avoid: {', '.join(current.failure_indicators) if current else 'N/A'}
Attempts on this goal: {current.attempts if current else 0}/{current.max_attempts if current else 5}

Plan Progress:
{self._format_plan()}
"""

    def update_memory_from_page(self, page_state: Dict):
        """Extract and remember important information from page"""
        url = page_state.get("url", "")
        if url and (not self.memory.urls_visited or url != self.memory.urls_visited[-1]):
            self.memory.urls_visited.append(url)

    def record_error(self, error: str):
        """Record an error for future reference"""
        self.memory.errors_encountered.append(error)

    def record_price(self, price: float):
        """Record a price we've seen"""
        self.memory.prices_seen.append(price)

    def advance_goal(self):
        """Mark current goal complete and move to next"""
        if self.current_plan:
            self.current_plan.advance()

    def retry_goal(self):
        """Increment attempt counter for current goal"""
        if self.current_plan and self.current_plan.current_goal:
            self.current_plan.current_goal.attempts += 1
            return self.current_plan.current_goal.attempts < self.current_plan.current_goal.max_attempts
        return False
