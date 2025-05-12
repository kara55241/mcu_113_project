/**
 * 修正版 - 地圖位置搜尋與跳轉功能
 */

// 設置 Google Maps API 密鑰
const GOOGLE_MAPS_API_KEY = 'AIzaSyBt9YpFmkuhaYe0zsvzDSFZ7mqct1wu5gU';

// 全局變量
let map;
let markers = [];
let placesService;
let geocoder;
let directionsService;
let directionsRenderer;
let infoWindow;
let autocomplete;
let searchBox;

function initMap() {
    console.log("初始化 Google Maps...");
    
    // 檢查 Google Maps API 是否已加載
    if (!window.google || !window.google.maps) {
        console.warn("Google Maps API 尚未加載，延遲初始化");
        // 如果沒有 Google Maps API，設置一個監聽器等待加載
        window.initMapWhenApiLoaded = function() {
            if (window.google && window.google.maps) {
                initMap();
            } else {
                setTimeout(window.initMapWhenApiLoaded, 500);
            }
        };
        setTimeout(window.initMapWhenApiLoaded, 500);
        return;
    }
    
    // 初始化地圖服務
    try {
        geocoder = new google.maps.Geocoder();
        directionsService = new google.maps.DirectionsService();
        infoWindow = new google.maps.InfoWindow();
        
        // 獲取地圖元素
        const mapElement = document.getElementById('map');
        
        if (mapElement) {
            // 創建地圖
            map = new google.maps.Map(mapElement, {
                center: { lat: 25.047675, lng: 121.517055 }, // 台北市中心
                zoom: 14,
                mapTypeControl: true,
                fullscreenControl: true,
                streetViewControl: true,
                zoomControl: true,
                mapTypeId: google.maps.MapTypeId.ROADMAP
            });
            
            // 保存地圖實例到全局
            window.map = map;
            
            // 初始化方向渲染器
            directionsRenderer = new google.maps.DirectionsRenderer({
                map: map,
                suppressMarkers: false,
                polylineOptions: {
                    strokeColor: '#7c9eff',
                    strokeWeight: 5
                }
            });
            
            // 初始化地點服務
            placesService = new google.maps.places.PlacesService(map);
            
            // 設置地圖點擊事件
            map.addListener('click', function(event) {
                handleMapClick(event);
            });
            
            // 設置搜索框
            setupSearchBox();
            
            console.log("Google Maps 初始化成功");
            
            // 觸發地圖初始化完成事件
            document.dispatchEvent(new Event('mapInitialized'));
        } else {
            console.error("找不到地圖容器元素");
        }
    } catch (e) {
        console.error("初始化地圖時出錯:", e);
    }
}
function displayHospitalsOnMap(hospitals) {
    if (!window.map) {
      console.error("地圖尚未初始化");
      return;
    }
  
    // 先清除舊標記
    clearMarkers();
  
    // 建立自動縮放的邊界
    const bounds = new google.maps.LatLngBounds();
  
    // 如果有選定的起點，先畫圓點標記
    if (window.selectedLocationInfo && window.selectedLocationInfo.coordinates) {
      const [olat, olng] = window.selectedLocationInfo.coordinates
        .split(',').map(parseFloat);
      const origin = new google.maps.LatLng(olat, olng);
      new google.maps.Marker({
        map: map,
        position: origin,
        icon: {
          path: google.maps.SymbolPath.CIRCLE,
          scale: 8,
          fillColor: '#7c9eff',
          fillOpacity: 1,
          strokeColor: '#fff',
          strokeWeight: 2
        }
      });
      bounds.extend(origin);
    }
  
    // 為每個醫院建立標記
    hospitals.forEach((h, i) => {
      const pos = { lat: parseFloat(h.lat), lng: parseFloat(h.lng) };
      const marker = new google.maps.Marker({
        map: map,
        position: pos,
        title: h.name,
        label: {
          text: (i + 1).toString(),
          color: '#fff',
          fontWeight: 'bold'
        }
      });
  
      // 點擊打開 InfoWindow
      marker.addListener('click', () => {
        const info = new google.maps.InfoWindow({
          content: `
            <div>
              <h3>${h.name}</h3>
              <p>地址：${h.address}</p>
              ${h.rating ? `<p>評分：${h.rating}/5.0</p>` : ''}
              <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(h.name)}" target="_blank">
                在 Google Maps 開啟
              </a>
            </div>
          `
        });
        info.open(map, marker);
      });
  
      markers.push(marker);
      bounds.extend(pos);
    });
  
    // 自動縮放地圖到這些標記範圍
    map.fitBounds(bounds);
  }
  
  // 把它掛到全域，讓 chat.js 可以直接呼叫
  window.displayHospitalsOnMap = displayHospitalsOnMap;

