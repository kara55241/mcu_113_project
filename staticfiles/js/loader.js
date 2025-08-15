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
  loadModules: async function() {
    const modulesToLoad = [
      // 工具模組 (優先加載，包含錯誤處理)
      { type: 'utils', name: 'error-handler', priority: 1 },
      { type: 'utils', name: 'performance-monitor', priority: 1 },
      { type: 'utils', name: 'api-manager', priority: 1 },
      { type: 'utils', name: 'security-config', priority: 1 },
      { type: 'utils', name: 'accessibility', priority: 2 },
      { type: 'utils', name: 'notifications', priority: 2 },
      { type: 'utils', name: 'speech', priority: 2 },
      
      // 聊天模組
      { type: 'chat', name: 'chat-core', priority: 3 },
      { type: 'chat', name: 'chat-history', priority: 4 },
      { type: 'chat', name: 'chat-input', priority: 4 },
      { type: 'chat', name: 'chat-display', priority: 4 },
      
      // 地圖模組
      { type: 'maps', name: 'maps-core', priority: 3 },
      { type: 'maps', name: 'maps-search', priority: 4 },
      { type: 'maps', name: 'maps-hospital', priority: 4 },
      { type: 'maps', name: 'maps-direction', priority: 4 }
    ];
    
    try {
      // 按優先級分組加載
      const modulesByPriority = this.groupByPriority(modulesToLoad);
      
      for (const priority of Object.keys(modulesByPriority).sort()) {
        await Promise.all(
          modulesByPriority[priority].map(module => 
            this.loadModuleWithRetry(module.type, module.name)
          )
        );
        MedApp.log(`優先級 ${priority} 的模組加載完成`, 'debug');
      }
      
      MedApp.log('所有模組加載完成', 'info');
      // 發出模組加載完成事件
      document.dispatchEvent(new Event('modulesLoaded'));
      
    } catch (error) {
      if (MedApp.utils?.errorHandler) {
        MedApp.utils.errorHandler.reportError(
          `模組加載錯誤: ${error.message}`, 
          'error', 
          'module-loader'
        );
      } else {
        MedApp.log(`模組加載錯誤: ${error.message}`, 'error');
      }
      
      // 即使有錯誤，也嘗試發出事件，讓已加載的模組可以初始化
      document.dispatchEvent(new Event('modulesLoaded'));
    }
  },
  
  // 按優先級分組模組
  groupByPriority: function(modules) {
    return modules.reduce((groups, module) => {
      const priority = module.priority || 999;
      if (!groups[priority]) {
        groups[priority] = [];
      }
      groups[priority].push(module);
      return groups;
    }, {});
  },
  
  // 帶重試機制的模組加載
  loadModuleWithRetry: async function(type, name, maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        await this.loadModule(type, name);
        return; // 成功加載，退出重試循環
      } catch (error) {
        MedApp.log(`模組 ${name} 第 ${attempt} 次加載失敗: ${error.message}`, 'warn');
        
        if (attempt === maxRetries) {
          throw new Error(`模組 ${name} 加載失敗，已重試 ${maxRetries} 次`);
        }
        
        // 等待後重試
        await this.delay(attempt * 1000);
      }
    }
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
        this.updateModuleStatus(type, name);
        resolve();
        return;
      }
      
      const script = document.createElement('script');
      script.src = scriptPath;
      script.async = true;
      
      // 設置超時
      const timeoutId = setTimeout(() => {
        script.onerror = null;
        script.onload = null;
        reject(new Error(`模組 ${name} 加載超時`));
      }, 10000); // 10秒超時
      
      script.onload = () => {
        clearTimeout(timeoutId);
        MedApp.log(`模組加載成功: ${name}`, 'debug');
        this.updateModuleStatus(type, name);
        resolve();
      };
      
      script.onerror = () => {
        clearTimeout(timeoutId);
        const errorMsg = `無法加載模組: ${scriptPath}`;
        reject(new Error(errorMsg));
      };
      
      document.head.appendChild(script);
    });
  },
  
  // 更新模組狀態
  updateModuleStatus: function(type, name) {
    // 為了兼容模組系統，根據文件名格式設置加載狀態
    if (name.includes('-')) {
      const parts = name.split('-');
      if (parts.length > 1 && this.modules[type] && this.modules[type][parts[1]] !== undefined) {
        this.modules[type][parts[1]] = true;
      }
    }
  },
  
  // 延遲函數
  delay: function(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
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