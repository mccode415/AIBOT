const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

// CSS Selectors for Costco website
const SELECTORS = {
  // Login
  loginEmail: '#logonId',
  loginPassword: '#logonPassword',
  loginButton: "input[type='submit'][value='Sign In']",

  // Search
  searchInput: '#search-field',
  searchButton: "button[aria-label='Search']",
  productCard: '.product-tile',
  productTitle: '.description a',
  productPrice: '.price',

  // Product page
  addToCartButton: '#add-to-cart-btn',
  quantityInput: '#quantity',

  // Cart
  cartItems: '.cart-item',
  cartItemName: '.item-name',
  cartItemPrice: '.item-price',
  cartItemQuantity: '.quantity-input',
  cartSubtotal: '.order-subtotal',
  proceedToCheckout: '#shopCartCheckoutSubmitButton',
  promoCodeInput: '#promoCode',
  applyPromoButton: '#applyPromoCodeButton',

  // Checkout
  placeOrderButton: '#placeOrderButton',
  orderTotal: '.order-total',

  // General
  modalClose: '.modal-close, .close-button, [aria-label="Close"]',
  errorMessage: '.error-message, .alert-error',

  // Loading/Wait screens
  loadingSpinner: '.loading, .spinner, .loader, [class*="loading"], [class*="spinner"]',
  loadingOverlay: '.overlay, .loading-overlay, [class*="overlay"]',
  skeleton: '[class*="skeleton"], [class*="placeholder"]',
  progressBar: '[role="progressbar"], .progress',

  // CAPTCHA selectors (common patterns)
  captchaFrame: 'iframe[src*="captcha"], iframe[src*="recaptcha"], iframe[src*="hcaptcha"]',
  captchaContainer: '.g-recaptcha, .h-captcha, [class*="captcha"]',
  captchaChallenge: '#captcha, [id*="captcha"]'
};

const URLS = {
  base: 'https://www.costco.com',
  login: 'https://www.costco.com/LogonForm',
  cart: 'https://www.costco.com/CheckoutCartView'
};

class CostcoAgent {
  constructor(options = {}) {
    this.options = {
      headless: options.headless ?? false,
      slowMo: options.slowMo ?? 100,
      screenshotDir: options.screenshotDir ?? './screenshots',
      ...options
    };
    this.browser = null;
    this.context = null;
    this.page = null;
    this.isLoggedIn = false;
  }

  async start() {
    this.browser = await chromium.launch({
      headless: this.options.headless,
      slowMo: this.options.slowMo
    });

    this.context = await this.browser.newContext({
      viewport: { width: 1920, height: 1080 },
      userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    });

    this.page = await this.context.newPage();
    this.page.setDefaultTimeout(30000);

    // Create screenshot directory
    if (!fs.existsSync(this.options.screenshotDir)) {
      fs.mkdirSync(this.options.screenshotDir, { recursive: true });
    }

    return { success: true };
  }

  async stop() {
    if (this.page) await this.page.close();
    if (this.context) await this.context.close();
    if (this.browser) await this.browser.close();
    this.browser = null;
    this.context = null;
    this.page = null;
  }

  async takeScreenshot(name = 'screenshot') {
    if (!this.page) return { success: false, error: 'No page available' };

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const filename = path.join(this.options.screenshotDir, `${name}_${timestamp}.png`);
    await this.page.screenshot({ path: filename });
    return { success: true, path: filename };
  }

  async closeModals() {
    try {
      const modal = this.page.locator(SELECTORS.modalClose);
      if (await modal.count() > 0) {
        await modal.first().click();
        await this.page.waitForTimeout(500);
      }
    } catch (e) {
      // No modal to close
    }
  }

