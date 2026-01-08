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
  errorMessage: '.error-message, .alert-error'
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

  async navigate(url) {
    try {
      await this.page.goto(url);
      await this.page.waitForLoadState('networkidle');
      await this.closeModals();
      return { success: true };
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
