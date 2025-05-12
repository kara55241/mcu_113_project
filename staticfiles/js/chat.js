const sendButton = document.getElementById('sendButton');
const inputField = document.getElementById('userInput');
const chatContainer = document.getElementById('chatContainer');
const progressBar = document.getElementById('progressBar');
const newChatButton = document.getElementById('newChatButton');
const suggestionButtons = document.querySelectorAll('.suggestion-btn');
const welcomeMessage = document.querySelector('.welcome-message');
const chatHistoryList = document.getElementById('chatHistoryList');
const currentChatTitle = document.getElementById('currentChatTitle');
// 獲取 CSRF Token
const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

// 初始化當前聊天ID
let currentChatId = null;

// 顯示載入中狀態
function showLoading(show = true) {
    progressBar.style.display = show ? 'block' : 'none';
}

// 添加消息到聊天界面
function appendMessage(content, sender = 'user') {
    // 移除歡迎消息
    if (welcomeMessage && welcomeMessage.parentNode && sender === 'user') {
        welcomeMessage.style.display = 'none';
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);
    
    // 添加消息內容
    messageDiv.innerHTML = content;
    
    // 添加時間戳
    const timeSpan = document.createElement('span');
    timeSpan.classList.add('message-time');
    
    const now = new Date();
    timeSpan.textContent = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    
    messageDiv.appendChild(timeSpan);
    chatContainer.appendChild(messageDiv);
    
    // 滾動到底部
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// 修改 addToHistory 函數中的 HTML 結構
function addToHistory(message, chatId = null) {
    // 如果沒有提供 chatId，則使用當前的
    if (!chatId) {
        if (!currentChatId) {
            currentChatId = Date.now().toString();
        }
        chatId = currentChatId;
    }
    
    // 檢查此聊天ID是否已在列表中
    const existingItem = document.querySelector(`#chatHistoryList li[data-chat-id="${chatId}"]`);
    if (existingItem) {
        // 更新現有項目
        existingItem.querySelector('.chat-title').textContent = message.length > 20 ? message.substring(0, 20) + '...' : message;
        existingItem.title = message;
        
        // 移到列表頂部
        if (chatHistoryList.firstChild !== existingItem) {
            chatHistoryList.insertBefore(existingItem, chatHistoryList.firstChild);
        }
        
        // 更新本地存儲
        updateChatInStorage(chatId, message);
        return;
    }
    
    // 創建新的歷史記錄項目
    const now = new Date();
    const dateTime = `${now.getMonth()+1}月${now.getDate()}日 ${now.getHours()}:${now.getMinutes()}`;
    
    const li = document.createElement('li');
    li.dataset.chatId = chatId;
    li.title = `${message} (${dateTime})`;
    
    // 修改HTML結構，確保刪除按鈕總是可見
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
        loadChatHistory(chatId);
    });
    
    // 添加刪除事件
    li.querySelector('.delete-chat').addEventListener('click', (event) => {
        event.stopPropagation(); // 防止觸發對話載入
        deleteChat(chatId, li);
    });
    
    // 添加到列表頂部
    if (chatHistoryList.firstChild) {
        chatHistoryList.insertBefore(li, chatHistoryList.firstChild);
    } else {
        chatHistoryList.appendChild(li);
    }
    
    // 保存到本地存儲
    saveChatToStorage(chatId, message);
}

