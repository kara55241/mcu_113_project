# myproject/urls.py
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from myproject.views import ChatView, NewChatView, FileUploadView, ChatHistoryView , FeedbackAPIView, ConversationAPIView, MessageAPIView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('chat/', ChatView.as_view(), name='chat'),
    path('chat/new/', NewChatView.as_view(), name='new_chat'),
    path('chat/upload/', FileUploadView.as_view(), name='file_upload'),
    path('chat/history/', ChatHistoryView.as_view(), name='chat_history_all'),
    path('chat/history/<str:chat_id>/', ChatHistoryView.as_view(), name='chat_history_detail'),
    path('', ChatView.as_view(), name='home'),

    path('api/feedback/', FeedbackAPIView.as_view(), name='feedback_api'),
    path('api/messages/', MessageAPIView.as_view(), name='messages_api'),
    path('api/conversations/', ConversationAPIView.as_view(), name='conversations_api'),
    path('api/conversations/<str:chat_id>/', ConversationAPIView.as_view(), name='conversation_detail_api'),
]

# 靜態與媒體檔案設定
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += [
        path('static-debug/<path:path>', RedirectView.as_view(url='/static/%(path)s')),
    ]
