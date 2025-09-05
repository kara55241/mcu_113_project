/**
 * chat-history.js - 聊天歷史管理
 * 負責處理對話歷史的存儲、加載和管理
 */

MedApp.chat.history = {
    // DOM 元素引用
    elements: {
      chatHistoryList: null,
      currentChatTitle: null
    },
    
    // 初始化
    init: function() {
      this.initElements();
      this.fetchAllChatHistory();
      
      MedApp.log('聊天歷史模組初始化完成', 'info');
    },
    
    // 初始化DOM元素引用
    initElements: function() {
      this.elements.chatHistoryList = document.getElementById('chatHistoryList');
      this.elements.currentChatTitle = document.getElementById('currentChatTitle');
    },
    
    // 添加對話到歷史列表
    addToHistory: function(message, chatId = null) {
      // 如果沒有提供 chatId，則使用當前的
      if (!chatId) {
        if (!MedApp.state.currentChatId) {
          MedApp.state.currentChatId = Date.now().toString();
        }
        chatId = MedApp.state.currentChatId;
      }
      
      // 檢查此聊天ID是否已在列表中
      const existingItem = document.querySelector(`#chatHistoryList li[data-chat-id="${chatId}"]`);
      if (existingItem) {
        // 更新現有項目
        existingItem.querySelector('.chat-title').textContent = message.length > 20 ? message.substring(0, 20) + '...' : message;
        existingItem.title = message;
        
        // 移到列表頂部
        if (this.elements.chatHistoryList && this.elements.chatHistoryList.firstChild !== existingItem) {
          this.elements.chatHistoryList.insertBefore(existingItem, this.elements.chatHistoryList.firstChild);
        }
        
        // 更新本地存儲
        this.updateChatInStorage(chatId, message);
        return;
      }
      
      // 創建新的歷史記錄項目
      const now = new Date();
      const dateTime = `${now.getMonth()+1}月${now.getDate()}日 ${now.getHours()}:${now.getMinutes()}`;
      
      const li = document.createElement('li');
      li.dataset.chatId = chatId;
      li.title = `${message} (${dateTime})`;
      
      // 創建 HTML 結構
      li.innerHTML = `
        <div class="chat-item-container">
          <div class="chat-item-content">
            <i class="fas fa-comment-dots"></i>
            <span class="chat-title">${message.length > 20 ? message.substring(0, 20) + '...' : message}</span>
          </div>
          <button class="delete-chat" title="刪除對話" aria-label="刪除對話">
            <i class="fas fa-trash"></i>
          </button>
        </div>
      `;
      
      // 添加點擊事件
      li.querySelector('.chat-item-content').addEventListener('click', () => {
        // 移除所有項目的活動狀態
        document.querySelectorAll('#chatHistoryList li').forEach(item => {
          item.classList.remove('active');
        });
        
        // 添加活動狀態到當前項目
        li.classList.add('active');
        
        // 載入此對話
        this.loadChatHistory(chatId);
      });
      
      // 添加刪除事件
      li.querySelector('.delete-chat').addEventListener('click', (event) => {
        event.stopPropagation(); // 防止觸發對話載入
        this.deleteChat(chatId, li);
      });
      
      // 添加到列表頂部
      if (this.elements.chatHistoryList) {
        if (this.elements.chatHistoryList.firstChild) {
          this.elements.chatHistoryList.insertBefore(li, this.elements.chatHistoryList.firstChild);
        } else {
          this.elements.chatHistoryList.appendChild(li);
        }
      }
      
      // 保存到本地存儲
      this.saveChatToStorage(chatId, message);
    },
    
    // 刪除對話
    deleteChat: function(chatId, listItem) {
      // 確認刪除
      if (!confirm("確定要刪除此對話嗎？")) {
        return;
      }
      
      // 先從界面和本地刪除，提供即時反饋
      // 從列表中刪除
      if (listItem) {
        listItem.remove();
      } else {
        const item = document.querySelector(`#chatHistoryList li[data-chat-id="${chatId}"]`);
        if (item) item.remove();
      }
      
      // 從本地存儲刪除
      let chats = JSON.parse(localStorage.getItem('chats') || '{}');
      if (chats[chatId]) {
        delete chats[chatId];
        localStorage.setItem('chats', JSON.stringify(chats));
      }
      
      // 如果刪除的是當前對話，創建新對話
      if (chatId === MedApp.state.currentChatId) {
        MedApp.chat.core.createNewChat();
      }
      
      // 然後從伺服器刪除 (不等待響應)
      try {
        fetch(`${MedApp.config.apiRoot || '/'}chat/history/${chatId}/`, {
          method: 'DELETE',
          headers: {
            'X-CSRFToken': MedApp.config.csrfToken,
            'Content-Type': 'application/json'
          }
        })
        .then(response => {
          if (response.ok) {
            MedApp.log("對話已從服務器刪除", 'info');
          } else {
            MedApp.log("服務器刪除對話失敗，狀態碼: " + response.status, 'warn');
          }
        })
        .catch(error => {
          MedApp.log("從服務器刪除對話時出錯: " + error.message, 'error');
        });
      } catch (e) {
        MedApp.log("刪除請求執行出錯: " + e.message, 'error');
      }
    },
    
    // 保存聊天到本地存儲
    saveChatToStorage: function(chatId, message) {
      let chats = JSON.parse(localStorage.getItem('chats') || '{}');
      
      if (!chats[chatId]) {
        chats[chatId] = {
          id: chatId,
          title: message,
          lastUpdate: new Date().toISOString(),
          messages: []
        };
      }
      
      localStorage.setItem('chats', JSON.stringify(chats));
    },
    
    // 更新本地存儲中的聊天
    updateChatInStorage: function(chatId, message) {
      let chats = JSON.parse(localStorage.getItem('chats') || '{}');
      
      if (chats[chatId]) {
        chats[chatId].title = message;
        chats[chatId].lastUpdate = new Date().toISOString();
        localStorage.setItem('chats', JSON.stringify(chats));
      }
    },
    
    // 保存消息到本地存儲
    saveMessageToStorage: function(chatId, content, sender) {
      let chats = JSON.parse(localStorage.getItem('chats') || '{}');
      
      if (!chats[chatId]) {
        chats[chatId] = {
          id: chatId,
          title: content.length > 20 ? content.substring(0, 20) + '...' : content,
          lastUpdate: new Date().toISOString(),
          messages: []
        };
      }
      
      // 添加新消息
      chats[chatId].messages.push({
        content: content,
        sender: sender,
        timestamp: new Date().toISOString()
      });
      
      if (sender === 'user') {
        chats[chatId].lastUpdate = new Date().toISOString();
      }
      
      localStorage.setItem('chats', JSON.stringify(chats));
      
      // 更新側邊欄的對話標題
      this.updateChatTitle(chatId, chats[chatId].title);
    },
    
    // 更新側邊欄中的對話標題
    updateChatTitle: function(chatId, title) {
      const chatItem = document.querySelector(`#chatHistoryList li[data-chat-id="${chatId}"]`);
      if (chatItem) {
        const titleElement = chatItem.querySelector('.chat-title');
        if (titleElement) {
          titleElement.textContent = title.length > 20 ? title.substring(0, 20) + '...' : title;
          chatItem.title = title;
        }
      }
    },
    
    // 載入聊天歷史
    loadChatHistory: function(chatId) {
      // 設置當前聊天ID
      MedApp.state.currentChatId = chatId;
      
      // 嘗試從本地存儲載入
      const chats = JSON.parse(localStorage.getItem('chats') || '{}');
      
      if (chats[chatId]) {
        // 更新聊天標題
        if (this.elements.currentChatTitle) {
          this.elements.currentChatTitle.textContent = chats[chatId].title;
        }
        
        // 清空聊天容器
        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
          chatContainer.innerHTML = '';
        }
        
        // 隱藏歡迎消息
        const welcomeMessage = document.querySelector('.welcome-message');
        if (welcomeMessage) {
          welcomeMessage.style.display = 'none';
        }
        
        // 從服務器獲取消息
        MedApp.chat.core.showLoading(true);
        
        fetch(`${MedApp.config.apiRoot || '/'}chat/history/${chatId}/`, {
          method: 'GET',
          headers: {
            'X-CSRFToken': MedApp.config.csrfToken
          }
        })
        .then(response => response.json())
        .then(data => {
          MedApp.chat.core.showLoading(false);
          
          if (data.messages && data.messages.length > 0) {
            // 渲染所有消息
            data.messages.forEach(msg => {
              MedApp.chat.display.appendMessage(msg.content, msg.sender);
              
              // 同步到本地存儲
              if (!chats[chatId].messages.some(m => 
                m.content === msg.content && m.sender === msg.sender
              )) {
                this.saveMessageToStorage(chatId, msg.content, msg.sender);
              }
            });
          } else {
            // 如果服務器沒有數據，嘗試從本地存儲渲染
            this.renderMessagesFromStorage(chatId);
          }
        })
        .catch(error => {
          MedApp.log("載入歷史記錄錯誤: " + error.message, 'error');
          MedApp.chat.core.showLoading(false);
          
          // 從本地存儲渲染
          this.renderMessagesFromStorage(chatId);
        });
      } else {
        MedApp.log("找不到聊天ID: " + chatId, 'error');
        MedApp.chat.display.appendMessage("無法找到此對話的歷史記錄", "bot");
      }
    },
    
    // 從本地存儲渲染消息
    renderMessagesFromStorage: function(chatId) {
      const chats = JSON.parse(localStorage.getItem('chats') || '{}');
      const welcomeMessage = document.querySelector('.welcome-message');
      
      if (chats[chatId] && chats[chatId].messages) {
        if (chats[chatId].messages.length === 0 && welcomeMessage) {
          // 如果沒有消息，顯示歡迎消息
          welcomeMessage.style.display = 'block';
          return;
        }
        
        // 清空聊天容器
        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
          chatContainer.innerHTML = '';
        }
        
        // 渲染所有消息
        chats[chatId].messages.forEach(msg => {
          MedApp.chat.display.appendMessage(msg.content, msg.sender);
        });
      } else if (welcomeMessage) {
        // 如果沒有找到聊天，顯示歡迎消息
        welcomeMessage.style.display = 'block';
      }
    },
    
    // 初始化聊天歷史列表
    initChatHistory: function() {
      // 從本地存儲加載所有聊天
      const chats = JSON.parse(localStorage.getItem('chats') || '{}');
      
      // 按最後更新時間排序
      const sortedChats = Object.values(chats).sort((a, b) => {
        return new Date(b.lastUpdate) - new Date(a.lastUpdate);
      });
      
      // 清空現有列表
      if (this.elements.chatHistoryList) {
        this.elements.chatHistoryList.innerHTML = '';
      
        // 添加到列表
        sortedChats.forEach(chat => {
          const li = document.createElement('li');
          li.dataset.chatId = chat.id;
          li.title = chat.title;
          
          // 添加刪除按鈕和標題
          li.innerHTML = `
            <div class="chat-item-container">
              <div class="chat-item-content">
                <i class="fas fa-comment-dots"></i>
                <span class="chat-title">${chat.title.length > 20 ? chat.title.substring(0, 20) + '...' : chat.title}</span>
              </div>
              <button class="delete-chat" title="刪除對話" aria-label="刪除對話">
                <i class="fas fa-trash"></i>
              </button>
            </div>
          `;
          
          // 添加點擊事件
          li.querySelector('.chat-item-content').addEventListener('click', () => {
            // 移除所有項目的活動狀態
            document.querySelectorAll('#chatHistoryList li').forEach(item => {
              item.classList.remove('active');
            });
            
            // 添加活動狀態到當前項目
            li.classList.add('active');
            
            // 載入此對話
            this.loadChatHistory(chat.id);
          });
          
          // 添加刪除事件
          li.querySelector('.delete-chat').addEventListener('click', (event) => {
            event.stopPropagation(); // 防止觸發對話載入
            this.deleteChat(chat.id, li);
          });
          
          this.elements.chatHistoryList.appendChild(li);
        });
      }
      
      // 加載最新的對話（如果有）
      if (sortedChats.length > 0) {
        const latestChat = sortedChats[0];
        MedApp.state.currentChatId = latestChat.id;
        
        // 標記最新對話為活動狀態
        const latestChatItem = document.querySelector(`#chatHistoryList li[data-chat-id="${latestChat.id}"]`);
        if (latestChatItem) {
          latestChatItem.classList.add('active');
        }
        
        // 加載最新對話
        this.loadChatHistory(latestChat.id);
      }
    },
    
    // 從服務器獲取所有聊天歷史
    fetchAllChatHistory: function() {
      MedApp.chat.core.showLoading(true);
      
      fetch(`${MedApp.config.apiRoot || '/'}chat/history/`, {
        method: 'GET',
        headers: {
          'X-CSRFToken': MedApp.config.csrfToken
        }
      })
      .then(response => response.json())
      .then(data => {
        MedApp.chat.core.showLoading(false);
        
        if (data.chats && data.chats.length > 0) {
          // 同步到本地存儲
          data.chats.forEach(chat => {
            // 檢查本地是否已有此聊天
            let chats = JSON.parse(localStorage.getItem('chats') || '{}');
            if (!chats[chat.id]) {
              // 如果本地沒有，添加到本地存儲
              chats[chat.id] = {
                id: chat.id,
                title: chat.title,
                lastUpdate: chat.timestamp,
                messages: []
              };
              localStorage.setItem('chats', JSON.stringify(chats));
            }
          });
          
          // 重新初始化聊天歷史列表
          this.initChatHistory();
        } else {
          // 即使沒有聊天記錄，也初始化列表（基於本地存儲）
          this.initChatHistory();
        }
      })
      .catch(error => {
        MedApp.log("獲取所有聊天歷史錯誤: " + error.message, 'error');
        MedApp.chat.core.showLoading(false);
        
        // 如果無法從服務器獲取，使用本地存儲初始化
        this.initChatHistory();
      });
    },
    
    // 同步對話歷史到服務器
    syncChatHistory: function() {
      try {
        const chats = JSON.parse(localStorage.getItem('chats') || '{}');
        
        Object.values(chats).forEach(chat => {
          // 對每個聊天記錄嘗試同步
          if (chat.messages && chat.messages.length > 0) {
            // 檢查是否是新對話（無對應的伺服器記錄）
            fetch(`${MedApp.config.apiRoot || '/'}chat/history/${chat.id}/`, {
              method: 'GET',
              headers: {
                'X-CSRFToken': MedApp.config.csrfToken
              }
            })
            .then(response => {
              if (!response.ok && response.status === 404) {
                // 如果對話在伺服器上不存在，創建它
                return fetch(`${MedApp.config.apiRoot || '/'}chat/new/`, {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': MedApp.config.csrfToken
                  },
                  body: JSON.stringify({ chat_id: chat.id })
                });
              }
              return null;
            })
            .catch(error => {
              MedApp.log("同步對話時出錯: " + error.message, 'error');
            });
          }
        });
      } catch (e) {
        MedApp.log("同步對話歷史時發生錯誤: " + e.message, 'error');
      }
    }
  }