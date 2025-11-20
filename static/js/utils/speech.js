/**
 * speech.js - 語音相關功能
 * 負責處理語音輸入和語音合成功能
 */

MedApp.utils.speech = {
    // 語音辨識物件
    recognition: null,
    
    // 語音合成物件
    synthesis: window.speechSynthesis,
    
    // 語音辨識狀態
    isRecognizing: false,
    
    // DOM 元素引用
    elements: {
      micButton: null,
      inputField: null
    },
    
    // 初始化
    init: function() {
      this.initElements();
      this.setupSpeechRecognition();

      // 確保初始化時停止任何現有的語音合成
      if (this.synthesis && this.synthesis.speaking) {
        this.synthesis.cancel();
      }

      MedApp.log('語音模組初始化完成', 'info');
    },
    
    // 初始化 DOM 元素引用
    initElements: function() {
      this.elements.micButton = document.getElementById('micButton');
      this.elements.inputField = document.getElementById('userInput');
    },
    
    // 設置語音辨識
    setupSpeechRecognition: function() {
      // 檢查瀏覽器是否支援語音辨識
      if (!MedApp.features.speechRecognition) {
        MedApp.log("瀏覽器不支援語音辨識功能", 'warn');
        
        // 隱藏麥克風按鈕
        if (this.elements.micButton) {
          this.elements.micButton.style.display = 'none';
        }
        
        return;
      }
      
      // 建立語音辨識物件
      this.recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
      
      // 設定語音辨識參數
      this.recognition.continuous = false;  // 不持續聆聽
      this.recognition.interimResults = false;  // 不顯示中間結果
      this.recognition.lang = 'zh-TW';  // 設定語言為繁體中文
      
      // 設定語音辨識開始處理
      this.recognition.onstart = () => {
        MedApp.log("語音辨識已開始", 'debug');
        this.isRecognizing = true;
        this.updateMicButtonState(true);
      };

      // 設定語音辨識結果處理
      this.recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        const confidence = event.results[0][0].confidence;

        MedApp.log(`語音辨識結果：${transcript}，信心度：${confidence}`, 'debug');

        // 更新輸入欄位
        if (this.elements.inputField) {
          this.elements.inputField.value = transcript;
          // 觸發輸入框的 input 事件，以便其他模組可以響應
          this.elements.inputField.dispatchEvent(new Event('input', { bubbles: true }));
        }

        // 更新狀態並更新麥克風按鈕
        this.isRecognizing = false;
        this.updateMicButtonState(false);
      };

      // 設定語音辨識結束處理
      this.recognition.onend = () => {
        MedApp.log("語音辨識結束", 'debug');

        // 確保狀態正確更新
        this.isRecognizing = false;
        this.updateMicButtonState(false);
      };
      
      // 設定語音辨識錯誤處理
      this.recognition.onerror = (event) => {
        MedApp.log(`語音辨識錯誤：${event.error}`, 'error');

        // 重置狀態
        this.isRecognizing = false;

        // 顯示錯誤訊息
        switch (event.error) {
          case 'no-speech':
            this.showErrorMessage("未檢測到語音，請再試一次");
            break;
          case 'aborted':
            // 不顯示訊息，因為是用戶主動取消
            MedApp.log("語音辨識被中止", 'debug');
            break;
          case 'audio-capture':
            this.showErrorMessage("無法存取麥克風，請檢查設備連接");
            break;
          case 'not-allowed':
            this.showErrorMessage("未獲得麥克風使用權限，請在瀏覽器設定中允許麥克風存取");
            break;
          case 'network':
            this.showErrorMessage("網路連線錯誤，請檢查網路連接");
            break;
          case 'service-not-allowed':
            this.showErrorMessage("瀏覽器不允許語音辨識服務");
            break;
          default:
            this.showErrorMessage(`語音辨識發生錯誤：${event.error}`);
        }

        // 更新麥克風按鈕狀態
        this.updateMicButtonState(false);
      };
      
      // 綁定麥克風按鈕事件
      this.bindMicButtonEvent();
    },
    
    // 綁定麥克風按鈕事件
    bindMicButtonEvent: function() {
      if (!this.elements.micButton) return;
      
      this.elements.micButton.addEventListener('click', () => {
        // 檢查是否正在辨識中
        if (this.isRecognizing) {
          // 停止語音辨識
          this.stopSpeechRecognition();
        } else {
          // 開始語音辨識
          this.startSpeechRecognition();
        }
      });
    },
    
    // 開始語音辨識
    startSpeechRecognition: function() {
      if (!this.recognition) {
        MedApp.log("語音辨識物件不存在", 'error');
        return;
      }

      // 如果已經在辨識中，不要重複啟動
      if (this.isRecognizing) {
        MedApp.log("語音辨識已在進行中", 'debug');
        return;
      }

      try {
        // 開始辨識
        this.recognition.start();

        MedApp.log("啟動語音辨識", 'info');

        // 注意：狀態會在 onstart 事件中更新
      } catch (error) {
        MedApp.log(`啟動語音辨識失敗：${error.message}`, 'error');

        // 重置狀態
        this.isRecognizing = false;
        this.updateMicButtonState(false);

        // 顯示錯誤訊息
        if (error.name === 'InvalidStateError') {
          this.showErrorMessage("語音辨識正在進行中，請稍後再試");
        } else {
          this.showErrorMessage("無法啟動語音辨識");
        }
      }
    },
    
    // 停止語音辨識
    stopSpeechRecognition: function() {
      if (!this.recognition) return;
      
      try {
        // 停止辨識
        this.recognition.stop();
        
        // 更新狀態
        this.isRecognizing = false;
        
        // 更新麥克風按鈕狀態
        this.updateMicButtonState(false);
        
        MedApp.log("停止語音辨識", 'info');
      } catch (error) {
        MedApp.log(`停止語音辨識失敗：${error.message}`, 'error');
      }
    },
    
    // 更新麥克風按鈕狀態
    updateMicButtonState: function(active) {
      if (!this.elements.micButton) return;
      
      if (active) {
        this.elements.micButton.classList.add('active');
      } else {
        this.elements.micButton.classList.remove('active');
        this.isRecognizing = false;
      }
    },
    
    // 顯示錯誤訊息
    showErrorMessage: function(message) {
      // 使用通知模組顯示錯誤訊息
      if (MedApp.utils.notifications) {
        MedApp.utils.notifications.error(message);
      } else {
        MedApp.log(message, 'error');
      }
    },
    
    // 語音合成 - 朗讀文字
    speak: function(text, options = {}) {
      // 檢查瀏覽器是否支援語音合成
      if (!MedApp.features.speechSynthesis) {
        MedApp.log("瀏覽器不支援語音合成功能", 'warn');
        return;
      }
      
      // 檢查是否已在朗讀中
      if (this.synthesis.speaking) {
        // 取消當前朗讀
        this.synthesis.cancel();
        MedApp.log('取消之前的朗讀', 'debug');
      }
      
      // 創建語音物件
      const utterance = new SpeechSynthesisUtterance(text);
      
      // 設定語音參數
      utterance.lang = options.lang || 'zh-TW';
      utterance.volume = options.volume !== undefined ? options.volume : 1.0;  // 音量 (0-1)
      utterance.rate = options.rate !== undefined ? options.rate : 1.0;    // 語速 (0.1-10)
      utterance.pitch = options.pitch !== undefined ? options.pitch : 1.0;   // 音調 (0-2)
      
      // 事件處理
      utterance.onstart = () => {
        MedApp.log('開始朗讀文字', 'debug');
        
        // 觸發 onStart 回調
        if (typeof options.onStart === 'function') {
          options.onStart();
        }
      };
      
      utterance.onend = () => {
        MedApp.log('朗讀文字結束', 'debug');
        
        // 觸發 onEnd 回調
        if (typeof options.onEnd === 'function') {
          options.onEnd();
        }
      };
      
      utterance.onerror = (event) => {
        MedApp.log('朗讀文字錯誤: ' + event.error, 'error');
        
        // 觸發 onError 回調
        if (typeof options.onError === 'function') {
          options.onError(event);
        }
      };
      
      // 開始朗讀
      this.synthesis.speak(utterance);
      
      return utterance;
    },
    
    // 取消語音合成
    stopSpeaking: function() {
      if (this.synthesis && this.synthesis.speaking) {
        this.synthesis.cancel();
        MedApp.log('語音合成已取消', 'info');

        // 重置朗讀按鈕圖標
        const voiceBtn = document.getElementById('voiceReadBtn');
        if (voiceBtn) {
          voiceBtn.classList.remove('active');
          const icon = voiceBtn.querySelector('i');
          if (icon) {
            icon.className = 'fas fa-volume-up';
          }
        }
      }
    },
    
    // 取得可用的語音
    getVoices: function() {
      return this.synthesis ? this.synthesis.getVoices() : [];
    },
    
    // 取得中文語音
    getChineseVoices: function() {
      const voices = this.getVoices();
      return voices.filter(voice => 
        voice.lang === 'zh-TW' || 
        voice.lang === 'zh-CN' || 
        voice.lang === 'zh-HK'
      );
    },
    
    // 朗讀最後一條機器人訊息
    readLastBotMessage: function() {
      // 如果正在朗讀，則停止朗讀
      if (this.synthesis && this.synthesis.speaking) {
        MedApp.log('停止當前朗讀', 'info');
        this.stopSpeaking();
        return;
      }

      // 獲取最後一條機器人訊息
      const botMessages = document.querySelectorAll('.message.bot');
      if (botMessages.length === 0) {
        MedApp.log('沒有找到機器人訊息', 'warn');
        this.showErrorMessage('沒有可朗讀的訊息');
        return;
      }

      const lastBotMessage = botMessages[botMessages.length - 1];

      // 優先獲取 message-bubble 的內容，避免包含時間戳和頭像
      let textElement = lastBotMessage.querySelector('.message-bubble');
      if (!textElement) {
        // 如果找不到 message-bubble，嘗試 message-content
        textElement = lastBotMessage.querySelector('.message-content');
      }
      if (!textElement) {
        // 最後備選：使用整個訊息
        textElement = lastBotMessage;
      }

      // 清理文本
      const text = this.cleanTextForSpeech(textElement.textContent);

      if (!text || text.length < 2) {
        MedApp.log('沒有可朗讀的內容', 'warn');
        this.showErrorMessage('沒有可朗讀的內容');
        return;
      }

      // 朗讀文字
      return this.speak(text, {
        onStart: () => {
          // 添加視覺提示
          const voiceBtn = document.getElementById('voiceReadBtn');
          if (voiceBtn) {
            voiceBtn.classList.add('active');
            // 改變圖標為停止圖標
            const icon = voiceBtn.querySelector('i');
            if (icon) {
              icon.className = 'fas fa-stop';
            }
          }
        },
        onEnd: () => {
          // 移除視覺提示
          const voiceBtn = document.getElementById('voiceReadBtn');
          if (voiceBtn) {
            voiceBtn.classList.remove('active');
            // 恢復圖標
            const icon = voiceBtn.querySelector('i');
            if (icon) {
              icon.className = 'fas fa-volume-up';
            }
          }
        },
        onError: () => {
          // 移除視覺提示
          const voiceBtn = document.getElementById('voiceReadBtn');
          if (voiceBtn) {
            voiceBtn.classList.remove('active');
            // 恢復圖標
            const icon = voiceBtn.querySelector('i');
            if (icon) {
              icon.className = 'fas fa-volume-up';
            }
          }
        }
      });
    },
    
    // 清理文本用於朗讀
    cleanTextForSpeech: function(text) {
      if (!text) return '';

      let cleanText = text;

      // 移除時間戳記 (格式如 "12:34" 在結尾)
      cleanText = cleanText.replace(/\d{1,2}:\d{2}\s*$/g, '').trim();

      // 移除 HTML 標籤，但保留換行
      cleanText = cleanText.replace(/<br\s*\/?>/gi, '\n');
      cleanText = cleanText.replace(/<\/p>/gi, '\n\n');
      cleanText = cleanText.replace(/<li>/gi, '\n• ');
      cleanText = cleanText.replace(/<[^>]*>/g, ' ');

      // 解碼常見的 HTML 實體
      cleanText = cleanText.replace(/&nbsp;/g, ' ');
      cleanText = cleanText.replace(/&quot;/g, '"');
      cleanText = cleanText.replace(/&apos;/g, "'");
      cleanText = cleanText.replace(/&amp;/g, '&');
      cleanText = cleanText.replace(/&lt;/g, '<');
      cleanText = cleanText.replace(/&gt;/g, '>');

      // 移除 Markdown 格式字符
      cleanText = cleanText.replace(/[*_~`#]/g, '');

      // 移除多餘的連續空格和換行
      cleanText = cleanText.replace(/\n{3,}/g, '\n\n');
      cleanText = cleanText.replace(/[ \t]+/g, ' ');

      // 移除開頭和結尾的空白
      cleanText = cleanText.trim();

      return cleanText;
    }
  };