// 刪除對話 - 修復版
function deleteChat(chatId, listItem) {
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
    if (chatId === currentChatId) {
        createNewChat();
    }
    
    // 然後從伺服器刪除 (不等待響應)
    try {
        fetch(`/chat/history/${chatId}/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (response.ok) {
                console.log("對話已從服務器刪除");
            } else {
                console.warn("服務器刪除對話失敗，狀態碼:", response.status);
            }
        })
        .catch(error => {
            console.error("從服務器刪除對話時出錯:", error);
        });
    } catch (e) {
        console.error("刪除請求執行出錯:", e);
    }
}

// 創建新對話
function createNewChat() {
    // 生成新的聊天ID
    currentChatId = Date.now().toString();
    
    // 清空聊天容器
    chatContainer.innerHTML = '';
    
    // 重新添加歡迎消息
    welcomeMessage.style.display = 'block';
    
    // 移除所有聊天項目的活動狀態
    document.querySelectorAll('#chatHistoryList li').forEach(item => {
        item.classList.remove('active');
    });
    
    // 更新標題
    currentChatTitle.textContent = 'AI助手已就緒';
    
    // 清空輸入框
    inputField.value = '';
    
    // 向伺服器發送新對話請求
    fetch('/chat/new/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({ chat_id: currentChatId })
    }).catch(error => console.error("無法創建新對話:", error));
}

// 保存聊天到本地存儲
function saveChatToStorage(chatId, message) {
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
}

// 更新本地存儲中的聊天
function updateChatInStorage(chatId, message) {
    let chats = JSON.parse(localStorage.getItem('chats') || '{}');
    
    if (chats[chatId]) {
        chats[chatId].title = message;
        chats[chatId].lastUpdate = new Date().toISOString();
        localStorage.setItem('chats', JSON.stringify(chats));
    }
}

// 保存消息到本地存儲
function saveMessageToStorage(chatId, content, sender) {
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
    updateChatTitle(chatId, chats[chatId].title);
}

// 更新側邊欄中的對話標題
function updateChatTitle(chatId, title) {
    const chatItem = document.querySelector(`#chatHistoryList li[data-chat-id="${chatId}"]`);
    if (chatItem) {
        const titleElement = chatItem.querySelector('.chat-title');
        if (titleElement) {
            titleElement.textContent = title.length > 20 ? title.substring(0, 20) + '...' : title;
            chatItem.title = title;
        }
    }
}

// 載入聊天歷史
function loadChatHistory(chatId) {
    // 設置當前聊天ID
    currentChatId = chatId;
    
    // 嘗試從本地存儲載入
    const chats = JSON.parse(localStorage.getItem('chats') || '{}');
    
    if (chats[chatId]) {
        // 更新聊天標題
        currentChatTitle.textContent = chats[chatId].title;
        
        // 清空聊天容器
        chatContainer.innerHTML = '';
        
        // 隱藏歡迎消息
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }
        
        // 從服務器獲取消息
        showLoading(true);
        
        fetch(`/chat/history/${chatId}/`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            showLoading(false);
            
            if (data.messages && data.messages.length > 0) {
                // 渲染所有消息
                data.messages.forEach(msg => {
                    appendMessage(msg.content, msg.sender);
                    
                    // 同步到本地存儲
                    if (!chats[chatId].messages.some(m => 
                        m.content === msg.content && m.sender === msg.sender
                    )) {
                        saveMessageToStorage(chatId, msg.content, msg.sender);
                    }
                });
            } else {
                // 如果服務器沒有數據，嘗試從本地存儲渲染
                renderMessagesFromStorage(chatId);
            }
        })
        .catch(error => {
            console.error("載入歷史記錄錯誤:", error);
            showLoading(false);
            
            // 從本地存儲渲染
            renderMessagesFromStorage(chatId);
        });
    } else {
        console.error("找不到聊天ID:", chatId);
        appendMessage("無法找到此對話的歷史記錄", "bot");
    }
}

// 從本地存儲渲染消息
function renderMessagesFromStorage(chatId) {
    const chats = JSON.parse(localStorage.getItem('chats') || '{}');
    
    if (chats[chatId] && chats[chatId].messages) {
        if (chats[chatId].messages.length === 0) {
            // 如果沒有消息，顯示歡迎消息
            welcomeMessage.style.display = 'block';
            return;
        }
        
        // 清空聊天容器
        chatContainer.innerHTML = '';
        
        // 渲染所有消息
        chats[chatId].messages.forEach(msg => {
            appendMessage(msg.content, msg.sender);
        });
    } else {
        // 如果沒有找到聊天，顯示歡迎消息
        welcomeMessage.style.display = 'block';
    }
}

// 初始化聊天歷史列表 - 修復版
function initChatHistory() {
    // 從本地存儲加載所有聊天
    const chats = JSON.parse(localStorage.getItem('chats') || '{}');
    
    // 按最後更新時間排序
    const sortedChats = Object.values(chats).sort((a, b) => {
        return new Date(b.lastUpdate) - new Date(a.lastUpdate);
    });
    
    // 清空現有列表
    chatHistoryList.innerHTML = '';
    
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
            loadChatHistory(chat.id);
        });
        
        // 添加刪除事件
        li.querySelector('.delete-chat').addEventListener('click', (event) => {
            event.stopPropagation(); // 防止觸發對話載入
            deleteChat(chat.id, li);
        });
        
        chatHistoryList.appendChild(li);
    });
    
    // 加載最新的對話（如果有）
    if (sortedChats.length > 0) {
        const latestChat = sortedChats[0];
        currentChatId = latestChat.id;
        
        // 標記最新對話為活動狀態
        const latestChatItem = document.querySelector(`#chatHistoryList li[data-chat-id="${latestChat.id}"]`);
        if (latestChatItem) {
            latestChatItem.classList.add('active');
        }
        
        // 加載最新對話
        loadChatHistory(latestChat.id);
    }
}



