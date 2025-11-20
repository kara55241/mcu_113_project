/**
 * maps-direction.js - 地圖路線規劃功能
 * 負責處理路線規劃和導航功能
 */

MedApp.maps.direction = {
    // 初始化
    init: function() {
      MedApp.log('路線規劃模組初始化完成', 'info');
    },

    // 計算並顯示路線
    calculateAndDisplayRoute: function(destination, destinationName) {
      MedApp.log(`開始計算路線到: ${destinationName}`, 'info');

      // 檢查必要的服務是否存在
      if (!MedApp.maps.core.services.directionsService || !MedApp.maps.core.services.directionsRenderer) {
        MedApp.log('路線服務未初始化', 'error');
        alert('路線規劃服務尚未就緒，請稍後再試');
        return;
      }

      // 檢查是否有起點（用戶當前位置或選定位置）
      if (!MedApp.state.selectedLocation || !MedApp.state.selectedLocation.coordinates) {
        // 嘗試獲取當前位置
        this.getOriginAndCalculateRoute(destination, destinationName);
      } else {
        // 使用已選定的位置作為起點
        const [lat, lng] = MedApp.state.selectedLocation.coordinates.split(',').map(parseFloat);
        const origin = new google.maps.LatLng(lat, lng);
        this.displayRoute(origin, destination, destinationName);
      }
    },

    // 獲取起點並計算路線
    getOriginAndCalculateRoute: function(destination, destinationName) {
      // 嘗試使用瀏覽器地理位置
      if (navigator.geolocation) {
        // 顯示載入提示
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'map-loading';
        loadingDiv.id = 'routeLoading';
        loadingDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在規劃路線...';
        document.querySelector('.map-modal-body')?.appendChild(loadingDiv);

        navigator.geolocation.getCurrentPosition(
          (position) => {
            // 移除載入提示
            document.getElementById('routeLoading')?.remove();

            const origin = new google.maps.LatLng(
              position.coords.latitude,
              position.coords.longitude
            );
            this.displayRoute(origin, destination, destinationName);
          },
          (error) => {
            // 移除載入提示
            document.getElementById('routeLoading')?.remove();

            MedApp.log('無法獲取當前位置: ' + error.message, 'error');

            // 使用地圖中心作為起點
            if (MedApp.maps.core.map) {
              const origin = MedApp.maps.core.map.getCenter();
              this.displayRoute(origin, destination, destinationName);
            } else {
              alert('無法確定起點位置，請先選擇一個位置或允許位置存取權限');
            }
          },
          {
            enableHighAccuracy: true,
            timeout: 5000,
            maximumAge: 0
          }
        );
      } else {
        // 瀏覽器不支援地理位置，使用地圖中心
        if (MedApp.maps.core.map) {
          const origin = MedApp.maps.core.map.getCenter();
          this.displayRoute(origin, destination, destinationName);
        } else {
          alert('無法使用路線規劃功能，請確保地圖已載入');
        }
      }
    },

    // 顯示路線
    displayRoute: function(origin, destination, destinationName) {
      MedApp.log(`規劃路線: 從 ${origin} 到 ${destinationName}`, 'info');

      // 創建路線請求
      const request = {
        origin: origin,
        destination: destination,
        travelMode: google.maps.TravelMode.DRIVING,
        provideRouteAlternatives: true,
        unitSystem: google.maps.UnitSystem.METRIC
      };

      // 顯示載入提示
      const loadingDiv = document.createElement('div');
      loadingDiv.className = 'map-loading';
      loadingDiv.id = 'routeLoading';
      loadingDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 正在計算路線...';
      document.querySelector('.map-modal-body')?.appendChild(loadingDiv);

      // 計算路線
      MedApp.maps.core.services.directionsService.route(request, (result, status) => {
        // 移除載入提示
        document.getElementById('routeLoading')?.remove();

        if (status === 'OK') {
          MedApp.log('路線計算成功', 'info');

          // 清除現有標記（可選）
          // MedApp.maps.core.clearMarkers();

          // 設置路線渲染器
          MedApp.maps.core.services.directionsRenderer.setMap(MedApp.maps.core.map);
          MedApp.maps.core.services.directionsRenderer.setDirections(result);

          // 顯示路線信息
          this.showRouteInfo(result, destinationName);
        } else {
          MedApp.log('路線計算失敗: ' + status, 'error');

          let errorMessage;
          switch(status) {
            case 'NOT_FOUND':
              errorMessage = '找不到起點或終點位置';
              break;
            case 'ZERO_RESULTS':
              errorMessage = '找不到可用的路線';
              break;
            case 'MAX_WAYPOINTS_EXCEEDED':
              errorMessage = '航點數量超過限制';
              break;
            case 'INVALID_REQUEST':
              errorMessage = '無效的路線請求';
              break;
            case 'OVER_QUERY_LIMIT':
              errorMessage = '查詢次數超過限制';
              break;
            case 'REQUEST_DENIED':
              errorMessage = '路線請求被拒絕';
              break;
            case 'UNKNOWN_ERROR':
              errorMessage = '伺服器錯誤，請稍後再試';
              break;
            default:
              errorMessage = '路線規劃失敗';
          }

          alert(`路線規劃失敗：${errorMessage}`);
        }
      });
    },

    // 顯示路線信息
    showRouteInfo: function(result, destinationName) {
      if (!result.routes || !result.routes[0]) {
        return;
      }

      const route = result.routes[0];
      const leg = route.legs[0];

      // 創建路線信息窗口
      const infoContent = `
        <div class="route-info-content">
          <h3 style="color: #1a1a1a; margin-bottom: 10px;">
            <i class="fas fa-route"></i> 路線到 ${destinationName}
          </h3>
          <div style="color: #4a4a4a; margin: 8px 0;">
            <p><strong>距離：</strong>${leg.distance.text}</p>
            <p><strong>預計時間：</strong>${leg.duration.text}</p>
            <p><strong>起點：</strong>${leg.start_address}</p>
            <p><strong>終點：</strong>${leg.end_address}</p>
          </div>
          <div style="margin-top: 12px; display: flex; gap: 8px;">
            <button id="clearRouteBtn" class="secondary-button" style="flex: 1; padding: 8px 12px; font-size: 14px;">
              <i class="fas fa-times"></i> 清除路線
            </button>
            <a href="https://www.google.com/maps/dir/?api=1&origin=${leg.start_location.lat()},${leg.start_location.lng()}&destination=${leg.end_location.lat()},${leg.end_location.lng()}"
               target="_blank" class="primary-button" style="flex: 1; padding: 8px 12px; font-size: 14px; text-decoration: none; text-align: center;">
              <i class="fas fa-external-link-alt"></i> Google Maps
            </a>
          </div>
        </div>
      `;

      // 顯示信息窗口在路線中點
      const midPoint = {
        lat: (leg.start_location.lat() + leg.end_location.lat()) / 2,
        lng: (leg.start_location.lng() + leg.end_location.lng()) / 2
      };

      MedApp.maps.core.infoWindow.setContent(infoContent);
      MedApp.maps.core.infoWindow.setPosition(midPoint);
      MedApp.maps.core.infoWindow.open(MedApp.maps.core.map);

      // 添加清除路線按鈕事件
      google.maps.event.addListenerOnce(MedApp.maps.core.infoWindow, 'domready', () => {
        const clearBtn = document.getElementById('clearRouteBtn');
        if (clearBtn) {
          clearBtn.addEventListener('click', () => {
            this.clearRoute();
          });
        }
      });

      MedApp.log('路線信息已顯示', 'info');
    },

    // 清除路線
    clearRoute: function() {
      if (MedApp.maps.core.services.directionsRenderer) {
        MedApp.maps.core.services.directionsRenderer.setMap(null);
        MedApp.maps.core.infoWindow.close();
        MedApp.log('路線已清除', 'info');
      }
    }
  };
