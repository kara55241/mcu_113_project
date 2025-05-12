/**
 * app-core.js - 應用程式核心設定與初始化
 * 處理全局變數、應用程式設定和主要初始化流程
 */

// 全局應用程式命名空間
window.MedApp = {
  // 全局設定
  config: {
    apiRoot: window.appConfig?.apiRoot || '/',
    mapApiKey: window.appConfig?.mapApiKey || '',
    csrfToken: document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '',
    debug: true  // 啟用調試模式以便更容易追蹤問題
  },
  
  // 子模組容器
  chat: {},
  maps: {
    core: {},
    search: {},
    hospital: {},
    direction: {}
  },
  utils: {},
  
  // 全局狀態
  state: {
    currentChatId: null,
    selectedLocation: null
  },
  
  // 初始化應用程式
  init: function() {
    // 設定錯誤處理
    window.onerror = function(message, source, lineno, colno, error) {
      console.error(`錯誤: ${message} 在 ${source} 第 ${lineno} 行`);
      return false;
    };
    
    // 檢測瀏覽器功能支援
    this.detectBrowserFeatures();
    
    // 初始化緊急函數
    this.initEmergencyFunctions();
    
    // 初始化各模組
    this.initModules();
    
    // 載入使用者設定
    this.loadUserPreferences();
    
    // 初始化關鍵按鈕
    this.initializeButtons();
    
    // 標記初始化完成
    this.initialized = true;
    
    console.log('MedApp 應用程式初始化完成');
  },
  
  // 檢測瀏覽器功能支援
  detectBrowserFeatures: function() {
    this.features = {
      speechRecognition: 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window,
      geolocation: 'geolocation' in navigator,
      speechSynthesis: 'speechSynthesis' in window,
      localStorage: typeof localStorage !== 'undefined'
    };
    
    if (this.config.debug) {
      console.log('瀏覽器功能支援檢測:', this.features);
    }
  },
  
  // 初始化緊急函數
  initEmergencyFunctions: function() {
    // 創建緊急函數對象
    window.emergencyFunctions = {
      // 調整字體大小的緊急函數
      adjustFontSize: function() {
        const body = document.body;
        const currentSize = parseInt(window.getComputedStyle(body).fontSize);
        const newSize = currentSize < 20 ? currentSize + 2 : 16;
        body.style.fontSize = newSize + 'px';
        console.log('緊急字體大小調整: ' + newSize + 'px');
      },
      
      // 重新連接聊天的緊急函數
      reconnectChat: function() {
        const inputField = document.getElementById('userInput');
        const sendButton = document.getElementById('sendButton');
        if (inputField && sendButton) {
          sendButton.addEventListener('click', function() {
            const message = inputField.value.trim();
            if (message) {
              const chatContainer = document.getElementById('chatContainer');
              const userMsg = document.createElement('div');
              userMsg.classList.add('message', 'user');
              userMsg.textContent = message;
              chatContainer.appendChild(userMsg);
              inputField.value = '';
            }
          });
          console.log('緊急聊天重連功能已啟用');
        }
      }
    };
  },
  
  // 初始化關鍵按鈕
  initializeButtons: function() {
    MedApp.log('初始化關鍵按鈕功能', 'info');
    
    // 初始化新對話按鈕
    const newChatButton = document.getElementById('newChatButton');
    if (newChatButton) {
      MedApp.log('綁定新對話按鈕事件', 'info');
      newChatButton.addEventListener('click', function() {
        MedApp.log('新對話按鈕被點擊', 'info');
        
        // 檢查正常的 createNewChat 函數是否可用
        if (MedApp.chat.core && typeof MedApp.chat.core.createNewChat === 'function') {
          MedApp.chat.core.createNewChat();
        } else {
          // 備用方案：如果找不到正常的方法，使用基本功能
          MedApp.log('找不到 createNewChat 函數，使用替代方案', 'warn');
          
          // 產生新的聊天 ID
          MedApp.state.currentChatId = Date.now().toString();
          
          // 清空聊天容器
          const chatContainer = document.getElementById('chatContainer');
          if (chatContainer) {
            chatContainer.innerHTML = '';
          }
          
          // 顯示歡迎消息
          const welcomeMessage = document.querySelector('.welcome-message');
          if (welcomeMessage) {
            welcomeMessage.style.display = 'block';
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
          const userInput = document.getElementById('userInput');
          if (userInput) {
            userInput.value = '';
          }
          
          // 通知用戶
          alert('已建立新對話');
        }
      });
    }
    
    // 初始化字體放大按鈕
    const increaseFontBtn = document.getElementById('increaseFontBtn');
    if (increaseFontBtn) {
      MedApp.log('綁定字體放大按鈕事件', 'info');
      increaseFontBtn.addEventListener('click', function() {
        MedApp.log('字體放大按鈕被點擊', 'info');
        
        // 嘗試使用 accessibility 模組的方法
        if (MedApp.utils.accessibility && typeof MedApp.utils.accessibility.adjustFontSize === 'function') {
          MedApp.utils.accessibility.adjustFontSize();
        } else {
          // 備用方案：直接實現字體調整
          MedApp.log('找不到 adjustFontSize 函數，使用替代方案', 'warn');
          
          // 獲取當前字體大小
          let currentSize = parseInt(window.getComputedStyle(document.body).fontSize);
          
          // 如果無法解析當前大小，設置一個預設值
          if (isNaN(currentSize)) {
            currentSize = 16;
          }
          
          // 字體大小循環切換
          let newSize;
          if (currentSize >= 20) {
            newSize = 16; // 重置到預設大小
          } else {
            newSize = currentSize + 2; // 增加字體大小
          }
          
          // 應用新的字體大小
          document.body.style.fontSize = newSize + 'px';
          
          // 如果支持 localStorage，保存設定
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem('fontSize', newSize);
          }
          
          MedApp.log('字體大小已調整為: ' + newSize + 'px', 'info');
        }
      });
    }
    
    // 初始化朗讀按鈕
    const voiceReadBtn = document.getElementById('voiceReadBtn');
    if (voiceReadBtn) {
      MedApp.log('綁定朗讀按鈕事件', 'info');
      voiceReadBtn.addEventListener('click', function() {
        MedApp.log('朗讀按鈕被點擊', 'info');
        
        // 嘗試使用 speech 模組的方法
        if (MedApp.utils.speech && typeof MedApp.utils.speech.readLastBotMessage === 'function') {
          MedApp.utils.speech.readLastBotMessage();
        } else {
          // 備用方案
          MedApp.log('找不到 readLastBotMessage 函數，使用替代方案', 'warn');
          
          // 獲取最後一條機器人訊息
          const botMessages = document.querySelectorAll('.message.bot');
          if (botMessages.length > 0) {
            const lastBotMessage = botMessages[botMessages.length - 1];
            
            // 如果瀏覽器支持語音合成，朗讀文本
            if ('speechSynthesis' in window) {
              const utterance = new SpeechSynthesisUtterance(lastBotMessage.textContent);
              utterance.lang = 'zh-TW';
              window.speechSynthesis.speak(utterance);
              MedApp.log('正在朗讀最後一條訊息', 'info');
            } else {
              alert('您的瀏覽器不支持語音合成功能');
            }
          } else {
            alert('找不到可朗讀的訊息');
          }
        }
      });
    }
  },
  
  initModules: function() {
    // 監聽模組載入完成事件
    document.addEventListener('modulesLoaded', () => {
      // 初始化各子模組
      this.initializeModules();
    });
  },
  
  // 初始化各子模組的方法
  initializeModules: function() {
    MedApp.log('開始初始化所有模組...', 'info');
    
    // 初始化工具模組 (最先初始化)
    if (this.utils.accessibility && this.utils.accessibility.init) {
      MedApp.log('初始化 accessibility 模組', 'debug');
      this.utils.accessibility.init();
    }
    
    if (this.utils.notifications && this.utils.notifications.init) {
      MedApp.log('初始化 notifications 模組', 'debug');
      this.utils.notifications.init();
    }
    
    if (this.utils.speech && this.utils.speech.init) {
      MedApp.log('初始化 speech 模組', 'debug');
      this.utils.speech.init();
    }
    
    // 確保地圖核心模組有基本功能
    if (!this.maps.core.init) {
      this.maps.core.init = function() {
        MedApp.log('初始化地圖核心模組替代版本', 'info');
      };
      
      // 添加基本的地圖功能
      this.maps.core.initMap = function() {
        MedApp.log('正在初始化地圖...', 'info');
        const mapContainer = document.getElementById('map');
        if (mapContainer && window.google && window.google.maps) {
          MedApp.maps.core.map = new google.maps.Map(mapContainer, {
            center: { lat: 25.047675, lng: 121.517055 },
            zoom: 14,
            mapTypeControl: true,
            fullscreenControl: true,
            streetViewControl: true,
            zoomControl: true,
            mapTypeId: google.maps.MapTypeId.ROADMAP
          });
          
          MedApp.log('地圖初始化成功', 'info');
          
          // 初始化基本服務
          MedApp.maps.core.services = {
            geocoder: new google.maps.Geocoder(),
            directionsService: new google.maps.DirectionsService(),
            directionsRenderer: new google.maps.DirectionsRenderer({
              map: MedApp.maps.core.map
            })
          };
          
          if (google.maps.places) {
            MedApp.maps.core.services.placesService = new google.maps.places.PlacesService(MedApp.maps.core.map);
          }
          
          // 設置基本的信息窗口
          MedApp.maps.core.infoWindow = new google.maps.InfoWindow();
          
          // 初始化標記數組
          MedApp.maps.core.markers = [];
          
          // 觸發初始化完成事件
          document.dispatchEvent(new Event('mapInitialized'));
        } else {
          MedApp.log('無法初始化地圖：缺少地圖容器或 Google Maps API', 'error');
        }
      };
      
      // 添加基本的地圖操作函數
      this.maps.core.showMapModal = function() {
        const mapModal = document.getElementById('mapModal');
        if (mapModal) {
          mapModal.style.display = "block";
          
          setTimeout(() => {
            if (!MedApp.maps.core.map && document.getElementById('map')) {
              MedApp.maps.core.initMap();
            } else if (MedApp.maps.core.map && window.google && window.google.maps) {
              google.maps.event.trigger(MedApp.maps.core.map, "resize");
            }
          }, 300);
        }
      };
      
      this.maps.core.clearMarkers = function() {
        if (MedApp.maps.core.markers) {
          MedApp.maps.core.markers.forEach(marker => {
            if (marker && marker.setMap) marker.setMap(null);
          });
          MedApp.maps.core.markers = [];
        }
      };
    }
    
    // 初始化地圖模組 (先初始化核心)
    if (this.maps.core && this.maps.core.init) {
      MedApp.log('初始化 maps-core 模組', 'debug');
      this.maps.core.init();
      
      // 等待地圖核心初始化完成後，再初始化其他地圖模組
      setTimeout(() => {
        if (this.maps.search && this.maps.search.init) {
          MedApp.log('初始化 maps-search 模組', 'debug');
          this.maps.search.init();
        }
        
        if (this.maps.hospital && this.maps.hospital.init) {
          MedApp.log('初始化 maps-hospital 模組', 'debug');
          this.maps.hospital.init();
        }
        
        if (this.maps.direction && this.maps.direction.init) {
          MedApp.log('初始化 maps-direction 模組', 'debug');
          this.maps.direction.init();
        }
      }, 100);
    }
    
    // 初始化聊天模組 (先初始化核心)
    if (this.chat.core && this.chat.core.init) {
      MedApp.log('初始化 chat-core 模組', 'debug');
      this.chat.core.init();
      
      // 等待聊天核心初始化完成後，再初始化其他聊天模組
      setTimeout(() => {
        if (this.chat.display && this.chat.display.init) {
          MedApp.log('初始化 chat-display 模組', 'debug');
          this.chat.display.init();
        }
        
        if (this.chat.history && this.chat.history.init) {
          MedApp.log('初始化 chat-history 模組', 'debug');
          this.chat.history.init();
        }
        
        if (this.chat.input && this.chat.input.init) {
          MedApp.log('初始化 chat-input 模組', 'debug');
          this.chat.input.init();
        }
      }, 100);
    }
    
    MedApp.log('所有模組初始化完成', 'info');
  },
  
  // 載入使用者偏好設定
  loadUserPreferences: function() {
    if (!this.features.localStorage) return;
    
    // 載入字體大小設定
    const savedFontSize = localStorage.getItem('fontSize');
    if (savedFontSize) {
      document.body.style.fontSize = `${savedFontSize}px`;
    }
  },
  
  // 全局日誌功能
  log: function(message, type = 'log') {
    if (!this.config.debug && type === 'debug') return;
    
    const timestamp = new Date().toISOString().slice(11, 19);
    const prefix = `[MedApp ${timestamp}]`;
    
    switch (type) {
      case 'error':
        console.error(prefix, message);
        break;
      case 'warn':
        console.warn(prefix, message);
        break;
      case 'info':
        console.info(prefix, message);
        break;
      case 'debug':
        console.debug(prefix, message);
        break;
      default:
        console.log(prefix, message);
    }
  }
};

// DOM 載入完成後初始化應用程式
document.addEventListener('DOMContentLoaded', function() {
  MedApp.init();
});

// 檢測並自動啟動測試
setTimeout(() => {
  if (MedApp && !MedApp.initialized) {
    console.warn('MedApp 似乎沒有正確初始化，啟動測試...');
    
    // 直接執行關鍵初始化
    if (typeof MedApp.initializeButtons === 'function') {
      MedApp.initializeButtons();
    }
  }
}, 3000);