async function sendLocationMessage(locationInfo) {
    if (!locationInfo) {
        return sendMessage(inputField.value);
    }

    const userMessage = inputField.value.trim();
    if (!userMessage) return;

    if (!currentChatId) {
        currentChatId = Date.now().toString();
    }

    appendMessage(userMessage, 'user');
    saveMessageToStorage(currentChatId, userMessage, 'user');

    const welcomeEl = document.querySelector('.welcome-message');
    if (welcomeEl && welcomeEl.style.display !== 'none') {
        addToHistory(userMessage, currentChatId);
    }

    inputField.value = '';
    showLoading(true);

    try {
        const response = await fetch('/chat/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            },
            body: JSON.stringify({ 
                message: userMessage,
                chat_id: currentChatId,
                location_info: locationInfo
            })
        });

        showLoading(false);

        if (!response.ok) {
            throw new Error(`Server responded with status: ${response.status}`);
        }

        const data = await response.json();
        console.log("✅ 從伺服器回傳的內容：", JSON.stringify(data, null, 2));

        const reply = typeof data === 'string' ? data : (data.output || "（伺服器沒有回傳內容）");

        appendMessage(reply, 'bot');
        saveMessageToStorage(currentChatId, reply, 'bot');

        // 顯示醫療地點（如果有）
        if (data.data && Array.isArray(data.data.results) && data.data.results.length > 0) {
            displayHospitalsOnMap(data.data.results);
        }

        // 處理地點標記（如果有）
        if (data.location && data.location.coordinates) {
            const coords = data.location.coordinates.split(',').map(parseFloat);

            if (coords.length === 2 && !isNaN(coords[0]) && !isNaN(coords[1])) {
                const position = { lat: coords[0], lng: coords[1] };

                if (typeof google !== 'undefined' && window.map) {
                    const marker = new google.maps.Marker({
                        position: position,
                        map: window.map,
                        title: data.location.name || "回傳位置",
                        animation: google.maps.Animation.DROP
                    });

                    if (!window.markers) window.markers = [];
                    window.markers.push(marker);

                    window.map.setCenter(position);
                    window.map.setZoom(15);
                } else {
                    console.warn("地圖尚未加載，無法標記位置。");
                }
            } else {
                console.warn("無效座標格式：", data.location.coordinates);
            }
        }

    } catch (error) {
        showLoading(false);
        console.error("Error:", error);
        appendMessage(`無法連線到伺服器。錯誤: ${error.message}`, 'bot');

        setTimeout(() => {
            appendMessage(`正在嘗試重新連接...`, 'bot');
            retryConnection();
        }, 3000);
    }
}



// 添加顯示地圖位置的消息
function appendLocationMessage(location, sender = 'user') {
    // 移除歡迎消息
    if (welcomeMessage && welcomeMessage.parentNode && sender === 'user') {
        welcomeMessage.style.display = 'none';
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);
    
    // 創建位置消息的HTML
    const locationHTML = `
        <div class="location-message">
            <div class="location-header">
                <i class="fas fa-map-marker-alt"></i>
                <strong>${location.name || '選定位置'}</strong>
            </div>
            <div class="location-address">
                ${location.address || ''}
            </div>
            <div class="location-coordinates">
                座標: ${location.coordinates || ''}
            </div>
        </div>
    `;
    
    // 添加消息內容
    messageDiv.innerHTML = locationHTML;
    
    // 添加時間戳
    const timeSpan = document.createElement('span');
    timeSpan.classList.add('message-time');
    
    const now = new Date();
    timeSpan.textContent = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;
    
    messageDiv.appendChild(timeSpan);
    chatContainer.appendChild(messageDiv);
    
    // 滾動到底部
    chatContainer.scrollTop = chatContainer.scrollHeight;
}
function handleHospitalRequest() {
    const userInputField = document.getElementById('userInput');
    const sendButton = document.getElementById('sendButton');

    // 如果已選擇位置（手動選點）
    if (window.selectedLocationInfo && window.selectedLocationInfo.name) {
        const locationName = window.selectedLocationInfo.name;
        const query = `${locationName}附近的醫院和診所`;
        userInputField.value = query;
        sendButton.click();
        return;
    }

    // 使用瀏覽器定位
    if (navigator.geolocation) {
        appendMessage("正在獲取您的位置以查詢附近醫院...", "bot");

        navigator.geolocation.getCurrentPosition(
            (position) => {
                const coords = `${position.coords.latitude},${position.coords.longitude}`;

                fetch(`https://maps.googleapis.com/maps/api/geocode/json?latlng=${coords}&key=AIzaSyAEW_iMaTrOPg0vQJJN3pMiy84-u8C_ZiE&language=zh-TW`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.results && data.results.length > 0) {
                            const address = data.results[0].formatted_address;

                            // 儲存為全域位置信息
                            window.selectedLocationInfo = {
                                name: address,
                                address: address,
                                coordinates: coords
                            };

                            const query = `${address}附近的醫院和診所`;
                            userInputField.value = query;
                            sendButton.click();
                        } else {
                            appendMessage("找不到您的具體地址資訊，請手動選擇地點或輸入地址。", "bot");
                        }
                    })
                    .catch(error => {
                        console.error("反向地理編碼錯誤:", error);
                        appendMessage("取得地址資訊失敗，請點擊地圖選擇位置或手動輸入地址。", "bot");
                    });
            },
            (error) => {
                console.error("地理定位錯誤:", error);
                appendMessage("無法獲取您的位置。請使用地圖手動選擇位置或輸入地址。", "bot");
            }
        );
    } else {
        appendMessage("您的瀏覽器不支援定位功能，請手動選擇位置或輸入地址。", "bot");
    }
}

