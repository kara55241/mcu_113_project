/**
 * performance-monitor.js - 效能監控模組
 * 負責監控和優化應用程式效能
 */

MedApp.utils.performanceMonitor = {
    // 效能統計
    stats: {
        pageLoadTime: 0,
        moduleLoadTime: 0,
        apiCallTimes: {},
        memoryUsage: {},
        domUpdates: 0,
        renderTime: 0
    },
    
    // 監控標記
    marks: new Map(),
    
    // 觀察器
    observers: {
        performance: null,
        intersection: null,
        mutation: null
    },
    
    // 初始化
    init: function() {
        this.measurePageLoadTime();
        this.setupPerformanceObserver();
        this.setupIntersectionObserver();
        this.setupMutationObserver();
        this.startMemoryMonitoring();
        
        MedApp.log('效能監控模組初始化完成', 'info');
    },
    
    // 測量頁面載入時間
    measurePageLoadTime: function() {
        if (window.performance && window.performance.timing) {
            const timing = window.performance.timing;
            this.stats.pageLoadTime = timing.loadEventEnd - timing.navigationStart;
            
            if (MedApp.config.debug) {
                console.log(`頁面載入時間: ${this.stats.pageLoadTime}ms`);
            }
        }
    },
    
    // 設置效能觀察器
    setupPerformanceObserver: function() {
        if ('PerformanceObserver' in window) {
            try {
                this.observers.performance = new PerformanceObserver((list) => {
                    const entries = list.getEntries();
                    
                    entries.forEach(entry => {
                        switch (entry.entryType) {
                            case 'navigation':
                                this.handleNavigationEntry(entry);
                                break;
                            case 'resource':
                                this.handleResourceEntry(entry);
                                break;
                            case 'measure':
                                this.handleMeasureEntry(entry);
                                break;
                            case 'paint':
                                this.handlePaintEntry(entry);
                                break;
                        }
                    });
                });
                
                this.observers.performance.observe({
                    entryTypes: ['navigation', 'resource', 'measure', 'paint']
                });
                
            } catch (error) {
                MedApp.log('PerformanceObserver 設置失敗: ' + error.message, 'warn');
            }
        }
    },
    
    // 設置交集觀察器（懶加載）
    setupIntersectionObserver: function() {
        if ('IntersectionObserver' in window) {
            this.observers.intersection = new IntersectionObserver((entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        this.handleElementVisible(entry.target);
                    }
                });
            }, {
                threshold: 0.1,
                rootMargin: '50px'
            });
        }
    },
    
    // 設置變異觀察器（DOM 更新監控）
    setupMutationObserver: function() {
        if ('MutationObserver' in window) {
            this.observers.mutation = new MutationObserver((mutations) => {
                this.stats.domUpdates += mutations.length;
                
                // 檢測大量 DOM 操作
                if (mutations.length > 50) {
                    MedApp.log(`檢測到大量 DOM 操作: ${mutations.length} 次變更`, 'warn');
                }
            });
            
            this.observers.mutation.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeOldValue: true
            });
        }
    },
    
    // 開始記憶體監控
    startMemoryMonitoring: function() {
        if (window.performance && window.performance.memory) {
            setInterval(() => {
                this.stats.memoryUsage = {
                    used: window.performance.memory.usedJSHeapSize,
                    total: window.performance.memory.totalJSHeapSize,
                    limit: window.performance.memory.jsHeapSizeLimit,
                    timestamp: Date.now()
                };
                
                // 檢測記憶體洩漏
                const usagePercent = (this.stats.memoryUsage.used / this.stats.memoryUsage.limit) * 100;
                if (usagePercent > 80) {
                    MedApp.log(`記憶體使用率過高: ${usagePercent.toFixed(1)}%`, 'warn');
                }
            }, 30000); // 每30秒檢查一次
        }
    },
    
    // 處理導航條目
    handleNavigationEntry: function(entry) {
        this.stats.renderTime = entry.loadEventEnd - entry.fetchStart;
        
        if (MedApp.config.debug) {
            console.log('導航效能:', {
                DNS查詢: entry.domainLookupEnd - entry.domainLookupStart,
                TCP連接: entry.connectEnd - entry.connectStart,
                請求響應: entry.responseEnd - entry.requestStart,
                DOM處理: entry.domComplete - entry.domLoading,
                載入完成: entry.loadEventEnd - entry.loadEventStart
            });
        }
    },
    
    // 處理資源條目
    handleResourceEntry: function(entry) {
        if (entry.name.includes('.js')) {
            this.stats.moduleLoadTime += entry.duration;
        }
        
        // 檢測慢資源
        if (entry.duration > 2000) {
            MedApp.log(`慢資源檢測: ${entry.name} 載入時間 ${entry.duration}ms`, 'warn');
        }
    },
    
    // 處理測量條目
    handleMeasureEntry: function(entry) {
        if (MedApp.config.debug) {
            console.log(`測量 ${entry.name}: ${entry.duration}ms`);
        }
    },
    
    // 處理繪製條目
    handlePaintEntry: function(entry) {
        if (MedApp.config.debug) {
            console.log(`${entry.name}: ${entry.startTime}ms`);
        }
    },
    
    // 處理元素可見
    handleElementVisible: function(element) {
        // 懶加載圖片
        if (element.tagName === 'IMG' && element.dataset.src) {
            element.src = element.dataset.src;
            element.removeAttribute('data-src');
            this.observers.intersection.unobserve(element);
        }
    },
    
    // 開始計時
    startTiming: function(name) {
        if (window.performance && window.performance.mark) {
            window.performance.mark(`${name}-start`);
        }
        this.marks.set(name, Date.now());
    },
    
    // 結束計時
    endTiming: function(name) {
        const startTime = this.marks.get(name);
        if (startTime) {
            const duration = Date.now() - startTime;
            this.marks.delete(name);
            
            if (window.performance && window.performance.mark && window.performance.measure) {
                window.performance.mark(`${name}-end`);
                window.performance.measure(name, `${name}-start`, `${name}-end`);
            }
            
            return duration;
        }
        return 0;
    },
    
    // 測量 API 調用
    measureApiCall: function(url, duration) {
        if (!this.stats.apiCallTimes[url]) {
            this.stats.apiCallTimes[url] = {
                count: 0,
                totalTime: 0,
                avgTime: 0,
                maxTime: 0,
                minTime: Infinity
            };
        }
        
        const stats = this.stats.apiCallTimes[url];
        stats.count++;
        stats.totalTime += duration;
        stats.avgTime = stats.totalTime / stats.count;
        stats.maxTime = Math.max(stats.maxTime, duration);
        stats.minTime = Math.min(stats.minTime, duration);
        
        // 檢測慢 API
        if (duration > 5000) {
            MedApp.log(`慢 API 檢測: ${url} 響應時間 ${duration}ms`, 'warn');
        }
    },
    
    // 優化圖片懶加載
    enableLazyLoading: function() {
        const images = document.querySelectorAll('img[data-src]');
        images.forEach(img => {
            this.observers.intersection.observe(img);
        });
    },
    
    // 節流函數
    throttle: function(func, delay) {
        let timeoutId;
        let lastExecTime = 0;
        
        return function (...args) {
            const currentTime = Date.now();
            
            if (currentTime - lastExecTime > delay) {
                func.apply(this, args);
                lastExecTime = currentTime;
            } else {
                clearTimeout(timeoutId);
                timeoutId = setTimeout(() => {
                    func.apply(this, args);
                    lastExecTime = Date.now();
                }, delay - (currentTime - lastExecTime));
            }
        };
    },
    
    // 防抖函數
    debounce: function(func, delay) {
        let timeoutId;
        
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
                func.apply(this, args);
            }, delay);
        };
    },
    
    // 獲取效能報告
    getPerformanceReport: function() {
        return {
            ...this.stats,
            timestamp: Date.now(),
            userAgent: navigator.userAgent,
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight
            }
        };
    },
    
    // 清理觀察器
    cleanup: function() {
        Object.values(this.observers).forEach(observer => {
            if (observer && observer.disconnect) {
                observer.disconnect();
            }
        });
    }
};