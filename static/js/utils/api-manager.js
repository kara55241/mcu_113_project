/**
 * api-manager.js - API 管理模組
 * 負責管理所有 API 調用和配置
 */

MedApp.utils.apiManager = {
    // 基礎配置
    config: {
        retryAttempts: 3,
        timeout: 10000,
        retryDelay: 1000
    },
    
    // API 端點
    endpoints: {
        chat: '/chat/',
        conversations: '/api/conversations/',
        messages: '/api/messages/',
        feedback: '/api/feedback/',
        health: '/chat/health/',
        chatHistory: '/chat/history/',
        upload: '/chat/upload/'
    },
    
    // 請求計數器
    requestCounter: 0,
    
    // 初始化
    init: function() {
        this.setupRequestInterceptors();
        MedApp.log('API 管理模組初始化完成', 'info');
    },
    
    // 設置請求攔截器
    setupRequestInterceptors: function() {
        // 攔截 fetch 請求以添加通用處理
        const originalFetch = window.fetch;
        
        window.fetch = async (...args) => {
            const [url, options = {}] = args;
            
            // 添加請求 ID
            const requestId = ++this.requestCounter;
            
            // 性能監控
            if (MedApp.utils.performanceMonitor) {
                MedApp.utils.performanceMonitor.startTiming(`api-request-${requestId}`);
            }
            
            try {
                // 添加默認選項
                const mergedOptions = this.mergeDefaultOptions(options);
                
                // 執行請求
                const response = await originalFetch(url, mergedOptions);
                
                // 性能記錄
                if (MedApp.utils.performanceMonitor) {
                    const duration = MedApp.utils.performanceMonitor.endTiming(`api-request-${requestId}`);
                    MedApp.utils.performanceMonitor.measureApiCall(url, duration);
                }
                
                // 檢查響應狀態
                if (!response.ok) {
                    this.handleApiError(response, url);
                }
                
                return response;
                
            } catch (error) {
                // 性能記錄（錯誤情況）
                if (MedApp.utils.performanceMonitor) {
                    MedApp.utils.performanceMonitor.endTiming(`api-request-${requestId}`);
                }
                
                // 錯誤處理
                this.handleNetworkError(error, url);
                throw error;
            }
        };
    },
    
    // 合併默認選項
    mergeDefaultOptions: function(options) {
        const defaults = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken(),
                ...options.headers
            },
            credentials: 'same-origin'
        };
        
        return { ...defaults, ...options };
    },
    
    // 處理 API 錯誤
    handleApiError: function(response, url) {
        const errorMsg = `API 錯誤: ${response.status} ${response.statusText} - ${url}`;
        
        if (MedApp.utils.errorHandler) {
            MedApp.utils.errorHandler.reportError(
                errorMsg,
                'error',
                'api'
            );
        } else {
            MedApp.log(errorMsg, 'error');
        }
    },
    
    // 處理網路錯誤
    handleNetworkError: function(error, url) {
        const errorMsg = `網路錯誤: ${error.message} - ${url}`;
        
        if (MedApp.utils.errorHandler) {
            MedApp.utils.errorHandler.reportError(
                errorMsg,
                'error',
                'network'
            );
        } else {
            MedApp.log(errorMsg, 'error');
        }
    },
    
    // 帶重試的請求
    requestWithRetry: async function(url, options = {}, retries = this.config.retryAttempts) {
        try {
            const response = await fetch(url, options);
            
            if (!response.ok && retries > 0 && this.shouldRetry(response.status)) {
                MedApp.log(`請求失敗，準備重試: ${url} (${retries} 次剩餘)`, 'warn');
                await this.delay(this.config.retryDelay);
                return this.requestWithRetry(url, options, retries - 1);
            }
            
            return response;
            
        } catch (error) {
            if (retries > 0) {
                MedApp.log(`網路錯誤，準備重試: ${url} (${retries} 次剩餘)`, 'warn');
                await this.delay(this.config.retryDelay);
                return this.requestWithRetry(url, options, retries - 1);
            }
            
            throw error;
        }
    },
    
    // 判斷是否應該重試
    shouldRetry: function(status) {
        // 重試服務器錯誤和某些客戶端錯誤
        return status >= 500 || status === 408 || status === 429;
    },
    
    // 延遲函數
    delay: function(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    },
    
    // 安全的 POST 請求
    post: async function(endpoint, data, options = {}) {
        const url = this.getFullUrl(endpoint);
        
        const requestOptions = {
            method: 'POST',
            body: JSON.stringify(data),
            ...options
        };
        
        return this.requestWithRetry(url, requestOptions);
    },
    
    // 安全的 GET 請求
    get: async function(endpoint, options = {}) {
        const url = this.getFullUrl(endpoint);
        
        const requestOptions = {
            method: 'GET',
            ...options
        };
        
        return this.requestWithRetry(url, requestOptions);
    },
    
    // 安全的 DELETE 請求
    delete: async function(endpoint, options = {}) {
        const url = this.getFullUrl(endpoint);
        
        const requestOptions = {
            method: 'DELETE',
            ...options
        };
        
        return this.requestWithRetry(url, requestOptions);
    },
    
    // 獲取完整 URL
    getFullUrl: function(endpoint) {
        const baseUrl = MedApp.config.apiRoot || '';
        
        // 如果端點已經是完整 URL，直接返回
        if (endpoint.startsWith('http')) {
            return endpoint;
        }
        
        // 如果端點在預定義列表中，使用預定義值
        if (this.endpoints[endpoint]) {
            return baseUrl + this.endpoints[endpoint];
        }
        
        // 否則組合基礎 URL 和端點
        return baseUrl + endpoint;
    },
    
    // 獲取 CSRF Token
    getCSRFToken: function() {
        return document.querySelector('[name=csrf-token]')?.content ||
               document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
               MedApp.config.csrfToken ||
               '';
    },
    
    // 檢查 API 健康狀態
    checkHealth: async function() {
        try {
            const response = await this.get('health');
            const data = await response.json();
            
            MedApp.log('API 健康檢查通過', 'info');
            return { healthy: true, data };
            
        } catch (error) {
            MedApp.log('API 健康檢查失敗: ' + error.message, 'error');
            return { healthy: false, error: error.message };
        }
    },
    
    // 批量請求
    batchRequest: async function(requests) {
        const promises = requests.map(async (req) => {
            try {
                const response = await this[req.method](req.endpoint, req.data, req.options);
                return { success: true, data: response, request: req };
            } catch (error) {
                return { success: false, error: error.message, request: req };
            }
        });
        
        return Promise.all(promises);
    },
    
    // 取消進行中的請求（使用 AbortController）
    createCancellableRequest: function(endpoint, options = {}) {
        const controller = new AbortController();
        const signal = controller.signal;
        
        const promise = fetch(this.getFullUrl(endpoint), {
            ...options,
            signal
        });
        
        return {
            promise,
            cancel: () => controller.abort()
        };
    },
    
    // 獲取 API 統計
    getStats: function() {
        return {
            totalRequests: this.requestCounter,
            endpoints: Object.keys(this.endpoints),
            config: this.config
        };
    }
};