async function sendMessage(userMessage) {
    if (!userMessage.trim()) return;
  
    const locationInfo = window.selectedLocationInfo || null;
  
    if (!currentChatId) currentChatId = Date.now().toString();
    appendMessage(userMessage, 'user');
    saveMessageToStorage(currentChatId, userMessage, 'user');
  
    if (welcomeMessage.style.display !== 'none') {
      addToHistory(userMessage, currentChatId);
    }
  
    inputField.value = '';
    showLoading(true);
  
    try {
      const response = await fetch('/chat/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
          message: userMessage,
          chat_id: currentChatId,
          location_info: locationInfo
        })
      });
  
      showLoading(false);
  
      if (!response.ok) {
        throw new Error(`Server responded with status: ${response.status}`);
      }
  
      const res = await response.json();
      const reply = typeof res === 'string' ? res : res.output || "（伺服器沒有回傳內容）";
      appendMessage(reply, 'bot');
      saveMessageToStorage(currentChatId, reply, 'bot');
  
      // 顯示位置標記
      if (res.location?.coordinates) {
        const [lat, lng] = res.location.coordinates.split(',').map(parseFloat);
        const position = { lat, lng };
  
        if (typeof google !== 'undefined' && window.map) {
          const marker = new google.maps.Marker({
            position,
            map: window.map,
            title: res.location.name || "回傳位置",
          });
  
          window.map.setCenter(position);
          window.map.setZoom(15);
  
          if (!window.markers) window.markers = [];
          window.markers.push(marker);
        }
      }
  
      // 顯示醫療標記
      if (res.data?.results?.length > 0) {
        displayHospitalsOnMap(res.data.results);
      }
  
    } catch (error) {
      showLoading(false);
      console.error("Error:", error);
      appendMessage(`無法連線到伺服器。錯誤: ${error.message}`, 'bot');
      setTimeout(() => {
        appendMessage(`正在嘗試重新連接...`, 'bot');
        retryConnection();
      }, 3000);
    }
  }
  
  
  


// 重試連接
function retryConnection() {
    fetch('/chat/', { method: 'GET' })
        .then(response => {
            if (response.ok) {
                appendMessage(`已重新連接到伺服器`, 'bot');
            } else {
                appendMessage(`無法連接到伺服器，請稍後再試`, 'bot');
            }
        })
        .catch(error => {
            appendMessage(`重新連接失敗：${error.message}`, 'bot');
        });
}

// 送出按鈕點擊事件
sendButton.addEventListener('click', () => {
    sendMessage(inputField.value);
});

// 讓使用者按 Enter 也可以送出訊息
inputField.addEventListener('keypress', e => {
    if (e.key === 'Enter') {
        sendMessage(inputField.value);
    }
});

// 建議按鈕點擊事件
suggestionButtons.forEach(button => {
    button.addEventListener('click', () => {
        const suggestion = button.textContent;
        inputField.value = suggestion;
        sendMessage(suggestion);
    });
});

// 新對話按鈕
newChatButton.addEventListener('click', () => {
    createNewChat();
});

// 檔案上傳功能
const fileInput = document.getElementById('fileInput');
fileInput.addEventListener('change', function(e) {
    if (this.files && this.files[0]) {
        const file = this.files[0];
        
        // 如果開始新對話，則生成新的聊天ID
        if (!currentChatId) {
            currentChatId = Date.now().toString();
        }
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('chat_id', currentChatId);
        formData.append('csrfmiddlewaretoken', csrfToken);
        
        // 顯示上傳中
        appendMessage(`正在上傳檔案：${file.name}...`, 'bot');
        showLoading(true);
        
        fetch('/chat/upload/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken
            }
        })
        .then(response => response.json())
        .then(data => {
            showLoading(false);
            if (data.success) {
                appendMessage(`檔案已上傳：${file.name}`, 'bot');
                appendMessage(`${data.message}`, 'bot');
                
                // 將上傳消息添加到本地存儲
                saveMessageToStorage(currentChatId, `上傳檔案：${file.name}`, 'user');
                saveMessageToStorage(currentChatId, `檔案已上傳：${file.name}`, 'bot');
                saveMessageToStorage(currentChatId, data.message, 'bot');
                
                // 將此對話添加到歷史記錄
                addToHistory(`檔案討論: ${file.name}`, currentChatId);
            } else {
                appendMessage(`檔案上傳失敗：${data.error}`, 'bot');
            }
        })
        .catch(error => {
            showLoading(false);
            appendMessage(`檔案上傳錯誤：${error.message}`, 'bot');
        });
    }
});

// 字體大小調整功能
const increaseFontBtn = document.getElementById('increaseFontBtn');
let currentFontSize = 100; // 百分比

