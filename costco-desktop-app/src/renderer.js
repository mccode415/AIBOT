// DOM Elements
const elements = {
  items: document.getElementById('items'),
  promo: document.getElementById('promo'),
  browseOnly: document.getElementById('browseOnly'),
  headless: document.getElementById('headless'),
  email: document.getElementById('email'),
  password: document.getElementById('password'),
  credentialsSection: document.getElementById('credentialsSection'),
  startBtn: document.getElementById('startBtn'),
  stopBtn: document.getElementById('stopBtn'),
  clearBtn: document.getElementById('clearBtn'),
  activityLog: document.getElementById('activityLog'),
  productsSection: document.getElementById('productsSection'),
  productsGrid: document.getElementById('productsGrid'),
  statusDot: document.getElementById('statusDot'),
  statusText: document.getElementById('statusText')
};

// State
let isRunning = false;

// Initialize
function init() {
  // Toggle credentials visibility based on browse-only mode
  elements.browseOnly.addEventListener('change', () => {
    elements.credentialsSection.classList.toggle('hidden', elements.browseOnly.checked);
  });

  // Button handlers
  elements.startBtn.addEventListener('click', startShopping);
  elements.stopBtn.addEventListener('click', stopAgent);
  elements.clearBtn.addEventListener('click', clearLog);

  // Listen for agent updates
  window.api.onAgentUpdate(handleAgentUpdate);
}

// Play alert sound for CAPTCHA
function playAlertSound() {
  // Create audio context and play a beep
  try {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);

    oscillator.frequency.value = 800; // Hz
    oscillator.type = 'sine';
    gainNode.gain.value = 0.3;

    oscillator.start();

    // Beep pattern: beep-beep-beep
    setTimeout(() => oscillator.stop(), 150);
    setTimeout(() => {
      const osc2 = audioContext.createOscillator();
      osc2.connect(gainNode);
      osc2.frequency.value = 800;
      osc2.type = 'sine';
      osc2.start();
      setTimeout(() => osc2.stop(), 150);
    }, 200);
    setTimeout(() => {
      const osc3 = audioContext.createOscillator();
      osc3.connect(gainNode);
      osc3.frequency.value = 1000;
      osc3.type = 'sine';
      osc3.start();
      setTimeout(() => osc3.stop(), 300);
    }, 400);
  } catch (e) {
    console.log('Could not play sound:', e);
  }
}

// Add log entry
function addLog(type, content, data = null) {
  const icons = {
    thinking: '🤔',
    action: '⚡',
    result: '✅',
    error: '❌',
    info: 'ℹ️',
    captcha: '🔐'
  };

  // Play sound for CAPTCHA
  if (type === 'captcha') {
    playAlertSound();
  }

  const entry = document.createElement('div');
  entry.className = `log-entry ${type}`;
  entry.innerHTML = `
    <span class="log-icon">${icons[type] || '📝'}</span>
    <span class="log-content">${content}</span>
  `;

  elements.activityLog.appendChild(entry);
  elements.activityLog.scrollTop = elements.activityLog.scrollHeight;

  // Display products if available
  if (data?.products) {
    displayProducts(data.products);
  }
}

// Display products
function displayProducts(products) {
  elements.productsSection.classList.remove('hidden');
  elements.productsGrid.innerHTML = '';

  products.slice(0, 5).forEach((product, index) => {
    const item = document.createElement('div');
    item.className = 'product-item';
    item.innerHTML = `
      <div class="product-title">${index + 1}. ${product.title?.substring(0, 60) || 'Unknown'}...</div>
      <div class="product-price">${product.price || 'N/A'}</div>
    `;
    elements.productsGrid.appendChild(item);
  });
}

// Update status
function setStatus(active, text) {
  elements.statusDot.classList.toggle('active', active);
  elements.statusText.textContent = text;
  isRunning = active;

  elements.startBtn.disabled = active;
  elements.stopBtn.disabled = !active;
}

// Clear log
function clearLog() {
  elements.activityLog.innerHTML = `
    <div class="log-entry result">
      <span class="log-icon">ℹ️</span>
      <span class="log-content">Log cleared. Ready to start.</span>
    </div>
  `;
  elements.productsSection.classList.add('hidden');
  elements.productsGrid.innerHTML = '';
}

// Handle agent updates
function handleAgentUpdate(data) {
  addLog(data.type, data.content, data.data);
}

// Start shopping
async function startShopping() {
  // Parse items
  const itemsText = elements.items.value.trim();
  if (!itemsText) {
    addLog('error', 'Please enter at least one item to search for.');
    return;
  }

  const items = itemsText.split('\n').map(s => s.trim()).filter(s => s);
  const browseOnly = elements.browseOnly.checked;
  const headless = elements.headless.checked;
  const promoCode = elements.promo.value.trim();
  const email = elements.email.value.trim();
  const password = elements.password.value.trim();

  // Validate credentials if not browse-only
  if (!browseOnly && (!email || !password)) {
    addLog('error', 'Please enter your Costco email and password, or enable browse-only mode.');
    return;
  }

  // Clear previous products
  elements.productsSection.classList.add('hidden');
  elements.productsGrid.innerHTML = '';

  setStatus(true, 'Running...');
  addLog('info', `Starting shopping agent... (${items.length} items)`);

  try {
    const result = await window.api.shop({
      items,
      browseOnly,
      headless,
      promoCode,
      email,
      password
    });

    if (result.success) {
      addLog('result', 'Shopping workflow completed!');
    } else {
      addLog('error', `Workflow ended with error: ${result.error || 'Unknown'}`);
    }
  } catch (error) {
    addLog('error', `Error: ${error.message}`);
  }

  setStatus(false, 'Ready');
}

// Stop agent
async function stopAgent() {
  setStatus(false, 'Stopping...');
  addLog('action', 'Stopping agent...');

  try {
    await window.api.stopAgent();
    addLog('result', 'Agent stopped.');
  } catch (error) {
    addLog('error', `Error stopping agent: ${error.message}`);
  }

  setStatus(false, 'Ready');
}

// Initialize on load
init();
