# Autonomous Purchasing Agent

A **true reasoning agent** that can navigate any e-commerce website and complete purchases without hardcoded page knowledge.

## How This Is Different From Traditional Automation

### ❌ Traditional Approach (What You Had Before)
```python
# Hardcoded selectors for specific sites
driver.find_element(By.ID, "add-to-cart-button").click()
driver.find_element(By.CSS_SELECTOR, ".checkout-btn").click()
```

**Problems:**
- Breaks when websites change
- Need different code for each site
- Can't handle unexpected pop-ups or variations
- No understanding of what's on the page

### ✅ This Agent's Approach (True Reasoning)
```python
# Agent SEES the page and REASONS about what to do
observation = await agent.observe()      # Take screenshot + analyze DOM
thought = await agent.think(observation) # Ask LLM: "What should I do?"
await agent.act(thought, observation)    # Execute the decision
```

**Benefits:**
- Works on ANY website without modification
- Adapts to page changes automatically
- Handles unexpected situations
- Understands context and meaning

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     AGENT CONTROL LOOP                          │
│                                                                 │
│    ┌──────────┐      ┌──────────┐      ┌──────────┐            │
│    │ OBSERVE  │ ───▶ │  THINK   │ ───▶ │   ACT    │            │
│    │          │      │          │      │          │            │
│    │ • Screenshot    │ • Analyze │      │ • Click  │            │
│    │ • DOM tree      │ • Reason  │      │ • Type   │            │
│    │ • Elements      │ • Decide  │      │ • Scroll │            │
│    └──────────┘      └──────────┘      └──────────┘            │
│         ▲                                    │                  │
│         └────────────────────────────────────┘                  │
│                                                                 │
│    Supporting Systems:                                          │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│    │  Planner    │  │   Memory    │  │   Visual    │           │
│    │ (Goals)     │  │ (Context)   │  │  Locator    │           │
│    └─────────────┘  └─────────────┘  └─────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
cd purchasing_agent
pip install -r requirements.txt
playwright install chromium
```

### 2. Set Up API Key

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

### 3. Run the Agent

```python
import asyncio
from enhanced_agent import EnhancedPurchasingAgent, PurchaseTask

async def main():
    agent = EnhancedPurchasingAgent()
    await agent.start(headless=False)

    task = PurchaseTask(
        product_description="Wireless headphones",
        max_price=100.00
    )

    await agent.run(task, "https://www.amazon.com")
    await agent.stop()

asyncio.run(main())
```

## Key Components

### 1. Observation (Vision)
The agent captures:
- **Screenshot**: Visual representation of the page
- **Accessibility Tree**: Semantic structure of elements
- **Interactive Elements**: All clickable/typeable things with positions
- **Visible Text**: Content for context

### 2. Reasoning (Thinking)
The agent sends everything to Claude and asks:
- "What do I see on this page?"
- "Where am I in the purchase flow?"
- "What should I do next?"
- "Which element should I interact with?"

### 3. Action (Execution)
The agent can:
- **CLICK**: Click on elements (by index, text, or visual description)
- **TYPE**: Enter text into fields
- **SCROLL**: Navigate up/down the page
- **SELECT**: Choose dropdown options
- **NAVIGATE**: Go to URLs
- **WAIT**: Pause for loading
- **NEED_HELP**: Ask the human for assistance

### 4. Strategic Planner
Tracks high-level goals:
```
✅ 1. Search for the product
✅ 2. Find and select the right product
👉 3. Add to cart
⬜ 4. Proceed to checkout
⬜ 5. Enter shipping info
⬜ 6. Enter payment info
⬜ 7. Confirm order
```

### 5. Visual Element Locator
When DOM selectors fail, the agent can:
- Ask Claude to find elements visually in the screenshot
- Get precise coordinates for clicking
- Handle dynamic/unusual UI elements

## How Reasoning Works

Each step, the agent receives a prompt like:

```
## YOUR MISSION
Find and purchase: Wireless headphones
Maximum price: $100.00

## CURRENT PAGE
URL: https://amazon.com/dp/B08...
Title: Sony WH-1000XM4 Headphones

## INTERACTIVE ELEMENTS
[0] <button> Add to Cart (640, 450)
[1] <button> Buy Now (640, 510)
[2] <select> Color: Black (400, 300)

## YOUR TASK
Look at the screenshot and decide the next action.
```

And responds with structured reasoning:

```json
{
    "observation": "Product page for Sony headphones at $278",
    "current_stage": "product",
    "reasoning": "Price $278 exceeds max $100. Need to go back and find cheaper option.",
    "action": {
        "type": "CLICK",
        "target": "Back to search results"
    },
    "confidence": 0.85
}
```

## Advanced Usage

### Custom Preferred Options
```python
task = PurchaseTask(
    product_description="Running shoes",
    max_price=80.00,
    quantity=1,
    preferred_options={
        "size": "10",
        "color": "Blue",
        "width": "Wide"
    }
)
```

### Disable Purchase Confirmation
```python
task = PurchaseTask(
    product_description="USB Cable",
    max_price=15.00,
    require_confirmation=False  # Will complete without asking
)
```

### Access Agent Memory
```python
# During execution, the agent remembers:
agent.planner.memory.product_info      # Found product details
agent.planner.memory.prices_seen       # All prices encountered
agent.planner.memory.urls_visited      # Navigation history
agent.planner.memory.errors_encountered # Problems hit
```

## Safety Features

1. **Price Check**: Won't purchase if price exceeds max_price
2. **Confirmation**: Asks before final purchase (configurable)
3. **Action Limit**: Stops after 100 actions to prevent infinite loops
4. **Error Recovery**: Handles failures and asks for help when stuck
5. **No Secrets in Logs**: Payment info never logged

## Files Overview

| File | Purpose |
|------|---------|
| `agent.py` | Basic autonomous agent |
| `enhanced_agent.py` | Full-featured agent with all systems |
| `planner.py` | Strategic goal tracking and memory |
| `visual_locator.py` | Vision-based element finding |
| `requirements.txt` | Dependencies |

## Comparison: CNN vs LLM Approach

Your original project used a CNN to learn actions from demonstrations:

| Aspect | CNN (Original) | LLM (This Agent) |
|--------|----------------|------------------|
| Training | Needs gameplay data | Zero-shot, no training |
| Adaptability | Fixed to trained scenarios | Handles any page |
| Understanding | Pattern matching | Semantic reasoning |
| Explainability | Black box | Can explain decisions |
| Flexibility | New sites = new training | Works immediately |

## Limitations

- Requires Claude API access (costs money)
- Slower than hardcoded automation (~2-5 seconds per action)
- May struggle with complex CAPTCHAs
- Depends on Claude's vision accuracy

## Future Improvements

1. **Multi-modal reasoning**: Combine text + vision better
2. **Learning from corrections**: Remember when human helps
3. **Parallel browsing**: Compare prices across sites
4. **Receipt extraction**: Parse confirmation emails
5. **Price monitoring**: Wait for sales
