/**
 * notifications.js - 通知和提示功能
 * 負責處理提示、通知和警告訊息
 */

MedApp.utils.notifications = {
    // 通知設定
    settings: {
      duration: 3000, // 通知顯示時間（毫秒）
      position: 'bottom-right' // 通知位置
    },
    
    // 通知容器
    container: null,
    
    // 初始化
    init: function() {
      this.createNotificationContainer();
      
      MedApp.log('通知模組初始化完成', 'info');
    },
    
    // 創建通知容器
    createNotificationContainer: function() {
      // 檢查是否已存在
      if (document.getElementById('notification-container')) {
        this.container = document.getElementById('notification-container');
        return;
      }
      
      // 創建容器
      this.container = document.createElement('div');
      this.container.id = 'notification-container';
      this.container.className = `notification-container ${this.settings.position}`;
      
      // 添加到 body
      document.body.appendChild(this.container);
      
      // 添加樣式
      this.addStyles();
    },
    
    // 顯示通知
    show: function(message, type = 'info', duration = null) {
      // 如果沒有容器，先創建
      if (!this.container) {
        this.createNotificationContainer();
      }
      
      // 創建通知元素
      const notification = document.createElement('div');
      notification.className = `notification notification-${type}`;
      
      // 添加圖標
      let icon = '';
      switch (type) {
        case 'success':
          icon = '<i class="fas fa-check-circle"></i>';
          break;
        case 'error':
          icon = '<i class="fas fa-exclamation-circle"></i>';
          break;
        case 'warning':
          icon = '<i class="fas fa-exclamation-triangle"></i>';
          break;
        case 'info':
        default:
          icon = '<i class="fas fa-info-circle"></i>';
          break;
      }
      
      // 設置內容
      notification.innerHTML = `
        <div class="notification-icon">${icon}</div>
        <div class="notification-message">${message}</div>
        <button class="notification-close">&times;</button>
      `;
      
      // 添加到容器
      this.container.appendChild(notification);
      
      // 添加關閉按鈕事件
      const closeBtn = notification.querySelector('.notification-close');
      if (closeBtn) {
        closeBtn.addEventListener('click', () => {
          this.close(notification);
        });
      }
      
      // 添加顯示動畫
      setTimeout(() => {
        notification.classList.add('show');
      }, 10);
      
      // 設置自動關閉
      const notificationDuration = duration || this.settings.duration;
      if (notificationDuration > 0) {
        setTimeout(() => {
          this.close(notification);
        }, notificationDuration);
      }
      
      return notification;
    },
    
    // 關閉通知
    close: function(notification) {
      // 添加關閉動畫
      notification.classList.remove('show');
      
      // 移除元素
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300); // 與 CSS 動畫時間同步
    },
    
    // 顯示成功通知
    success: function(message, duration) {
      return this.show(message, 'success', duration);
    },
    
    // 顯示錯誤通知
    error: function(message, duration) {
      return this.show(message, 'error', duration);
    },
    
    // 顯示警告通知
    warning: function(message, duration) {
      return this.show(message, 'warning', duration);
    },
    
    // 顯示資訊通知
    info: function(message, duration) {
      return this.show(message, 'info', duration);
    },
    
    // 添加樣式
    addStyles: function() {
      const style = document.createElement('style');
      style.textContent = `
        /* 通知容器 */
        .notification-container {
          position: fixed;
          z-index: 9999;
          max-width: 350px;
        }
        
        /* 位置設定 */
        .notification-container.top-right {
          top: 20px;
          right: 20px;
        }
        
        .notification-container.top-left {
          top: 20px;
          left: 20px;
        }
        
        .notification-container.bottom-right {
          bottom: 20px;
          right: 20px;
        }
        
        .notification-container.bottom-left {
          bottom: 20px;
          left: 20px;
        }
        
        /* 通知樣式 */
        .notification {
          display: flex;
          align-items: center;
          background-color: var(--background-lighter, #3a3a4a);
          color: var(--text-color, #e8e8e8);
          border-radius: 6px;
          padding: 12px 15px;
          margin-bottom: 10px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
          transform: translateX(100%);
          opacity: 0;
          transition: transform 0.3s ease, opacity 0.3s ease;
          overflow: hidden;
          max-width: 100%;
        }
        
        /* 顯示動畫 */
        .notification.show {
          transform: translateX(0);
          opacity: 1;
        }
        
        /* 通知類型 */
        .notification-success {
          border-left: 4px solid var(--success-color, #5cccb0);
        }
        
        .notification-error {
          border-left: 4px solid #ff6b6b;
        }
        
        .notification-warning {
          border-left: 4px solid var(--warning-color, #ffb86b);
        }
        
        .notification-info {
          border-left: 4px solid var(--primary-color, #7c9eff);
        }
        
        /* 圖標 */
        .notification-icon {
          margin-right: 12px;
          font-size: 20px;
          flex-shrink: 0;
        }
        
        .notification-success .notification-icon {
          color: var(--success-color, #5cccb0);
        }
        
        .notification-error .notification-icon {
          color: #ff6b6b;
        }
        
        .notification-warning .notification-icon {
          color: var(--warning-color, #ffb86b);
        }
        
        .notification-info .notification-icon {
          color: var(--primary-color, #7c9eff);
        }
        
        /* 訊息內容 */
        .notification-message {
          flex: 1;
          font-size: 14px;
          overflow-wrap: break-word;
          word-break: break-word;
        }
        
        /* 關閉按鈕 */
        .notification-close {
          background: none;
          border: none;
          color: var(--text-secondary, #b0b0b0);
          font-size: 18px;
          cursor: pointer;
          margin-left: 12px;
          padding: 0;
          line-height: 1;
          opacity: 0.7;
          transition: opacity 0.2s;
        }
        
        .notification-close:hover {
          opacity: 1;
        }
      `;
      
      document.head.appendChild(style);
    }
  };