  /**
   * Wait for loading screens to disappear
   * @param {number} timeout - Max time to wait in ms
   * @returns {Promise<{success: boolean, waited: boolean}>}
   */
  async waitForLoadingScreens(timeout = 30000) {
    const startTime = Date.now();
    let waited = false;

    try {
      // Wait for spinners to disappear
      const spinner = this.page.locator(SELECTORS.loadingSpinner);
      if (await spinner.count() > 0) {
        waited = true;
        await spinner.first().waitFor({ state: 'hidden', timeout });
      }

      // Wait for overlays to disappear
      const overlay = this.page.locator(SELECTORS.loadingOverlay);
      if (await overlay.count() > 0) {
        const remainingTime = timeout - (Date.now() - startTime);
        if (remainingTime > 0) {
          waited = true;
          await overlay.first().waitFor({ state: 'hidden', timeout: remainingTime });
        }
      }

      // Wait for skeleton loaders
      const skeleton = this.page.locator(SELECTORS.skeleton);
      if (await skeleton.count() > 0) {
        const remainingTime = timeout - (Date.now() - startTime);
        if (remainingTime > 0) {
          waited = true;
          await skeleton.first().waitFor({ state: 'hidden', timeout: remainingTime });
        }
      }

      return { success: true, waited };
    } catch (error) {
      // Timeout waiting - might be stuck
      return { success: false, waited, error: error.message };
    }
  }

  /**
   * Check if a CAPTCHA is present on the page
   * @returns {Promise<{detected: boolean, type: string|null}>}
   */
  async detectCaptcha() {
    try {
      // Check for reCAPTCHA iframe
      const recaptchaFrame = this.page.locator('iframe[src*="recaptcha"]');
      if (await recaptchaFrame.count() > 0) {
        return { detected: true, type: 'recaptcha' };
      }

      // Check for hCaptcha iframe
      const hcaptchaFrame = this.page.locator('iframe[src*="hcaptcha"]');
      if (await hcaptchaFrame.count() > 0) {
        return { detected: true, type: 'hcaptcha' };
      }

      // Check for generic captcha container
      const captchaContainer = this.page.locator(SELECTORS.captchaContainer);
      if (await captchaContainer.count() > 0) {
        return { detected: true, type: 'generic' };
      }

      // Check for captcha in page content
      const pageContent = await this.page.content();
      if (pageContent.toLowerCase().includes('captcha') ||
          pageContent.includes('robot') ||
          pageContent.includes('verify you are human')) {
        return { detected: true, type: 'text-based' };
      }

      return { detected: false, type: null };
    } catch (error) {
      return { detected: false, type: null, error: error.message };
    }
  }

  /**
   * Handle CAPTCHA - pause for manual solving or use service
   * @param {Object} options - Captcha handling options
   * @returns {Promise<{success: boolean, method: string}>}
   */
  async handleCaptcha(options = {}) {
    const {
      manualTimeout = 120000,  // 2 minutes for manual solving
      onCaptchaDetected = null, // Callback when captcha detected
      solverService = null,     // Optional: '2captcha', 'anticaptcha'
      solverApiKey = null       // API key for solver service
    } = options;

    const captchaStatus = await this.detectCaptcha();

    if (!captchaStatus.detected) {
      return { success: true, method: 'none', message: 'No CAPTCHA detected' };
    }

    await this.takeScreenshot('captcha_detected');

    // Notify callback if provided
    if (onCaptchaDetected) {
      onCaptchaDetected({ type: captchaStatus.type });
    }

    // Option 1: Use external solver service
    if (solverService && solverApiKey) {
      try {
        const result = await this.solveCaptchaWithService(
          captchaStatus.type,
          solverService,
          solverApiKey
        );
        return result;
      } catch (error) {
        console.log('Solver service failed, falling back to manual');
      }
    }

    // Option 2: Wait for manual solving
    console.log(`⚠️ CAPTCHA detected (${captchaStatus.type}). Please solve it manually.`);

    const startTime = Date.now();
    while (Date.now() - startTime < manualTimeout) {
      await this.page.waitForTimeout(2000);

      const stillPresent = await this.detectCaptcha();
      if (!stillPresent.detected) {
        return { success: true, method: 'manual', message: 'CAPTCHA solved manually' };
      }
    }

    return {
      success: false,
      method: 'timeout',
      message: 'CAPTCHA solving timed out'
    };
  }