increaseFontBtn.addEventListener('click', () => {
    currentFontSize = (currentFontSize >= 150) ? 100 : currentFontSize + 25;
    document.body.style.fontSize = `${currentFontSize}%`;
    localStorage.setItem('fontSize', currentFontSize);
});

// 語音輸入功能
const micButton = document.getElementById('micButton');
let recognition;

// 檢查瀏覽器是否支持語音識別
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.continuous = false;
    recognition.lang = 'zh-TW';
    
    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        inputField.value = transcript;
        micButton.classList.remove('active');
    };
    
    recognition.onerror = function(event) {
        console.error('Speech recognition error', event.error);
        micButton.classList.remove('active');
    };
    
    micButton.addEventListener('click', function() {
        if (micButton.classList.contains('active')) {
            recognition.stop();
            micButton.classList.remove('active');
        } else {
            recognition.start();
            micButton.classList.add('active');
        }
    });
} else {
    micButton.style.display = 'none';
}

// 朗讀文字功能
const voiceReadBtn = document.getElementById('voiceReadBtn');

voiceReadBtn.addEventListener('click', () => {
    // 獲取最後一條機器人消息
    const botMessages = document.querySelectorAll('.message.bot');
    if (botMessages.length > 0) {
        const lastBotMessage = botMessages[botMessages.length - 1];
        const textToRead = lastBotMessage.textContent.replace(/\d+:\d+$/, '').trim(); // 移除時間戳
        
        if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(textToRead);
            utterance.lang = 'zh-TW';
            window.speechSynthesis.speak(utterance);
        } else {
            alert('您的瀏覽器不支持語音合成功能');
        }
    }
});

// 從服務器獲取所有聊天歷史 - 修復版
function fetchAllChatHistory() {
    showLoading(true);
    
    fetch('/chat/history/', {
        method: 'GET',
        headers: {
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {
        showLoading(false);
        
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
            initChatHistory();
        } else {
            // 即使沒有聊天記錄，也初始化列表（基於本地存儲）
            initChatHistory();
        }
    })
    .catch(error => {
        console.error("獲取所有聊天歷史錯誤:", error);
        showLoading(false);
        
        // 如果無法從服務器獲取，使用本地存儲初始化
        initChatHistory();
    });
}

// 同步對話歷史到服務器 - 修復版
function syncChatHistory() {
    try {
        const chats = JSON.parse(localStorage.getItem('chats') || '{}');
        
        Object.values(chats).forEach(chat => {
            // 對每個聊天記錄嘗試同步
            if (chat.messages && chat.messages.length > 0) {
                // 檢查是否是新對話（無對應的伺服器記錄）
                fetch(`/chat/history/${chat.id}/`, {
                    method: 'GET',
                    headers: {
                        'X-CSRFToken': csrfToken
                    }
                })
                .then(response => {
                    if (!response.ok && response.status === 404) {
                        // 如果對話在伺服器上不存在，創建它
                        return fetch('/chat/new/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken
                            },
                            body: JSON.stringify({ chat_id: chat.id })
                        });
                    }
                    return null;
                })
                .catch(error => {
                    console.error("同步對話時出錯:", error);
                });
            }
        });
    } catch (e) {
        console.error("同步對話歷史時發生錯誤:", e);
    }
}

// 在 chat.js 文件中修改 hospitalsFound 事件處理

