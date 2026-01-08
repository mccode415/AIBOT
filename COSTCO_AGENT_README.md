# Costco Shopping Automation Agent

An AI-powered shopping automation agent for Costco.com with multiple interfaces (CLI, Web GUI, Desktop App).

## Features

- **Automated Shopping Flow**: Search products, add to cart, apply promos, checkout
- **Multiple Interfaces**: CLI, Streamlit Web GUI, Electron Desktop App
- **Cross-Platform**: Windows, Mac, Linux executables
- **CAPTCHA Handling**: Manual solving with notifications or automated via 2Captcha/Anti-Captcha
- **Smart Waiting**: Detects and waits for loading screens, spinners, overlays
- **Browse-Only Mode**: Test without logging in
- **Safety Checks**: Order placement requires explicit confirmation

---

## Project Structure

```
├── costco_agent/                 # Python agent module
│   ├── __init__.py
│   ├── agent.py                  # Main orchestrator
│   ├── browser.py                # Playwright browser automation
│   ├── config.py                 # Configuration & CSS selectors
│   └── tools.py                  # Tool definitions for Claude Agent SDK
│
├── costco-desktop-app/           # Electron desktop application
│   ├── package.json              # Dependencies & build scripts
│   ├── src/
│   │   ├── main.js               # Electron main process
│   │   ├── agent.js              # Playwright automation (JS)
│   │   ├── preload.js            # IPC bridge
│   │   ├── index.html            # UI markup
│   │   └── renderer.js           # UI logic
│   └── assets/                   # App icons
│
├── costco_app.py                 # Streamlit web GUI
├── run_costco_agent.py           # CLI entry point
└── requirements.txt              # Python dependencies
```

---

## Installation

### Python Agent (CLI & Streamlit)

```bash
# Install Python dependencies
pip install playwright streamlit

# Install browser
playwright install chromium
```

### Electron Desktop App

```bash
cd costco-desktop-app
npm install
```

---

## Usage

### Option 1: Command Line (Python)

```bash
# Browse-only mode (no login required)
python run_costco_agent.py --browse --items "kirkland olive oil" "toilet paper"

# Full shopping mode
export COSTCO_EMAIL="your@email.com"
export COSTCO_PASSWORD="your_password"
python run_costco_agent.py --items "olive oil" "paper towels"

# With promo code
python run_costco_agent.py --items "coffee" --promo "SAVE10"

# Headless browser (invisible)
python run_costco_agent.py --browse --items "snacks" --headless

# Interactive mode
python run_costco_agent.py --interactive

# Launch web GUI
python run_costco_agent.py --gui
```

### Option 2: Streamlit Web GUI

```bash
streamlit run costco_app.py
# Open http://localhost:8501
```

### Option 3: Electron Desktop App

```bash
cd costco-desktop-app

# Development mode
npm start

# Build executables
npm run build          # Current platform
npm run build:win      # Windows (.exe, .portable)
npm run build:mac      # Mac (.dmg, .zip)
npm run build:linux    # Linux (.AppImage, .deb)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER INTERFACES                             │
├─────────────────┬─────────────────┬─────────────────────────────┤
│  CLI (Python)   │  Streamlit GUI  │  Electron Desktop App       │
│  Terminal-based │  Web browser    │  Native Win/Mac/Linux       │
└────────┬────────┴────────┬────────┴──────────────┬──────────────┘
         │                 │                       │
         ▼                 ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                       AGENT LAYER                                │
│  • Shopping workflow orchestration                               │
│  • Tool execution (search, add to cart, checkout)                │
│  • State management                                              │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 BROWSER AUTOMATION (Playwright)                  │
│  • Navigate pages          • Smart waiting                       │
│  • Fill forms              • CAPTCHA detection                   │
│  • Click buttons           • Screenshot capture                  │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        COSTCO.COM                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Shopping Workflow

```
1. Launch Browser (Playwright/Chromium)
          │
          ▼
2. Login (skip if browse-only)
          │
          ├──→ CAPTCHA? → Notify user → Wait for manual solve
          │
          ▼
