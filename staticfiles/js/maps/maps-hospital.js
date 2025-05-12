/**
 * 完整的maps-hospital.js修復
 * 
 * 修復以下問題：
 * 1. 添加缺失的displayHospitals方法
 * 2. 修改searchNearbyHospitals方法以過濾不相關結果
 * 3. 確保所有方法正確連接
 */

// 確保MedApp.maps.hospital命名空間存在
if (!MedApp.maps.hospital) {
    MedApp.maps.hospital = {};
  }
  
  // 初始化方法 - 保留原有的init方法
  MedApp.maps.hospital.init = MedApp.maps.hospital.init || function() {
    this.bindEvents();
    MedApp.log('醫院標記模組初始化完成', 'info');
  };
  
  // 綁定事件處理 - 保留原有的bindEvents方法
  MedApp.maps.hospital.bindEvents = MedApp.maps.hospital.bindEvents || function() {
    // 監聽醫院數據事件
    document.addEventListener('hospitalsFound', (e) => {
      const data = e.detail;
      this.handleHospitalsFound(data.hospitals, data.location);
    });
  };
  
  // 處理找到醫院事件 - 保留原有的handleHospitalsFound方法
  MedApp.maps.hospital.handleHospitalsFound = MedApp.maps.hospital.handleHospitalsFound || function(hospitals, location) {
    // 顯示醫院資訊在聊天中
    MedApp.chat.display.displayHospitalResults(hospitals, location);
    
    // 自動顯示地圖並添加標記
    setTimeout(() => {
      MedApp.maps.core.showMapModal();
      
      // 等待地圖載入完成
      setTimeout(() => {
        this.createHospitalMarkers(hospitals);
      }, 500);
    }, 300);
  };
  
  // 修復 - 添加缺失的displayHospitals方法
  MedApp.maps.hospital.displayHospitals = function(hospitals, location) {
    if (!hospitals || !hospitals.length || !location) {
      MedApp.log("沒有醫院數據可顯示", 'warn');
      return;
    }
    
    // 清除現有標記
    if (MedApp.maps.core && MedApp.maps.core.clearMarkers) {
      MedApp.maps.core.clearMarkers();
    }
    
    // 創建醫院標記
    this.createHospitalMarkers(hospitals);
    
    // 發送醫院結果到聊天
    this.sendHospitalsToChat(hospitals);
  };
  
  // 搜尋附近醫院方法 - 修改過的searchNearbyHospitals方法
  MedApp.maps.hospital.searchNearbyHospitals = function() {
    MedApp.log("搜尋附近醫院...", 'info');
    
    // 確保有選定位置
    if (!MedApp.state.selectedLocation || !MedApp.state.selectedLocation.coordinates) {
      // 如果沒有選定位置，使用當前地圖中心
      if (MedApp.maps.core.map) {
        const center = MedApp.maps.core.map.getCenter();
        MedApp.state.selectedLocation = {
          name: "當前地圖中心",
          address: `座標: ${center.lat().toFixed(6)}, ${center.lng().toFixed(6)}`,
          coordinates: `${center.lat()},${center.lng()}`
        };
      } else {
        alert("請先選擇一個位置");
        return;
      }
    }
    
    // 顯示載入提示
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'map-loading';
    loadingDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在搜尋醫療設施...';
    document.querySelector('.map-modal-body')?.appendChild(loadingDiv);
    
    // 獲取座標
    const [lat, lng] = MedApp.state.selectedLocation.coordinates.split(',').map(parseFloat);
    const location = new google.maps.LatLng(lat, lng);
    
    // 確保 Places 服務可用
    if (!MedApp.maps.core.services.placesService) {
      MedApp.log("Places 服務未初始化", 'error');
      document.querySelector('.map-loading')?.remove();
      alert("無法使用地點搜尋服務，請稍後再試");
      return;
    }
    
    // 搜尋參數 - 更精確的關鍵詞和類型
    const request = {
      location: location,
      radius: 2000, // 2公里範圍
      type: 'hospital', // 主類型為醫院
      keyword: '醫院 診所 醫療中心', // 明確指定醫療設施的關鍵詞
    };
    
    // 使用 Places API 進行附近搜尋
    MedApp.maps.core.services.placesService.nearbySearch(request, (results, status) => {
      // 移除載入提示
      document.querySelector('.map-loading')?.remove();
      
      if (status === google.maps.places.PlacesServiceStatus.OK && results && results.length > 0) {
        MedApp.log(`找到 ${results.length} 個醫療設施，開始過濾...`, 'info');
        
        // 過濾結果 - 移除不相關結果
        const hospitals = results.filter(place => {
          // 排除動物醫院
          const isAnimalHospital = 
            (place.name && (
              place.name.includes('動物') || 
              place.name.includes('寵物') || 
              place.name.includes('獸醫')
            )) || 
            (place.types && place.types.includes('veterinary_care'));
          
          // 排除只有"藥局"名稱的結果
          const isGenericPharmacy = 
            place.name === '藥局' || 
            place.name === 'Pharmacy' || 
            place.name === '藥房';
          
          // 確保有有效名稱
          const hasValidName = place.name && place.name.length > 1;
          
          return !isAnimalHospital && !isGenericPharmacy && hasValidName;
        }).map(place => {
          return {
            name: place.name,
            address: place.vicinity,
            lat: place.geometry.location.lat(),
            lng: place.geometry.location.lng(),
            rating: place.rating,
            place_id: place.place_id,
            types: place.types
          };
        });
        
        // 限制結果數量
        const filteredHospitals = hospitals.slice(0, 8);
        
        if (filteredHospitals.length > 0) {
          MedApp.log(`過濾後找到 ${filteredHospitals.length} 個醫療設施`, 'info');
          
          // 在地圖上顯示醫院
          this.displayHospitals(filteredHospitals, MedApp.state.selectedLocation);
        } else {
          MedApp.log("過濾後沒有找到合適的醫療設施", 'warn');
          alert("在所選位置附近找不到合適的醫療設施，請嘗試擴大搜尋範圍或選擇不同的位置。");
        }
      } else {
        MedApp.log("搜尋醫院失敗: " + status, 'error');
        
        if (status === google.maps.places.PlacesServiceStatus.ZERO_RESULTS) {
          alert("在所選位置附近找不到醫院，請嘗試調整搜尋範圍或選擇不同的位置。");
        } else {
          alert("搜尋醫院時發生錯誤，請稍後再試。");
        }
      }
    });
  };
  
  // 保留原有的createHospitalMarkers方法，或添加缺失的版本
  if (!MedApp.maps.hospital.createHospitalMarkers) {
    MedApp.maps.hospital.createHospitalMarkers = function(hospitals) {
      if (!hospitals || !hospitals.length) {
        MedApp.log("沒有醫院數據可顯示", 'warn');
        return;
      }
      
      // 檢查地圖是否初始化
      if (!MedApp.maps.core.map) {
        MedApp.log("地圖未初始化", 'error');
        return;
      }
      
      // 清除現有標記
      if (MedApp.maps.core.clearMarkers) {
        MedApp.maps.core.clearMarkers();
      }
      
      // 創建邊界物件以自動調整地圖視圖
      const bounds = new google.maps.LatLngBounds();
      
      // 如果有選定位置，先添加標記並納入邊界
      if (MedApp.state.selectedLocation && MedApp.state.selectedLocation.coordinates) {
        const [lat, lng] = MedApp.state.selectedLocation.coordinates.split(',').map(parseFloat);
        const position = new google.maps.LatLng(lat, lng);
        
        const marker = new google.maps.Marker({
          position: position,
          map: MedApp.maps.core.map,
          title: "選定位置",
          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            fillColor: '#7c9eff',
            fillOpacity: 1,
            strokeColor: '#FFFFFF',
            strokeWeight: 2,
            scale: 12
          },
          zIndex: 1 // 確保顯示在其他標記上方
        });
        
        if (MedApp.maps.core.markers) {
          MedApp.maps.core.markers.push(marker);
        }
        bounds.extend(position);
      }
      
      // 添加每個醫院的標記
      hospitals.forEach((hospital, index) => {
        if (!hospital.lat || !hospital.lng || isNaN(hospital.lat) || isNaN(hospital.lng)) {
          MedApp.log(`醫院 "${hospital.name}" 座標無效`, 'warn');
          return;
        }
        
        // 創建醫院位置
        const lat = parseFloat(hospital.lat);
        const lng = parseFloat(hospital.lng);
        const position = new google.maps.LatLng(lat, lng);
        
        // 將位置添加到邊界
        bounds.extend(position);
        
        // 創建自定義標記
        const hospitalMarker = new google.maps.Marker({
          position: position,
          map: MedApp.maps.core.map,
          title: hospital.name,
          icon: {
            path: google.maps.SymbolPath.CIRCLE,
            fillColor: '#e53935',
            fillOpacity: 1,
            strokeColor: '#FFFFFF',
            strokeWeight: 2,
            scale: 12
          },
          label: {
            text: (index + 1).toString(),
            color: '#FFFFFF',
            fontSize: '14px',
            fontWeight: 'bold'
          },
          animation: google.maps.Animation.DROP
        });
        
        // 創建信息窗口內容
        const content = `
          <div class="hospital-info-window">
            <h3>${hospital.name}</h3>
            <p><strong>地址:</strong> ${hospital.address || '無資料'}</p>
            ${hospital.rating ? `<p><strong>評分:</strong> ${hospital.rating}/5.0</p>` : ''}
            <div class="hospital-actions">
              <button id="directionBtn-${index}" class="direction-btn">
                <i class="fas fa-directions"></i> 路線規劃
              </button>
              <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(hospital.name)}&query_place_id=${hospital.place_id}" 
                target="_blank" class="map-link">
                <i class="fas fa-external-link-alt"></i> Google Maps
              </a>
            </div>
          </div>
        `;
        
        // 添加點擊事件
        hospitalMarker.addListener('click', () => {
          // 關閉所有已打開的信息窗口
          if (MedApp.maps.core.infoWindow) {
            MedApp.maps.core.infoWindow.close();
          }
          
          // 設置并打開信息窗口
          if (MedApp.maps.core.infoWindow) {
            MedApp.maps.core.infoWindow.setContent(content);
            MedApp.maps.core.infoWindow.open(MedApp.maps.core.map, hospitalMarker);
            
            // 添加路線規劃按鈕事件
            setTimeout(() => {
              const directionBtn = document.getElementById(`directionBtn-${index}`);
              if (directionBtn && MedApp.maps.direction) {
                directionBtn.addEventListener('click', () => {
                  MedApp.maps.direction.calculateAndDisplayRoute(position, hospital.name);
                });
              }
            }, 100);
          }
        });
        
        // 將標記添加到數組
        if (MedApp.maps.core.markers) {
          MedApp.maps.core.markers.push(hospitalMarker);
        }
      });
      
      // 調整地圖視圖以顯示所有標記
      MedApp.maps.core.map.fitBounds(bounds);
      
      // 如果只有一個醫院，設置合適的縮放級別
      if (hospitals.length === 1) {
        MedApp.maps.core.map.setZoom(16);
      }
      
      MedApp.log("醫院標記添加完成，共 " + hospitals.length + " 個", 'info');
    };
  }
  
  // 保留原有的sendHospitalsToChat方法，或添加缺失的版本
  if (!MedApp.maps.hospital.sendHospitalsToChat) {
    MedApp.maps.hospital.sendHospitalsToChat = function(hospitals) {
      // 確保有位置信息
      if (!MedApp.state.selectedLocation) {
        MedApp.log("沒有選定位置信息", 'warn');
        return;
      }
      
      // 創建事件來傳遞醫院資訊
      const event = new CustomEvent('hospitalsFound', {
        detail: {
          hospitals: hospitals,
          location: MedApp.state.selectedLocation
        }
      });
      
      // 分發事件
      document.dispatchEvent(event);
      MedApp.log("醫院信息已發送到聊天", 'info');
    };
  }
  
  // 添加HTML顯示修復功能 - 可以在這裡直接添加，或放到單獨的文件中
  if (!MedApp.utils.htmlEntities) {
    MedApp.utils.htmlEntities = {
      // 解碼HTML實體
      decode: function(str) {
        if (!str) return '';
        
        // 使用textarea元素的原生HTML解碼能力
        const textarea = document.createElement('textarea');
        textarea.innerHTML = str;
        return textarea.value;
      },
      
      // 編碼HTML實體
      encode: function(str) {
        if (!str) return '';
        
        // 使用div和textNode進行HTML編碼
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
      }
    };
  }
  
  // 修復已存在的消息中的HTML顯示問題
  function fixExistingMessages() {
    console.log("執行現有消息HTML修復...");
    
    // 查找所有機器人消息
    const botMessages = document.querySelectorAll('.message.bot');
    
    // 遍歷每條消息
    botMessages.forEach(messageDiv => {
      // 檢查內容是否包含未渲染的HTML標籤
      const content = messageDiv.innerHTML;
      
      if (content.includes('&lt;div') || 
          content.includes('&lt;p') || 
          content.includes('&lt;strong')) {
        
        // 獲取時間戳記 (如果有)
        let timeSpan = messageDiv.querySelector('.message-time');
        let timeSpanHTML = '';
        
        if (timeSpan) {
          timeSpanHTML = timeSpan.outerHTML;
        }
        
        // 解碼HTML內容
        let decodedContent = MedApp.utils.htmlEntities.decode(content);
        
        // 如果是結尾有時間戳，確保保留時間戳
        if (timeSpanHTML && !decodedContent.includes(timeSpanHTML)) {
          decodedContent = decodedContent.replace(/<\/div>$/, timeSpanHTML + '</div>');
        }
        
        // 更新消息內容
        messageDiv.innerHTML = decodedContent;
        
        // 如果缺少時間戳，重新添加
        if (timeSpanHTML && !messageDiv.querySelector('.message-time')) {
          messageDiv.innerHTML += timeSpanHTML;
        }
      }
    });
  }
  
  // 在頁面加載時執行修復
  setTimeout(fixExistingMessages, 1000);
  
  console.log("醫院搜索功能和HTML顯示修復已加載");