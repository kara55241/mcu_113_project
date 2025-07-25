/**
 * chat-history.js - 統一使用 feedback_graph API 的聊天歷史管理
 * 所有操作都透過統一的 API 端點，移除本地存儲依賴
 */

MedApp.chat.history = {
    // DOM 元素引用
    elements: {
      chatHistoryList: null,
      currentChatTitle: null
    },
    
    // 緩存已加載的對話（僅會話級別緩存）
    loadedChats: new Map(),
    loadedMessages: new Map(),
    
    // 加載狀態追蹤
    isLoading: false,
    
    // 初始化
    init: function() {
      this.initElements();
      this.fetchAllChatHistory();
      
      MedApp.log('聊天歷史模組初始化完成 (統一 feedback_graph)', 'info');
    },
    
    // 初始化DOM元素引用
    initElements: function() {
      this.elements.chatHistoryList = document.getElementById('chatHistoryList');
      this.elements.currentChatTitle = document.getElementById('currentChatTitle');
    },
    
    // 創建新對話（統一 API）
    createNewChat: async function() {
      const chatId = Date.now().toString();
      
      try {
        const response = await fetch(`${MedApp.config.apiRoot || '/'}api/conversations/`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': MedApp.config.csrfToken
          },
          body: JSON.stringify({ 
            chat_id: chatId,
            session_id: this.getSessionId(),
            metadata: {
              created_by: 'new_chat_button',
              timestamp: new Date().toISOString()
            }
          })
        });
        
        if (response.ok) {
          MedApp.state.currentChatId = chatId;
          this.clearChatDisplay();
          this.refreshChatHistory();
          MedApp.log('新對話已創建: ' + chatId, 'info');
          return chatId;
        } else {
          throw new Error('創建對話失敗');
        }
      } catch (error) {
        MedApp.log('創建新對話錯誤: ' + error.message, 'error');
        // 降級處理：僅在前端創建
        MedApp.state.currentChatId = chatId;
        this.clearChatDisplay();
        return chatId;
      }
    },
    
    // 保存訊息到統一資料庫（唯一入口）
    saveMessage: async function(chatId, content, sender, messageId = null) {
      if (!messageId) {
        messageId = this.generateMessageId();
      }
      
      // 防止重複保存
      const messageKey = `${chatId}-${content}-${sender}`;
      if (this.loadedMessages.has(messageKey)) {
        MedApp.log('訊息已存在，跳過保存', 'debug');
        return messageId;
      }
      
      const messageData = {
        message_id: messageId,
        chat_id: chatId,
        content: content,
        sender: sender,
        timestamp: new Date().toISOString(),
        session_id: this.getSessionId(),
        metadata: {}
      };
      
      try {
        const response = await fetch('/api/messages/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': this.getCSRFToken()
          },
          body: JSON.stringify(messageData)
        });
        
        if (response.ok) {
          const result = await response.json();
          // 標記為已保存
          this.loadedMessages.set(messageKey, messageId);
          MedApp.log('訊息已保存到統一資料庫: ' + messageId, 'debug');
          
          // 如果是用戶訊息，更新對話列表
          if (sender === 'user') {
            this.updateChatInHistory(chatId, content);
          }
          
          return result.message_id || messageId;
        } else {
          throw new Error(`保存失敗: ${response.status}`);
        }
      } catch (error) {
        MedApp.log('保存訊息到統一資料庫失敗: ' + error.message, 'error');
        return messageId;
      }
    },
    
    // 從統一資料庫獲取所有聊天歷史
    fetchAllChatHistory: async function() {
      if (this.isLoading) return;
      
      this.isLoading = true;
      this.showLoadingIndicator(true);
      
      try {
        const response = await fetch(`${MedApp.config.apiRoot || '/'}chat/history/`, {
          method: 'GET',
          headers: {
            'X-CSRFToken': MedApp.config.csrfToken
          }
        });
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // 清空現有列表
        if (this.elements.chatHistoryList) {
          this.elements.chatHistoryList.innerHTML = '';
        }
        
        if (data.chats && data.chats.length > 0) {
          // 按時間排序
          const sortedChats = data.chats.sort((a, b) => {
            return new Date(b.last_message_at || b.created_at) - 
                   new Date(a.last_message_at || a.created_at);
          });
          
          // 渲染對話列表
          sortedChats.forEach(chat => {
            this.addChatToList(chat);
            // 緩存對話信息
            this.loadedChats.set(chat.chat_id, chat);
          });
          
          // 自動選擇最新對話
          if (sortedChats.length > 0 && !MedApp.state.currentChatId) {
            const latestChatId = sortedChats[0].chat_id;
            if (latestChatId && latestChatId !== 'undefined') {
              this.loadChatHistory(latestChatId);
            }
          }
        } else {
          this.showEmptyState();
        }
        
      } catch (error) {
        MedApp.log('獲取聊天歷史失敗: ' + error.message, 'error');
        this.showErrorState(error.message);
      } finally {
        this.isLoading = false;
        this.showLoadingIndicator(false);
      }
    },
    
    // 載入特定對話的訊息
    loadChatHistory: async function(chatId) {
      if (this.isLoading) return;
      
      MedApp.state.currentChatId = chatId;
      this.setActiveChat(chatId);
      this.clearChatDisplay();
      this.showLoadingIndicator(true);
      
      try {
        const response = await fetch(`${MedApp.config.apiRoot || '/'}chat/history/${chatId}/`, {
          method: 'GET',
          headers: {
            'X-CSRFToken': MedApp.config.csrfToken
          }
        });
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // 更新對話標題
        if (data.chat && data.chat.title) {
          this.updateChatTitle(data.chat.title);
        }
        
        // 渲染訊息
        if (data.messages && data.messages.length > 0) {
          data.messages.forEach(msg => {
            // 檢測並處理Markdown
            const isMarkdown = this.detectMarkdown(msg.content);
            if (MedApp.chat.display && MedApp.chat.display.appendMessage) {
              MedApp.chat.display.appendMessage(msg.content, msg.sender, isMarkdown, msg.message_id, true);
            }
            
            // 緩存訊息
            const messageKey = `${chatId}-${msg.content}-${msg.sender}`;
            this.loadedMessages.set(messageKey, msg.message_id);
          });
        } else {
          // 顯示歡迎訊息
          this.showWelcomeMessage();
        }
        
      } catch (error) {
        MedApp.log('載入對話歷史失敗: ' + error.message, 'error');
        if (MedApp.chat.display && MedApp.chat.display.appendMessage) {
          MedApp.chat.display.appendMessage('載入對話歷史時發生錯誤', 'bot', false, null, true);
        }
      } finally {
        this.showLoadingIndicator(false);
      }
    },
    
    // 刪除對話
    deleteChat: async function(chatId, listItem) {
      if (!confirm("確定要刪除此對話嗎？此操作無法復原。")) {
        return;
      }
      
      // 立即從UI移除，提供快速反饋
      if (listItem) {
        listItem.remove();
      }
      
      // 從緩存移除
      this.loadedChats.delete(chatId);
      
      // 如果是當前對話，創建新對話
      if (chatId === MedApp.state.currentChatId) {
        this.createNewChat();
      }
      
      try {
        const response = await fetch(`${MedApp.config.apiRoot || '/'}chat/history/${chatId}/`, {
          method: 'DELETE',
          headers: {
            'X-CSRFToken': MedApp.config.csrfToken,
            'Content-Type': 'application/json'
          }
        });
        
        if (response.ok) {
          const result = await response.json();
          MedApp.log('對話已從統一資料庫刪除: ' + chatId, 'info');
          MedApp.log(`刪除統計: 對話 ${result.deleted_chats}, 訊息 ${result.deleted_messages}, 回饋 ${result.deleted_feedbacks}`, 'info');
        } else {
          MedApp.log('從統一資料庫刪除對話失敗: ' + response.status, 'warn');
          // 如果刪除失敗，重新載入列表
          this.fetchAllChatHistory();
        }
      } catch (error) {
        MedApp.log('刪除對話請求失敗: ' + error.message, 'error');
        this.fetchAllChatHistory();
      }
    },
    
    // 添加對話到列表
    addChatToList: function(chat) {
      if (!this.elements.chatHistoryList) return;
      
      const li = document.createElement('li');
      li.dataset.chatId = chat.chat_id;
      li.title = chat.title || '未命名對話';
      
      const displayTitle = chat.title || '未命名對話';
      const truncatedTitle = displayTitle.length > 20 ? 
                           displayTitle.substring(0, 20) + '...' : 
                           displayTitle;
      
      li.innerHTML = `
        <div class="chat-item-container">
          <div class="chat-item-content">
            <i class="fas fa-comment-dots"></i>
            <span class="chat-title">${truncatedTitle}</span>
          </div>
          <button class="delete-chat" title="刪除對話" aria-label="刪除對話">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      `;
      
      // 綁定事件
      li.querySelector('.chat-item-content').addEventListener('click', () => {
        this.loadChatHistory(chat.chat_id);
      });
      
      li.querySelector('.delete-chat').addEventListener('click', (event) => {
        event.stopPropagation();
        this.deleteChat(chat.chat_id, li);
      });
      
      this.elements.chatHistoryList.appendChild(li);
    },
    
    // 更新對話歷史中的對話
    updateChatInHistory: function(chatId, message) {
      // 先更新UI
      const chatItem = document.querySelector(`#chatHistoryList li[data-chat-id="${chatId}"]`);
      if (chatItem) {
        const titleElement = chatItem.querySelector('.chat-title');
        if (titleElement) {
          const truncatedTitle = message.length > 20 ? 
                                message.substring(0, 20) + '...' : 
                                message;
          titleElement.textContent = truncatedTitle;
          chatItem.title = message;
        }
        
        // 移到列表頂部
        if (this.elements.chatHistoryList.firstChild !== chatItem) {
          this.elements.chatHistoryList.insertBefore(chatItem, this.elements.chatHistoryList.firstChild);
        }
      } else {
        // 如果不存在，添加新的對話項目
        const newChat = {
          chat_id: chatId,
          title: message,
          created_at: new Date().toISOString()
        };
        this.addChatToList(newChat);
      }
    },
    
    // 工具函數
    generateMessageId: function() {
      return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    },
    
    getSessionId: function() {
      return MedApp.state.currentChatId || 
             sessionStorage.getItem('sessionId') || 
             'anonymous_' + Date.now();
    },
    
    getCSRFToken: function() {
      return document.querySelector('[name=csrf-token]')?.content ||
             document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
             MedApp.config.csrfToken;
    },
    
    detectMarkdown: function(content) {
      return /(\*\*|__|\*|_|##|###|```|---|>|!\[|\[|\|-)/.test(content);
    },
    
    // UI 控制函數
    clearChatDisplay: function() {
      const chatContainer = document.getElementById('chatContainer');
      if (chatContainer) {
        chatContainer.innerHTML = '';
      }
      
      const welcomeMessage = document.querySelector('.welcome-message');
      if (welcomeMessage) {
        welcomeMessage.style.display = 'none';
      }
    },
    
    showWelcomeMessage: function() {
      const welcomeMessage = document.querySelector('.welcome-message');
      if (welcomeMessage) {
        welcomeMessage.style.display = 'block';
      }
    },
    
    setActiveChat: function(chatId) {
      // 移除所有活動狀態
      document.querySelectorAll('#chatHistoryList li').forEach(item => {
        item.classList.remove('active');
      });
      
      // 設置當前活動狀態
      const currentItem = document.querySelector(`#chatHistoryList li[data-chat-id="${chatId}"]`);
      if (currentItem) {
        currentItem.classList.add('active');
      }
    },
    
    updateChatTitle: function(title) {
      if (this.elements.currentChatTitle) {
        this.elements.currentChatTitle.textContent = title || 'AI助手已就緒';
      }
    },
    
    showLoadingIndicator: function(show) {
      // 可以在這裡添加載入指示器
      if (MedApp.chat.core && MedApp.chat.core.showLoading) {
        MedApp.chat.core.showLoading(show);
      }
    },
    
    showEmptyState: function() {
      if (this.elements.chatHistoryList) {
        this.elements.chatHistoryList.innerHTML = `
          <li class="empty-state">
            <div style="text-align: center; padding: 20px; color: var(--text-secondary);">
              <i class="fas fa-comments" style="font-size: 24px; margin-bottom: 10px;"></i>
              <p>還沒有對話記錄</p>
              <p style="font-size: 14px;">開始新對話來建立歷史記錄</p>
            </div>
          </li>
        `;
      }
    },
    
    showErrorState: function(error) {
      if (this.elements.chatHistoryList) {
        this.elements.chatHistoryList.innerHTML = `
          <li class="error-state">
            <div style="text-align: center; padding: 20px; color: var(--warning-color);">
              <i class="fas fa-exclamation-triangle" style="font-size: 24px; margin-bottom: 10px;"></i>
              <p>載入歷史記錄失敗</p>
              <p style="font-size: 14px;">${error}</p>
              <button onclick="MedApp.chat.history.fetchAllChatHistory()" 
                      style="margin-top: 10px; padding: 5px 15px; border: 1px solid var(--border-color); background: var(--background-lighter); color: var(--text-color); border-radius: 4px; cursor: pointer;">
                重試
              </button>
            </div>
          </li>
        `;
      }
    },
    
    refreshChatHistory: function() {
      this.fetchAllChatHistory();
    }
  };