3. For each item:
   ├── Search for product
   ├── View product page
   └── Add to cart
          │
          ▼
4. View cart summary
          │
          ▼
5. Apply promo code (optional)
          │
          ▼
6. Proceed to checkout
          │
          ▼
7. Place order (requires confirm=true)
```

---

## CAPTCHA Handling

### Detection
The agent scans for:
- reCAPTCHA iframes (`iframe[src*="recaptcha"]`)
- hCaptcha iframes (`iframe[src*="hcaptcha"]`)
- Generic captcha containers (`.g-recaptcha`, `.h-captcha`)
- Text indicators ("captcha", "robot", "verify you are human")

### Manual Solving (Default)
1. Agent detects CAPTCHA
2. Takes screenshot
3. Shows desktop notification (Windows/Mac/Linux)
4. Plays 3-beep audio alert
5. UI shows pulsing yellow alert
6. Agent polls every 2 seconds (up to 2 minutes)
7. Once solved, agent continues automatically

### Automated Solving (Optional)
```javascript
// 2Captcha (~$3 per 1000 solves)
await agent.handleCaptcha({
  solverService: '2captcha',
  solverApiKey: 'YOUR_API_KEY'
});

// Anti-Captcha
await agent.handleCaptcha({
  solverService: 'anticaptcha',
  solverApiKey: 'YOUR_API_KEY'
});
```

---

## Smart Waiting

The agent automatically handles loading states:

| Element Type | CSS Selectors |
|--------------|---------------|
| Spinners | `.loading`, `.spinner`, `[class*="loading"]` |
| Overlays | `.overlay`, `.loading-overlay` |
| Skeletons | `[class*="skeleton"]`, `[class*="placeholder"]` |
| Progress bars | `[role="progressbar"]`, `.progress` |

```javascript
// Waits for all loading indicators to disappear
await agent.smartWait({ timeout: 30000 });
```

---

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `COSTCO_EMAIL` | Costco account email |
| `COSTCO_PASSWORD` | Costco account password |
| `HEADLESS` | Run browser invisibly (`true`/`false`) |

### Python Config (`costco_agent/config.py`)

```python
@dataclass
class CostcoConfig:
    email: str                    # From COSTCO_EMAIL
    password: str                 # From COSTCO_PASSWORD
    headless: bool = False        # Visible browser by default
    browser_timeout: int = 30000  # 30 second timeout
    slow_mo: int = 100            # 100ms between actions
    save_screenshots: bool = True
    screenshot_dir: str = "screenshots"
```

### Electron Config (`costco-desktop-app/src/agent.js`)

```javascript
const agent = new CostcoAgent({
  headless: false,      // Visible browser
  slowMo: 100,          // 100ms between actions
  screenshotDir: './screenshots'
});
```

---

## API Reference

### Python Agent

```python
from costco_agent import CostcoShoppingAgent, CostcoConfig

# Initialize
config = CostcoConfig.from_env()
agent = CostcoShoppingAgent(config, browse_only=False)

# Use as context manager
async with agent:
    # Shop for items
    async for message in agent.shop(
        items=["olive oil", "paper towels"],
        promo_code="SAVE10",
        auto_checkout=False
    ):
        print(f"{message.type}: {message.content}")

    # Or execute individual tools
    result = await agent.execute_tool("costco_search", {"query": "coffee"})
    result = await agent.execute_tool("costco_add_to_cart", {"quantity": 2})
    result = await agent.execute_tool("costco_view_cart", {})
```

### Available Tools

| Tool Name | Description | Parameters |
|-----------|-------------|------------|
| `costco_login` | Log into Costco | None (uses env vars) |
| `costco_search` | Search for products | `query`, `max_results` |
| `costco_view_product` | View product page | `product_url` |
| `costco_add_to_cart` | Add to cart | `quantity` |
| `costco_view_cart` | View cart contents | None |
| `costco_apply_promo` | Apply promo code | `code` |
| `costco_checkout` | Proceed to checkout | None |
| `costco_place_order` | Complete purchase | `confirm` (must be true) |
| `costco_screenshot` | Take screenshot | `name` |

### JavaScript Agent (Electron)

```javascript
const CostcoAgent = require('./agent');

