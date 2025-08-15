/**
 * chat-input.js - 聊天輸入處理
 * 負責處理用戶輸入相關功能，包括文字輸入、語音輸入、檔案上傳等
 */

MedApp.chat.input = {
    // DOM 元素引用
    elements: {
      inputField: null,
      sendButton: null,
      micButton: null,
      fileInput: null,
      suggestionButtons: null
    },
    
    // 語音辨識物件
    recognition: null,
    
    // 初始化
    init: function() {
      this.initElements();
      this.setupSpeechRecognition();
      this.bindEvents();
      
      MedApp.log('聊天輸入模組初始化完成', 'info');
    },
    
    // 初始化 DOM 元素引用
    initElements: function() {
      this.elements.inputField = document.getElementById('userInput');
      this.elements.sendButton = document.getElementById('sendButton');
      this.elements.micButton = document.getElementById('micButton');
      this.elements.fileInput = document.getElementById('fileInput');
      this.elements.suggestionButtons = document.querySelectorAll('.suggestion-btn');
      
      // 檢查元素是否存在
      if (!this.elements.inputField) {
        MedApp.log('找不到輸入框元素 userInput', 'error');
      }
      
      if (!this.elements.sendButton) {
        MedApp.log('找不到發送按鈕元素 sendButton', 'error');
      }
    },
    
    // 綁定事件處理
    bindEvents: function() {
      // 送出按鈕點擊事件
      if (this.elements.sendButton) {
        this.elements.sendButton.addEventListener('click', () => {
          MedApp.log('發送按鈕被點擊', 'debug');
          const userMessage = this.elements.inputField.value.trim();
          if (userMessage) {
            MedApp.chat.core.sendMessage(userMessage);
          }
        });
      }
      
      // 輸入框 Enter 鍵事件
      if (this.elements.inputField) {
        this.elements.inputField.addEventListener('keypress', (e) => {
          if (e.key === 'Enter') {
            MedApp.log('Enter 鍵被按下', 'debug');
            const userMessage = this.elements.inputField.value.trim();
            if (userMessage) {
              MedApp.chat.core.sendMessage(userMessage);
            }
          }
        });
      }
      
      // 建議按鈕點擊事件
      if (this.elements.suggestionButtons) {
        this.elements.suggestionButtons.forEach(button => {
          button.addEventListener('click', () => {
            const suggestion = button.textContent || button.dataset.suggestion;
            MedApp.log('建議按鈕被點擊: ' + suggestion, 'debug');
            if (this.elements.inputField) {
              this.elements.inputField.value = suggestion;
            }
            MedApp.chat.core.sendMessage(suggestion);
          });
        });
      }
      
      // 檔案上傳事件
      if (this.elements.fileInput) {
        this.elements.fileInput.addEventListener('change', this.handleFileUpload.bind(this));
      }
      
      // 確保所有按鈕事件已綁定
      MedApp.log('聊天輸入事件已綁定', 'debug');
      
      // 添加備用事件處理
      this.addFallbackHandlers();
    },
    
    // 添加備用事件處理 - 簡化版本
    addFallbackHandlers: function() {
      // 延遲檢查核心功能是否正常工作
      setTimeout(() => {
        if (!this.elements.sendButton || !this.elements.inputField) {
          MedApp.log('輸入元素未正確初始化', 'warn');
          return;
        }
        
        // 檢查是否需要重新綁定事件
        const testInput = () => {
          if (!MedApp.chat.core || typeof MedApp.chat.core.sendMessage !== 'function') {
            MedApp.log('核心聊天功能未準備就緒，啟用備用模式', 'warn');
            this.enableFallbackMode();
          }
        };
        
        testInput();
      }, 2000);
    },
    
    // 啟用備用模式
    enableFallbackMode: function() {
      if (!this.elements.sendButton || !this.elements.inputField) return;
      
      // 添加備用發送功能
      const fallbackSend = () => {
        const message = this.elements.inputField.value.trim();
        if (!message) return;
        
        // 簡單的訊息顯示
        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
          const messageEl = document.createElement('div');
          messageEl.className = 'message user';
          messageEl.textContent = message;
          chatContainer.appendChild(messageEl);
          
          this.elements.inputField.value = '';
          
          if (MedApp.utils.notifications) {
            MedApp.utils.notifications.warning('聊天功能正在加載中，請稍後再試');
          }
        }
      };
      
      // 只在需要時添加備用事件
      this.elements.sendButton.addEventListener('click', fallbackSend);
      this.elements.inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') fallbackSend();
      });
      
      MedApp.log('備用聊天模式已啟用', 'info');
    },
    
    // 設置語音辨識
    setupSpeechRecognition: function() {
      // 檢查瀏覽器是否支援語音辨識
      if (MedApp.features.speechRecognition) {
        this.recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        this.recognition.continuous = false;
        this.recognition.lang = 'zh-TW';
        
        // 設定語音辨識結果處理
        this.recognition.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          if (this.elements.inputField) {
            this.elements.inputField.value = transcript;
          }
          if (this.elements.micButton) {
            this.elements.micButton.classList.remove('active');
          }
        };
        
        // 設定語音辨識錯誤處理
        this.recognition.onerror = (event) => {
          MedApp.log('語音辨識錯誤: ' + event.error, 'error');
          if (this.elements.micButton) {
            this.elements.micButton.classList.remove('active');
          }
        };
        
        // 綁定麥克風按鈕事件
        if (this.elements.micButton) {
          this.elements.micButton.addEventListener('click', () => {
            if (this.elements.micButton.classList.contains('active')) {
              this.recognition.stop();
              this.elements.micButton.classList.remove('active');
            } else {
              this.recognition.start();
              this.elements.micButton.classList.add('active');
            }
          });
        }
      } else if (this.elements.micButton) {
        // 如果不支援語音辨識，隱藏麥克風按鈕
        this.elements.micButton.style.display = 'none';
      }
    },
    
    // 處理檔案上傳
    handleFileUpload: function(e) {
      if (!this.elements.fileInput || !this.elements.fileInput.files || !this.elements.fileInput.files[0]) {
        return;
      }
      
      const file = this.elements.fileInput.files[0];
      
      // 如果開始新對話，則生成新的聊天ID
      if (!MedApp.state.currentChatId) {
        MedApp.state.currentChatId = Date.now().toString();
      }
      
      const formData = new FormData();
      formData.append('file', file);
      formData.append('chat_id', MedApp.state.currentChatId);
      formData.append('csrfmiddlewaretoken', MedApp.config.csrfToken);
      
      // 顯示上傳中
      MedApp.chat.display.appendMessage(`正在上傳檔案：${file.name}...`, 'bot');
      MedApp.chat.core.showLoading(true);
      
      fetch(`${MedApp.config.apiRoot || '/'}chat/upload/`, {
        method: 'POST',
        body: formData,
        headers: {
          'X-CSRFToken': MedApp.config.csrfToken
        }
      })
      .then(response => response.json())
      .then(data => {
        MedApp.chat.core.showLoading(false);
        if (data.success) {
          MedApp.chat.display.appendMessage(`檔案已上傳：${file.name}`, 'bot');
          MedApp.chat.display.appendMessage(`${data.message}`, 'bot');
          
          // 將上傳消息添加到本地存儲
          MedApp.chat.history.saveMessageToStorage(MedApp.state.currentChatId, `上傳檔案：${file.name}`, 'user');
          MedApp.chat.history.saveMessageToStorage(MedApp.state.currentChatId, `檔案已上傳：${file.name}`, 'bot');
          MedApp.chat.history.saveMessageToStorage(MedApp.state.currentChatId, data.message, 'bot');
          
          // 將此對話添加到歷史記錄
          MedApp.chat.history.addToHistory(`檔案討論: ${file.name}`, MedApp.state.currentChatId);
        } else {
          MedApp.chat.display.appendMessage(`檔案上傳失敗：${data.error}`, 'bot');
        }
      })
      .catch(error => {
        MedApp.chat.core.showLoading(false);
        MedApp.chat.display.appendMessage(`檔案上傳錯誤：${error.message}`, 'bot');
      });
    },
    
    // 送出位置相關訊息
    sendLocationMessage: function(locationInfo) {
      if (!locationInfo) {
        return MedApp.chat.core.sendMessage(this.elements.inputField.value);
      }
      
      const userMessage = this.elements.inputField.value.trim();
      if (!userMessage) return;
      
      // 送出訊息
      MedApp.chat.core.sendMessage(userMessage, locationInfo);
    },
    
    // 處理醫院請求
    handleHospitalRequest: function() {
      // 如果已選擇位置（手動選點）
      if (MedApp.state.selectedLocation && MedApp.state.selectedLocation.name) {
        const locationName = MedApp.state.selectedLocation.name;
        const query = `${locationName}附近的醫院和診所`;
        
        if (this.elements.inputField) {
          this.elements.inputField.value = query;
        }
        
        if (this.elements.sendButton) {
          this.elements.sendButton.click();
        }
        return;
      }
      
      // 使用瀏覽器定位
      if (navigator.geolocation) {
        MedApp.chat.display.appendMessage("正在獲取您的位置以查詢附近醫院...", "bot");
        
        navigator.geolocation.getCurrentPosition(
          (position) => {
            const coords = `${position.coords.latitude},${position.coords.longitude}`;
            
            fetch(`https://maps.googleapis.com/maps/api/geocode/json?latlng=${coords}&key=${MedApp.config.mapApiKey}&language=zh-TW`)
              .then(response => response.json())
              .then(data => {
                if (data.results && data.results.length > 0) {
                  const address = data.results[0].formatted_address;
                  
                  // 儲存為全域位置信息
                  MedApp.state.selectedLocation = {
                    name: address,
                    address: address,
                    coordinates: coords
                  };
                  
                  const query = `${address}附近的醫院和診所`;
                  if (this.elements.inputField) {
                    this.elements.inputField.value = query;
                  }
                  
                  if (this.elements.sendButton) {
                    this.elements.sendButton.click();
                  }
                } else {
                  MedApp.chat.display.appendMessage("找不到您的具體地址資訊，請手動選擇地點或輸入地址。", "bot");
                }
              })
              .catch(error => {
                MedApp.log("反向地理編碼錯誤: " + error.message, 'error');
                MedApp.chat.display.appendMessage("取得地址資訊失敗，請點擊地圖選擇位置或手動輸入地址。", "bot");
              });
          },
          (error) => {
            MedApp.log("地理定位錯誤: " + error.message, 'error');
            MedApp.chat.display.appendMessage("無法獲取您的位置。請使用地圖手動選擇位置或輸入地址。", "bot");
          }
        );
      } else {
        MedApp.chat.display.appendMessage("您的瀏覽器不支援定位功能，請手動選擇位置或輸入地址。", "bot");
      }
    }
  };