# myproject/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from myproject.views import ChatView, NewChatView, FileUploadView, ChatHistoryView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("chat/", ChatView.as_view(), name="chat"),
    path("chat/new/", NewChatView.as_view(), name="new_chat"),
    path("chat/upload/", FileUploadView.as_view(), name="file_upload"),
    path("chat/history/", ChatHistoryView.as_view(), name="chat_history_all"),
    path("chat/history/<str:chat_id>/", ChatHistoryView.as_view(), name="chat_history_detail"),
    path("", ChatView.as_view(), name="home"),
]

# 始終添加靜態文件服務，無論 DEBUG 模式如何
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# 添加媒體文件服務
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# 添加一個直接訪問靜態文件的路徑，用於調試
if settings.DEBUG:
    urlpatterns += [
        path('static-debug/<path:path>', RedirectView.as_view(url='/static/%(path)s')),
    ]