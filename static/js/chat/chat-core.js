/**
 * chat-core.js - 聊天核心功能（統一 feedback_graph 修正版）
 * 主要修正：統一使用 feedback_graph API，確保請求發送到正確端點
 */

MedApp.chat.core = {
  // DOM 元素參考
  elements: {
    container: null,
    welcomeMessage: null,
    chatContainer: null,
    inputField: null,
    sendButton: null,
    progressBar: null
  },
  
  // 防重複發送
  isProcessing: false,
  
  // 初始化聊天功能
  init: function() {
    this.initElements();
    this.bindEvents();
    
    // 初始化聊天 ID（但不立即創建對話）
    if (!MedApp.state.currentChatId) {
      MedApp.state.currentChatId = null; // 延遲到第一條訊息時創建
    }
    
    MedApp.log('聊天核心模組初始化完成 (統一 feedback_graph)', 'info');
  },
  
  // 初始化DOM元素引用
  initElements: function() {
    this.elements.container = document.getElementById('chatContainer');
    this.elements.welcomeMessage = document.querySelector('.welcome-message');
    this.elements.inputField = document.getElementById('userInput');
    this.elements.sendButton = document.getElementById('sendButton');
    this.elements.progressBar = document.getElementById('progressBar');
    
    if (this.elements.inputField) {
      this.elements.inputField.focus();
    }
  },
  
  // 綁定事件處理
  bindEvents: function() {
    if (this.elements.sendButton) {
      this.elements.sendButton.addEventListener('click', () => {
        const userMessage = this.elements.inputField.value.trim();
        if (userMessage && !this.isProcessing) {
          this.sendMessage(userMessage);
        }
      });
    }
    
    if (this.elements.inputField) {
      this.elements.inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !this.isProcessing) {
          const userMessage = this.elements.inputField.value.trim();
          if (userMessage) {
            this.sendMessage(userMessage);
          }
        }
      });
    }
  },
  
  // 顯示/隱藏載入指示器
  showLoading: function(show = true) {
    if (this.elements.progressBar) {
      this.elements.progressBar.style.display = show ? 'block' : 'none';
    }
    
    // 禁用/啟用輸入控件
    if (this.elements.inputField) {
      this.elements.inputField.disabled = show;
    }
    if (this.elements.sendButton) {
      this.elements.sendButton.disabled = show;
    }
  },
  
  // 確保有對話ID（懶加載創建）- 統一使用 feedback_graph API
  ensureChatExists: async function() {
    if (MedApp.state.currentChatId) {
      return MedApp.state.currentChatId;
    }
    
    // 生成新的聊天 ID
    const newChatId = Date.now().toString();
    
    try {
      const response = await fetch('/api/conversations/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': MedApp.config.csrfToken
        },
        body: JSON.stringify({ 
          chat_id: newChatId,
          session_id: this.getSessionId(),
          metadata: {
            created_by: 'first_message',
            timestamp: new Date().toISOString()
          }
        })
      });
      
      if (response.ok) {
        MedApp.state.currentChatId = newChatId;
        MedApp.log('對話已創建到統一資料庫: ' + newChatId, 'info');
        return newChatId;
      } else {
        throw new Error('創建對話失敗');
      }
    } catch (error) {
      MedApp.log('創建對話錯誤: ' + error.message, 'warn');
      // 降級：即使創建失敗也設置ID，讓前端可以繼續使用
      MedApp.state.currentChatId = newChatId;
      return newChatId;
    }
  },
  
  // 🔧 修正的 sendMessage 方法 - 統一使用 feedback_graph，確保發送到正確端點
  sendMessage: async function(message, locationInfo = null) {
    if (!message || !message.trim() || this.isProcessing) return;

    this.isProcessing = true;
    const location = locationInfo || MedApp.state.selectedLocation;

    try {
      // 確保對話存在
      const chatId = await this.ensureChatExists();
      const userMessageId = this.generateMessageId();

      // 顯示用戶訊息（不跳過保存，讓統一API處理）
      if (MedApp.chat && MedApp.chat.display && typeof MedApp.chat.display.appendMessage === 'function') {
        MedApp.chat.display.appendMessage(message, 'user', false, userMessageId, false); // 改為 false，讓API處理保存
      }
      
      // 清空輸入框
      this.elements.inputField.value = '';
      this.showLoading(true);

      // 準備請求數據
      const requestData = {
        message: message,
        chat_id: chatId,
        user_message_id: userMessageId,
        location_info: location,
        timestamp: new Date().toISOString()
      };

      console.log('發送請求到統一API:', requestData);

      // 🚨 重要修正：明確指定 /chat/ 端點，這個端點已經統一使用 feedback_graph
      const chatEndpoint = '/chat/';
      console.log('🔧 使用統一聊天端點:', chatEndpoint);

      // 發送請求到後端統一API
      const response = await fetch(chatEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-CSRFToken': MedApp.config.csrfToken
        },
        body: JSON.stringify(requestData)
      });

      console.log('收到統一API回應狀態:', response.status, response.statusText);
      console.log('回應 URL:', response.url);

      // 檢查響應狀態
      if (!response.ok) {
        throw new Error(`統一API錯誤 (${response.status}): ${response.statusText}`);
      }

      // 解析響應
      let data;
      try {
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
          data = await response.json();
        } else {
          // 如果不是JSON，嘗試解析為文本
          const rawText = await response.text();
          console.warn("❗ 統一API返回非JSON回應，原始內容：", rawText.slice(0, 500));
          
          // 嘗試從HTML中提取錯誤信息
          if (rawText.includes('<!DOCTYPE html>') || rawText.includes('<html>')) {
            throw new Error("統一API回傳HTML頁面，可能是錯誤頁面或配置問題");
          }
          
          // 將文本當作回應內容
          data = { output: rawText };
        }
      } catch (parseError) {
        console.error("解析統一API回應失敗:", parseError);
        throw new Error("無法解析統一API回應");
      }

      // 處理回應數據
      const reply = typeof data === 'string' ? data : (data.output || '（統一API沒有回傳內容）');
      console.log("收到統一API回應:", data);

      // 檢測是否為Markdown格式
      const isMarkdown = data.is_markdown === true || this.detectMarkdown(reply);
      const botMessageId = data.bot_message_id || this.generateMessageId();
      
      // 顯示機器人回應（不跳過保存，讓統一API處理）
      if (MedApp.chat && MedApp.chat.display && typeof MedApp.chat.display.appendMessage === 'function') {
        MedApp.chat.display.appendMessage(reply, 'bot', isMarkdown, botMessageId, false); // 改為 false，讓API處理保存
      }

      // 處理位置信息
      if (data.location && data.location.coordinates && MedApp.maps && MedApp.maps.core) {
        MedApp.maps.core.handleLocationResponse(data.location);
      }

      // 處理醫院信息
      if (data.data && data.data.results && Array.isArray(data.data.results) && data.data.results.length > 0) {
        if (MedApp.maps && MedApp.maps.hospital && typeof MedApp.maps.hospital.displayHospitals === 'function') {
          MedApp.maps.hospital.displayHospitals(data.data.results, location);
        }
      }

      // 更新對話歷史
      if (data.should_refresh_history) {
        setTimeout(() => {
          if (MedApp.chat && MedApp.chat.history && typeof MedApp.chat.history.refreshChatHistory === 'function') {
            MedApp.chat.history.refreshChatHistory();
          }
        }, 500);
      } else {
        this.updateCurrentChatTitle(message);
      }

      // 記錄成功
      MedApp.log('消息已通過統一API成功處理', 'info');

    } catch (error) {
      console.error('發送訊息到統一API錯誤:', error);
      MedApp.log(`發送訊息到統一API錯誤: ${error.message}`, 'error');
      
      // 顯示錯誤訊息
      const errorMessageId = this.generateMessageId();
      if (MedApp.chat && MedApp.chat.display && typeof MedApp.chat.display.appendMessage === 'function') {
        MedApp.chat.display.appendMessage(
          `⚠️ 統一API錯誤：${error.message}`,
          'bot',
          false,
          errorMessageId,
          false // 錯誤訊息也保存
        );
      }
      
      // 嘗試重新連接（延遲執行）
      setTimeout(() => {
        this.retryConnection();
      }, 3000);
      
    } finally {
      this.isProcessing = false;
      this.showLoading(false);
    }
  },

  // 檢測Markdown語法
  detectMarkdown: function(content) {
    if (!content || typeof content !== 'string') return false;
    return /(\*\*|__|\*|_|##|###|```|---|>|!\[|\[|\|-)/.test(content);
  },
  
  // 更新當前對話標題（僅UI更新）
  updateCurrentChatTitle: function(message) {
    if (!message) return;
    
    const currentChatTitle = document.getElementById('currentChatTitle');
    if (currentChatTitle && currentChatTitle.textContent === 'AI助手已就緒') {
      const title = message.length > 20 ? message.substring(0, 20) + '...' : message;
      currentChatTitle.textContent = title;
    }
  },
  
  // 生成唯一的訊息 ID
  generateMessageId: function() {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  },
  
  // 嘗試重新連接 - 使用統一API健康檢查
  retryConnection: function() {
    const retryMessageId = this.generateMessageId();
    
    if (MedApp.chat && MedApp.chat.display && typeof MedApp.chat.display.appendMessage === 'function') {
      MedApp.chat.display.appendMessage('🔄 正在嘗試重新連接統一API...', 'bot', false, retryMessageId, false);
    }
    
    fetch('/chat/health', { 
      method: 'GET',
      headers: {
        'X-CSRFToken': MedApp.config.csrfToken
      }
    })
    .then(response => {
      const successMessageId = this.generateMessageId();
      if (response.ok) {
        if (MedApp.chat && MedApp.chat.display && typeof MedApp.chat.display.appendMessage === 'function') {
          MedApp.chat.display.appendMessage('✅ 已重新連接到統一API伺服器', 'bot', false, successMessageId, false);
        }
      } else {
        if (MedApp.chat && MedApp.chat.display && typeof MedApp.chat.display.appendMessage === 'function') {
          MedApp.chat.display.appendMessage('❌ 無法連接到統一API，請稍後再試', 'bot', false, successMessageId, false);
        }
      }
    })
    .catch(error => {
      const errorMessageId = this.generateMessageId();
      if (MedApp.chat && MedApp.chat.display && typeof MedApp.chat.display.appendMessage === 'function') {
        MedApp.chat.display.appendMessage(`❌ 重新連接統一API失敗：${error.message}`, 'bot', false, errorMessageId, false);
      }
    });
  },
  
  // 創建新對話 - 使用統一API
  createNewChat: async function() {
    if (this.isProcessing) return;
    
    this.isProcessing = true;
    this.showLoading(true);
    
    try {
      // 生成新的聊天 ID
      const newChatId = Date.now().toString();
      
      // 向統一API發送創建新對話請求
      const response = await fetch('/api/conversations/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': MedApp.config.csrfToken
        },
        body: JSON.stringify({ 
          chat_id: newChatId,
          session_id: this.getSessionId(),
          metadata: {
            created_by: 'new_chat_button',
            timestamp: new Date().toISOString()
          }
        })
      });
      
      if (response.ok) {
        // 設置新的聊天 ID
        MedApp.state.currentChatId = newChatId;
        
        // 清空聊天容器
        this.clearChatDisplay();
        
        // 顯示歡迎消息
        this.showWelcomeMessage();
        
        // 移除所有聊天項目的活動狀態
        this.clearActiveChatStates();
        
        // 更新聊天標題
        this.updateChatTitle('AI助手已就緒');
        
        // 清空輸入框
        this.clearInput();
        
        // 刷新聊天歷史列表（延遲執行，避免阻塞UI）
        setTimeout(() => {
          if (MedApp.chat && MedApp.chat.history && typeof MedApp.chat.history.fetchAllChatHistory === 'function') {
            MedApp.chat.history.fetchAllChatHistory();
          }
        }, 200);
        
        MedApp.log('已通過統一API創建新對話: ' + newChatId, 'info');
        
      } else {
        let errorData = {};
        try {
          errorData = await response.json();
        } catch (e) {
          // 如果無法解析JSON，使用預設錯誤
        }
        throw new Error(errorData.error || '統一API創建對話失敗');
      }
      
    } catch (error) {
      MedApp.log(`無法通過統一API創建新對話: ${error.message}`, 'error');
      
      // 降級處理：即使創建失敗，也允許用戶開始新對話
      const fallbackChatId = Date.now().toString();
      MedApp.state.currentChatId = fallbackChatId;
      
      this.clearChatDisplay();
      this.showWelcomeMessage();
      
      // 顯示錯誤提示
      const errorMessageId = this.generateMessageId();
      setTimeout(() => {
        if (MedApp.chat && MedApp.chat.display && typeof MedApp.chat.display.appendMessage === 'function') {
          MedApp.chat.display.appendMessage(
            '⚠️ 通過統一API創建新對話時遇到問題，但您仍可以繼續使用', 
            'bot', 
            false, 
            errorMessageId, 
            false
          );
        }
      }, 500);
      
    } finally {
      this.isProcessing = false;
      this.showLoading(false);
    }
  },
  
  // UI 控制輔助函數
  clearChatDisplay: function() {
    if (this.elements.container) {
      this.elements.container.innerHTML = '';
    }
  },
  
  showWelcomeMessage: function() {
    if (this.elements.welcomeMessage) {
      this.elements.welcomeMessage.style.display = 'block';
    }
  },
  
  clearActiveChatStates: function() {
    const chatItems = document.querySelectorAll('#chatHistoryList li');
    if (chatItems) {
      chatItems.forEach(item => {
        item.classList.remove('active');
      });
    }
  },
  
  updateChatTitle: function(title) {
    const currentChatTitle = document.getElementById('currentChatTitle');
    if (currentChatTitle && title) {
      currentChatTitle.textContent = title;
    }
  },
  
  clearInput: function() {
    if (this.elements.inputField) {
      this.elements.inputField.value = '';
      this.elements.inputField.focus();
    }
  },
  
  // 獲取會話 ID
  getSessionId: function() {
    // 優先使用當前聊天ID，然後是sessionStorage，最後生成匿名ID
    return MedApp.state.currentChatId || 
           sessionStorage.getItem('sessionId') || 
           (() => {
             const anonymousId = 'anonymous_' + Date.now();
             try {
               sessionStorage.setItem('sessionId', anonymousId);
             } catch (e) {
               // 如果sessionStorage不可用，直接返回匿名ID
               console.warn('無法訪問sessionStorage:', e);
             }
             return anonymousId;
           })();
  },
  
  // 獲取當前對話狀態
  getCurrentChatState: function() {
    return {
      chatId: MedApp.state.currentChatId,
      isProcessing: this.isProcessing,
      hasMessages: this.elements.container && this.elements.container.children.length > 0
    };
  }
};