document.addEventListener('hospitalsFound', function(e) {
    const data = e.detail;
    const hospitals = data.hospitals;
    const location = data.location;

    console.log("接收到醫院數據:", hospitals);
    appendMessage(`我在 ${location.name} 附近搜尋了醫療設施`, 'user');

    if (hospitals && hospitals.length > 0) {
        // 格式化顯示醫院信息
        let message = `<div class="hospital-results">
            <p>好的，根據您提供的「${location.name}」位置，我為您找到附近的一些醫院：</p>`;
        
        hospitals.forEach((hospital, index) => {
            message += `
                <div class="hospital-item">
                    <p>${index + 1}. <strong>${hospital.name}</strong></p>
                    <ul class="hospital-details">
                        <li>地址：${hospital.address}</li>
                        ${hospital.rating ? `<li>評分：${hospital.rating}/5.0</li>` : '<li>評分：無評分/5.0</li>'}
                    </ul>
                </div>
            `;
        });
        
        message += `<p>希望這些資訊對您有幫助。如果您需要更精確的搜尋結果，建議您使用地圖功能選擇一個更精確的地點。</p>`;
        
        message += `
            <div class="hospital-footer">
                <button id="viewOnMapBtn" class="primary-button">
                    <i class="fas fa-map-marked-alt"></i> 在地圖上查看
                </button>
            </div>
        </div>`;

        appendMessage(message, 'bot');

        // 處理完醫院數據後立即顯示地圖並添加標記
        setTimeout(() => {
            // 1. 先顯示地圖模態框
            showMapModal();
            
            // 2. 將醫院數據轉換為地圖可用格式
            const mapReadyHospitals = hospitals.map(hospital => {
                // 檢查並轉換座標
                let lat, lng;
                
                // 處理來自API的可能格式
                if (typeof hospital.lat === 'string') {
                    lat = parseFloat(hospital.lat);
                } else if (typeof hospital.latitude === 'string') {
                    lat = parseFloat(hospital.latitude);
                } else {
                    lat = hospital.lat || hospital.latitude;
                }
                
                if (typeof hospital.lng === 'string') {
                    lng = parseFloat(hospital.lng);
                } else if (typeof hospital.longitude === 'string') {
                    lng = parseFloat(hospital.longitude);
                } else {
                    lng = hospital.lng || hospital.longitude;
                }
                
                // 返回標準化的醫院數據
                return {
                    name: hospital.name,
                    address: hospital.address || hospital.vicinity || "",
                    lat: lat,
                    lng: lng,
                    rating: hospital.rating || null,
                    place_id: hospital.place_id || null
                };
            });
            
            console.log("準備添加到地圖的醫院數據:", mapReadyHospitals);
            
            // 3. 直接調用地圖標記函數
            try {
                // 等待地圖加載完成
                setTimeout(() => {
                    createHospitalMarkers(mapReadyHospitals);
                }, 500);
            } catch (e) {
                console.error("創建醫院標記時出錯:", e);
            }
            
            // 4. 註冊查看地圖按鈕事件
            const viewMapBtn = document.getElementById('viewOnMapBtn');
            if (viewMapBtn) {
                viewMapBtn.addEventListener('click', function() {
                    showMapModal();
                    
                    // 再次嘗試添加標記
                    setTimeout(() => {
                        createHospitalMarkers(mapReadyHospitals);
                    }, 300);
                });
            }
        }, 300);

    } else {
        appendMessage("抱歉，在所選位置附近找不到醫療設施。請嘗試選擇不同的位置或擴大搜尋範圍。", 'bot');
    }

    // 儲存對話
    if (!currentChatId) {
        currentChatId = Date.now().toString();
    }
    saveMessageToStorage(currentChatId, `我在 ${location.name} 附近搜尋了醫療設施`, 'user');
});

// 創建醫院標記的專用函數
function createHospitalMarkers(hospitals) {
    console.log("開始創建醫院標記，數量:", hospitals.length);

    const mapDiv = document.getElementById('map');
    if (!mapDiv) {
        console.error("找不到地圖容器 #map");
        return;
    }

    // 確保 Google Map 已經掛上去
    if (typeof google === 'undefined' || !window.map) {
        console.error("Google Maps 尚未初始化");
        return;
    }

    // 確保標記數組存在
    if (!window.markers) {
        window.markers = [];
    } else {
        // 清除現有標記
        window.markers.forEach(marker => {
            if (marker && typeof marker.setMap === 'function') {
                marker.setMap(null);
            }
        });
        window.markers = [];
    }

    const bounds = new google.maps.LatLngBounds();

    hospitals.forEach((hospital, index) => {
        if (!hospital.lat || !hospital.lng || isNaN(hospital.lat) || isNaN(hospital.lng)) {
            console.warn(`醫院 "${hospital.name}" 座標無效`, hospital);
            return;
        }

        const lat = parseFloat(hospital.lat);
        const lng = parseFloat(hospital.lng);
        const position = { lat, lng };

        const marker = new google.maps.Marker({
            position,
            map: window.map,
            title: hospital.name,
            animation: google.maps.Animation.DROP,
            label: {
                text: (index + 1).toString(),
                color: '#ffffff',
                fontSize: '14px',
                fontWeight: 'bold'
            },
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 14,
                fillColor: '#e53935',
                fillOpacity: 1,
                strokeColor: '#ffffff',
                strokeWeight: 2
            }
        });

        // InfoWindow
        const infoWindow = new google.maps.InfoWindow({
            content: `
                <div class="hospital-info-window">
                    <h3>${hospital.name}</h3>
                    <p><strong>地址:</strong> ${hospital.address || '無資料'}</p>
                    ${hospital.rating ? `<p><strong>評分:</strong> ${hospital.rating}/5.0</p>` : ''}
                </div>
            `
        });

        marker.addListener('click', () => {
            window.markers.forEach(m => {
                if (m.infoWindow) m.infoWindow.close();
            });
            infoWindow.open(window.map, marker);
        });

        marker.infoWindow = infoWindow;

        window.markers.push(marker);
        bounds.extend(position);
    });

    if (window.markers.length > 0) {
        window.map.fitBounds(bounds);
        if (window.markers.length === 1) {
            window.map.setZoom(15);
        }
    }
}