  /**
   * Solve CAPTCHA using external service (2Captcha, Anti-Captcha, etc.)
   * @param {string} captchaType - Type of captcha
   * @param {string} service - Service name
   * @param {string} apiKey - API key
   * @returns {Promise<{success: boolean}>}
   */
  async solveCaptchaWithService(captchaType, service, apiKey) {
    // Get site key from page
    let siteKey = null;

    if (captchaType === 'recaptcha') {
      const container = await this.page.$('.g-recaptcha');
      if (container) {
        siteKey = await container.getAttribute('data-sitekey');
      }
    } else if (captchaType === 'hcaptcha') {
      const container = await this.page.$('.h-captcha');
      if (container) {
        siteKey = await container.getAttribute('data-sitekey');
      }
    }

    if (!siteKey) {
      return { success: false, error: 'Could not find site key' };
    }

    const pageUrl = this.page.url();

    // Call solver service API
    if (service === '2captcha') {
      return await this.solve2Captcha(siteKey, pageUrl, apiKey, captchaType);
    } else if (service === 'anticaptcha') {
      return await this.solveAntiCaptcha(siteKey, pageUrl, apiKey, captchaType);
    }

    return { success: false, error: 'Unknown solver service' };
  }

  /**
   * Solve using 2Captcha service
   */
  async solve2Captcha(siteKey, pageUrl, apiKey, captchaType) {
    const fetch = (await import('node-fetch')).default;

    // Submit task
    const method = captchaType === 'hcaptcha' ? 'hcaptcha' : 'userrecaptcha';
    const submitUrl = `http://2captcha.com/in.php?key=${apiKey}&method=${method}&googlekey=${siteKey}&pageurl=${pageUrl}&json=1`;

    const submitResponse = await fetch(submitUrl);
    const submitData = await submitResponse.json();

    if (submitData.status !== 1) {
      return { success: false, error: submitData.request };
    }

    const taskId = submitData.request;

    // Poll for result (max 2 minutes)
    for (let i = 0; i < 24; i++) {
      await this.page.waitForTimeout(5000);

      const resultUrl = `http://2captcha.com/res.php?key=${apiKey}&action=get&id=${taskId}&json=1`;
      const resultResponse = await fetch(resultUrl);
      const resultData = await resultResponse.json();

      if (resultData.status === 1) {
        // Inject solution
        await this.injectCaptchaSolution(resultData.request, captchaType);
        return { success: true, method: '2captcha' };
      }
    }

    return { success: false, error: 'Solver timeout' };
  }

  /**
   * Inject CAPTCHA solution into page
   */
  async injectCaptchaSolution(token, captchaType) {
    if (captchaType === 'recaptcha') {
      await this.page.evaluate((token) => {
        document.querySelector('#g-recaptcha-response').value = token;
        document.querySelector('[name="g-recaptcha-response"]').value = token;
        // Trigger callback if exists
        if (typeof window.captchaCallback === 'function') {
          window.captchaCallback(token);
        }
      }, token);
    } else if (captchaType === 'hcaptcha') {
      await this.page.evaluate((token) => {
        document.querySelector('[name="h-captcha-response"]').value = token;
        document.querySelector('[name="g-recaptcha-response"]').value = token;
      }, token);
    }
  }

  /**
   * Smart wait - handles loading screens and checks for CAPTCHA
   * @param {Object} options
   * @returns {Promise<{success: boolean}>}
   */
  async smartWait(options = {}) {
    const {
      timeout = 30000,
      checkCaptcha = true,
      onCaptchaDetected = null
    } = options;

    // First wait for network to settle
    try {
      await this.page.waitForLoadState('networkidle', { timeout: timeout / 2 });
    } catch (e) {
      // Network didn't settle, continue anyway
    }

    // Wait for loading screens
    await this.waitForLoadingScreens(timeout / 2);

    // Check for CAPTCHA
    if (checkCaptcha) {
      const captchaStatus = await this.detectCaptcha();
      if (captchaStatus.detected) {
        return await this.handleCaptcha({ onCaptchaDetected });
      }
    }

    return { success: true };
  }

  async navigate(url, options = {}) {
    try {
      await this.page.goto(url);
      await this.closeModals();

      // Use smart wait to handle loading screens and CAPTCHAs
      const waitResult = await this.smartWait({
        timeout: options.timeout || 30000,
        checkCaptcha: options.checkCaptcha !== false,
        onCaptchaDetected: options.onCaptchaDetected
      });

      if (!waitResult.success && waitResult.method === 'timeout') {
        return { success: false, error: 'CAPTCHA timeout', captcha: true };
      }

      return { success: true, captchaSolved: waitResult.method === 'manual' };
    } catch (error) {
      await this.takeScreenshot('navigate_error');
      return { success: false, error: error.message };
    }
  }

