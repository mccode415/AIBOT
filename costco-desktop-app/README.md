# Costco Shopping Agent - Desktop App

Cross-platform desktop application for automating Costco shopping.

Built with **Electron** + **Playwright** - compiles to native apps for Windows, Mac, and Linux.

## Quick Start

```bash
# Install dependencies
npm install

# Run in development mode
npm start

# Build for your platform
npm run build
```

## Build for Specific Platforms

```bash
# Windows
npm run build:win

# Mac
npm run build:mac

# Linux
npm run build:linux
```

## Features

- **Browse-only mode**: Test without logging in
- **Full shopping mode**: Login, add to cart, checkout
- **Cross-platform**: Windows, Mac, Linux
- **Visual browser**: Watch the agent work (or run headless)
- **Activity log**: See every step in real-time

## Project Structure

```
costco-desktop-app/
├── package.json          # Dependencies & build config
├── src/
│   ├── main.js           # Electron main process
│   ├── preload.js        # IPC bridge
│   ├── agent.js          # Playwright automation
│   ├── index.html        # UI
│   └── renderer.js       # UI logic
├── assets/               # App icons
└── dist/                 # Built executables
```

## Requirements

- Node.js 18+
- npm or yarn

## How It Works

1. **Electron** creates the native desktop window
2. **Playwright** controls a Chromium browser
3. The agent automates Costco.com:
   - Searches for products
   - Views product pages
   - Adds items to cart
   - Applies promo codes
   - Proceeds to checkout

## Security Notes

- Credentials are never stored - enter them each session
- Order placement requires explicit confirmation
- Screenshots saved locally for debugging

## License

MIT