// 使用 gmp-map 元素直接添加標記
function addMarkersToMapElement(hospitals, mapElement) {
    console.log("使用地圖元素直接添加標記");
    
    // 清除舊標記
    const oldMarkers = mapElement.querySelectorAll('gmp-advanced-marker');
    oldMarkers.forEach(marker => marker.remove());
    
    // 添加新標記
    hospitals.forEach((hospital, index) => {
        if (!hospital.lat || !hospital.lng || isNaN(hospital.lat) || isNaN(hospital.lng)) {
            console.warn(`醫院 "${hospital.name}" 座標無效`);
            return;
        }
        
        const lat = parseFloat(hospital.lat);
        const lng = parseFloat(hospital.lng);
        
        try {
            const marker = document.createElement('gmp-advanced-marker');
            marker.setAttribute('position', `${lat},${lng}`);
            marker.setAttribute('title', hospital.name);
            
            // 創建標記內容
            const markerContent = document.createElement('div');
            markerContent.className = 'map-marker';
            markerContent.textContent = (index + 1).toString();
            
            marker.appendChild(markerContent);
            mapElement.appendChild(marker);
            
            console.log(`使用地圖元素添加標記 #${index + 1}:`, hospital.name);
        } catch (e) {
            console.error(`創建標記元素時出錯:`, e);
        }
    });
    
    // 嘗試調整地圖視圖
    try {
        const points = hospitals
            .filter(h => h.lat && h.lng && !isNaN(h.lat) && !isNaN(h.lng))
            .map(h => `${parseFloat(h.lat)},${parseFloat(h.lng)}`);
        
        if (points.length > 0) {
            // 使用第一個點作為中心點
            mapElement.setAttribute('center', points[0]);
            mapElement.setAttribute('zoom', '14');
            console.log("已設置地圖中心點");
        }
    } catch (e) {
        console.error("設置地圖視圖時出錯:", e);
    }
}

// 加入地圖顯示標記的函式
window.setMapMarkers = function(hospitals) {
    if (!window.map || !window.google || !hospitals) {
        console.error("無法設置標記：地圖未初始化或沒有醫院數據");
        return;
    }

    // 確保 markers 陣列存在
    if (!window.markers) window.markers = [];
    
    // 清除舊標記
    window.markers.forEach(marker => marker.setMap(null));
    window.markers = [];

    const bounds = new google.maps.LatLngBounds();

    // 添加每個醫院的標記
    hospitals.forEach((hospital, index) => {
        const lat = parseFloat(hospital.lat);
        const lng = parseFloat(hospital.lng);
        
        // 確保座標有效
        if (isNaN(lat) || isNaN(lng)) {
            console.warn(`醫院 ${hospital.name} 座標無效`);
            return;
        }

        const position = { lat, lng };
        
        // 自定義標記樣式
        const marker = new google.maps.Marker({
            position: position,
            map: window.map,
            title: hospital.name,
            animation: google.maps.Animation.DROP,
            label: {
                text: (index + 1).toString(),
                color: '#FFFFFF',
                fontSize: '14px',
                fontWeight: 'bold'
            },
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                scale: 14,
                fillColor: '#e53935',
                fillOpacity: 1,
                strokeColor: '#FFFFFF',
                strokeWeight: 2
            }
        });

        // 添加點擊事件顯示信息窗口
        const infoWindow = new google.maps.InfoWindow({
            content: `
                <div class="hospital-info-window">
                    <h3>${hospital.name}</h3>
                    <div><strong>地址:</strong> ${hospital.address || '無資料'}</div>
                    ${hospital.rating ? `<div><strong>評分:</strong> ${hospital.rating}/5.0</div>` : ''}
                    <div class="hospital-actions">
                        <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(hospital.name)}" 
                           target="_blank" class="map-link">
                            在 Google Maps 中開啟
                        </a>
                    </div>
                </div>
            `
        });

        marker.addListener('click', () => {
            // 關閉所有已開啟的信息窗口
            window.markers.forEach(m => {
                if (m.infoWindow && m.infoWindow.getMap()) {
                    m.infoWindow.close();
                }
            });
            
            // 打開當前標記的信息窗口
            infoWindow.open(window.map, marker);
        });

        // 保存信息窗口引用
        marker.infoWindow = infoWindow;
        
        // 添加到標記陣列
        window.markers.push(marker);
        
        // 擴展地圖邊界
        bounds.extend(position);
    });

    // 如果至少有一個有效標記，調整地圖視圖
    if (window.markers.length > 0) {
        window.map.fitBounds(bounds);
        
        // 如果只有一個標記，設置適當的縮放級別
        if (window.markers.length === 1) {
            window.map.setZoom(15);
        }
    }
    
    return window.markers.length; // 返回添加的標記數量
};

