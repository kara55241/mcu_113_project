/**
 * maps-search.js - 地圖搜索功能
 * 負責地圖搜索和地點查詢功能
 */

MedApp.maps.search = {
    // 搜索工具
    searchBox: null,
    
    // DOM 元素引用
    elements: {
      searchInput: null,
      searchButton: null
    },
    
    // 初始化
    init: function() {
      this.initElements();
      
      MedApp.log('地圖搜索模組初始化完成', 'info');
    },
    
    // 初始化 DOM 元素引用
    initElements: function() {
      this.elements.searchInput = document.getElementById('locationSearch');
      this.elements.searchButton = document.getElementById('locationSearchBtn');
    },
    
    // 設置搜索框
    setupSearchBox: function() {
      // 獲取搜索輸入框
      if (!this.elements.searchInput) {
        MedApp.log("找不到地點搜索輸入框", 'warn');
        return;
      }
      
      try {
        // 確保地圖和Google API已加載
        if (!window.google || !window.google.maps || !window.google.maps.places || !MedApp.maps.core.map) {
          MedApp.log("Google Maps Places API 尚未加載或地圖未初始化", 'warn');
          return;
        }
        
        // 創建搜索框
        this.searchBox = new google.maps.places.SearchBox(this.elements.searchInput);
        
        // 限制在當前地圖視圖內搜索
        MedApp.maps.core.map.addListener('bounds_changed', () => {
          this.searchBox.setBounds(MedApp.maps.core.map.getBounds());
        });
        
        // 監聽搜索框選擇事件
        this.searchBox.addListener('places_changed', () => {
          this.handlePlacesChanged();
        });
        
        // 搜索按鈕點擊事件
        if (this.elements.searchButton) {
          this.elements.searchButton.addEventListener('click', () => {
            this.handleSearchButtonClick();
          });
        }
        
        // 回車鍵搜索
        this.elements.searchInput.addEventListener('keydown', (event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            if (this.elements.searchButton) {
              this.elements.searchButton.click();
            }
          }
        });
        
        MedApp.log("地點搜索框設置完成", 'info');
      } catch (e) {
        MedApp.log("設置搜索框時出錯: " + e.message, 'error');
      }
    },
    
    // 處理地點變更事件
    handlePlacesChanged: function() {
      const places = this.searchBox.getPlaces();
      
      if (!places || places.length === 0) {
        return;
      }
      
      // 清除現有標記
      MedApp.maps.core.clearMarkers();
      
      // 創建邊界對象
      const bounds = new google.maps.LatLngBounds();
      
      // 為每個地點添加標記
      places.forEach((place) => {
        if (!place.geometry || !place.geometry.location) {
          MedApp.log("返回的地點不包含幾何信息", 'warn');
          return;
        }
        
        // 創建標記
        const marker = new google.maps.Marker({
          map: MedApp.maps.core.map,
          title: place.name,
          position: place.geometry.location,
          animation: google.maps.Animation.DROP
        });
        
        // 將地點信息保存到全局
        MedApp.state.selectedLocation = {
          name: place.name,
          address: place.formatted_address || place.vicinity || "",
          coordinates: `${place.geometry.location.lat()},${place.geometry.location.lng()}`
        };
        
        // 添加點擊事件
        marker.addListener('click', () => {
          // 顯示信息窗口
          const content = `
            <div class="info-window-content">
              <strong>${place.name || "選定位置"}</strong>
              <p>${place.formatted_address || place.vicinity || ""}</p>
              <button id="selectThisLocation" class="select-location-btn">選擇此位置</button>
            </div>
          `;
          
          MedApp.maps.core.infoWindow.setContent(content);
          MedApp.maps.core.infoWindow.open(MedApp.maps.core.map, marker);
          
          // 添加選擇按鈕事件
          setTimeout(() => {
            const selectBtn = document.getElementById('selectThisLocation');
            if (selectBtn) {
              selectBtn.addEventListener('click', () => {
                MedApp.maps.core.selectLocation();
              });
            }
          }, 100);
        });
        
        // 添加到標記數組
        MedApp.maps.core.markers.push(marker);
        
        // 如果地點有視圖範圍，使用它；否則，使用位置
        if (place.geometry.viewport) {
          bounds.union(place.geometry.viewport);
        } else {
          bounds.extend(place.geometry.location);
        }
      });
      
      // 調整地圖視圖
      MedApp.maps.core.map.fitBounds(bounds);
      
      // 如果只有一個結果，設置合適的縮放級別
      if (places.length === 1) {
        MedApp.maps.core.map.setZoom(16);
        
        // 自動打開信息窗口
        setTimeout(() => {
          if (MedApp.maps.core.markers[0]) {
            google.maps.event.trigger(MedApp.maps.core.markers[0], 'click');
          }
        }, 500);
      }
      
      MedApp.log("地點搜索完成，找到 " + places.length + " 個結果", 'info');
    },
    
    // 處理搜索按鈕點擊
    handleSearchButtonClick: function() {
      // 檢查輸入是否為經緯度格式
      const input = this.elements.searchInput.value.trim();
      if (this.isLatLngString(input)) {
        this.handleLatLngSearch(input);
      } else {
        // 觸發 PlacesSearch
        this.searchBox.dispatchEvent(new Event('places_changed'));
        
        // 如果搜索框沒有結果，嘗試使用 Geocoder
        setTimeout(() => {
          if (MedApp.maps.core.markers.length === 0) {
            this.geocodeAddress(input);
          }
        }, 500);
      }
    },
    
    // 處理經緯度搜索
    handleLatLngSearch: function(input) {
      // 解析經緯度
      const [lat, lng] = this.parseLatLng(input);
      const latLng = new google.maps.LatLng(lat, lng);
      
      // 更新地圖中心
      MedApp.maps.core.map.setCenter(latLng);
      MedApp.maps.core.map.setZoom(16);
      
      // 清除現有標記並創建新標記
      MedApp.maps.core.clearMarkers();
      
      const marker = new google.maps.Marker({
        position: latLng,
        map: MedApp.maps.core.map,
        animation: google.maps.Animation.DROP
      });
      
      MedApp.maps.core.markers.push(marker);
      
      // 進行反向地理編碼
      MedApp.maps.core.services.geocoder.geocode({ location: latLng }, (results, status) => {
        if (status === 'OK' && results[0]) {
          // 保存地點信息
          MedApp.state.selectedLocation = {
            name: results[0].formatted_address,
            address: results[0].formatted_address,
            coordinates: `${lat},${lng}`
          };
          
          // 顯示信息窗口
          const content = `
            <div class="info-window-content">
              <strong>${results[0].formatted_address}</strong>
              <p>座標: ${lat}, ${lng}</p>
              <button id="selectThisLocation" class="select-location-btn">選擇此位置</button>
            </div>
          `;
          
          MedApp.maps.core.infoWindow.setContent(content);
          MedApp.maps.core.infoWindow.open(MedApp.maps.core.map, marker);
          
          // 添加選擇按鈕事件
          setTimeout(() => {
            const selectBtn = document.getElementById('selectThisLocation');
            if (selectBtn) {
              selectBtn.addEventListener('click', () => MedApp.maps.core.selectLocation());
            }
          }, 100);
        } else {
          MedApp.log("反向地理編碼失敗: " + status, 'warn');
          
          // 僅使用座標作為信息
          MedApp.state.selectedLocation = {
            name: `座標 (${lat}, ${lng})`,
            address: `座標: ${lat}, ${lng}`,
            coordinates: `${lat},${lng}`
          };
          
          // 顯示信息窗口
          const content = `
            <div class="info-window-content">
              <strong>選定位置</strong>
              <p>座標: ${lat}, ${lng}</p>
              <button id="selectThisLocation" class="select-location-btn">選擇此位置</button>
            </div>
          `;
          
          MedApp.maps.core.infoWindow.setContent(content);
          MedApp.maps.core.infoWindow.open(MedApp.maps.core.map, marker);
          
          // 添加選擇按鈕事件
          setTimeout(() => {
            const selectBtn = document.getElementById('selectThisLocation');
            if (selectBtn) {
              selectBtn.addEventListener('click', () => MedApp.maps.core.selectLocation());
            }
          }, 100);
        }
      });
    },
    
    // 使用地址進行地理編碼
    geocodeAddress: function(address) {
      MedApp.maps.core.services.geocoder.geocode({ address: address }, (results, status) => {
        if (status === 'OK' && results[0]) {
          // 獲取位置
          const location = results[0].geometry.location;
          
          // 更新地圖中心
          MedApp.maps.core.map.setCenter(location);
          MedApp.maps.core.map.setZoom(16);
          
          // 清除現有標記並創建新標記
          MedApp.maps.core.clearMarkers();
          
          const marker = new google.maps.Marker({
            position: location,
            map: MedApp.maps.core.map,
            animation: google.maps.Animation.DROP
          });
          
          MedApp.maps.core.markers.push(marker);
          
          // 保存地點信息
          MedApp.state.selectedLocation = {
            name: results[0].formatted_address,
            address: results[0].formatted_address,
            coordinates: `${location.lat()},${location.lng()}`
          };
          
          // 顯示信息窗口
          const content = `
            <div class="info-window-content">
              <strong>${results[0].formatted_address}</strong>
              <p>座標: ${location.lat()}, ${location.lng()}</p>
              <button id="selectThisLocation" class="select-location-btn">選擇此位置</button>
            </div>
          `;
          
          MedApp.maps.core.infoWindow.setContent(content);
          MedApp.maps.core.infoWindow.open(MedApp.maps.core.map, marker);
          
          // 添加選擇按鈕事件
          setTimeout(() => {
            const selectBtn = document.getElementById('selectThisLocation');
            if (selectBtn) {
              selectBtn.addEventListener('click', () => MedApp.maps.core.selectLocation());
            }
          }, 100);
        } else {
          MedApp.log("地理編碼失敗: " + status, 'warn');
          alert("找不到該地點，請輸入更精確的地址或地點名稱。");
        }
      });
    },
    
    // 判斷輸入字串是否為經緯度格式
    isLatLngString: function(input) {
      // 匹配經緯度格式：12.345,67.890 或 12.345, 67.890
      const latLngRegex = /^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$/;
      return latLngRegex.test(input);
    },
    
    // 解析經緯度字串
    parseLatLng: function(input) {
      const parts = input.replace(/\s+/g, '').split(',');
      return [parseFloat(parts[0]), parseFloat(parts[1])];
    }
  };