  async login(email, password) {
    if (!email || !password) {
      return { success: false, error: 'Email and password are required' };
    }

    try {
      await this.navigate(URLS.login);
      await this.takeScreenshot('login_page');

      await this.page.fill(SELECTORS.loginEmail, email);
      await this.page.fill(SELECTORS.loginPassword, password);
      await this.page.click(SELECTORS.loginButton);

      await this.page.waitForLoadState('networkidle');
      await this.page.waitForTimeout(2000);

      // Check for errors
      const errorEl = this.page.locator(SELECTORS.errorMessage);
      if (await errorEl.count() > 0) {
        const errorText = await errorEl.first().textContent();
        await this.takeScreenshot('login_error');
        return { success: false, error: errorText };
      }

      this.isLoggedIn = true;
      await this.takeScreenshot('login_success');
      return { success: true, message: 'Successfully logged in' };
    } catch (error) {
      await this.takeScreenshot('login_exception');
      return { success: false, error: error.message };
    }
  }

  async searchProducts(query) {
    try {
      // Navigate to homepage if needed
      if (!this.page.url().includes('costco.com')) {
        await this.navigate(URLS.base);
      }

      await this.closeModals();

      // Search
      const searchInput = this.page.locator(SELECTORS.searchInput);
      await searchInput.fill(query);
      await searchInput.press('Enter');

      await this.page.waitForLoadState('networkidle');
      await this.page.waitForTimeout(2000);
      await this.takeScreenshot(`search_${query.replace(/\s+/g, '_')}`);

      // Parse results
      const products = [];
      const productCards = this.page.locator(SELECTORS.productCard);
      const count = await productCards.count();

      for (let i = 0; i < Math.min(count, 10); i++) {
        try {
          const card = productCards.nth(i);
          const titleEl = card.locator(SELECTORS.productTitle);
          const priceEl = card.locator(SELECTORS.productPrice);

          const title = await titleEl.count() > 0 ? await titleEl.textContent() : 'Unknown';
          const price = await priceEl.count() > 0 ? await priceEl.textContent() : 'N/A';
          const href = await titleEl.count() > 0 ? await titleEl.getAttribute('href') : '';

          products.push({
            index: i,
            title: title?.trim() || 'Unknown',
            price: price?.trim() || 'N/A',
            url: href?.startsWith('http') ? href : `${URLS.base}${href}`
          });
        } catch (e) {
          continue;
        }
      }

      return {
        success: true,
        query,
        resultCount: products.length,
        products
      };
    } catch (error) {
      await this.takeScreenshot('search_error');
      return { success: false, error: error.message };
    }
  }

  async viewProduct(productUrl) {
    try {
      await this.navigate(productUrl);
      await this.closeModals();
      await this.takeScreenshot('product_page');

      const title = await this.page.title();
      const addToCartBtn = this.page.locator(SELECTORS.addToCartButton);
      const canAddToCart = await addToCartBtn.count() > 0;

      return {
        success: true,
        title,
        url: productUrl,
        canAddToCart
      };
    } catch (error) {
      await this.takeScreenshot('product_error');
      return { success: false, error: error.message };
    }
  }

  async addToCart(quantity = 1) {
    try {
      // Set quantity if needed
      if (quantity > 1) {
        const qtyInput = this.page.locator(SELECTORS.quantityInput);
        if (await qtyInput.count() > 0) {
          await qtyInput.fill(String(quantity));
        }
      }

      const addBtn = this.page.locator(SELECTORS.addToCartButton);
      if (await addBtn.count() === 0) {
        return { success: false, error: 'Add to cart button not found' };
      }

      await addBtn.click();
      await this.page.waitForTimeout(2000);
      await this.page.waitForLoadState('networkidle');
      await this.takeScreenshot('added_to_cart');

      return { success: true, message: `Added ${quantity} item(s) to cart` };
    } catch (error) {
      await this.takeScreenshot('add_to_cart_error');
      return { success: false, error: error.message };
    }
  }

