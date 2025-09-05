// Enhanced Accessibility - 增強的輔助功能
// 專為長輩友善設計的互動功能

(function() {
    'use strict';
    
    // 確保 MedApp 命名空間存在
    if (typeof window.MedApp === 'undefined') {
        window.MedApp = {};
    }
    
    if (typeof window.MedApp.utils === 'undefined') {
        window.MedApp.utils = {};
    }
    
    // 增強輔助功能模組
    window.MedApp.utils.enhancedAccessibility = {
        // 狀態管理
        state: {
            largeFontMode: false,
            highContrastMode: false,
            voiceEnabled: false,
            speechSynthesis: null,
            currentSpeechUtterance: null
        },
        
        // 初始化
        init: function() {
            this.setupEventListeners();
            this.initializeSpeechSynthesis();
            this.loadUserPreferences();
            this.setupVisualFeedback();
            this.setupKeyboardNavigation();
            console.log('Enhanced Accessibility initialized');
        },
        
        // 設定事件監聽器
        setupEventListeners: function() {
            const increaseFontBtn = document.getElementById('increaseFontBtn');
            const voiceReadBtn = document.getElementById('voiceReadBtn');
            
            // 大字體切換
            if (increaseFontBtn) {
                increaseFontBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.toggleLargeFontMode();
                    this.playClickSound();
                    this.announceAction('字體大小已切換');
                });
            }
            
            // 語音朗讀切換
            if (voiceReadBtn) {
                voiceReadBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    this.toggleVoiceMode();
                    this.playClickSound();
                });
            }
        },
        
        // 初始化語音合成
        initializeSpeechSynthesis: function() {
            if ('speechSynthesis' in window) {
                this.state.speechSynthesis = window.speechSynthesis;
                
                // 等待語音載入
                const loadVoices = () => {
                    const voices = this.state.speechSynthesis.getVoices();
                    // 優先選擇中文語音
                    const chineseVoice = voices.find(voice => 
                        voice.lang.includes('zh') || voice.name.includes('Chinese')
                    );
                    if (chineseVoice) {
                        this.state.preferredVoice = chineseVoice;
                    }
                };
                
                if (this.state.speechSynthesis.getVoices().length > 0) {
                    loadVoices();
                } else {
                    this.state.speechSynthesis.addEventListener('voiceschanged', loadVoices);
                }
            } else {
                console.warn('Speech Synthesis not supported');
            }
        },
        
        // 切換大字體模式
        toggleLargeFontMode: function() {
            this.state.largeFontMode = !this.state.largeFontMode;
            const body = document.body;
            
            if (this.state.largeFontMode) {
                body.classList.add('large-font-mode');
                this.updateAccessibilityButton('increaseFontBtn', 'fas fa-search-minus', '縮小字體');
                this.saveUserPreference('largeFontMode', true);
            } else {
                body.classList.remove('large-font-mode');
                this.updateAccessibilityButton('increaseFontBtn', 'fas fa-search-plus', '放大字體');
                this.saveUserPreference('largeFontMode', false);
            }
            
            // 平滑動畫效果
            this.animateLayoutChange();
        },
        
        // 切換語音模式
        toggleVoiceMode: function() {
            this.state.voiceEnabled = !this.state.voiceEnabled;
            
            if (this.state.voiceEnabled) {
                this.updateAccessibilityButton('voiceReadBtn', 'fas fa-volume-mute', '關閉語音');
                this.announceAction('語音朗讀已開啟');
                this.saveUserPreference('voiceEnabled', true);
            } else {
                this.updateAccessibilityButton('voiceReadBtn', 'fas fa-volume-up', '開啟語音');
                this.stopSpeaking();
                this.saveUserPreference('voiceEnabled', false);
            }
        },
        
        // 更新輔助功能按鈕
        updateAccessibilityButton: function(buttonId, iconClass, title) {
            const button = document.getElementById(buttonId);
            if (button) {
                const icon = button.querySelector('i');
                if (icon) {
                    icon.className = iconClass;
                }
                button.title = title;
                button.setAttribute('aria-label', title);
                
                // 添加視覺反饋
                button.classList.add('accessibility-button-updated');
                setTimeout(() => {
                    button.classList.remove('accessibility-button-updated');
                }, 300);
            }
        },
        
        // 語音播報
        speak: function(text, priority = 'normal') {
            if (!this.state.voiceEnabled || !this.state.speechSynthesis || !text) {
                return;
            }
            
            // 如果是高優先級，停止當前播報
            if (priority === 'high') {
                this.stopSpeaking();
            }
            
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = 'zh-TW';
            utterance.rate = 0.9;
            utterance.pitch = 1.0;
            utterance.volume = 0.8;
            
            if (this.state.preferredVoice) {
                utterance.voice = this.state.preferredVoice;
            }
            
            // 錯誤處理
            utterance.onerror = (event) => {
                console.warn('Speech synthesis error:', event.error);
            };
            
            utterance.onend = () => {
                this.state.currentSpeechUtterance = null;
            };
            
            this.state.currentSpeechUtterance = utterance;
            this.state.speechSynthesis.speak(utterance);
        },
        
        // 停止語音播報
        stopSpeaking: function() {
            if (this.state.speechSynthesis) {
                this.state.speechSynthesis.cancel();
                this.state.currentSpeechUtterance = null;
            }
        },
        
        // 播報操作動作
        announceAction: function(message) {
            this.speak(message, 'high');
        },
        
        // 播放點擊音效
        playClickSound: function() {
            // 使用 Web Audio API 生成簡單的點擊音效
            try {
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();
                
                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);
                
                oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
                gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);
                
                oscillator.start(audioContext.currentTime);
                oscillator.stop(audioContext.currentTime + 0.1);
            } catch (error) {
                // 靜默處理音效錯誤
                console.debug('Audio feedback not available');
            }
        },
        
        // 視覺反饋設定
        setupVisualFeedback: function() {
            // 為所有可點擊元素添加漣漪效果
            const clickableElements = document.querySelectorAll('button, .suggestion-btn, .input-button');
            
            clickableElements.forEach(element => {
                element.addEventListener('click', (e) => {
                    this.createRippleEffect(e);
                });
            });
        },
        
        // 創建漣漪效果
        createRippleEffect: function(event) {
            const button = event.currentTarget;
            const ripple = document.createElement('span');
            const rect = button.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = event.clientX - rect.left - size / 2;
            const y = event.clientY - rect.top - size / 2;
            
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple-effect');
            
            // CSS for ripple effect
            if (!document.querySelector('#ripple-styles')) {
                const style = document.createElement('style');
                style.id = 'ripple-styles';
                style.textContent = `
                    .ripple-effect {
                        position: absolute;
                        border-radius: 50%;
                        background: rgba(255, 255, 255, 0.6);
                        transform: scale(0);
                        animation: ripple-animation 0.6s linear;
                        pointer-events: none;
                    }
                    
                    @keyframes ripple-animation {
                        to {
                            transform: scale(4);
                            opacity: 0;
                        }
                    }
                    
                    .accessibility-button-updated {
                        transform: scale(1.05);
                        box-shadow: 0 4px 20px rgba(0, 122, 255, 0.3) !important;
                    }
                    
                    button, .suggestion-btn, .input-button {
                        position: relative;
                        overflow: hidden;
                    }
                `;
                document.head.appendChild(style);
            }
            
            button.appendChild(ripple);
            
            // 清理漣漪效果
            setTimeout(() => {
                if (ripple.parentNode) {
                    ripple.parentNode.removeChild(ripple);
                }
            }, 600);
        },
        
        // 設定鍵盤導航
        setupKeyboardNavigation: function() {
            // 改善 Tab 鍵導航的視覺指示
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Tab') {
                    document.body.classList.add('keyboard-navigation');
                }
                
                // 快捷鍵支援
                if (e.ctrlKey || e.metaKey) {
                    switch (e.key) {
                        case '+':
                        case '=':
                            e.preventDefault();
                            this.toggleLargeFontMode();
                            break;
                        case 'h':
                            e.preventDefault();
                            this.toggleHighContrastMode();
                            break;
                        case 's':
                            e.preventDefault();
                            this.toggleVoiceMode();
                            break;
                    }
                }
                
                // ESC 鍵關閉模態框
                if (e.key === 'Escape') {
                    this.closeActiveModals();
                }
            });
            
            document.addEventListener('mousedown', () => {
                document.body.classList.remove('keyboard-navigation');
            });
        },
        
        // 切換高對比度模式
        toggleHighContrastMode: function() {
            this.state.highContrastMode = !this.state.highContrastMode;
            const body = document.body;
            
            if (this.state.highContrastMode) {
                body.classList.add('high-contrast-mode');
            } else {
                body.classList.remove('high-contrast-mode');
            }
            
            this.saveUserPreference('highContrastMode', this.state.highContrastMode);
            this.announceAction(this.state.highContrastMode ? '高對比度已開啟' : '高對比度已關閉');
        },
        
        // 關閉活動的模態框
        closeActiveModals: function() {
            const activeModals = document.querySelectorAll('.map-modal.active');
            activeModals.forEach(modal => {
                modal.classList.remove('active');
            });
        },
        
        // 動畫佈局變化
        animateLayoutChange: function() {
            const elements = document.querySelectorAll('*');
            elements.forEach(element => {
                element.style.transition = 'all 0.3s ease-out';
            });
            
            // 清理過渡效果
            setTimeout(() => {
                elements.forEach(element => {
                    element.style.transition = '';
                });
            }, 300);
        },
        
        // 保存用戶偏好
        saveUserPreference: function(key, value) {
            try {
                localStorage.setItem(`medapp_${key}`, JSON.stringify(value));
            } catch (error) {
                console.warn('Cannot save user preference:', error);
            }
        },
        
        // 載入用戶偏好
        loadUserPreferences: function() {
            try {
                const largeFontMode = JSON.parse(localStorage.getItem('medapp_largeFontMode'));
                const voiceEnabled = JSON.parse(localStorage.getItem('medapp_voiceEnabled'));
                const highContrastMode = JSON.parse(localStorage.getItem('medapp_highContrastMode'));
                
                if (largeFontMode) {
                    setTimeout(() => this.toggleLargeFontMode(), 100);
                }
                
                if (voiceEnabled) {
                    setTimeout(() => this.toggleVoiceMode(), 150);
                }
                
                if (highContrastMode) {
                    setTimeout(() => this.toggleHighContrastMode(), 200);
                }
            } catch (error) {
                console.warn('Cannot load user preferences:', error);
            }
        },
        
        // 朗讀頁面內容
        readPageContent: function(selector = '.message-bubble:last-child') {
            const element = document.querySelector(selector);
            if (element && this.state.voiceEnabled) {
                const text = element.textContent || element.innerText;
                if (text) {
                    this.speak(text);
                }
            }
        },
        
        // 朗讀錯誤信息
        announceError: function(message) {
            this.speak(`錯誤：${message}`, 'high');
            
            // 視覺錯誤提示
            const errorToast = this.createToast(message, 'error');
            document.body.appendChild(errorToast);
        },
        
        // 朗讀成功信息
        announceSuccess: function(message) {
            this.speak(`成功：${message}`, 'high');
            
            // 視覺成功提示
            const successToast = this.createToast(message, 'success');
            document.body.appendChild(successToast);
        },
        
        // 創建提示框
        createToast: function(message, type = 'info') {
            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.textContent = message;
            
            // 添加 Toast 樣式
            if (!document.querySelector('#toast-styles')) {
                const style = document.createElement('style');
                style.id = 'toast-styles';
                style.textContent = `
                    .toast {
                        position: fixed;
                        top: 80px;
                        right: 20px;
                        background: var(--primary-white);
                        border: 2px solid var(--border-subtle);
                        border-radius: var(--border-radius-md);
                        padding: var(--spacing-md) var(--spacing-lg);
                        font-size: var(--font-size-sm);
                        font-weight: 500;
                        box-shadow: var(--shadow-strong);
                        z-index: 3000;
                        animation: toastSlideIn 0.3s ease-out;
                        max-width: 300px;
                    }
                    
                    .toast-error {
                        border-color: var(--accent-red);
                        background: #fff5f5;
                        color: var(--accent-red);
                    }
                    
                    .toast-success {
                        border-color: var(--accent-green);
                        background: #f0fff4;
                        color: var(--accent-green);
                    }
                    
                    @keyframes toastSlideIn {
                        from {
                            opacity: 0;
                            transform: translateX(100%);
                        }
                        to {
                            opacity: 1;
                            transform: translateX(0);
                        }
                    }
                    
                    @keyframes toastSlideOut {
                        from {
                            opacity: 1;
                            transform: translateX(0);
                        }
                        to {
                            opacity: 0;
                            transform: translateX(100%);
                        }
                    }
                `;
                document.head.appendChild(style);
            }
            
            // 自動移除
            setTimeout(() => {
                toast.style.animation = 'toastSlideOut 0.3s ease-out';
                setTimeout(() => {
                    if (toast.parentNode) {
                        toast.parentNode.removeChild(toast);
                    }
                }, 300);
            }, 3000);
            
            return toast;
        }
    };
    
    // 在頁面載入完成時初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            window.MedApp.utils.enhancedAccessibility.init();
        });
    } else {
        window.MedApp.utils.enhancedAccessibility.init();
    }
})();