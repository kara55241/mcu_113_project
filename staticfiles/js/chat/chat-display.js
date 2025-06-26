/**
 * chat-display.js - 聊天訊息顯示功能
 * 負責處理聊天介面上的訊息渲染和顯示
 */

MedApp.chat.display = {
    // DOM 元素引用
    elements: {
      chatContainer: null,
      welcomeMessage: null
    },
    
    // 初始化
    init: function() {
      this.initElements();
      this.setupMarkdownParser();
      
      MedApp.log('聊天顯示模組初始化完成', 'info');
    },
    
    // 初始化 DOM 元素引用
    initElements: function() {
      this.elements.chatContainer = document.getElementById('chatContainer');
      this.elements.welcomeMessage = document.querySelector('.welcome-message');
    },
    
    // 設置Markdown解析器配置
    setupMarkdownParser: function() {
      if (typeof marked !== 'undefined') {
        marked.setOptions({
          breaks: true,           // 允許換行
          gfm: true,              // GitHub 風格 Markdown
          headerIds: false,       // 不為標題添加 ID
          mangle: false,          // 不轉義內聯 HTML
          pedantic: false,        // 不糾正原始 markdown 中的細微錯誤
          sanitize: false,        // 允許 HTML 標籤
          smartLists: true,       // 使用更智能的列表行為
          smartypants: true,      // 使用"智能"排版標點
          xhtml: true             // 使用自閉合標籤
        });
        
        // 自定義渲染器
        const renderer = new marked.Renderer();
        
        // 增強表格渲染
        renderer.table = function(header, body) {
          return '<div class="table-container"><table class="markdown-table">' +
            '<thead>' + header + '</thead>' +
            '<tbody>' + body + '</tbody>' +
            '</table></div>';
        };
        
        // 增強列表渲染
        renderer.list = function(body, ordered, start) {
          const type = ordered ? 'ol' : 'ul';
          const startAttr = (ordered && start !== 1) ? (' start="' + start + '"') : '';
          const className = ordered ? 'markdown-ordered-list' : 'markdown-unordered-list';
          return '<' + type + startAttr + ' class="' + className + '">' + body + '</' + type + '>';
        };
        
        // 增強代碼塊渲染
        renderer.code = function(code, infostring, escaped) {
          return '<pre class="markdown-code-block"><code class="language-' + 
                 (infostring || 'text') + '">' + 
                 (escaped ? code : this.escapeHtml(code)) + 
                 '</code></pre>';
        };
        
        // 使用自定義渲染器
        marked.use({ renderer });
      }
    },
    
    // 生成唯一的訊息 ID
    generateMessageId: function() {
      return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    },

    // 添加消息到聊天界面（主要函數）
    appendMessage: function(content, sender = 'user', isMarkdown = false, messageId = null) {
      if (!this.elements.chatContainer) return;
      
      // 隱藏歡迎訊息
      if (this.elements.welcomeMessage && sender === 'user') {
        this.elements.welcomeMessage.style.display = 'none';
      }
      
      // 生成或使用提供的訊息 ID
      if (!messageId) {
        messageId = this.generateMessageId();
      }
      
      const messageDiv = document.createElement('div');
      messageDiv.classList.add('message', sender);
      messageDiv.setAttribute('data-message-id', messageId);
      
      // 處理內容 - 確保內容是字符串
      if (typeof content !== 'string') {
        content = String(content);
      }
      
      const contentDiv = document.createElement('div');
      contentDiv.classList.add('message-content');
      
      if (sender === 'bot') {
        // 處理機器人訊息的 Markdown
        if (isMarkdown || this.hasMarkdownSyntax(content)) {
          try {
            // 預處理內容
            content = this.preprocessMarkdown(content);
            
            // 使用 marked.js 解析
            if (typeof window.marked !== 'undefined') {
              contentDiv.innerHTML = window.marked.parse(content);
            } else {
              contentDiv.textContent = content;
            }
            
            // 後處理
            this.postProcessMarkdown(contentDiv);
          } catch (error) {
            console.error('Markdown解析錯誤:', error);
            contentDiv.textContent = content;
          }
        } else {
          // 處理可能的HTML實體
          if (content.includes('&lt;') || content.includes('&gt;')) {
            try {
              const decoded = this.decodeHtmlEntities(content);
              contentDiv.innerHTML = decoded;
            } catch (e) {
              console.warn('HTML實體解碼失敗:', e);
              contentDiv.textContent = content;
            }
          } else {
            contentDiv.textContent = content;
          }
        }
      } else {
        // 用戶消息使用純文本處理
        contentDiv.textContent = content;
      }
      
      // 添加時間戳
      const timeSpan = document.createElement('span');
      timeSpan.classList.add('message-time');
      const now = new Date();
      timeSpan.textContent = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
      
      messageDiv.appendChild(contentDiv);
      messageDiv.appendChild(timeSpan);
      
      this.elements.chatContainer.appendChild(messageDiv);
      
      // 為機器人訊息添加回饋按鈕（延遲執行確保 DOM 已渲染）
      if (sender === 'bot') {
        setTimeout(() => {
          this.addFeedbackButtons(messageDiv, messageId);
          // 同時保存訊息到 Neo4j
          this.saveMessageToNeo4j(messageId, content, sender);
        }, 100);
      } else {
        // 用戶訊息也保存到 Neo4j
        this.saveMessageToNeo4j(messageId, content, sender);
      }
      
      this.scrollToBottom();
      return messageDiv;
    },

    // 檢查是否包含Markdown語法
    hasMarkdownSyntax: function(content) {
      return /(\*\*|__|\*|_|##|###|```|---|>|!\[|\[|\|-)/.test(content);
    },

    // 添加一個HTML實體解碼函數
    decodeHtmlEntities: function(str) {
      if (!str) return '';
      
      // 使用textarea元素的原生HTML解碼能力
      const textarea = document.createElement('textarea');
      textarea.innerHTML = str;
      return textarea.value;
    },
        
    // 預處理Markdown內容
    preprocessMarkdown: function(content) {
      // 1. 修復加粗語法：***XXX:** 改為 **XXX:**
      content = content.replace(/\*\*\*(.*?):\*\*/g, '**$1:**');
      
      // 2. 確保列表項目前有空行
      content = content.replace(/([^\n])\n(\s*[-*+]\s)/g, '$1\n\n$2');
      content = content.replace(/([^\n])\n(\s*\d+\.\s)/g, '$1\n\n$2');
      
      // 3. 處理知識圖譜查詢
      content = content.replace(/(🔍\s*\*\*知識圖譜查詢過程：\*\*[\s\S]*?)(?=##|$)/g, 
          '<div class="knowledge-graph-process">$1</div>');
      
      // 4. 標準化標題前的空行
      content = content.replace(/([^\n])(\n#+\s)/g, '$1\n\n$2');
      
      // 5. 修復錯誤的列表嵌套
      content = content.replace(/(\* .+\n)(\* )/g, '$1\n$2');
      
      // 6. 處理可能的引用區塊
      content = content.replace(/\n> /g, '\n\n> ');
      
      // 7. 處理表格格式
      content = content.replace(/\|[\s-]+\|/g, function(match) {
        return match.replace(/\s+/g, '');
      });
      
      // 8. 確保代碼塊前後有空行
      content = content.replace(/([^\n])\n```/g, '$1\n\n```');
      content = content.replace(/```\n([^\n])/g, '```\n\n$1');
      
      // 9. 處理特殊符號表示法
      content = content.replace(/\*\*\*/g, '**');  // 修正過多的星號
      
      // 10. 新增：修復可能的多層嵌套列表格式
      content = content.replace(/(\s{2,}[-*+]\s)/g, '\n  $1');
      
      return content;
    },
    
    // Markdown解析後的後處理
    postProcessMarkdown: function(element) {
      // 1. 處理表格，添加響應式容器
      const tables = element.querySelectorAll('table:not(.markdown-table)');
      tables.forEach(table => {
        if (!table.parentElement.classList.contains('table-container')) {
          const container = document.createElement('div');
          container.className = 'table-container';
          table.parentNode.insertBefore(container, table);
          container.appendChild(table);
          table.classList.add('markdown-table');
        }
      });
      
      // 2. 確保列表正確顯示
      const lists = element.querySelectorAll('ul:not(.markdown-unordered-list), ol:not(.markdown-ordered-list)');
      lists.forEach(list => {
        if (list.tagName === 'UL') {
          list.classList.add('markdown-unordered-list');
        } else {
          list.classList.add('markdown-ordered-list');
        }
      });
      
      // 3. 處理代碼塊
      const preBlocks = element.querySelectorAll('pre:not(.markdown-code-block)');
      preBlocks.forEach(pre => {
        pre.classList.add('markdown-code-block');
        const code = pre.querySelector('code');
        if (code) {
          if (!code.classList.contains('language-')) {
            code.classList.add('language-text');
          }
        }
      });
      
      // 4. 確保所有鏈接在新窗口打開
      const links = element.querySelectorAll('a');
      links.forEach(link => {
        link.setAttribute('target', '_blank');
        link.setAttribute('rel', 'noopener noreferrer');
      });
      
      // 5. 將純文本的列表標記轉換為真正的列表
      this.convertTextListsToHTML(element);
    },
    
    // 將純文本的列表標記轉換為HTML列表
    convertTextListsToHTML: function(element) {
      // 查找可能包含純文本列表的段落
      const paragraphs = element.querySelectorAll('p');
      paragraphs.forEach(p => {
        const text = p.innerHTML;
        
        // 檢查是否包含列表標記模式
        if (/^(\d+\.\s|\*\s|-\s|\+\s)/.test(text)) {
          // 檢查是否為有序列表
          const isOrdered = /^\d+\.\s/.test(text);
          
          // 分割行
          const lines = text.split('<br>');
          
          // 檢查是否所有行都匹配列表模式
          const allLinesAreList = lines.every(line => 
            /^(\d+\.\s|\*\s|-\s|\+\s)/.test(line.trim()));
          
          if (allLinesAreList) {
            // 創建新的列表元素
            const list = document.createElement(isOrdered ? 'ol' : 'ul');
            list.className = isOrdered ? 'markdown-ordered-list' : 'markdown-unordered-list';
            
            // 處理每一行
            lines.forEach(line => {
              const itemText = line.replace(/^(\d+\.\s|\*\s|-\s|\+\s)/, '').trim();
              const li = document.createElement('li');
              li.innerHTML = itemText;
              list.appendChild(li);
            });
            
            // 替換原始段落
            p.parentNode.replaceChild(list, p);
          }
        }
      });
    },
    
    // 顯示醫院資訊
    displayHospitalResults: function(hospitals, location) {
      if (!hospitals || !hospitals.length || !location || !this.elements.chatContainer) return;
      
      // 創建使用者消息
      this.appendMessage(`我在 ${location.name} 附近搜尋了醫療設施`, 'user');
      
      // 創建機器人消息容器
      const messageDiv = document.createElement('div');
      messageDiv.classList.add('message', 'bot');
      
      // 創建醫院結果容器
      const resultsDiv = document.createElement('div');
      resultsDiv.className = 'hospital-results';
      
      // 添加標題段落
      const titleP = document.createElement('p');
      titleP.textContent = `好的，根據您提供的「${location.name}」位置，我為您找到附近的一些醫院：`;
      resultsDiv.appendChild(titleP);
      
      // 添加醫院列表
      hospitals.forEach((hospital, index) => {
        const hospitalItem = document.createElement('div');
        hospitalItem.className = 'hospital-item';
        
        // 醫院名稱
        const nameP = document.createElement('p');
        const indexText = document.createTextNode(`${index + 1}. `);
        const nameStrong = document.createElement('strong');
        nameStrong.textContent = hospital.name;
        nameP.appendChild(indexText);
        nameP.appendChild(nameStrong);
        
        // 醫院詳情
        const detailsUl = document.createElement('ul');
        detailsUl.className = 'hospital-details';
        
        const addressLi = document.createElement('li');
        addressLi.textContent = `地址：${hospital.address}`;
        detailsUl.appendChild(addressLi);
        
        const ratingLi = document.createElement('li');
        ratingLi.textContent = hospital.rating ? `評分：${hospital.rating}/5.0` : '評分：無評分/5.0';
        detailsUl.appendChild(ratingLi);
        
        // 組裝醫院元素
        hospitalItem.appendChild(nameP);
        hospitalItem.appendChild(detailsUl);
        resultsDiv.appendChild(hospitalItem);
      });
      
      // 添加結尾段落
      const footerP = document.createElement('p');
      footerP.textContent = '希望這些資訊對您有幫助。如果您需要更精確的搜尋結果，建議您使用地圖功能選擇一個更精確的地點。';
      resultsDiv.appendChild(footerP);
      
      // 添加查看地圖按鈕
      const footerDiv = document.createElement('div');
      footerDiv.className = 'hospital-footer';
      
      const viewMapBtn = document.createElement('button');
      viewMapBtn.id = 'viewOnMapBtn';
      viewMapBtn.className = 'primary-button';
      
      const mapIcon = document.createElement('i');
      mapIcon.className = 'fas fa-map-marked-alt';
      viewMapBtn.appendChild(mapIcon);
      
      const btnText = document.createTextNode(' 在地圖上查看');
      viewMapBtn.appendChild(btnText);
      footerDiv.appendChild(viewMapBtn);
      resultsDiv.appendChild(footerDiv);
      
      // 將結果添加到消息中
      messageDiv.appendChild(resultsDiv);
      
      // 添加時間戳
      const timeSpan = document.createElement('span');
      timeSpan.classList.add('message-time');
      
      const now = new Date();
      timeSpan.textContent = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
      
      messageDiv.appendChild(timeSpan);
      this.elements.chatContainer.appendChild(messageDiv);
      
      // 滾動到底部
      this.scrollToBottom();
      
      // 添加地圖顯示按鈕事件
      setTimeout(() => {
        const viewMapBtn = document.getElementById('viewOnMapBtn');
        if (viewMapBtn) {
          viewMapBtn.addEventListener('click', () => {
            MedApp.maps.core.showMapModal();
            
            // 確保在地圖初始化後添加醫院標記
            setTimeout(() => {
              MedApp.maps.hospital.createHospitalMarkers(hospitals);
            }, 500);
          });
        }
      }, 100);
      
      // 儲存對話
      if (!MedApp.state.currentChatId) {
        MedApp.state.currentChatId = Date.now().toString();
      }
      MedApp.chat.history.saveMessageToStorage(MedApp.state.currentChatId, `我在 ${location.name} 附近搜尋了醫療設施`, 'user');
    },
    
    // 滾動聊天窗口到底部
    scrollToBottom: function() {
      if (this.elements.chatContainer) {
        this.elements.chatContainer.scrollTop = this.elements.chatContainer.scrollHeight;
      }
    },
    
    // 安全處理內容的函數
    sanitizeContent: function(content) {
      // 確保內容是字符串
      if (typeof content !== 'string') {
        return String(content);
      }
      
      // 簡單的 HTML 字符轉義
      return content
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    },

    // 為機器人訊息添加回饋按鈕
    addFeedbackButtons: function(messageDiv, messageId) {
      // 檢查是否已經有回饋按鈕
      if (messageDiv.querySelector('.feedback-container')) return;
      
      const feedbackContainer = document.createElement('div');
      feedbackContainer.className = 'feedback-container';
      feedbackContainer.innerHTML = `
        <div class="feedback-buttons">
          <button class="feedback-btn like-btn" data-feedback="like" data-message-id="${messageId}" title="有幫助">
            <i class="fas fa-thumbs-up"></i>
            <span class="feedback-text">有幫助</span>
          </button>
          <button class="feedback-btn dislike-btn" data-feedback="dislike" data-message-id="${messageId}" title="需要改進">
            <i class="fas fa-thumbs-down"></i>
            <span class="feedback-text">需要改進</span>
          </button>
        </div>
        <div class="feedback-details" style="display: none;">
          <div class="feedback-form">
            <textarea class="feedback-text-input" placeholder="請告訴我們如何改進（選填）" maxlength="500"></textarea>
            <div class="feedback-actions">
              <button class="feedback-submit">送出回饋</button>
              <button class="feedback-cancel">取消</button>
            </div>
          </div>
        </div>
        <div class="feedback-status" style="display: none;"></div>
      `;
      
      messageDiv.appendChild(feedbackContainer);
      
      // 綁定事件監聽器
      this.bindFeedbackEvents(feedbackContainer, messageId);
    },

    // 綁定回饋按鈕事件
    bindFeedbackEvents: function(container, messageId) {
      const likeBtn = container.querySelector('.like-btn');
      const dislikeBtn = container.querySelector('.dislike-btn');
      const feedbackDetails = container.querySelector('.feedback-details');
      const submitBtn = container.querySelector('.feedback-submit');
      const cancelBtn = container.querySelector('.feedback-cancel');
      const textInput = container.querySelector('.feedback-text-input');
      
      // 點讚按鈕事件
      likeBtn.addEventListener('click', () => {
        this.handleFeedback('like', messageId, likeBtn, dislikeBtn, container);
      });
      
      // 倒讚按鈕事件
      dislikeBtn.addEventListener('click', () => {
        this.handleFeedback('dislike', messageId, likeBtn, dislikeBtn, container);
        // 顯示詳細回饋選項
        feedbackDetails.style.display = 'block';
        textInput.focus();
      });
      
      // 送出回饋事件
      submitBtn.addEventListener('click', () => {
        const feedbackText = textInput.value.trim();
        this.submitDetailedFeedback(messageId, 'dislike', feedbackText, container);
        feedbackDetails.style.display = 'none';
        textInput.value = '';
      });
      
      // 取消回饋事件
      cancelBtn.addEventListener('click', () => {
        feedbackDetails.style.display = 'none';
        textInput.value = '';
        // 重置按鈕狀態
        dislikeBtn.classList.remove('active');
        dislikeBtn.disabled = false;
        likeBtn.disabled = false;
      });
    },

    // 處理回饋點擊
    handleFeedback: function(type, messageId, likeBtn, dislikeBtn, container) {
      // 更新按鈕狀態
      likeBtn.classList.toggle('active', type === 'like');
      dislikeBtn.classList.toggle('active', type === 'dislike');
      
      // 禁用按鈕防止重複點擊
      likeBtn.disabled = true;
      dislikeBtn.disabled = true;
      
      // 如果是正讚，立即提交
      if (type === 'like') {
        this.submitDetailedFeedback(messageId, type, '', container);
      }
      
      console.log(`用戶對訊息 ${messageId} 給予 ${type} 回饋`);
    },

    // 提交詳細回饋
    submitDetailedFeedback: function(messageId, type, details, container) {
      const feedbackId = this.generateFeedbackId();
      const chatId = MedApp.state.currentChatId || 'default';
      
      const feedbackData = {
        feedback_id: feedbackId,
        message_id: messageId,
        chat_id: chatId,
        type: type,
        details: details,
        timestamp: new Date().toISOString(),
        session_id: this.getSessionId()
      };
      
      // 儲存到本地存儲
      this.saveFeedbackToLocalStorage(feedbackData);
      
      // 發送到伺服器
      this.sendFeedbackToServer(feedbackData, container);
    },

    // 生成唯一的回饋 ID
    generateFeedbackId: function() {
      return `feedback_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    },

    // 獲取會話 ID
    getSessionId: function() {
      // 嘗試從多個來源獲取會話 ID
      return MedApp.state.currentChatId || 
             sessionStorage.getItem('sessionId') || 
             localStorage.getItem('sessionId') || 
             'anonymous_' + Date.now();
    },

    // 儲存回饋到本地存儲
    saveFeedbackToLocalStorage: function(feedbackData) {
      try {
        let feedbacks = JSON.parse(localStorage.getItem('chatFeedbacks') || '[]');
        
        // 移除該訊息的舊回饋
        feedbacks = feedbacks.filter(f => f.message_id !== feedbackData.message_id);
        
        // 添加新回饋
        feedbacks.push(feedbackData);
        
        localStorage.setItem('chatFeedbacks', JSON.stringify(feedbacks));
        console.log('回饋已儲存到本地存儲:', feedbackData.feedback_id);
      } catch (error) {
        console.error('儲存回饋到本地存儲失敗:', error);
      }
    },

    // 發送回饋到伺服器
    sendFeedbackToServer: function(feedbackData, container) {
      const statusDiv = container.querySelector('.feedback-status');
      
      // 顯示載入狀態
      this.showFeedbackStatus(statusDiv, '正在送出回饋...', 'loading');
      
      fetch('/api/feedback/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
        },
        body: JSON.stringify(feedbackData)
      })
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
      })
      .then(data => {
        console.log('回饋已送出:', data);
        this.showFeedbackStatus(statusDiv, '感謝您的回饋！', 'success');
        
        // 3秒後隱藏狀態訊息
        setTimeout(() => {
          statusDiv.style.display = 'none';
        }, 3000);
      })
      .catch(error => {
        console.error('送出回饋時發生錯誤:', error);
        this.showFeedbackStatus(statusDiv, '回饋送出失敗，已儲存到本地', 'error');
        
        // 重新啟用按鈕
        const buttons = container.querySelectorAll('.feedback-btn');
        buttons.forEach(btn => btn.disabled = false);
        
        // 5秒後隱藏錯誤訊息
        setTimeout(() => {
          statusDiv.style.display = 'none';
        }, 5000);
      });
    },

    // 顯示回饋狀態
    showFeedbackStatus: function(statusDiv, message, type) {
      statusDiv.textContent = message;
      statusDiv.className = `feedback-status ${type}`;
      statusDiv.style.display = 'block';
    },

    // 獲取 CSRF Token
    getCSRFToken: function() {
      const token = document.querySelector('[name=csrf-token]')?.content ||
                    document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                    MedApp.config.csrfToken;
      
      if (!token) {
        console.warn('找不到 CSRF Token');
      }
      
      return token;
    },

    // 保存訊息到 Neo4j（透過後端 API）
    saveMessageToNeo4j: function(messageId, content, sender) {
      const chatId = MedApp.state.currentChatId || 'default';
      
      // 如果還沒有對話 ID，創建一個新的對話
      if (!MedApp.state.conversationCreated) {
        this.createConversationInNeo4j(chatId);
        MedApp.state.conversationCreated = true;
      }
      
      const messageData = {
        message_id: messageId,
        chat_id: chatId,
        content: content,
        sender: sender,
        timestamp: new Date().toISOString(),
        session_id: this.getSessionId()
      };
      
      fetch('/api/messages/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
        },
        body: JSON.stringify(messageData)
      })
      .then(response => response.json())
      .then(data => {
        console.log('訊息已儲存到 Neo4j:', data);
      })
      .catch(error => {
        console.error('儲存訊息到 Neo4j 失敗:', error);
      });
    },

    // 在 Neo4j 中創建對話
    createConversationInNeo4j: function(chatId) {
      const conversationData = {
        chat_id: chatId,
        session_id: this.getSessionId(),
        metadata: {
          started_at: new Date().toISOString(),
          user_agent: navigator.userAgent,
          platform: navigator.platform
        }
      };
      
      fetch('/api/conversations/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': this.getCSRFToken()
        },
        body: JSON.stringify(conversationData)
      })
      .then(response => response.json())
      .then(data => {
        console.log('對話已創建在 Neo4j:', data);
      })
      .catch(error => {
        console.error('創建對話失敗:', error);
      });
    },

    // 修復 Markdown 顯示的函數
    fixMarkdownDisplay: function() {
      console.log('開始修復 Markdown 顯示...');
      
      // 查找所有機器人訊息
      const botMessages = document.querySelectorAll('.message.bot');
      if (botMessages.length === 0) {
        console.log('沒有找到機器人訊息');
        return;
      }
      
      console.log(`找到 ${botMessages.length} 條機器人訊息`);
      
      // 確保 marked.js 已載入
      if (typeof marked === 'undefined') {
        console.error('Marked.js 未載入，無法修復 Markdown');
        return;
      }
      
      // 遍歷每條訊息
      botMessages.forEach((messageDiv, index) => {
        // 尋找訊息內容元素
        const contentEl = messageDiv.querySelector('.message-content');
        if (!contentEl) return;
        
        // 獲取原始內容
        const originalContent = contentEl.innerHTML || contentEl.textContent;
        
        // 處理 HTML 實體
        let decodedContent = originalContent;
        if (originalContent.includes('&lt;') || originalContent.includes('&gt;')) {
          try {
            // 解碼 HTML 實體
            decodedContent = this.decodeHtmlEntities(originalContent);
          } catch (e) {
            console.warn(`無法解碼訊息 #${index} 的 HTML 實體:`, e);
          }
        }
        
        // 嘗試重新解析為 Markdown
        try {
          // 預處理內容
          decodedContent = this.preprocessMarkdown(decodedContent);
          
          // 使用 marked.js 解析
          contentEl.innerHTML = marked.parse(decodedContent);
          
          // 後處理
          this.postProcessMarkdown(contentEl);
          
          console.log(`成功修復訊息 #${index}`);
        } catch (error) {
          console.error(`修復訊息 #${index} 時出錯:`, error);
        }
      });
      
      console.log('Markdown 修復完成');
    }
  };

// 全域函數：頁面載入完成後自動修復
function initMarkdownFixer() {
  document.addEventListener('DOMContentLoaded', function() {
    // 等待 MedApp 初始化完成
    setTimeout(function() {
      if (window.MedApp && MedApp.initialized && MedApp.chat && MedApp.chat.display) {
        console.log('MedApp 已初始化，開始修復 Markdown');
        MedApp.chat.display.fixMarkdownDisplay();
      } else {
        console.log('等待 MedApp 初始化...');
        // 再等一會兒
        setTimeout(() => {
          if (window.MedApp && MedApp.chat && MedApp.chat.display) {
            MedApp.chat.display.fixMarkdownDisplay();
          }
        }, 2000);
      }
    }, 1000);
  });
}

// 初始化修復器
initMarkdownFixer();

// 也可以從控制台手動呼叫
window.fixMarkdownDisplay = function() {
  if (window.MedApp && MedApp.chat && MedApp.chat.display) {
    MedApp.chat.display.fixMarkdownDisplay();
  } else {
    console.error('MedApp.chat.display 未初始化');
  }
};