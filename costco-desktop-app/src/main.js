const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const CostcoAgent = require('./agent');

let mainWindow;
let agent = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    },
    icon: path.join(__dirname, '../assets/icon.png')
  });

  mainWindow.loadFile(path.join(__dirname, 'index.html'));

  // Open DevTools in development
  if (process.env.NODE_ENV === 'development') {
    mainWindow.webContents.openDevTools();
  }
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', async () => {
  if (agent) {
    await agent.stop();
  }
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// IPC Handlers for agent communication
ipcMain.handle('agent:start', async (event, options) => {
  try {
    agent = new CostcoAgent(options);
    await agent.start();
    return { success: true };
  } catch (error) {
    return { success: false, error: error.message };
  }
});

ipcMain.handle('agent:stop', async () => {
  if (agent) {
    await agent.stop();
    agent = null;
  }
  return { success: true };
});

ipcMain.handle('agent:login', async (event, credentials) => {
  if (!agent) return { success: false, error: 'Agent not started' };
  return await agent.login(credentials.email, credentials.password);
});

ipcMain.handle('agent:search', async (event, query) => {
  if (!agent) return { success: false, error: 'Agent not started' };
  return await agent.searchProducts(query);
});

ipcMain.handle('agent:viewProduct', async (event, url) => {
  if (!agent) return { success: false, error: 'Agent not started' };
  return await agent.viewProduct(url);
});

ipcMain.handle('agent:addToCart', async (event, quantity) => {
  if (!agent) return { success: false, error: 'Agent not started' };
  return await agent.addToCart(quantity);
});

ipcMain.handle('agent:viewCart', async () => {
  if (!agent) return { success: false, error: 'Agent not started' };
  return await agent.viewCart();
});

ipcMain.handle('agent:applyPromo', async (event, code) => {
  if (!agent) return { success: false, error: 'Agent not started' };
  return await agent.applyPromoCode(code);
});

ipcMain.handle('agent:checkout', async () => {
  if (!agent) return { success: false, error: 'Agent not started' };
  return await agent.proceedToCheckout();
});

ipcMain.handle('agent:placeOrder', async (event, confirm) => {
  if (!agent) return { success: false, error: 'Agent not started' };
  return await agent.placeOrder(confirm);
});

ipcMain.handle('agent:screenshot', async () => {
  if (!agent) return { success: false, error: 'Agent not started' };
  return await agent.takeScreenshot();
});

// Shopping workflow handler
ipcMain.handle('agent:shop', async (event, options) => {
  if (!agent) {
    agent = new CostcoAgent({ headless: options.headless });
    await agent.start();
  }

  const results = [];
  const sendUpdate = (type, content, data = null) => {
    mainWindow.webContents.send('agent:update', { type, content, data });
    results.push({ type, content, data });
  };

  try {
    // Login (skip if browse-only)
    if (!options.browseOnly) {
      sendUpdate('thinking', 'Logging into Costco...');
      const loginResult = await agent.login(options.email, options.password);
      if (!loginResult.success) {
        sendUpdate('error', `Login failed: ${loginResult.error}`);
        return { success: false, results };
      }
      sendUpdate('result', 'Successfully logged in');
    } else {
      sendUpdate('result', 'Browse-only mode: skipping login');
    }

    // Search for each item
    for (const item of options.items) {
      sendUpdate('thinking', `Searching for: ${item}`);
      const searchResult = await agent.searchProducts(item);

      if (!searchResult.success || !searchResult.products?.length) {
        sendUpdate('error', `No results found for: ${item}`);
        continue;
      }

      sendUpdate('result', `Found ${searchResult.products.length} results for "${item}"`, searchResult);

      // View first product
      const firstProduct = searchResult.products[0];
      sendUpdate('thinking', `Selecting: ${firstProduct.title.substring(0, 50)}...`);

      const viewResult = await agent.viewProduct(firstProduct.url);
      if (!viewResult.success) {
        sendUpdate('error', `Failed to view product: ${viewResult.error}`);
        continue;
      }

      // Add to cart (skip if browse-only)
      if (options.browseOnly) {
        sendUpdate('result', `[Browse-only] Found: ${firstProduct.title.substring(0, 50)}... (${firstProduct.price})`);
      } else if (viewResult.canAddToCart) {
        sendUpdate('action', 'Adding to cart...');
        const addResult = await agent.addToCart(1);
        if (addResult.success) {
          sendUpdate('result', `Added to cart: ${firstProduct.title.substring(0, 50)}...`);
        } else {
          sendUpdate('error', `Failed to add to cart: ${addResult.error}`);
        }
      }
    }

    // View cart (skip if browse-only)
    if (options.browseOnly) {
      sendUpdate('result', 'Browse-only mode complete! Login to add items to cart.');
    } else {
      sendUpdate('thinking', 'Viewing cart...');
      const cartResult = await agent.viewCart();
      sendUpdate('result', `Cart has ${cartResult.itemCount || 0} items. Subtotal: ${cartResult.subtotal || 'N/A'}`, cartResult);

      // Apply promo code
      if (options.promoCode) {
        sendUpdate('action', `Applying promo code: ${options.promoCode}`);
        const promoResult = await agent.applyPromoCode(options.promoCode);
        if (promoResult.success) {
          sendUpdate('result', 'Promo code applied!');
        } else {
          sendUpdate('error', `Promo code failed: ${promoResult.error}`);
        }
      }
    }

    return { success: true, results };
  } catch (error) {
    sendUpdate('error', `Agent error: ${error.message}`);
    return { success: false, error: error.message, results };
  }
});
