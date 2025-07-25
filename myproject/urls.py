# myproject/urls.py - 修正的主URL配置文件

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# 只導入實際存在的視圖
from myproject.views import (
    home,
    ChatView,
    ConversationView,
    ConversationDetailView,
    MessageView,
    FeedbackView,
    ChatHistoryListView,
    ChatHistoryDetailView,
    health_check
)

urlpatterns = [
    # Django管理界面
    path('admin/', admin.site.urls),
    
    # 主頁
    path('', home, name='home'),
    
    # 聊天相關 - 修正：添加缺少的 chat/ 路由
    path('chat/', ChatView.as_view(), name='chat'),
    path('chat/health/', health_check, name='chat_health'),
    
    # 對話管理API
    path('api/conversations/', ConversationView.as_view(), name='create_conversation'),
    path('api/conversations/<str:chat_id>/', ConversationDetailView.as_view(), name='conversation_detail'),
    
    # 訊息管理API
    path('api/messages/', MessageView.as_view(), name='save_message'),
    path('api/feedback/', FeedbackView.as_view(), name='save_feedback'),
    
    # 聊天歷史API
    path('chat/history/', ChatHistoryListView.as_view(), name='chat_history_list'),
    path('chat/history/<str:chat_id>/', ChatHistoryDetailView.as_view(), name='chat_history_detail'),
]

# 靜態文件服務（僅在開發環境）
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    if hasattr(settings, 'MEDIA_URL') and hasattr(settings, 'MEDIA_ROOT'):
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)