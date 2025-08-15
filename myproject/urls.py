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

# 靜態文件路由（最優先）
from django.views.static import serve
from django.urls import re_path
import os

def debug_static_view(request, path):
    """Debug static file serving"""
    print(f"Static request: {path}")
    return serve(request, path, document_root=settings.STATICFILES_DIRS[0])

urlpatterns = [
    # 靜態文件服務（最高優先級）
    re_path(r'^static/(?P<path>.*)$', debug_static_view),
    
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

# 添加媒體文件服務
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)