// 設置搜索框
function setupSearchBox() {
    // 獲取搜索輸入框
    const searchInput = document.getElementById('locationSearch');
    if (!searchInput) {
        console.warn("找不到地點搜索輸入框");
        return;
    }
    
    try {
        // 創建搜索框
        searchBox = new google.maps.places.SearchBox(searchInput);
        
        // 限制在當前地圖視圖內搜索
        map.addListener('bounds_changed', function() {
            searchBox.setBounds(map.getBounds());
        });
        
        // 監聽搜索框選擇事件
        searchBox.addListener('places_changed', function() {
            const places = searchBox.getPlaces();
            
            if (places.length === 0) {
                return;
            }
            
            // 清除現有標記
            clearMarkers();
            
            // 創建邊界對象
            const bounds = new google.maps.LatLngBounds();
            
            // 為每個地點添加標記
            places.forEach(function(place) {
                if (!place.geometry || !place.geometry.location) {
                    console.log("返回的地點不包含幾何信息");
                    return;
                }
                
                // 創建標記
                const marker = new google.maps.Marker({
                    map: map,
                    title: place.name,
                    position: place.geometry.location,
                    animation: google.maps.Animation.DROP
                });
                
                // 將地點信息保存到全局
                window.selectedLocationInfo = {
                    name: place.name,
                    address: place.formatted_address || place.vicinity || "",
                    coordinates: `${place.geometry.location.lat()},${place.geometry.location.lng()}`
                };
                
                window.selectedPlace = place;
                
                // 添加點擊事件
                marker.addListener('click', function() {
                    // 顯示信息窗口
                    const content = `
                        <div class="info-window-content">
                            <strong>${place.name || "選定位置"}</strong>
                            <p>${place.formatted_address || place.vicinity || ""}</p>
                            <button id="selectThisLocation" class="select-location-btn">選擇此位置</button>
                        </div>
                    `;
                    
                    infoWindow.setContent(content);
                    infoWindow.open(map, marker);
                    
                    // 添加選擇按鈕事件
                    setTimeout(() => {
                        document.getElementById('selectThisLocation')?.addEventListener('click', () => {
                            selectLocation();
                        });
                    }, 100);
                });
                
                // 添加到標記數組
                markers.push(marker);
                
                // 如果地點有視圖範圍，使用它；否則，使用位置
                if (place.geometry.viewport) {
                    bounds.union(place.geometry.viewport);
                } else {
                    bounds.extend(place.geometry.location);
                }
            });
            
            // 調整地圖視圖
            map.fitBounds(bounds);
            
            // 如果只有一個結果，設置合適的縮放級別
            if (places.length === 1) {
                map.setZoom(16);
                
                // 自動打開信息窗口
                setTimeout(() => {
                    markers[0].click();
                }, 500);
            }
            
            console.log("地點搜索完成，找到", places.length, "個結果");
        });
        
        // 搜索按鈕點擊事件
        const searchButton = document.getElementById('locationSearchBtn');
        if (searchButton) {
            searchButton.addEventListener('click', () => {
                // 檢查輸入是否為經緯度格式
                const input = searchInput.value.trim();
                if (isLatLngString(input)) {
                    // 如果是經緯度，直接設置地圖中心
                    const [lat, lng] = parseLatLng(input);
                    const latLng = new google.maps.LatLng(lat, lng);
                    
                    // 更新地圖中心
                    map.setCenter(latLng);
                    map.setZoom(16);
                    
                    // 創建標記
                    const marker = new google.maps.Marker({
                        position: latLng,
                        map: map,
                        animation: google.maps.Animation.DROP
                    });
                    
                    // 清除現有標記並添加新標記
                    clearMarkers();
                    markers.push(marker);
                    
                    // 進行反向地理編碼，獲取地址
                    geocoder.geocode({ location: latLng }, (results, status) => {
                        if (status === 'OK' && results[0]) {
                            // 保存地點信息
                            window.selectedLocationInfo = {
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
                            
                            infoWindow.setContent(content);
                            infoWindow.open(map, marker);
                            
                            // 添加選擇按鈕事件
                            setTimeout(() => {
                                document.getElementById('selectThisLocation')?.addEventListener('click', () => {
                                    selectLocation();
                                });
                            }, 100);
                        } else {
                            console.warn("反向地理編碼失敗:", status);
                            
                            // 僅使用座標作為信息
                            window.selectedLocationInfo = {
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
                            
                            infoWindow.setContent(content);
                            infoWindow.open(map, marker);
                            
                            // 添加選擇按鈕事件
                            setTimeout(() => {
                                document.getElementById('selectThisLocation')?.addEventListener('click', () => {
                                    selectLocation();
                                });
                            }, 100);
                        }
                    });
                } else {
                    // 否則，觸發搜索框的地點搜索
                    const event = new Event('places_changed');
                    searchBox.dispatchEvent(event);
                    
                    // 如果搜索框沒有結果，嘗試使用 Geocoder
                    setTimeout(() => {
                        if (markers.length === 0) {
                            // 嘗試將地址轉換為座標
                            geocoder.geocode({ address: input }, (results, status) => {
                                if (status === 'OK' && results[0]) {
                                    // 獲取位置
                                    const location = results[0].geometry.location;
                                    
                                    // 更新地圖中心
                                    map.setCenter(location);
                                    map.setZoom(16);
                                    
                                    // 創建標記
                                    const marker = new google.maps.Marker({
                                        position: location,
                                        map: map,
                                        animation: google.maps.Animation.DROP
                                    });
                                    
                                    // 清除現有標記並添加新標記
                                    clearMarkers();
                                    markers.push(marker);
                                    
                                    // 保存地點信息
                                    window.selectedLocationInfo = {
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
                                    
                                    infoWindow.setContent(content);
                                    infoWindow.open(map, marker);
                                    
                                    // 添加選擇按鈕事件
                                    setTimeout(() => {
                                        document.getElementById('selectThisLocation')?.addEventListener('click', () => {
                                            selectLocation();
                                        });
                                    }, 100);
                                } else {
                                    console.warn("地理編碼失敗:", status);
                                    alert("找不到該地點，請輸入更精確的地址或地點名稱。");
                                }
                            });
                        }
                    }, 500);
                }
            });
        }
        
        // 回車鍵搜索
        searchInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                event.preventDefault();
                document.getElementById('locationSearchBtn')?.click();
            }
        });
        
        console.log("地點搜索框設置完成");
    } catch (e) {
        console.error("設置搜索框時出錯:", e);
    }
}

