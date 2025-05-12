/**
 * chat-core.js - 聊天核心功能
 * 負責聊天功能的主要初始化和核心操作
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
  
  // 初始化聊天功能
  init: function() {
    this.initElements();
    this.bindEvents();
    
    // 初始化聊天 ID
    if (!MedApp.state.currentChatId) {
      MedApp.state.currentChatId = Date.now().toString();
    }
    
    MedApp.log('聊天核心模組初始化完成', 'info');
  },
  
  // 初始化DOM元素引用
  initElements: function() {
    this.elements.container = document.getElementById('chatContainer');
    this.elements.welcomeMessage = document.querySelector('.welcome-message');
    this.elements.inputField = document.getElementById('userInput');
    this.elements.sendButton = document.getElementById('sendButton');
    this.elements.progressBar = document.getElementById('progressBar');
    
    // 確保輸入欄位獲得焦點
    if (this.elements.inputField) {
      this.elements.inputField.focus();
    }
  },
  
  // 綁定事件處理
  bindEvents: function() {
    // 送出按鈕點擊事件
    if (this.elements.sendButton) {
      this.elements.sendButton.addEventListener('click', () => {
        const userMessage = this.elements.inputField.value.trim();
        if (userMessage) {
          this.sendMessage(userMessage);
        }
      });
    }
    
    // 輸入欄位按 Enter 鍵事件
    if (this.elements.inputField) {
      this.elements.inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
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
  },
  
  // 送出訊息
  sendMessage: async function(message, locationInfo = null) {
    if (!message || !message.trim()) return;
    
    // 使用傳入的位置信息或全局儲存的位置
    const location = locationInfo || MedApp.state.selectedLocation;
    
    // 確保有聊天 ID
    if (!MedApp.state.currentChatId) {
      MedApp.state.currentChatId = Date.now().toString();
    }
    
    // 顯示用戶消息
    MedApp.chat.display.appendMessage(message, 'user');
    
    // 儲存到聊天歷史
    MedApp.chat.history.saveMessageToStorage(MedApp.state.currentChatId, message, 'user');
    
    // 如果歡迎消息仍然顯示，添加到歷史記錄
    if (this.elements.welcomeMessage && this.elements.welcomeMessage.style.display !== 'none') {
      MedApp.chat.history.addToHistory(message, MedApp.state.currentChatId);
    }
    
    // 清空輸入欄位
    this.elements.inputField.value = '';
    
    // 顯示載入中
    this.showLoading(true);
    
    try {
      // 發送請求到服務器
      const response = await fetch(MedApp.config.apiRoot || '/chat/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': MedApp.config.csrfToken
        },
        body: JSON.stringify({
          message: message,
          chat_id: MedApp.state.currentChatId,
          location_info: location
        })
      });
      
      // 隱藏載入中
      this.showLoading(false);
      
      if (!response.ok) {
        throw new Error(`伺服器回應錯誤: ${response.status}`);
      }
      
      // 解析回應資料
      const data = await response.json();
      
      // 取得回應文本
      const reply = typeof data === 'string' ? data : (data.output || '（伺服器沒有回傳內容）');
      
      // 顯示回應
      MedApp.chat.display.appendMessage(reply, 'bot');
      
      // 儲存到聊天歷史
      MedApp.chat.history.saveMessageToStorage(MedApp.state.currentChatId, reply, 'bot');
      
      // 處理位置資訊
      if (data.location && data.location.coordinates) {
        MedApp.maps.core.handleLocationResponse(data.location);
      }
      
      // 處理醫院資訊
      if (data.data && Array.isArray(data.data.results) && data.data.results.length > 0) {
        MedApp.maps.hospital.displayHospitals(data.data.results, location);
      }
      
    } catch (error) {
      this.showLoading(false);
      MedApp.log(`發送訊息錯誤: ${error.message}`, 'error');
      
      // 顯示錯誤訊息
      MedApp.chat.display.appendMessage(`無法連線到伺服器。錯誤: ${error.message}`, 'bot');
      
      // 嘗試重新連接
      setTimeout(() => {
        MedApp.chat.display.appendMessage('正在嘗試重新連接...', 'bot');
        this.retryConnection();
      }, 3000);
    }
  },
  
  // 嘗試重新連接
  retryConnection: function() {
    fetch(MedApp.config.apiRoot || '/chat/', { method: 'GET' })
      .then(response => {
        if (response.ok) {
          MedApp.chat.display.appendMessage('已重新連接到伺服器', 'bot');
        } else {
          MedApp.chat.display.appendMessage('無法連接到伺服器，請稍後再試', 'bot');
        }
      })
      .catch(error => {
        MedApp.chat.display.appendMessage(`重新連接失敗：${error.message}`, 'bot');
      });
  },
  
  // 創建新對話
  createNewChat: function() {
    // 生成新的聊天 ID
    MedApp.state.currentChatId = Date.now().toString();
    
    // 清空聊天容器
    if (this.elements.container) {
      this.elements.container.innerHTML = '';
    }
    
    // 顯示歡迎消息
    if (this.elements.welcomeMessage) {
      this.elements.welcomeMessage.style.display = 'block';
    }
    
    // 移除所有聊天項目的活動狀態
    document.querySelectorAll('#chatHistoryList li').forEach(item => {
      item.classList.remove('active');
    });
    
    // 更新聊天標題
    const currentChatTitle = document.getElementById('currentChatTitle');
    if (currentChatTitle) {
      currentChatTitle.textContent = 'AI助手已就緒';
    }
    
    // 清空輸入框
    if (this.elements.inputField) {
      this.elements.inputField.value = '';
    }
    
    // 向伺服器發送新對話請求
    fetch(`${MedApp.config.apiRoot || '/'}chat/new/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': MedApp.config.csrfToken
      },
      body: JSON.stringify({ chat_id: MedApp.state.currentChatId })
    }).catch(error => MedApp.log(`無法創建新對話: ${error.message}`, 'error'));
    
    MedApp.log('已創建新對話', 'info');
  }
};