  async viewCart() {
    try {
      await this.navigate(URLS.cart);
      await this.closeModals();
      await this.page.waitForTimeout(2000);
      await this.takeScreenshot('cart_page');

      const items = [];
      const cartItems = this.page.locator(SELECTORS.cartItems);
      const count = await cartItems.count();

      for (let i = 0; i < count; i++) {
        try {
          const item = cartItems.nth(i);
          const nameEl = item.locator(SELECTORS.cartItemName);
          const priceEl = item.locator(SELECTORS.cartItemPrice);
          const qtyEl = item.locator(SELECTORS.cartItemQuantity);

          const name = await nameEl.count() > 0 ? await nameEl.textContent() : 'Unknown';
          const price = await priceEl.count() > 0 ? await priceEl.textContent() : 'N/A';
          const qty = await qtyEl.count() > 0 ? await qtyEl.inputValue() : '1';

          items.push({
            name: name?.trim() || 'Unknown',
            price: price?.trim() || 'N/A',
            quantity: qty
          });
        } catch (e) {
          continue;
        }
      }

      const subtotalEl = this.page.locator(SELECTORS.cartSubtotal);
      const subtotal = await subtotalEl.count() > 0 ? await subtotalEl.textContent() : 'N/A';

      return {
        success: true,
        itemCount: items.length,
        items,
        subtotal: subtotal?.trim() || 'N/A'
      };
    } catch (error) {
      await this.takeScreenshot('cart_error');
      return { success: false, error: error.message };
    }
  }

  async applyPromoCode(code) {
    try {
      if (!this.page.url().includes('cart')) {
        await this.navigate(URLS.cart);
      }

      const promoInput = this.page.locator(SELECTORS.promoCodeInput);
      if (await promoInput.count() === 0) {
        return { success: false, error: 'Promo code input not found' };
      }

      await promoInput.fill(code);
      await this.page.locator(SELECTORS.applyPromoButton).click();
      await this.page.waitForTimeout(2000);
      await this.takeScreenshot('promo_applied');

      const errorEl = this.page.locator(SELECTORS.errorMessage);
      if (await errorEl.count() > 0) {
        const errorText = await errorEl.textContent();
        return { success: false, error: errorText };
      }

      return { success: true, message: `Applied promo code: ${code}` };
    } catch (error) {
      await this.takeScreenshot('promo_error');
      return { success: false, error: error.message };
    }
  }

  async proceedToCheckout() {
    try {
      if (!this.page.url().includes('cart')) {
        await this.navigate(URLS.cart);
      }

      const checkoutBtn = this.page.locator(SELECTORS.proceedToCheckout);
      if (await checkoutBtn.count() === 0) {
        return { success: false, error: 'Checkout button not found' };
      }

      await checkoutBtn.click();
      await this.page.waitForLoadState('networkidle');
      await this.page.waitForTimeout(2000);
      await this.takeScreenshot('checkout_page');

      return { success: true, message: 'Proceeded to checkout' };
    } catch (error) {
      await this.takeScreenshot('checkout_error');
      return { success: false, error: error.message };
    }
  }

  async placeOrder(confirm = false) {
    if (!confirm) {
      return {
        success: false,
        error: 'Order not placed. Set confirm=true to place order.',
        message: 'Safety check: Review order and confirm to complete purchase.'
      };
    }

    try {
      await this.takeScreenshot('before_place_order');

      const placeOrderBtn = this.page.locator(SELECTORS.placeOrderButton);
      if (await placeOrderBtn.count() === 0) {
        return { success: false, error: 'Place order button not found' };
      }

      await placeOrderBtn.click();
      await this.page.waitForLoadState('networkidle');
      await this.page.waitForTimeout(5000);
      await this.takeScreenshot('order_placed');

      return {
        success: true,
        message: 'Order placed successfully!',
        confirmationUrl: this.page.url()
      };
    } catch (error) {
      await this.takeScreenshot('place_order_error');
      return { success: false, error: error.message };
    }
  }
}

module.exports = CostcoAgent;
