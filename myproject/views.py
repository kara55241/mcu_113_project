from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from langchain_core.messages import HumanMessage
from graph_rag_agent.multi_agent import app
import json
import logging
import os
import uuid

logger = logging.getLogger(__name__)

# 簡單的聊天歷史模型（可替代為實際的資料庫模型）
class ChatHistory:
    _chat_history = {}

    @classmethod
    def add_message(cls, chat_id, content, sender, metadata=None):
        import time
        if chat_id not in cls._chat_history:
            cls._chat_history[chat_id] = []
        message = {
            'chat_id': chat_id,
            'content': content,
            'sender': sender,
            'timestamp': time.time()
        }
        if metadata:
            message['metadata'] = metadata
        cls._chat_history[chat_id].append(message)

    @classmethod
    def get_chat_history(cls, chat_id):
        return cls._chat_history.get(chat_id, [])

    @classmethod
    def get_all_chats(cls):
        chat_summaries = []
        for chat_id, messages in cls._chat_history.items():
            if messages:
                first_message = next((m for m in messages if m['sender'] == 'user'), None)
                title = first_message['content'] if first_message else "無標題對話"
                timestamp = messages[-1]['timestamp']
                chat_summaries.append({
                    'id': chat_id,
                    'title': title[:20] + '...' if len(title) > 20 else title,
                    'last_message': messages[-1]['content'],
                    'timestamp': timestamp
                })
        chat_summaries.sort(key=lambda x: x['timestamp'], reverse=True)
        return chat_summaries

    @classmethod
    def delete_chat(cls, chat_id):
        if chat_id in cls._chat_history:
            del cls._chat_history[chat_id]
            return True
        return False

class ChatView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        from django.shortcuts import render
        return render(request, 'myapp/index.html')

    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            user_message = data.get("message")
            chat_id = data.get("chat_id")
            location_info = data.get("location_info")

            if not user_message:
                return JsonResponse({"error": "請提供訊息"}, status=400)

            session_id = chat_id or request.session.session_key
            if not session_id:
                request.session.create()
                session_id = request.session.session_key

            if location_info and isinstance(location_info, dict):
                coords = location_info.get('coordinates')
                if coords and isinstance(coords, str):
                    parts = coords.replace(' ', '').split(',')
                    if len(parts) == 2:
                        try:
                            lat = float(parts[0])
                            lng = float(parts[1])
                            location_info['coordinates'] = f"{lat},{lng}"
                            location_info['latitude'] = lat
                            location_info['longitude'] = lng
                        except Exception:
                            logger.warning(f"無法解析座標: {coords}")

            metadata = {"location": location_info} if location_info else None
            ChatHistory.add_message(session_id, user_message, 'user', metadata)

            is_location_query = any(k in user_message.lower() for k in ['位置', '附近', '醫院', '診所', '地點', '地圖'])
            context_prefix = ""
            if is_location_query and location_info:
                context_prefix += f"使用者正在詢問與地點有關的問題，其目前的位置資訊如下：\n" \
                                  f"名稱：{location_info.get('name', '')}\n" \
                                  f"地址：{location_info.get('address', '')}\n" \
                                  f"座標：{location_info.get('coordinates', '')}\n\n"

            result = app.invoke(
                input={"messages": [HumanMessage(content=context_prefix + user_message)]},
                config={"configurable": {"thread_id": session_id}},
            )
            messages = result.get("messages", [])
            filtered = app.filter_messages(messages)

            # 只取最新一則回應
            output_text = filtered[-1] if filtered else "（無有效回應）"

            logger.info(f"[MultiAgent] ChatID={session_id} 輸出回應：{output_text}")  # 👈 建議新增
            ChatHistory.add_message(session_id, output_text, 'bot')



            ChatHistory.add_message(session_id, output_text, 'bot')

            return JsonResponse({
                "output": output_text,
                "is_markdown": True,
                "location": location_info,
                "data": {}
            })

        except json.JSONDecodeError:
            return JsonResponse({"error": "無效的JSON格式"}, status=400)
        except Exception as e:
            logger.exception("處理聊天請求時發生錯誤")
            return JsonResponse({"error": f"處理請求時發生錯誤: {str(e)}"}, status=500)

class NewChatView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            request.session.flush()
            request.session.create()
            chat_id = request.session.session_key
            return JsonResponse({"success": True, "message": "會話已重置", "chat_id": chat_id})
        except Exception as e:
            logger.exception("重置會話時發生錯誤")
            return JsonResponse({"error": f"重置會話時發生錯誤: {str(e)}"}, status=500)

class ChatHistoryView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, chat_id=None, *args, **kwargs):
        try:
            if not chat_id:
                chats = ChatHistory.get_all_chats()
                return JsonResponse({"chats": chats})
            messages = ChatHistory.get_chat_history(chat_id)
            return JsonResponse({"chat_id": chat_id, "messages": messages})
        except Exception as e:
            logger.exception("獲取聊天歷史時發生錯誤")
            return JsonResponse({"error": f"獲取聊天歷史時發生錯誤: {str(e)}"}, status=500)

    def delete(self, request, chat_id, *args, **kwargs):
        try:
            success = ChatHistory.delete_chat(chat_id)
            if success:
                return JsonResponse({"success": True, "message": "對話已刪除"})
            else:
                return JsonResponse({"success": False, "error": "找不到指定的對話"}, status=404)
        except Exception as e:
            logger.exception("刪除聊天歷史時發生錯誤")
            return JsonResponse({"success": False, "error": f"刪除聊天歷史時發生錯誤: {str(e)}"}, status=500)

class FileUploadView(View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            if 'file' not in request.FILES:
                return JsonResponse({"success": False, "error": "未提供檔案"}, status=400)

            chat_id = request.POST.get('chat_id') or request.session.session_key
            if not chat_id:
                request.session.create()
                chat_id = request.session.session_key

            uploaded_file = request.FILES['file']
            original_filename = os.path.basename(uploaded_file.name)
            filename = f"{uuid.uuid4()}_{original_filename}"
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', chat_id)
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)

            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            file_info = {
                'original_name': original_filename,
                'saved_path': file_path,
                'chat_id': chat_id
            }

            uploaded_files = request.session.get('uploaded_files', [])
            uploaded_files.append(file_info)
            request.session['uploaded_files'] = uploaded_files
            request.session.modified = True

            ChatHistory.add_message(chat_id, f"上傳檔案：{original_filename}", 'user')

            return JsonResponse({
                "success": True,
                "message": "檔案已成功上傳，您可以繼續提問關於此檔案的問題。",
                "file_info": file_info
            })

        except Exception as e:
            logger.exception("處理檔案上傳時發生錯誤")
            return JsonResponse({
                "success": False,
                "error": f"處理檔案上傳時發生錯誤: {str(e)}"
            }, status=500)