// 判斷輸入字串是否為經緯度格式
function isLatLngString(input) {
    // 匹配經緯度格式：12.345,67.890 或 12.345, 67.890
    const latLngRegex = /^(-?\d+(\.\d+)?),\s*(-?\d+(\.\d+)?)$/;
    return latLngRegex.test(input);
}

// 解析經緯度字串
function parseLatLng(input) {
    const parts = input.replace(/\s+/g, '').split(',');
    return [parseFloat(parts[0]), parseFloat(parts[1])];
}

// 與 GMP 組件同步
function syncWithGmpMap() {
    // 檢查是否有 gmp-map 組件
    const gmpMap = document.querySelector('gmp-map');
    if (!gmpMap) return;
    
    // 檢查是否有地點選擇器
    const placePicker = document.querySelector('gmpx-place-picker');
    if (!placePicker) return;
    
    // 監聽地點變更事件
    placePicker.addEventListener('gmpx-placechange', () => {
        const place = placePicker.value;
        if (!place || !place.location) return;
        
        // 更新選定的位置
        window.selectedLocationInfo = {
            name: place.displayName || place.formattedAddress || "選定位置",
            address: place.formattedAddress || "",
            coordinates: `${place.location.lat()},${place.location.lng()}`
        };
        
        window.selectedPlace = place;
        
        console.log("GMP 選擇的位置:", window.selectedLocationInfo);
        
        // 如果有常規地圖，也更新它
        if (map) {
            map.setCenter(place.location);
            map.setZoom(16);
            
            // 清除現有標記
            clearMarkers();
            
            // 添加新標記
            const marker = new google.maps.Marker({
                position: place.location,
                map: map,
                title: place.displayName || "選定位置",
                animation: google.maps.Animation.DROP
            });
            
            markers.push(marker);
        }
    });
}