const agent = new CostcoAgent({ headless: false });
await agent.start();

// Individual operations
await agent.login(email, password);
const results = await agent.searchProducts("olive oil");
await agent.viewProduct(results.products[0].url);
await agent.addToCart(1);
await agent.viewCart();
await agent.applyPromoCode("SAVE10");
await agent.proceedToCheckout();
await agent.placeOrder(true); // confirm=true required

await agent.stop();
```

---

## Electron IPC API

Communication between UI (renderer) and backend (main):

```javascript
// From renderer.js (UI)
window.api.shop({
  items: ["olive oil"],
  browseOnly: true,
  headless: false,
  email: "user@email.com",
  password: "password",
  promoCode: "SAVE10"
});

// Listen for updates
window.api.onAgentUpdate((data) => {
  // data.type: 'thinking' | 'action' | 'result' | 'error' | 'captcha'
  // data.content: string message
  // data.data: optional extra data
});
```

---

## CSS Selectors Reference

Located in `config.py` (Python) and `agent.js` (JS):

```javascript
const SELECTORS = {
  // Login
  loginEmail: '#logonId',
  loginPassword: '#logonPassword',
  loginButton: "input[type='submit'][value='Sign In']",

  // Search
  searchInput: '#search-field',
  productCard: '.product-tile',
  productTitle: '.description a',
  productPrice: '.price',

  // Product page
  addToCartButton: '#add-to-cart-btn',
  quantityInput: '#quantity',

  // Cart
  cartItems: '.cart-item',
  cartSubtotal: '.order-subtotal',
  proceedToCheckout: '#shopCartCheckoutSubmitButton',
  promoCodeInput: '#promoCode',
  applyPromoButton: '#applyPromoCodeButton',

  // Checkout
  placeOrderButton: '#placeOrderButton',
  orderTotal: '.order-total',

  // Loading states
  loadingSpinner: '.loading, .spinner, [class*="loading"]',
  loadingOverlay: '.overlay, .loading-overlay',
  skeleton: '[class*="skeleton"], [class*="placeholder"]',

  // CAPTCHA
  captchaFrame: 'iframe[src*="captcha"], iframe[src*="recaptcha"]',
  captchaContainer: '.g-recaptcha, .h-captcha, [class*="captcha"]'
};
```

---

## Build Outputs

### Electron Desktop App

| Platform | Command | Output |
|----------|---------|--------|
| Windows | `npm run build:win` | `dist/Costco Shopping Agent.exe` |
| Mac | `npm run build:mac` | `dist/Costco Shopping Agent.dmg` |
| Linux | `npm run build:linux` | `dist/Costco Shopping Agent.AppImage` |

---

## Security Considerations

| Concern | Implementation |
|---------|----------------|
| Credentials | Stored in environment variables, never in code |
| Order placement | Requires explicit `confirm=true` parameter |
| Screenshots | Saved locally only, not transmitted |
| Headless mode | Optional - browser visible by default for transparency |

---

## Troubleshooting

### CAPTCHA keeps appearing
- Slow down automation: increase `slowMo` to 200-500ms
- Use residential proxies
- Save/restore browser cookies between sessions
- Try at different times of day

### Elements not found
- Update CSS selectors in `config.py` / `agent.js`
- Costco may have changed their HTML structure
- Take screenshots to debug: `await agent.takeScreenshot("debug")`

### Timeout errors
- Increase `browser_timeout` in config
- Check internet connection
- Costco may be experiencing high load

---

## Dependencies

### Python
```
playwright>=1.40.0
streamlit>=1.28.0
```

### Node.js (Electron)
```json
{
  "dependencies": {
    "playwright": "^1.40.0"
  },
  "devDependencies": {
    "electron": "^28.0.0",
    "electron-builder": "^24.9.0"
  }
}
```

---

## License

MIT

---

## Disclaimer

This tool is for educational and personal use only. Automated purchasing may violate Costco's Terms of Service. Use responsibly and at your own risk.
