const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to the renderer process
contextBridge.exposeInMainWorld('api', {
  // Agent controls
  startAgent: (options) => ipcRenderer.invoke('agent:start', options),
  stopAgent: () => ipcRenderer.invoke('agent:stop'),

  // Shopping actions
  login: (credentials) => ipcRenderer.invoke('agent:login', credentials),
  search: (query) => ipcRenderer.invoke('agent:search', query),
  viewProduct: (url) => ipcRenderer.invoke('agent:viewProduct', url),
  addToCart: (quantity) => ipcRenderer.invoke('agent:addToCart', quantity),
  viewCart: () => ipcRenderer.invoke('agent:viewCart'),
  applyPromo: (code) => ipcRenderer.invoke('agent:applyPromo', code),
  checkout: () => ipcRenderer.invoke('agent:checkout'),
  placeOrder: (confirm) => ipcRenderer.invoke('agent:placeOrder', confirm),
  screenshot: () => ipcRenderer.invoke('agent:screenshot'),

  // Full shopping workflow
  shop: (options) => ipcRenderer.invoke('agent:shop', options),

  // Listen for agent updates
  onAgentUpdate: (callback) => {
    ipcRenderer.on('agent:update', (event, data) => callback(data));
  }
});
