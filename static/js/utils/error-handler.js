/**
 * error-handler.js - 統一錯誤處理模組
 * 負責處理應用程式中的錯誤和異常
 */

MedApp.utils.errorHandler = {
    // 錯誤級別
    LEVELS: {
        INFO: 'info',
        WARN: 'warn', 
        ERROR: 'error',
        FATAL: 'fatal'
    },
    
    // 錯誤統計
    errorStats: {
        total: 0,
        byLevel: {},
        bySource: {}
    },
    
    // 初始化
    init: function() {
        this.setupGlobalErrorHandlers();
        this.initErrorStats();
        
        MedApp.log('錯誤處理模組初始化完成', 'info');
    },
    
    // 設置全域錯誤處理器
    setupGlobalErrorHandlers: function() {
        // JavaScript 錯誤
        window.addEventListener('error', (event) => {
            this.handleError({
                message: event.message,
                filename: event.filename,
                lineno: event.lineno,
                colno: event.colno,
                error: event.error,
                level: this.LEVELS.ERROR,
                source: 'javascript'
            });
        });
        
        // Promise 拒絕
        window.addEventListener('unhandledrejection', (event) => {
            this.handleError({
                message: event.reason?.message || '未處理的 Promise 拒絕',
                error: event.reason,
                level: this.LEVELS.ERROR,
                source: 'promise'
            });
        });
        
        // 資源載入錯誤
        window.addEventListener('error', (event) => {
            if (event.target !== window) {
                this.handleError({
                    message: `資源載入失敗: ${event.target.src || event.target.href}`,
                    level: this.LEVELS.WARN,
                    source: 'resource'
                });
            }
        }, true);
    },
    
    // 初始化錯誤統計
    initErrorStats: function() {
        Object.values(this.LEVELS).forEach(level => {
            this.errorStats.byLevel[level] = 0;
        });
    },
    
    // 處理錯誤
    handleError: function(errorInfo) {
        // 更新統計
        this.updateStats(errorInfo);
        
        // 記錄錯誤
        this.logError(errorInfo);
        
        // 根據錯誤級別決定處理方式
        switch (errorInfo.level) {
            case this.LEVELS.FATAL:
                this.handleFatalError(errorInfo);
                break;
            case this.LEVELS.ERROR:
                this.handleRegularError(errorInfo);
                break;
            case this.LEVELS.WARN:
                this.handleWarning(errorInfo);
                break;
            case this.LEVELS.INFO:
                this.handleInfo(errorInfo);
                break;
        }
        
        // 在開發環境顯示詳細資訊
        if (MedApp.config.debug) {
            this.showDebugInfo(errorInfo);
        }
    },
    
    // 更新錯誤統計
    updateStats: function(errorInfo) {
        this.errorStats.total++;
        this.errorStats.byLevel[errorInfo.level]++;
        
        const source = errorInfo.source || 'unknown';
        if (!this.errorStats.bySource[source]) {
            this.errorStats.bySource[source] = 0;
        }
        this.errorStats.bySource[source]++;
    },
    
    // 記錄錯誤
    logError: function(errorInfo) {
        const timestamp = new Date().toISOString();
        const logMessage = `[${timestamp}] [${errorInfo.level.toUpperCase()}] ${errorInfo.message}`;
        
        switch (errorInfo.level) {
            case this.LEVELS.FATAL:
            case this.LEVELS.ERROR:
                console.error(logMessage, errorInfo.error);
                break;
            case this.LEVELS.WARN:
                console.warn(logMessage);
                break;
            case this.LEVELS.INFO:
                console.info(logMessage);
                break;
        }
    },
    
    // 處理致命錯誤
    handleFatalError: function(errorInfo) {
        // 顯示用戶友好的錯誤訊息
        if (MedApp.utils.notifications) {
            MedApp.utils.notifications.error(
                '系統發生嚴重錯誤，請重新整理頁面',
                0 // 不自動關閉
            );
        }
        
        // 禁用部分功能以防止進一步錯誤
        this.disableFeatures();
    },
    
    // 處理一般錯誤
    handleRegularError: function(errorInfo) {
        // 根據錯誤來源提供不同的處理方式
        if (errorInfo.source === 'network') {
            this.handleNetworkError(errorInfo);
        } else if (errorInfo.source === 'api') {
            this.handleApiError(errorInfo);
        } else {
            // 一般錯誤處理
            if (MedApp.utils.notifications) {
                MedApp.utils.notifications.error(
                    '操作失敗，請稍後再試',
                    5000
                );
            }
        }
    },
    
    // 處理網路錯誤
    handleNetworkError: function(errorInfo) {
        if (MedApp.utils.notifications) {
            MedApp.utils.notifications.warning(
                '網路連線問題，請檢查您的網路連線',
                7000
            );
        }
    },
    
    // 處理 API 錯誤
    handleApiError: function(errorInfo) {
        const message = errorInfo.statusCode === 500 
            ? '伺服器暫時無法處理請求，請稍後再試'
            : '服務暫時不可用，請稍後再試';
            
        if (MedApp.utils.notifications) {
            MedApp.utils.notifications.error(message, 5000);
        }
    },
    
    // 處理警告
    handleWarning: function(errorInfo) {
        // 對於非關鍵性問題，只記錄不打擾用戶
        MedApp.log(`警告: ${errorInfo.message}`, 'warn');
    },
    
    // 處理資訊
    handleInfo: function(errorInfo) {
        MedApp.log(`資訊: ${errorInfo.message}`, 'info');
    },
    
    // 顯示除錯資訊
    showDebugInfo: function(errorInfo) {
        console.group(`🐛 Debug Info - ${errorInfo.level.toUpperCase()}`);
        console.log('Message:', errorInfo.message);
        console.log('Source:', errorInfo.source);
        console.log('Timestamp:', new Date().toISOString());
        if (errorInfo.error) {
            console.log('Error Object:', errorInfo.error);
            console.log('Stack Trace:', errorInfo.error.stack);
        }
        console.log('Error Stats:', this.errorStats);
        console.groupEnd();
    },
    
    // 禁用功能（錯誤恢復）
    disableFeatures: function() {
        // 禁用可能導致更多錯誤的功能
        const buttonsToDisable = document.querySelectorAll('button:not(.error-recovery)');
        buttonsToDisable.forEach(button => {
            button.disabled = true;
        });
        
        // 顯示錯誤恢復選項
        this.showRecoveryOptions();
    },
    
    // 顯示錯誤恢復選項
    showRecoveryOptions: function() {
        const recoveryDiv = document.createElement('div');
        recoveryDiv.className = 'error-recovery-panel';
        recoveryDiv.innerHTML = `
            <div class="error-recovery-content">
                <h3>系統發生錯誤</h3>
                <p>請選擇以下恢復選項：</p>
                <button class="error-recovery btn btn-primary" onclick="location.reload()">
                    重新整理頁面
                </button>
                <button class="error-recovery btn btn-secondary" onclick="MedApp.utils.errorHandler.resetApplication()">
                    重置應用程式
                </button>
            </div>
        `;
        
        document.body.appendChild(recoveryDiv);
    },
    
    // 重置應用程式
    resetApplication: function() {
        // 清理本地儲存
        if (window.localStorage) {
            localStorage.removeItem('fontSize');
        }
        
        if (window.sessionStorage) {
            sessionStorage.clear();
        }
        
        // 重新載入頁面
        location.reload();
    },
    
    // 手動報告錯誤
    reportError: function(message, level = this.LEVELS.ERROR, source = 'manual') {
        this.handleError({
            message: message,
            level: level,
            source: source,
            timestamp: Date.now()
        });
    },
    
    // 獲取錯誤統計
    getErrorStats: function() {
        return { ...this.errorStats };
    },
    
    // 清除錯誤統計
    clearErrorStats: function() {
        this.errorStats.total = 0;
        this.initErrorStats();
    }
};