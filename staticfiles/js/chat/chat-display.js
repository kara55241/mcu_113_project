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
      
      MedApp.log('聊天顯示模組初始化完成', 'info');
    },
    
    // 初始化 DOM 元素引用
    initElements: function() {
      this.elements.chatContainer = document.getElementById('chatContainer');
      this.elements.welcomeMessage = document.querySelector('.welcome-message');
    },
    
    // 添加消息到聊天界面
    /**
 * 將此方法替換到 chat-display.js 的 appendMessage 方法
 * 解決中文顯示不正確的問題
 */

// 添加消息到聊天界面
    appendMessage: function(content, sender = 'user') {
        // 檢查聊天容器是否存在
        if (!this.elements.chatContainer) return;
        
        // 移除歡迎消息
        if (this.elements.welcomeMessage && this.elements.welcomeMessage.parentNode && sender === 'user') {
        this.elements.welcomeMessage.style.display = 'none';
        }
        
        // 創建訊息元素
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);
        
        // 處理內容 - 確保內容是字符串
        if (typeof content !== 'string') {
        content = String(content);
        }
        
        // 替代HTML處理方式，避免中文顯示問題
        // 創建純文本元素，然後處理換行
        const contentWrapper = document.createElement('div');
        contentWrapper.className = 'message-content';
        
        // 處理換行符
        const lines = content.split('\n');
        lines.forEach((line, index) => {
        const span = document.createElement('span');
        span.textContent = line;
        contentWrapper.appendChild(span);
        
        // 最後一行不加換行符
        if (index < lines.length - 1) {
            contentWrapper.appendChild(document.createElement('br'));
        }
        });
        
        messageDiv.appendChild(contentWrapper);
        
        // 添加時間戳
        const timeSpan = document.createElement('span');
        timeSpan.classList.add('message-time');
        
        const now = new Date();
        timeSpan.textContent = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
        
        messageDiv.appendChild(timeSpan);
        this.elements.chatContainer.appendChild(messageDiv);
        
        // 滾動到底部
        this.scrollToBottom();
    },
    
    // 添加位置訊息
    appendMessage: function(content, sender = 'user') {
        // 檢查聊天容器是否存在
        if (!this.elements.chatContainer) return;
        
        // 移除歡迎消息
        if (this.elements.welcomeMessage && this.elements.welcomeMessage.parentNode && sender === 'user') {
          this.elements.welcomeMessage.style.display = 'none';
        }
        
        // 創建訊息元素
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', sender);
        
        // 檢測是否包含HTML實體，如果是則解碼
        if (typeof content === 'string' && 
            (content.includes('&lt;') || content.includes('&gt;') || 
             content.includes('&quot;') || content.includes('&amp;'))) {
          
          // 解碼HTML實體
          const decodedContent = MedApp.utils.htmlEntities.decode(content);
          
          // 檢查解碼後的內容是否包含HTML標籤
          if (decodedContent.includes('<div') || 
              decodedContent.includes('<p') || 
              decodedContent.includes('<ul')) {
            // 直接設置innerHTML以正確渲染HTML
            messageDiv.innerHTML = decodedContent;
            
            // 確保添加時間戳
            const timeSpan = document.createElement('span');
            timeSpan.classList.add('message-time');
            
            const now = new Date();
            timeSpan.textContent = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
            
            messageDiv.appendChild(timeSpan);
          } else {
            // 如果解碼後沒有HTML標籤，使用原始方式設置內容
            messageDiv.innerHTML = content;
          }
        } else {
          // 常規內容處理方式
          messageDiv.innerHTML = content;
        }
        
        // 添加到聊天容器
        this.elements.chatContainer.appendChild(messageDiv);
        
        // 滾動到底部
        this.scrollToBottom();
      },
      
      // 新增一個安全處理內容的函數
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
    }
  };