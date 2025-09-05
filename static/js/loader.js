/**
 * loader.js - 模組加載器
 * 負責按正確順序加載所有模組並確保依賴關係
 */

MedApp.loader = {
  // 模組加載狀態
  modules: {
    chat: {
      core: false,
      history: false,
      input: false,
      display: false
    },
    maps: {
      core: false,
      search: false,
      hospital: false,
      direction: false
    },
    utils: {
      accessibility: false,
      notifications: false,
      speech: false
    }
  },
  
  // 加載所有模組
  loadModules: function() {
    const modulesToLoad = [
      // 工具模組 (優先加載)
      { type: 'utils', name: 'accessibility' },
      { type: 'utils', name: 'notifications' },
      { type: 'utils', name: 'speech' },
      
      // 聊天模組
      { type: 'chat', name: 'chat-core' },
      { type: 'chat', name: 'chat-history' },
      { type: 'chat', name: 'chat-input' },
      { type: 'chat', name: 'chat-display' },
      
      // 地圖模組
      { type: 'maps', name: 'maps-core' },
      { type: 'maps', name: 'maps-search' },
      { type: 'maps', name: 'maps-hospital' },
      { type: 'maps', name: 'maps-direction' }
    ];
    
    Promise.all(modulesToLoad.map(module => this.loadModule(module.type, module.name)))
      .then(() => {
        MedApp.log('所有模組加載完成', 'info');
        // 發出模組加載完成事件
        document.dispatchEvent(new Event('modulesLoaded'));
      })
      .catch(error => {
        MedApp.log(`模組加載錯誤: ${error.message}`, 'error');
        // 即使有錯誤，也嘗試發出事件，讓已加載的模組可以初始化
        document.dispatchEvent(new Event('modulesLoaded'));
      });
  },
  
  // 加載單個模組
  loadModule: function(type, name) {
    return new Promise((resolve, reject) => {
      // 構建腳本路徑 - 使用正確的文件名
      const basePath = window.MedApp?.config?.staticPath || '/static/js/';
      
      // 直接使用完整的文件名，因為每個文件都有各自的前綴
      const scriptPath = `${basePath}${type}/${name}.js`;
      
      // 檢查腳本是否已加載
      const existingScript = document.querySelector(`script[src="${scriptPath}"]`);
      if (existingScript) {
        MedApp.log(`模組已加載: ${name}`, 'debug');
        
        // 為了兼容模組系統，根據文件名格式設置加載狀態
        // 例如 chat-core.js 對應 modules.chat.core
        if (name.includes('-')) {
          const parts = name.split('-');
          if (parts.length > 1 && this.modules[type] && this.modules[type][parts[1]]) {
            this.modules[type][parts[1]] = true;
          }
        }
        
        resolve();
        return;
      }
      
      const script = document.createElement('script');
      script.src = scriptPath;
      script.async = true;
      
      script.onload = () => {
        MedApp.log(`模組加載成功: ${name}`, 'debug');
        
        // 為了兼容模組系統，根據文件名格式設置加載狀態
        if (name.includes('-')) {
          const parts = name.split('-');
          if (parts.length > 1 && this.modules[type] && this.modules[type][parts[1]]) {
            this.modules[type][parts[1]] = true;
          }
        }
        
        resolve();
      };
      
      script.onerror = () => {
        const errorMsg = `無法加載模組: ${scriptPath}`;
        MedApp.log(errorMsg, 'error');
        reject(new Error(errorMsg));
      };
      
      document.head.appendChild(script);
    });
  },
  
  // 檢查模組是否已經加載
  isModuleLoaded: function(type, name) {
    return this.modules[type] && this.modules[type][name] === true;
  },
  
  // 等待模組加載完成
  waitForModule: function(type, name) {
    return new Promise((resolve) => {
      if (this.isModuleLoaded(type, name)) {
        resolve();
        return;
      }
      
      const checkInterval = setInterval(() => {
        if (this.isModuleLoaded(type, name)) {
          clearInterval(checkInterval);
          resolve();
        }
      }, 100);
    });
  }
};

// DOM 載入後開始加載模組
document.addEventListener('DOMContentLoaded', function() {
  // 確保在 app-core 初始化後才加載其他模組
  setTimeout(() => {
    MedApp.loader.loadModules();
  }, 0);
});