// 清除所有標記
function clearMarkers() {
    markers.forEach(marker => marker.setMap(null));
    markers = [];
}

// 處理地圖點擊
function handleMapClick(event) {
    const latLng = event.latLng;
    
    // 清除現有標記
    clearMarkers();
    
    // 創建新標記
    const marker = new google.maps.Marker({
        position: latLng,
        map: map,
        animation: google.maps.Animation.DROP
    });
    
    // 添加到標記數組
    markers.push(marker);
    
    // 進行反向地理編碼
    geocoder.geocode({ location: latLng }, (results, status) => {
        if (status === 'OK' && results[0]) {
            // 保存選定位置
            window.selectedLocationInfo = {
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
            
            infoWindow.setContent(content);
            infoWindow.open(map, marker);
            
            // 添加選擇按鈕事件
            setTimeout(() => {
                document.getElementById('selectThisLocation')?.addEventListener('click', () => {
                    selectLocation();
                });
            }, 100);
        } else {
            console.warn("反向地理編碼失敗:", status);
            
            // 僅使用座標
            window.selectedLocationInfo = {
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
            
            infoWindow.setContent(content);
            infoWindow.open(map, marker);
            
            // 添加選擇按鈕事件
            setTimeout(() => {
                document.getElementById('selectThisLocation')?.addEventListener('click', () => {
                    selectLocation();
                });
            }, 100);
        }
    });
}

// 搜尋附近醫院
function searchNearbyHospitals() {
    console.log("搜尋附近醫院...");
    
    // 確保有選定位置
    if (!window.selectedLocationInfo || !window.selectedLocationInfo.coordinates) {
        // 如果沒有選定位置，使用當前地圖中心
        if (map) {
            const center = map.getCenter();
            window.selectedLocationInfo = {
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
    document.querySelector('.map-modal-body').appendChild(loadingDiv);
    
    // 獲取座標
    const [lat, lng] = window.selectedLocationInfo.coordinates.split(',').map(parseFloat);
    const location = new google.maps.LatLng(lat, lng);
    
    // 搜尋參數
    const request = {
        location: location,
        radius: 3000, // 3公里範圍
        types: ['hospital', 'doctor', 'health'], // 醫院、醫生、健康設施
        keyword: '醫院 診所 藥局' // 關鍵字
    };
    
    // 使用 Places API 進行附近搜尋
    placesService.nearbySearch(request, (results, status) => {
        // 移除載入提示
        document.querySelector('.map-loading')?.remove();
        
        if (status === google.maps.places.PlacesServiceStatus.OK && results && results.length > 0) {
            console.log(`找到 ${results.length} 個醫療設施`);
            
            // 處理搜尋結果
            const hospitals = results.map(place => {
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
            
            // 如果結果太多，只取前 8 個
            const filteredHospitals = hospitals.slice(0, 8);
            
            // 在地圖上顯示醫院
            displayHospitalsOnMap(filteredHospitals);
            
            // 將結果顯示在聊天中
            sendHospitalsToChat(filteredHospitals);
        } else {
            console.error("搜尋醫院失敗:", status);
            
            if (status === google.maps.places.PlacesServiceStatus.ZERO_RESULTS) {
                alert("在所選位置附近找不到醫院，請嘗試調整搜尋範圍或選擇不同的位置。");
            } else {
                alert("搜尋醫院時發生錯誤，請稍後再試。");
            }
        }
    });
}

// 在地圖上顯示醫院
function displayHospitalsOnMap(hospitals) {
    console.log("在地圖上顯示醫院:", hospitals);
    
    // 清除現有標記
    clearMarkers();
    
    // 創建邊界物件以自動調整地圖視圖
    const bounds = new google.maps.LatLngBounds();
    
    // 如果有選定位置，先添加標記並納入邊界
    if (window.selectedLocationInfo && window.selectedLocationInfo.coordinates) {
        const [lat, lng] = window.selectedLocationInfo.coordinates.split(',').map(parseFloat);
        const position = new google.maps.LatLng(lat, lng);
        
        const marker = new google.maps.Marker({
            position: position,
            map: map,
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
        
        markers.push(marker);
        bounds.extend(position);
    }
    
    // 添加每個醫院的標記
    hospitals.forEach((hospital, index) => {
        // 創建醫院位置
        const position = new google.maps.LatLng(
            hospital.lat,
            hospital.lng
        );
        
        // 將位置添加到邊界
        bounds.extend(position);
        
        // 創建自定義標記
        const hospitalMarker = new google.maps.Marker({
            position: position,
            map: map,
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
            infoWindow.close();
            
            // 設置并打開信息窗口
            infoWindow.setContent(content);
            infoWindow.open(map, hospitalMarker);
            
            // 添加路線規劃按鈕事件
            setTimeout(() => {
                const directionBtn = document.getElementById(`directionBtn-${index}`);
                if (directionBtn) {
                    directionBtn.addEventListener('click', () => {
                        calculateAndDisplayRoute(position, hospital.name);
                    });
                }
            }, 100);
        });
        
        // 將標記添加到數組
        markers.push(hospitalMarker);
    });
    
    // 調整地圖視圖以顯示所有標記
    map.fitBounds(bounds);
    
    // 如果只有一個醫院，設置合適的縮放級別
    if (hospitals.length === 1) {
        map.setZoom(16);
    }
    
    console.log("醫院標記添加完成，共", hospitals.length, "個");
}

// 計算並顯示路線
function calculateAndDisplayRoute(destination, destinationName) {
    console.log("計算路線到:", destinationName);
    
    // 確保有起點
    if (!window.selectedLocationInfo || !window.selectedLocationInfo.coordinates) {
        alert("請先選擇起點位置");
        return;
    }
    
    // 獲取起點座標
    const [originLat, originLng] = window.selectedLocationInfo.coordinates.split(',').map(parseFloat);
    const origin = new google.maps.LatLng(originLat, originLng);
    
    // 設置路線請求
    const request = {
        origin: origin,
        destination: destination,
        travelMode: google.maps.TravelMode.DRIVING, // 預設為駕車
        region: 'tw' // 限制在台灣
    };
    
    // 計算路線
    directionsService.route(request, (response, status) => {
        if (status === 'OK') {
            // 顯示路線
            directionsRenderer.setMap(map);
            directionsRenderer.setDirections(response);
            
            // 獲取路線信息
            const route = response.routes[0].legs[0];
            
            // 更新信息窗口顯示路線詳情
            const content = `
                <div class="hospital-info-window">
                    <h3>路線到 ${destinationName}</h3>
                    <p><strong>距離:</strong> ${route.distance.text}</p>
                    <p><strong>預計時間:</strong> ${route.duration.text}</p>
                    <div class="route-actions">
                        <button id="clearRouteBtn" class="secondary-button">
                            <i class="fas fa-times"></i> 關閉路線
                        </button><a href="https://www.google.com/maps/dir/?api=1&origin=${originLat},${originLng}&destination=${destination.lat()},${destination.lng()}" 
                           target="_blank" class="primary-button">
                            <i class="fas fa-external-link-alt"></i> 在 Google Maps 開啟
                        </a>
                    </div>
                </div>
            `;
            
            infoWindow.setContent(content);
            infoWindow.open(map);
            
            // 添加清除路線按鈕事件
            setTimeout(() => {
                const clearRouteBtn = document.getElementById('clearRouteBtn');
                if (clearRouteBtn) {
                    clearRouteBtn.addEventListener('click', () => {
                        directionsRenderer.setMap(null);
                        infoWindow.close();
                    });
                }
            }, 100);
            
            console.log("路線顯示完成");
        } else {
            console.error("計算路線失敗:", status);
            alert("無法計算到該醫院的路線，請稍後再試。");
        }
    });
}

// 將醫院結果發送到聊天
function sendHospitalsToChat(hospitals) {
    console.log("將醫院結果發送到聊天");
    
    // 確保有位置信息
    if (!window.selectedLocationInfo) {
        console.warn("沒有選定位置信息");
        return;
    }
    
    // 創建事件來傳遞醫院資訊
    const event = new CustomEvent('hospitalsFound', {
        detail: {
            hospitals: hospitals,
            location: window.selectedLocationInfo
        }
    });
    
    // 分發事件
    document.dispatchEvent(event);
    console.log("醫院信息已發送到聊天");
}

// 獲取用戶當前位置
function getCurrentLocation() {
    return new Promise((resolve, reject) => {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (position) => {
                    const lat = position.coords.latitude;
                    const lng = position.coords.longitude;
                    resolve({ lat, lng });
                },
                (error) => {
                    console.error("獲取位置錯誤:", error);
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
}

// 使用當前位置並顯示在地圖上
async function useCurrentLocation() {
    try {
        // 顯示載入中...
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'map-loading';
        loadingDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在獲取您的位置...';
        document.querySelector('.map-modal-body').appendChild(loadingDiv);
        
        // 獲取當前位置
        const { lat, lng } = await getCurrentLocation();
        
        // 清除載入提示
        document.querySelector('.map-loading')?.remove();
        
        // 設置地圖中心
        map.setCenter({ lat, lng });
        map.setZoom(16);
        
        // 清除現有標記
        clearMarkers();
        
        // 創建標記
        const marker = new google.maps.Marker({
            position: { lat, lng },
            map: map,
            animation: google.maps.Animation.DROP
        });
        
        // 添加到標記數組
        markers.push(marker);
        
        // 進行反向地理編碼
        geocoder.geocode({ location: { lat, lng } }, (results, status) => {
            if (status === 'OK' && results[0]) {
                // 保存選定位置
                window.selectedLocationInfo = {
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
                
                infoWindow.setContent(content);
                infoWindow.open(map, marker);
                
                // 添加搜尋按鈕事件
                setTimeout(() => {
                    document.getElementById('searchNearbyHospitalsHereBtn')?.addEventListener('click', () => {
                        searchNearbyHospitals();
                    });
                }, 100);
            } else {
                console.warn("反向地理編碼失敗:", status);
                
                // 僅使用座標
                window.selectedLocationInfo = {
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
                
                infoWindow.setContent(content);
                infoWindow.open(map, marker);
                
                // 添加搜尋按鈕事件
                setTimeout(() => {
                    document.getElementById('searchNearbyHospitalsHereBtn')?.addEventListener('click', () => {
                        searchNearbyHospitals();
                    });
                }, 100);
            }
        });
    } catch (error) {
        // 清除載入提示
        document.querySelector('.map-loading')?.remove();
        
        // 顯示錯誤消息
        let errorMessage;
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
        
        alert(errorMessage);
    }
}

// 選擇位置
function selectLocation() {
    // 確保有選定位置
    if (!window.selectedLocationInfo) {
        alert("請先選擇一個位置");
        return;
    }
    
    // 關閉模態框
    const mapModal = document.getElementById('mapModal');
    if (mapModal) {
        mapModal.style.display = 'none';
    }
    
    // 向聊天發送位置信息
    appendLocationMessage(window.selectedLocationInfo);
    
    // 自動填入相關問題
    const userInput = document.getElementById('userInput');
    if (userInput) {
        userInput.value = `${window.selectedLocationInfo.name}附近有哪些醫院?`;
        userInput.focus();
    }
    
    console.log("位置已選擇:", window.selectedLocationInfo);
}

// 顯示地圖模態框 - 優化版
function showMapModal() {
    const modal = document.getElementById('mapModal');
    if (!modal) {
        console.error("找不到地圖模態框 #mapModal");
        return;
    }
    
    modal.style.display = "block";

    setTimeout(() => {
        const mapDiv = document.getElementById('map');
        if (!mapDiv) {
            console.error("找不到地圖容器 #map");
            return;
        }

        if (!window.map) {
            console.log("🗺️ 初始化新的 Google Map");
            window.map = new google.maps.Map(mapDiv, {
                center: { lat: 25.0330, lng: 121.5654 }, // 預設台北 101
                zoom: 13
            });
        } else {
            console.log("🗺️ 地圖已存在，刷新地圖大小");
            google.maps.event.trigger(window.map, "resize");
            window.map.setCenter({ lat: 25.0330, lng: 121.5654 });
        }
    }, 300); // 等 modal 出現後，再初始化
}

// 初始化地圖模態框
function initMapModal() {
    // 獲取模態框元素
    const mapModal = document.getElementById('mapModal');
    if (!mapModal) {
        console.error("找不到地圖模態框");
        return;
    }
    
    // 獲取按鈕元素
    const closeMapModalButton = document.getElementById('closeMapModal');
    const selectLocationButton = document.getElementById('selectLocation');
    const searchHospitalsBtn = document.getElementById('searchHospitalsBtn');
    const getCurrentLocationBtn = document.getElementById('getCurrentLocationBtn');
    
    // 添加關閉按鈕事件
    if (closeMapModalButton) {
        closeMapModalButton.addEventListener('click', () => {
            mapModal.style.display = 'none';
            
            // 如果有路線顯示，清除它
            if (directionsRenderer) {
                directionsRenderer.setMap(null);
            }
        });
    }
    
    // 添加選擇位置按鈕事件
    if (selectLocationButton) {
        selectLocationButton.addEventListener('click', selectLocation);
    }
    
    // 添加搜尋醫院按鈕事件
    if (searchHospitalsBtn) {
        searchHospitalsBtn.addEventListener('click', searchNearbyHospitals);
    }
    
    // 添加獲取當前位置按鈕事件
    if (getCurrentLocationBtn) {
        getCurrentLocationBtn.addEventListener('click', useCurrentLocation);
    }
    
    // 點擊背景關閉模態框
    mapModal.addEventListener('click', (event) => {
        if (event.target === mapModal) {
            mapModal.style.display = 'none';
            
            // 如果有路線顯示，清除它
            if (directionsRenderer) {
                directionsRenderer.setMap(null);
            }
        }
    });
    
    // 添加 ESC 鍵關閉模態框
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && mapModal.style.display === 'block') {
            mapModal.style.display = 'none';
            
            // 如果有路線顯示，清除它
            if (directionsRenderer) {
                directionsRenderer.setMap(null);
            }
        }
    });
}

// 添加地圖樣式
function addMapStyles() {
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
        
        /* 路線和地圖按鈕 */
        .direction-btn, .map-link {
            background-color: #7c9eff;
            color: white;
            text-decoration: none;
            padding: 6px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            border: none;
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-family: 'Noto Sans TC', sans-serif;
        }
        
        .direction-btn:hover, .map-link:hover {
            background-color: #a991ff;
        }
        
        .map-link {
            background-color: #5cccb0;
        }
        
        .map-link:hover {
            background-color: #4db39e;
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

// 頁面載入時初始化
document.addEventListener('DOMContentLoaded', () => {
    // 添加樣式
    addMapStyles();
    
    // 初始化地圖模態框
    initMapModal();
    
    // 添加地圖按鈕點擊事件
    const locationButton = document.getElementById('locationButton');
    if (locationButton) {
        locationButton.addEventListener('click', showMapModal);
    }
    
    // 如果地圖框已經開啟，初始化地圖
    const mapModal = document.getElementById('mapModal');
    if (mapModal && mapModal.style.display === 'block') {
        initMap();
    }
    
    // 暴露全局方法
    window.showMapModal = showMapModal;
    window.searchNearbyHospitals = searchNearbyHospitals;
    window.displayHospitalsOnMap = displayHospitalsOnMap;
    window.getCurrentLocation = getCurrentLocation;
    window.useCurrentLocation = useCurrentLocation;
    window.markers = markers;
    
    console.log("地圖功能初始化完成");
});

// 處理在Google地圖中選擇位置後的回調
window.handlePlaceSelect = function(place) {
    if (!place) return;
    
    // 保存選擇的位置
    window.selectedPlace = place;
    window.selectedLocationInfo = {
        name: place.name || place.formatted_address || "選定位置",
        address: place.formatted_address || "",
        coordinates: place.geometry && place.geometry.location ? 
                   `${place.geometry.location.lat()},${place.geometry.location.lng()}` : ""
    };
    
    console.log("已選擇位置:", window.selectedLocationInfo);
    
    // 如果地圖已初始化，在地圖上顯示位置
    if (window.map) {
        // 清除現有標記
        clearMarkers();
        
        // 創建新標記
        const marker = new google.maps.Marker({
            position: place.geometry.location,
            map: window.map,
            title: place.name || "選定位置",
            animation: google.maps.Animation.DROP
        });
        
        // 添加到標記數組
        markers.push(marker);
        
        // 調整地圖視圖
        if (place.geometry.viewport) {
            window.map.fitBounds(place.geometry.viewport);
        } else {
            window.map.setCenter(place.geometry.location);
            window.map.setZoom(16);
        }
    }
};