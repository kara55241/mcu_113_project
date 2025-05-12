/**
 * accessibility.js - 輔助功能
 * 負責處理字體大小調整、朗讀內容等輔助功能
 */

MedApp.utils.accessibility = {
    // 字體大小設定
    fontSize: {
      current: 100, // 百分比
      min: 100,
      max: 150,
      step: 25
    },
    
    // DOM 元素引用
    elements: {
      increaseFontBtn: null,
      voiceReadBtn: null
    },
    
    // 語音合成物件
    speechSynthesis: window.speechSynthesis,
    
    // 初始化
    init: function() {
      this.initElements();
      this.loadPreferences();
      this.bindEvents();
      
      MedApp.log('輔助功能模組初始化完成', 'info');
    },
    
    // 初始化 DOM 元素引用
    initElements: function() {
      this.elements.increaseFontBtn = document.getElementById('increaseFontBtn');
      this.elements.voiceReadBtn = document.getElementById('voiceReadBtn');
    },
    
    // 載入偏好設定
    loadPreferences: function() {
      // 檢查本地儲存是否可用
      if (!MedApp.features.localStorage) return;
      
      // 載入字體大小設定
      const savedFontSize = localStorage.getItem('fontSize');
      if (savedFontSize) {
        this.fontSize.current = parseInt(savedFontSize);
        document.body.style.fontSize = `${this.fontSize.current}%`;
      }
    },
    
    // 綁定事件處理
    bindEvents: function() {
      // 字體大小調整按鈕
      if (this.elements.increaseFontBtn) {
        this.elements.increaseFontBtn.addEventListener('click', () => {
          this.adjustFontSize();
        });
      }
      
      // 朗讀文字按鈕
      if (this.elements.voiceReadBtn) {
        this.elements.voiceReadBtn.addEventListener('click', () => {
          this.readLastMessage();
        });
      }
    },
    
    // 調整字體大小
    adjustFontSize: function() {
      // 切換到下一個字體大小
      this.fontSize.current = (this.fontSize.current >= this.fontSize.max) ? 
                              this.fontSize.min : 
                              this.fontSize.current + this.fontSize.step;
      
      // 應用字體大小
      document.body.style.fontSize = `${this.fontSize.current}%`;
      
      // 儲存設定
      if (MedApp.features.localStorage) {
        localStorage.setItem('fontSize', this.fontSize.current);
      }
      
      MedApp.log('字體大小已調整為: ' + this.fontSize.current + '%', 'info');
    },
    
    // 朗讀最後一條訊息
    readLastMessage: function() {
      // 檢查語音合成功能是否可用
      if (!MedApp.features.speechSynthesis) {
        alert('您的瀏覽器不支持語音合成功能');
        return;
      }
      
      // 獲取最後一條機器人訊息
      const botMessages = document.querySelectorAll('.message.bot');
      if (botMessages.length > 0) {
        const lastBotMessage = botMessages[botMessages.length - 1];
        
        // 移除時間戳記等不需朗讀的內容
        const textToRead = this.cleanupTextForReading(lastBotMessage.textContent);
        
        // 如果有內容才朗讀
        if (textToRead.trim()) {
          this.speakText(textToRead);
        }
      } else {
        MedApp.log('沒有找到可朗讀的機器人訊息', 'warn');
      }
    },
    
    // 清理朗讀文本
    cleanupTextForReading: function(text) {
      // 移除時間戳（格式如 12:34）
      let cleanText = text.replace(/\d{1,2}:\d{2}$/, '').trim();
      
      // 移除特殊格式標記（如果需要）
      cleanText = cleanText.replace(/\*\*([^*]+)\*\*/g, '$1'); // 移除 markdown 粗體
      cleanText = cleanText.replace(/\*([^*]+)\*/g, '$1');     // 移除 markdown 斜體
      
      return cleanText;
    },
    
    // 朗讀文字
    speakText: function(text) {
      // 檢查是否已在朗讀中
      if (this.speechSynthesis.speaking) {
        // 取消當前朗讀
        this.speechSynthesis.cancel();
        MedApp.log('取消之前的朗讀', 'debug');
      }
      
      // 創建語音物件
      const utterance = new SpeechSynthesisUtterance(text);
      
      // 設定語音參數
      utterance.lang = 'zh-TW';
      utterance.volume = 1.0;  // 音量 (0-1)
      utterance.rate = 1.0;    // 語速 (0.1-10)
      utterance.pitch = 1.0;   // 音調 (0-2)
      
      // 事件處理
      utterance.onstart = () => {
        MedApp.log('開始朗讀文字', 'debug');
        
        // 添加視覺提示
        if (this.elements.voiceReadBtn) {
          this.elements.voiceReadBtn.classList.add('active');
        }
      };
      
      utterance.onend = () => {
        MedApp.log('朗讀文字結束', 'debug');
        
        // 移除視覺提示
        if (this.elements.voiceReadBtn) {
          this.elements.voiceReadBtn.classList.remove('active');
        }
      };
      
      utterance.onerror = (event) => {
        MedApp.log('朗讀文字錯誤: ' + event.error, 'error');
        
        // 移除視覺提示
        if (this.elements.voiceReadBtn) {
          this.elements.voiceReadBtn.classList.remove('active');
        }
      };
      
      // 開始朗讀
      this.speechSynthesis.speak(utterance);
    }
  };