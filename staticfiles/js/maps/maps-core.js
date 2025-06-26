/**
 * maps-core.js - 地圖核心功能
 * 負責地圖功能的初始化和基本操作
 */

MedApp.maps.core = {
    // 地圖物件
    map: null,
    
    // 地圖服務
    services: {
      geocoder: null,
      directionsService: null,
      directionsRenderer: null,
      placesService: null
    },
    
    // 資訊視窗
    infoWindow: null,
    
    // 標記數組
    markers: [],
    
    // DOM 元素引用
    elements: {
      mapContainer: null,
      mapModal: null,
      locationButton: null,
      closeMapModalButton: null,
      selectLocationButton: null,
      searchHospitalsBtn: null,
      getCurrentLocationBtn: null
    },
    
    // 初始化
    init: function() {
      this.initElements();
      this.bindEvents();
      this.addMapStyles();
      
      // 初始化地圖模態框
      this.initMapModal();
      
      MedApp.log('地圖核心模組初始化完成', 'info');
    },
    
    // 初始化 DOM 元素引用
    initElements: function() {
      this.elements.mapContainer = document.getElementById('map');
      this.elements.mapModal = document.getElementById('mapModal');
      this.elements.locationButton = document.getElementById('locationButton');
      this.elements.closeMapModalButton = document.getElementById('closeMapModal');
      this.elements.selectLocationButton = document.getElementById('selectLocation');
      this.elements.searchHospitalsBtn = document.getElementById('searchHospitalsBtn');
      this.elements.getCurrentLocationBtn = document.getElementById('getCurrentLocationBtn');
    },
    
    // 綁定事件處理
    bindEvents: function() {
        MedApp.log('綁定地圖按鈕事件', 'debug');
        
        // 地圖按鈕點擊事件
        if (this.elements.locationButton) {
          this.elements.locationButton.addEventListener('click', () => {
            MedApp.log('地圖按鈕被點擊', 'debug');
            this.showMapModal();
          });
        } else {
          MedApp.log('找不到地圖按鈕元素 locationButton', 'error');
        }
        
        // 添加地圖模態框按鈕事件
        this.initMapModal();
        
        // 手動添加全局事件處理器
        window.showMap = () => {
          MedApp.log('手動觸發顯示地圖', 'debug');
          this.showMapModal();
        };
      },
    
    // 初始化地圖
    initMap: function() {
      MedApp.log("初始化 Google Maps...", 'info');
      
      // 檢查 Google Maps API 是否已加載
      if (!window.google || !window.google.maps) {
        MedApp.log("Google Maps API 尚未加載，延遲初始化", 'warn');
        
        // 如果沒有加載，等待 API 加載完成
        window.initMapWhenApiLoaded = function() {
          if (window.google && window.google.maps) {
            MedApp.maps.core.initMap();
          } else {
            setTimeout(window.initMapWhenApiLoaded, 500);
          }
        };
        
        setTimeout(window.initMapWhenApiLoaded, 500);
        return;
      }
      
      try {
        // 初始化地圖服務
        this.services.geocoder = new google.maps.Geocoder();
        this.services.directionsService = new google.maps.DirectionsService();
        this.infoWindow = new google.maps.InfoWindow();
        
        // 創建地圖
        if (this.elements.mapContainer) {
          this.map = new google.maps.Map(this.elements.mapContainer, {
            center: { lat: 25.047675, lng: 121.517055 }, // 台北市中心
            zoom: 14,
            mapTypeControl: true,
            fullscreenControl: true,
            streetViewControl: true,
            zoomControl: true,
            mapTypeId: google.maps.MapTypeId.ROADMAP
          });
          
          // 保存地圖實例到全局
          window.map = this.map;
          
          // 初始化方向渲染器
          this.services.directionsRenderer = new google.maps.DirectionsRenderer({
            map: this.map,
            suppressMarkers: false,
            polylineOptions: {
              strokeColor: '#7c9eff',
              strokeWeight: 5
            }
          });
          
          // 初始化地點服務
          if (google.maps.places) {
            this.services.placesService = new google.maps.places.PlacesService(this.map);
          }
          
          // 設置地圖點擊事件
          this.map.addListener('click', (event) => {
            this.handleMapClick(event);
          });
          
          // 設置搜索框
          this.setupSearchBox();
          
          MedApp.log("Google Maps 初始化成功", 'info');
          
          // 觸發地圖初始化完成事件
          document.dispatchEvent(new Event('mapInitialized'));
        } else {
          MedApp.log("找不到地圖容器元素", 'error');
        }
      } catch (e) {
        MedApp.log("初始化地圖時出錯: " + e.message, 'error');
      }
        // 在初始化完成後，再次檢查 placesService 是否可用
        if (!this.services.placesService && google.maps.places && this.map) {
        MedApp.log('嘗試再次初始化 Places 服務', 'debug');
        this.services.placesService = new google.maps.places.PlacesService(this.map);
        }
        // 全局保存 MedApp.maps.core 的引用，方便調試
        window.mapCore = this;
        MedApp.log('地圖核心引用已保存到 window.mapCore', 'debug');
    },
    
    // 顯示地圖模態框
    showMapModal: function() {
      if (!this.elements.mapModal) {
        MedApp.log("找不到地圖模態框", 'error');
        return;
      }
      
      this.elements.mapModal.style.display = "block";
      
      setTimeout(() => {
        if (!this.map && this.elements.mapContainer) {
          MedApp.log("初始化新的 Google Map", 'info');
          this.initMap();
        } else if (this.map) {
          MedApp.log("地圖已存在，刷新地圖大小", 'debug');
          google.maps.event.trigger(this.map, "resize");
          // 重置地圖中心
          this.map.setCenter({ lat: 25.0330, lng: 121.5654 });
        }
      }, 300);
    },
    
    // 初始化地圖模態框
    initMapModal: function() {
      // 獲取模態框元素
      if (!this.elements.mapModal) {
        MedApp.log("找不到地圖模態框", 'error');
        return;
      }
      
      // 添加關閉按鈕事件
      if (this.elements.closeMapModalButton) {
        this.elements.closeMapModalButton.addEventListener('click', () => {
          this.elements.mapModal.style.display = 'none';
          
          // 如果有路線顯示，清除它
          if (this.services.directionsRenderer) {
            this.services.directionsRenderer.setMap(null);
          }
        });
      }
      
      // 添加選擇位置按鈕事件
      if (this.elements.selectLocationButton) {
        this.elements.selectLocationButton.addEventListener('click', () => this.selectLocation());
      }
      
      // 添加搜尋醫院按鈕事件
      if (this.elements.searchHospitalsBtn) {
        this.elements.searchHospitalsBtn.addEventListener('click', () => {
          if (MedApp.maps.hospital && MedApp.maps.hospital.searchNearbyHospitals) {
            MedApp.maps.hospital.searchNearbyHospitals();
          }
        });
      }
      
      // 添加獲取當前位置按鈕事件
      if (this.elements.getCurrentLocationBtn) {
        this.elements.getCurrentLocationBtn.addEventListener('click', () => this.useCurrentLocation());
      }
      
      // 點擊背景關閉模態框
      this.elements.mapModal.addEventListener('click', (event) => {
        if (event.target === this.elements.mapModal) {
          this.elements.mapModal.style.display = 'none';
          
          // 如果有路線顯示，清除它
          if (this.services.directionsRenderer) {
            this.services.directionsRenderer.setMap(null);
          }
        }
      });
      
      // 添加 ESC 鍵關閉模態框
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && this.elements.mapModal.style.display === 'block') {
          this.elements.mapModal.style.display = 'none';
          
          // 如果有路線顯示，清除它
          if (this.services.directionsRenderer) {
            this.services.directionsRenderer.setMap(null);
          }
        }
      });
    },
    
    // 設置搜索框
    setupSearchBox: function() {
      // 這個功能會在 maps-search.js 中實現
      if (MedApp.maps.search && typeof MedApp.maps.search.setupSearchBox === 'function') {
        MedApp.maps.search.setupSearchBox();
      }
    },
    
    // 處理地圖點擊
    handleMapClick: function(event) {
      const latLng = event.latLng;
      
      // 清除現有標記
      this.clearMarkers();
      
      // 創建新標記
      const marker = new google.maps.Marker({
        position: latLng,
        map: this.map,
        animation: google.maps.Animation.DROP
      });
      
      // 添加到標記數組
      this.markers.push(marker);
      
      // 進行反向地理編碼
      this.services.geocoder.geocode({ location: latLng }, (results, status) => {
        if (status === 'OK' && results[0]) {
          // 保存選定位置
          MedApp.state.selectedLocation = {
            name: results[0].formatted_address,
            address: results[0].formatted_address,
            coordinates: `${latLng.lat()},${latLng.lng()}`
          };
          
          // 顯示信息窗口
          const content = `
            <div class="info-window-content">
              <strong>${results[0].formatted_address}</strong>
              <p>座標: ${latLng.lat().toFixed(6)}, ${latLng.lng().toFixed(6)}</p>
              <button id="selectThisLocation" class="select-location-btn">選擇此位置</button>
            </div>
          `;
          
          this.infoWindow.setContent(content);
          this.infoWindow.open(this.map, marker);
          
          // 添加選擇按鈕事件
          setTimeout(() => {
            const selectBtn = document.getElementById('selectThisLocation');
            if (selectBtn) {
              selectBtn.addEventListener('click', () => this.selectLocation());
            }
          }, 100);
        } else {
          MedApp.log("反向地理編碼失敗: " + status, 'warn');
          
          // 僅使用座標
          MedApp.state.selectedLocation = {
            name: `座標 (${latLng.lat().toFixed(6)}, ${latLng.lng().toFixed(6)})`,
            address: `座標: ${latLng.lat().toFixed(6)}, ${latLng.lng().toFixed(6)}`,
            coordinates: `${latLng.lat()},${latLng.lng()}`
          };
          
          // 顯示信息窗口
          const content = `
            <div class="info-window-content">
              <strong>選定位置</strong>
              <p>座標: ${latLng.lat().toFixed(6)}, ${latLng.lng().toFixed(6)}</p>
              <button id="selectThisLocation" class="select-location-btn">選擇此位置</button>
            </div>
          `;
          
          this.infoWindow.setContent(content);
          this.infoWindow.open(this.map, marker);
          
          // 添加選擇按鈕事件
          setTimeout(() => {
            const selectBtn = document.getElementById('selectThisLocation');
            if (selectBtn) {
              selectBtn.addEventListener('click', () => this.selectLocation());
            }
          }, 100);
        }
      });
    },
    
    // 清除所有標記
    clearMarkers: function() {
      this.markers.forEach(marker => marker.setMap(null));
      this.markers = [];
    },
    
    // 選擇位置
    selectLocation: function() {
      // 確保有選定位置
      if (!MedApp.state.selectedLocation) {
        alert("請先選擇一個位置");
        return;
      }
      
      // 關閉模態框
      if (this.elements.mapModal) {
        this.elements.mapModal.style.display = 'none';
      }
      
      // 向聊天發送位置信息
      MedApp.chat.display.appendLocationMessage(MedApp.state.selectedLocation);
      
      // 自動填入相關問題
      const userInput = document.getElementById('userInput');
      if (userInput) {
        userInput.value = `${MedApp.state.selectedLocation.name}附近有哪些醫院?`;
        userInput.focus();
      }
      
      MedApp.log("位置已選擇: " + JSON.stringify(MedApp.state.selectedLocation), 'info');
    },
    
    // 使用當前位置
    useCurrentLocation: async function() {
      try {
        // 顯示載入中...
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'map-loading';
        loadingDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在獲取您的位置...';
        const modalBody = document.querySelector('.map-modal-body');
        if (modalBody) {
          modalBody.appendChild(loadingDiv);
        }
        
        // 獲取當前位置
        const position = await this.getCurrentLocation();
        const { lat, lng } = position;
        
        // 清除載入提示
        document.querySelector('.map-loading')?.remove();
        
        // 設置地圖中心
        if (this.map) {
          this.map.setCenter({ lat, lng });
          this.map.setZoom(16);
          
          // 清除現有標記
          this.clearMarkers();
          
          // 創建標記
          const marker = new google.maps.Marker({
            position: { lat, lng },
            map: this.map,
            animation: google.maps.Animation.DROP
          });
          
          // 添加到標記數組
          this.markers.push(marker);
          
          // 進行反向地理編碼
          this.services.geocoder.geocode({ location: { lat, lng } }, (results, status) => {
            this.processGeocodeResults(results, status, lat, lng, marker);
          });
        }
      } catch (error) {
        // 清除載入提示
        document.querySelector('.map-loading')?.remove();
        
        // 顯示錯誤消息
        let errorMessage;
        if (error.code) {
          switch(error.code) {
            case error.PERMISSION_DENIED:
              errorMessage = "您拒絕了位置存取權限，請手動選擇位置或允許位置存取。";
              break;
            case error.POSITION_UNAVAILABLE:
              errorMessage = "位置信息不可用，請手動選擇位置。";
              break;
            case error.TIMEOUT:
              errorMessage = "獲取位置超時，請手動選擇位置。";
              break;
            default:
              errorMessage = "獲取位置時發生未知錯誤，請手動選擇位置。";
          }
        } else {
          errorMessage = "獲取位置時發生錯誤: " + error.message;
        }
        
        alert(errorMessage);
        MedApp.log(errorMessage, 'error');
      }
    },
    
    // 處理地理編碼結果
    processGeocodeResults: function(results, status, lat, lng, marker) {
      if (status === 'OK' && results[0]) {
        // 保存選定位置
        MedApp.state.selectedLocation = {
          name: results[0].formatted_address,
          address: results[0].formatted_address,
          coordinates: `${lat},${lng}`
        };
        
        // 顯示信息窗口
        const content = `
          <div class="info-window-content">
            <strong>${results[0].formatted_address}</strong>
            <p>這是您的當前位置</p>
            <button id="searchNearbyHospitalsHereBtn" class="primary-button">
              <i class="fas fa-search"></i> 搜尋附近醫院
            </button>
          </div>
        `;
        
        this.infoWindow.setContent(content);
        this.infoWindow.open(this.map, marker);
        
        // 添加搜尋按鈕事件
        setTimeout(() => {
          const searchBtn = document.getElementById('searchNearbyHospitalsHereBtn');
          if (searchBtn && MedApp.maps.hospital && MedApp.maps.hospital.searchNearbyHospitals) {
            searchBtn.addEventListener('click', () => {
              MedApp.maps.hospital.searchNearbyHospitals();
            });
          }
        }, 100);
      } else {
        MedApp.log("反向地理編碼失敗: " + status, 'warn');
        
        // 僅使用座標
        MedApp.state.selectedLocation = {
          name: `當前位置 (${lat.toFixed(6)}, ${lng.toFixed(6)})`,
          address: `座標: ${lat.toFixed(6)}, ${lng.toFixed(6)}`,
          coordinates: `${lat},${lng}`
        };
        
        // 顯示信息窗口
        const content = `
          <div class="info-window-content">
            <strong>您的當前位置</strong>
            <p>座標: ${lat.toFixed(6)}, ${lng.toFixed(6)}</p>
            <button id="searchNearbyHospitalsHereBtn" class="primary-button">
              <i class="fas fa-search"></i> 搜尋附近醫院
            </button>
          </div>
        `;
        
        this.infoWindow.setContent(content);
        this.infoWindow.open(this.map, marker);
        
        // 添加搜尋按鈕事件
        setTimeout(() => {
          const searchBtn = document.getElementById('searchNearbyHospitalsHereBtn');
          if (searchBtn && MedApp.maps.hospital && MedApp.maps.hospital.searchNearbyHospitals) {
            searchBtn.addEventListener('click', () => {
              MedApp.maps.hospital.searchNearbyHospitals();
            });
          }
        }, 100);
      }
    },
    
    // 獲取用戶當前位置
    getCurrentLocation: function() {
      return new Promise((resolve, reject) => {
        if (navigator.geolocation) {
          navigator.geolocation.getCurrentPosition(
            (position) => {
              const lat = position.coords.latitude;
              const lng = position.coords.longitude;
              resolve({ lat, lng });
            },
            (error) => {
              MedApp.log("獲取位置錯誤: " + error.message, 'error');
              reject(error);
            },
            {
              enableHighAccuracy: true,
              timeout: 10000,
              maximumAge: 0
            }
          );
        } else {
          reject(new Error("您的瀏覽器不支持地理位置功能"));
        }
      });
    },
    
    // 處理從聊天回應中的位置資訊
    handleLocationResponse: function(location) {
      if (!location || !location.coordinates) return;
      
      const [lat, lng] = location.coordinates.split(',').map(parseFloat);
      
      if (isNaN(lat) || isNaN(lng)) {
        MedApp.log("無效的位置座標", 'error');
        return;
      }
      
      const position = { lat, lng };
      
      // 如果地圖已初始化，在地圖上顯示位置
      if (this.map) {
        // 清除現有標記
        this.clearMarkers();
        
        // 創建新標記
        const marker = new google.maps.Marker({
          position: position,
          map: this.map,
          title: location.name || "回傳位置",
          animation: google.maps.Animation.DROP
        });
        
        // 添加到標記數組
        this.markers.push(marker);
        
        // 更新地圖視圖
        this.map.setCenter(position);
        this.map.setZoom(15);
      }
      
      // 保存位置信息
      MedApp.state.selectedLocation = location;
    },
    
    // 添加地圖樣式
    addMapStyles: function() {
      const style = document.createElement('style');
      style.textContent = `
        /* 地圖容器樣式 */
        .map-container {
          width: 100%;
          height: 500px;
          border-radius: 12px;
          overflow: hidden;
          position: relative;
        }
        
        /* 搜索框容器 */
        .location-search-container {
          position: absolute;
          top: 10px;
          left: 10px;
          width: 300px;
          z-index: 10;
          background-color: rgba(37, 37, 50, 0.9);
          padding: 10px;
          border-radius: 8px;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
        }
        
        /* 輸入框組 */
        .input-group {
          display: flex;
          width: 100%;
        }
        
        /* 搜索輸入框 */
        .location-search-input {
          flex: 1;
          padding: 10px 15px;
          border: none;
          border-radius: 6px 0 0 6px;
          background-color: #3a3a4a;
          color: #e8e8e8;
          font-size: 16px;
          outline: none;
        }
        
        .location-search-input::placeholder {
          color: #b0b0b0;
        }
        
        /* 搜索按鈕 */
        .location-search-btn {
          background-color: #7c9eff;
          color: #252532;
          border: none;
          padding: 10px 15px;
          border-radius: 0 6px 6px 0;
          cursor: pointer;
          font-size: 16px;
        }
        
        .location-search-btn:hover {
          background-color: #a991ff;
        }
        
        /* 信息窗口樣式 */
        .info-window-content {
          font-family: 'Noto Sans TC', sans-serif;
          min-width: 250px;
          padding: 10px;
        }
        
        .info-window-content strong {
          display: block;
          margin-bottom: 5px;
          font-size: 16px;
          color: #7c9eff;
        }
        
        .info-window-content p {
          margin: 5px 0;
          font-size: 14px;
        }
        
        /* 選擇位置按鈕 */
        .select-location-btn {
          background-color: #7c9eff;
          color: white;
          border: none;
          padding: 8px 12px;
          border-radius: 4px;
          margin-top: 10px;
          cursor: pointer;
          font-size: 14px;
          font-family: 'Noto Sans TC', sans-serif;
        }
        
        .select-location-btn:hover {
          background-color: #a991ff;
        }
        
        /* 載入提示 */
        .map-loading {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          background-color: rgba(37, 37, 50, 0.8);
          color: white;
          padding: 15px 20px;
          border-radius: 8px;
          font-size: 18px;
          z-index: 1000;
          display: flex;
          align-items: center;
          gap: 12px;
        }
        
        /* 修正信息窗口樣式 */
        .gm-style .gm-style-iw-c {
          padding: 12px;
          border-radius: 8px;
          max-width: 300px;
        }
        
        .gm-style .gm-style-iw-d {
          overflow: hidden !important;
          max-width: 100% !important;
        }
      `;
      
      document.head.appendChild(style);
    }
  };