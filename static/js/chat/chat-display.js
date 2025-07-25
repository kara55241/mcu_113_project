/**
 * chat-display.js - 配合Neo4j的聊天顯示模組
 * 移除localStorage，統一使用Neo4j存儲
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
      
      MedApp.log('聊天顯示模組初始化完成 (Neo4j模式)', 'info');
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
          breaks: true,
          gfm: true,
          headerIds: false,
          mangle: false,
          pedantic: false,
          sanitize: false,
          smartLists: true,
          smartypants: true,
          xhtml: true
        });
        
        const renderer = new marked.Renderer();
        
        renderer.table = function(header, body) {
          return '<div class="table-container"><table class="markdown-table">' +
            '<thead>' + header + '</thead>' +
            '<tbody>' + body + '</tbody>' +
            '</table></div>';
        };
        
        renderer.list = function(body, ordered, start) {
          const type = ordered ? 'ol' : 'ul';
          const startAttr = (ordered && start !== 1) ? (' start="' + start + '"') : '';
          const className = ordered ? 'markdown-ordered-list' : 'markdown-unordered-list';
          return '<' + type + startAttr + ' class="' + className + '">' + body + '</' + type + '>';
        };
        
        renderer.code = function(code, infostring, escaped) {
          return '<pre class="markdown-code-block"><code class="language-' + 
                 (infostring || 'text') + '">' + 
                 (escaped ? code : this.escapeHtml(code)) + 
                 '</code></pre>';
        };
        
        marked.use({ renderer });
      }
    },
    
    // 生成唯一的訊息 ID
    generateMessageId: function() {
      return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    },

    // 添加消息到聊天界面（主要函數）
    appendMessage: function(content, sender = 'user', isMarkdown = false, messageId = null, skipSave = false) {
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
      
      // 處理內容
      if (typeof content !== 'string') {
        content = String(content);
      }
      
      const contentDiv = document.createElement('div');
      contentDiv.classList.add('message-content');
      
      if (sender === 'bot') {
        // 處理機器人訊息的 Markdown
        if (isMarkdown || this.hasMarkdownSyntax(content)) {
          try {
            content = this.preprocessMarkdown(content);
            
            if (typeof window.marked !== 'undefined') {
              contentDiv.innerHTML = window.marked.parse(content);
            } else {
              contentDiv.textContent = content;
            }
            
            this.postProcessMarkdown(contentDiv);
          } catch (error) {
            console.error('Markdown解析錯誤:', error);
            contentDiv.textContent = content;
          }
        } else {
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
      
      // 只保存到Neo4j（統一入口，避免重複）
      if (!skipSave && MedApp.chat.history && MedApp.chat.history.saveMessage) {
        const chatId = MedApp.state.currentChatId || Date.now().toString();
        MedApp.chat.history.saveMessage(chatId, content, sender, messageId);
      }
      
      // 為機器人訊息添加回饋按鈕（延遲執行）
      if (sender === 'bot') {
        setTimeout(() => {
          this.addFeedbackButtons(messageDiv, messageId);
        }, 100);
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
      
      const textarea = document.createElement('textarea');
      textarea.innerHTML = str;
      return textarea.value;
    },
        
    // 預處理Markdown內容
    preprocessMarkdown: function(content) {
      // 修復加粗語法
      content = content.replace(/\*\*\*(.*?):\*\*/g, '**$1:**');
      
      // 確保列表項目前有空行
      content = content.replace(/([^\n])\n(\s*[-*+]\s)/g, '$1\n\n$2');
      content = content.replace(/([^\n])\n(\s*\d+\.\s)/g, '$1\n\n$2');
      
      // 處理知識圖譜查詢
      content = content.replace(/(🔍\s*\*\*知識圖譜查詢過程：\*\*[\s\S]*?)(?=##|$)/g, 
          '<div class="knowledge-graph-process">$1</div>');
      
      // 標準化標題前的空行
      content = content.replace(/([^\n])(\n#+\s)/g, '$1\n\n$2');
      
      // 修復錯誤的列表嵌套
      content = content.replace(/(\* .+\n)(\* )/g, '$1\n$2');
      
      // 處理可能的引用區塊
      content = content.replace(/\n> /g, '\n\n> ');
      
      // 處理表格格式
      content = content.replace(/\|[\s-]+\|/g, function(match) {
        return match.replace(/\s+/g, '');
      });
      
      // 確保代碼塊前後有空行
      content = content.replace(/([^\n])\n```/g, '$1\n\n```');
      content = content.replace(/```\n([^\n])/g, '```\n\n$1');
      
      // 處理特殊符號表示法
      content = content.replace(/\*\*\*/g, '**');
      
      // 修復可能的多層嵌套列表格式
      content = content.replace(/(\s{2,}[-*+]\s)/g, '\n  $1');
      
      return content;
    },
    
    // Markdown解析後的後處理
    postProcessMarkdown: function(element) {
      // 處理表格
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
      
      // 確保列表正確顯示
      const lists = element.querySelectorAll('ul:not(.markdown-unordered-list), ol:not(.markdown-ordered-list)');
      lists.forEach(list => {
        if (list.tagName === 'UL') {
          list.classList.add('markdown-unordered-list');
        } else {
          list.classList.add('markdown-ordered-list');
        }
      });
      
      // 處理代碼塊
      const preBlocks = element.querySelectorAll('pre:not(.markdown-code-block)');
      preBlocks.forEach(pre => {
        pre.classList.add('markdown-code-block');
        const code = pre.querySelector('code');
        if (code && !code.classList.contains('language-')) {
          code.classList.add('language-text');
        }
      });
      
      // 確保所有鏈接在新窗口打開
      const links = element.querySelectorAll('a');
      links.forEach(link => {
        link.setAttribute('target', '_blank');
        link.setAttribute('rel', 'noopener noreferrer');
      });
      
      // 將純文本的列表標記轉換為真正的列表
      this.convertTextListsToHTML(element);
    },
    
    // 將純文本的列表標記轉換為HTML列表
    convertTextListsToHTML: function(element) {
      const paragraphs = element.querySelectorAll('p');
      paragraphs.forEach(p => {
        const text = p.innerHTML;
        
        if (/^(\d+\.\s|\*\s|-\s|\+\s)/.test(text)) {
          const isOrdered = /^\d+\.\s/.test(text);
          const lines = text.split('<br>');
          
          const allLinesAreList = lines.every(line => 
            /^(\d+\.\s|\*\s|-\s|\+\s)/.test(line.trim()));
          
          if (allLinesAreList) {
            const list = document.createElement(isOrdered ? 'ol' : 'ul');
            list.className = isOrdered ? 'markdown-ordered-list' : 'markdown-unordered-list';
            
            lines.forEach(line => {
              const itemText = line.replace(/^(\d+\.\s|\*\s|-\s|\+\s)/, '').trim();
              const li = document.createElement('li');
              li.innerHTML = itemText;
              list.appendChild(li);
            });
            
            p.parentNode.replaceChild(list, p);
          }
        }
      });
    },
    
    // 顯示位置訊息
    appendLocationMessage: function(locationInfo) {
      if (!locationInfo || !this.elements.chatContainer) return;
      
      const locationMessage = document.createElement('div');
      locationMessage.classList.add('message', 'user');
      
      const locationDiv = document.createElement('div');
      locationDiv.className = 'location-message';
      
      locationDiv.innerHTML = `
        <div class="location-header">
          <i class="fas fa-map-marker-alt"></i>
          <span>已選擇位置</span>
        </div>
        <div class="location-address">${locationInfo.name || locationInfo.address}</div>
        ${locationInfo.coordinates ? 
          `<div class="location-coordinates">座標: ${locationInfo.coordinates}</div>` : ''}
      `;
      
      locationMessage.appendChild(locationDiv);
      
      // 添加時間戳
      const timeSpan = document.createElement('span');
      timeSpan.classList.add('message-time');
      const now = new Date();
      timeSpan.textContent = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
      locationMessage.appendChild(timeSpan);
      
      this.elements.chatContainer.appendChild(locationMessage);
      this.scrollToBottom();
      
      // 保存位置訊息到Neo4j
      if (MedApp.chat.history && MedApp.chat.history.saveMessage) {
        const chatId = MedApp.state.currentChatId || Date.now().toString();
        const locationText = `已選擇位置: ${locationInfo.name || locationInfo.address}`;
        MedApp.chat.history.saveMessage(chatId, locationText, 'user');
      }
    },
    
    // 滾動聊天窗口到底部
    scrollToBottom: function() {
      if (this.elements.chatContainer) {
        this.elements.chatContainer.scrollTop = this.elements.chatContainer.scrollHeight;
      }
    },
    
    // 為機器人訊息添加回饋按鈕
    addFeedbackButtons: function(messageDiv, messageId) {
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
      
      likeBtn.addEventListener('click', () => {
        this.handleFeedback('like', messageId, likeBtn, dislikeBtn, container);
      });
      
      dislikeBtn.addEventListener('click', () => {
        this.handleFeedback('dislike', messageId, likeBtn, dislikeBtn, container);
        feedbackDetails.style.display = 'block';
        textInput.focus();
      });
      
      submitBtn.addEventListener('click', () => {
        const feedbackText = textInput.value.trim();
        this.submitDetailedFeedback(messageId, 'dislike', feedbackText, container);
        feedbackDetails.style.display = 'none';
        textInput.value = '';
      });
      
      cancelBtn.addEventListener('click', () => {
        feedbackDetails.style.display = 'none';
        textInput.value = '';
        dislikeBtn.classList.remove('active');
        dislikeBtn.disabled = false;
        likeBtn.disabled = false;
      });
    },

    // 處理回饋點擊
    handleFeedback: function(type, messageId, likeBtn, dislikeBtn, container) {
      likeBtn.classList.toggle('active', type === 'like');
      dislikeBtn.classList.toggle('active', type === 'dislike');
      
      likeBtn.disabled = true;
      dislikeBtn.disabled = true;
      
      if (type === 'like') {
        this.submitDetailedFeedback(messageId, type, '', container);
      }
      
      console.log(`用戶對訊息 ${messageId} 給予 ${type} 回饋`);
    },

    // 提交詳細回饋
    submitDetailedFeedback: function(messageId, type, details, container) {
      const feedbackId = `feedback_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
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
      
      this.sendFeedbackToServer(feedbackData, container);
    },

    // 發送回饋到伺服器
    sendFeedbackToServer: function(feedbackData, container) {
      const statusDiv = container.querySelector('.feedback-status');
      
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
        
        setTimeout(() => {
          statusDiv.style.display = 'none';
        }, 3000);
      })
      .catch(error => {
        console.error('送出回饋時發生錯誤:', error);
        this.showFeedbackStatus(statusDiv, '回饋送出失敗，請稍後再試', 'error');
        
        const buttons = container.querySelectorAll('.feedback-btn');
        buttons.forEach(btn => btn.disabled = false);
        
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
      return document.querySelector('[name=csrf-token]')?.content ||
             document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
             MedApp.config.csrfToken;
    },

    // 獲取會話 ID
    getSessionId: function() {
      return MedApp.state.currentChatId || 
             sessionStorage.getItem('sessionId') || 
             'anonymous_' + Date.now();
    }
  };