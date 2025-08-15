/**
 * security-config.js - 安全配置模組
 * 負責處理前端安全相關的配置和檢查
 */

MedApp.utils.security = {
    // CSP 配置
    cspConfig: {
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'", "https://maps.googleapis.com", "https://cdn.jsdelivr.net"],
        'style-src': ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com", "https://cdnjs.cloudflare.com"],
        'font-src': ["'self'", "https://fonts.gstatic.com", "https://cdnjs.cloudflare.com"],
        'img-src': ["'self'", "data:", "https:", "blob:"],
        'connect-src': ["'self'", "https://maps.googleapis.com"],
        'media-src': ["'self'"],
        'object-src': ["'none'"],
        'frame-src': ["'none'"],
        'worker-src': ["'self'"],
        'manifest-src': ["'self'"]
    },
    
    // 敏感資料規則
    sensitiveDataPatterns: [
        /sk-[a-zA-Z0-9]{48}/g,  // OpenAI API keys
        /AIza[0-9A-Za-z-_]{35}/g,  // Google API keys
        /[a-f0-9]{32}/g,  // MD5 hashes (可能是密碼)
        /\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g,  // Email addresses
        /\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/g  // 信用卡號碼格式
    ],
    
    // 初始化
    init: function() {
        this.setupSecurityHeaders();
        this.enableContentSecurityPolicy();
        this.setupDataLeakPrevention();
        this.initSecurityMonitoring();
        
        MedApp.log('安全配置模組初始化完成', 'info');
    },
    
    // 設置安全標頭
    setupSecurityHeaders: function() {
        // 添加安全相關的 meta 標籤
        this.addMetaTag('referrer', 'strict-origin-when-cross-origin');
        this.addMetaTag('x-content-type-options', 'nosniff');
        this.addMetaTag('x-frame-options', 'DENY');
        this.addMetaTag('x-xss-protection', '1; mode=block');
    },
    
    // 添加 meta 標籤
    addMetaTag: function(name, content) {
        if (!document.querySelector(`meta[name="${name}"]`)) {
            const meta = document.createElement('meta');
            meta.name = name;
            meta.content = content;
            document.head.appendChild(meta);
        }
    },
    
    // 啟用內容安全策略
    enableContentSecurityPolicy: function() {
        // 在開發環境中，CSP 會比較寬鬆
        if (MedApp.config.debug) {
            MedApp.log('開發環境：使用寬鬆的 CSP 策略', 'debug');
            return;
        }
        
        // 生成 CSP 字符串
        const cspString = Object.entries(this.cspConfig)
            .map(([directive, sources]) => `${directive} ${sources.join(' ')}`)
            .join('; ');
        
        // 添加 CSP meta 標籤
        if (!document.querySelector('meta[http-equiv="Content-Security-Policy"]')) {
            const meta = document.createElement('meta');
            meta.httpEquiv = 'Content-Security-Policy';
            meta.content = cspString;
            document.head.appendChild(meta);
        }
        
        MedApp.log('CSP 策略已啟用', 'info');
    },
    
    // 設置資料洩漏防護
    setupDataLeakPrevention: function() {
        // 監控 console.log 輸出
        if (!MedApp.config.debug) {
            this.sanitizeConsoleOutput();
        }
        
        // 監控複製操作
        this.monitorClipboard();
        
        // 防止右鍵選單（生產環境）
        if (!MedApp.config.debug) {
            this.disableContextMenu();
        }
    },
    
    // 清理 console 輸出
    sanitizeConsoleOutput: function() {
        const originalLog = console.log;
        const originalError = console.error;
        const originalWarn = console.warn;
        
        console.log = (...args) => {
            const sanitizedArgs = this.sanitizeArgs(args);
            originalLog.apply(console, sanitizedArgs);
        };
        
        console.error = (...args) => {
            const sanitizedArgs = this.sanitizeArgs(args);
            originalError.apply(console, sanitizedArgs);
        };
        
        console.warn = (...args) => {
            const sanitizedArgs = this.sanitizeArgs(args);
            originalWarn.apply(console, sanitizedArgs);
        };
    },
    
    // 清理參數
    sanitizeArgs: function(args) {
        return args.map(arg => {
            if (typeof arg === 'string') {
                return this.sanitizeString(arg);
            } else if (typeof arg === 'object') {
                return this.sanitizeObject(arg);
            }
            return arg;
        });
    },
    
    // 清理字符串
    sanitizeString: function(str) {
        let sanitized = str;
        
        this.sensitiveDataPatterns.forEach(pattern => {
            sanitized = sanitized.replace(pattern, '[REDACTED]');
        });
        
        return sanitized;
    },
    
    // 清理物件
    sanitizeObject: function(obj) {
        if (!obj) return obj;
        
        const sanitized = {};
        
        Object.keys(obj).forEach(key => {
            const value = obj[key];
            
            if (typeof value === 'string') {
                sanitized[key] = this.sanitizeString(value);
            } else if (typeof value === 'object') {
                sanitized[key] = this.sanitizeObject(value);
            } else {
                sanitized[key] = value;
            }
        });
        
        return sanitized;
    },
    
    // 監控剪貼簿
    monitorClipboard: function() {
        document.addEventListener('copy', (event) => {
            const selection = window.getSelection().toString();
            
            if (this.containsSensitiveData(selection)) {
                event.preventDefault();
                
                if (MedApp.utils.notifications) {
                    MedApp.utils.notifications.warning('不允許複製敏感資料');
                }
                
                MedApp.log('阻止了敏感資料的複製操作', 'warn');
            }
        });
    },
    
    // 檢查是否包含敏感資料
    containsSensitiveData: function(text) {
        return this.sensitiveDataPatterns.some(pattern => pattern.test(text));
    },
    
    // 禁用右鍵選單
    disableContextMenu: function() {
        document.addEventListener('contextmenu', (event) => {
            event.preventDefault();
            return false;
        });
        
        // 禁用 F12 等開發者工具快捷鍵
        document.addEventListener('keydown', (event) => {
            if (
                event.key === 'F12' ||
                (event.ctrlKey && event.shiftKey && event.key === 'I') ||
                (event.ctrlKey && event.shiftKey && event.key === 'C') ||
                (event.ctrlKey && event.key === 'U')
            ) {
                event.preventDefault();
                return false;
            }
        });
    },
    
    // 初始化安全監控
    initSecurityMonitoring: function() {
        // 監控異常腳本執行
        this.monitorScriptExecution();
        
        // 監控 DOM 變更
        this.monitorDOMChanges();
        
        // 監控網路請求
        this.monitorNetworkRequests();
    },
    
    // 監控腳本執行
    monitorScriptExecution: function() {
        // 監控 eval 使用
        const originalEval = window.eval;
        window.eval = function(...args) {
            MedApp.log('檢測到 eval 使用，可能存在安全風險', 'warn');
            
            if (MedApp.utils.errorHandler) {
                MedApp.utils.errorHandler.reportError(
                    'eval 函數被調用',
                    'warn',
                    'security'
                );
            }
            
            // 在生產環境中禁用 eval
            if (!MedApp.config.debug) {
                throw new Error('eval 在生產環境中被禁用');
            }
            
            return originalEval.apply(this, args);
        };
    },
    
    // 監控 DOM 變更
    monitorDOMChanges: function() {
        if ('MutationObserver' in window) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'childList') {
                        mutation.addedNodes.forEach((node) => {
                            if (node.nodeName === 'SCRIPT') {
                                this.checkScriptSecurity(node);
                            }
                        });
                    }
                });
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        }
    },
    
    // 檢查腳本安全性
    checkScriptSecurity: function(scriptNode) {
        const src = scriptNode.src;
        const content = scriptNode.textContent;
        
        // 檢查外部腳本來源
        if (src && !this.isAllowedScriptSource(src)) {
            MedApp.log(`檢測到未授權的外部腳本: ${src}`, 'error');
            scriptNode.remove();
            return;
        }
        
        // 檢查內聯腳本內容
        if (content && this.containsMaliciousCode(content)) {
            MedApp.log('檢測到可疑的內聯腳本', 'error');
            scriptNode.remove();
            return;
        }
    },
    
    // 檢查是否為允許的腳本來源
    isAllowedScriptSource: function(src) {
        const allowedDomains = [
            'maps.googleapis.com',
            'cdn.jsdelivr.net',
            'cdnjs.cloudflare.com'
        ];
        
        return allowedDomains.some(domain => src.includes(domain)) ||
               src.startsWith('/') ||
               src.startsWith('./');
    },
    
    // 檢查惡意代碼
    containsMaliciousCode: function(code) {
        const maliciousPatterns = [
            /document\.write/g,
            /eval\s*\(/g,
            /Function\s*\(/g,
            /setTimeout\s*\(\s*['"`]/g,
            /setInterval\s*\(\s*['"`]/g
        ];
        
        return maliciousPatterns.some(pattern => pattern.test(code));
    },
    
    // 監控網路請求
    monitorNetworkRequests: function() {
        // 這個功能由 api-manager 處理
        if (MedApp.utils.apiManager) {
            MedApp.log('網路請求監控已委託給 API 管理器', 'debug');
        }
    },
    
    // 生成安全報告
    generateSecurityReport: function() {
        return {
            cspEnabled: !!document.querySelector('meta[http-equiv="Content-Security-Policy"]'),
            debugMode: MedApp.config.debug,
            securityFeatures: {
                contentSecurityPolicy: true,
                dataLeakPrevention: true,
                sensitiveDataFiltering: true,
                scriptMonitoring: true,
                domChangeMonitoring: true
            },
            timestamp: new Date().toISOString()
        };
    }
};