// 修正地圖標記功能，確保標記能顯示在地圖上
function updateMapMarkers(hospitals) {
    console.log("正在更新地圖標記:", hospitals);
    
    // 延遲執行，確保地圖已載入
    setTimeout(() => {
        if (typeof window.setMapMarkers === 'function') {
            const markerCount = window.setMapMarkers(hospitals);
            console.log(`成功在地圖上標記了 ${markerCount} 個醫院`);
        } else {
            console.warn("地圖標記功能尚未準備好，嘗試再次延遲加載");
            
            // 再次延遲並重試
            setTimeout(() => {
                if (typeof window.setMapMarkers === 'function') {
                    window.setMapMarkers(hospitals);
                } else {
                    console.error("無法加載地圖標記功能");
                }
            }, 1000);
        }
    }, 300);
}

// 添加醫院結果樣式
function addHospitalStyles() {
    const style = document.createElement('style');
    style.textContent = `
        .hospital-results {
            background-color: var(--background-lighter);
            border-radius: 12px;
            padding: 18px;
            margin-top: 10px;
        }

        .hospital-item {
            margin-bottom: 16px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
        }

        .hospital-item:last-child {
            border-bottom: none;
        }

        .hospital-item p {
            margin: 0 0 5px 0;
        }

        .hospital-item strong {
            color: var(--primary-color);
            font-size: 16px;
        }

        .hospital-details {
            list-style-type: none;
            padding-left: 20px;
            margin: 5px 0 0 0;
            color: var(--text-secondary);
            font-size: 14px;
        }

        .hospital-details li {
            margin-bottom: 3px;
        }

        .hospital-footer {
            margin-top: 15px;
            display: flex;
            justify-content: center;
        }
    `;
    document.head.appendChild(style);
}

// 在頁面加載時添加樣式
// 調整頁面載入事件
document.addEventListener('DOMContentLoaded', function() {
    try {
        console.log("初始化聊天界面...");
        
        // 加入錯誤處理
        window.onerror = function(message, source, lineno, colno, error) {
            console.error("JavaScript錯誤:", message, "在", source, "第", lineno, "行");
            return false;
        };
        
        // 添加醫院樣式
        addHospitalStyles();
        
        // 從服務器獲取所有聊天歷史
        fetchAllChatHistory();
        
        // 同步對話歷史到服務器
        syncChatHistory();
        
        // 載入字體大小設置
        const savedFontSize = localStorage.getItem('fontSize');
        if (savedFontSize) {
            currentFontSize = parseInt(savedFontSize);
            document.body.style.fontSize = `${currentFontSize}%`;
        }
        
        // 讓輸入框獲得焦點
        const inputField = document.getElementById('userInput');
        if (inputField) {
            inputField.focus();
        } else {
            console.error("找不到輸入框元素 'userInput'");
        }
        
        // 設置進度條初始狀態
        const progressBar = document.getElementById('progressBar');
        if (progressBar) {
            progressBar.style.display = 'none';
        } else {
            console.error("找不到進度條元素 'progressBar'");
        }
        
        // 生成初始聊天ID（如果沒有載入現有聊天）
        if (!currentChatId) {
            currentChatId = Date.now().toString();
            console.log("創建新聊天ID:", currentChatId);
        }
        
        // 註冊按鈕事件
        registerEventListeners();
        
        console.log("聊天界面初始化完成");
    } catch (e) {
        console.error("初始化時發生錯誤:", e);
    }
});

function registerEventListeners() {
    try {
        console.log("註冊事件監聽器...");
        
        // 送出按鈕
        const sendButton = document.getElementById('sendButton');
        if (sendButton) {
            sendButton.addEventListener('click', () => {
                const inputField = document.getElementById('userInput');
                if (inputField) {
                    sendMessage(inputField.value);
                }
            });
            console.log("已註冊送出按鈕事件");
        } else {
            console.error("找不到送出按鈕元素 'sendButton'");
        }
        
        // 輸入框 Enter 鍵
        const inputField = document.getElementById('userInput');
        if (inputField) {
            inputField.addEventListener('keypress', e => {
                if (e.key === 'Enter') {
                    sendMessage(inputField.value);
                }
            });
            console.log("已註冊輸入框事件");
        }
        
        // 建議按鈕
        const suggestionButtons = document.querySelectorAll('.suggestion-btn');
        if (suggestionButtons.length > 0) {
            suggestionButtons.forEach(button => {
                button.addEventListener('click', () => {
                    const suggestion = button.textContent;
                    if (inputField) {
                        inputField.value = suggestion;
                    }
                    sendMessage(suggestion);
                });
            });
            console.log(`已註冊 ${suggestionButtons.length} 個建議按鈕事件`);
        } else {
            console.log("未找到建議按鈕");
        }
        
        // 新對話按鈕
        const newChatButton = document.getElementById('newChatButton');
        if (newChatButton) {
            newChatButton.addEventListener('click', () => {
                createNewChat();
            });
            console.log("已註冊新對話按鈕事件");
        }
        
        // 其他按鈕...添加更多需要的事件
        
        console.log("所有事件監聽器註冊完成");
    } catch (e) {
        console.error("註冊事件監聽器時發生錯誤:", e);
    }
}