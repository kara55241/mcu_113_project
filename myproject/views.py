from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from langchain_core.messages import HumanMessage
from graph_rag_agent.multi_agent import app
from .feedback_graph import get_feedback_graph
import json
import logging
import os
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)
feedback_graph = get_feedback_graph()
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
            user_msg_id = str(uuid.uuid4())
            feedback_graph.save_message(
                chat_id=session_id,
                message_id=user_msg_id,
                content=user_message,
                sender='user',
                metadata=metadata
            )

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
            output_text = filtered[-1] if filtered else "（無有效回應）"

            logger.info(f"[MultiAgent] ChatID={session_id} 輸出回應：{output_text}")

            bot_msg_id = str(uuid.uuid4())
            feedback_graph.save_message(
                chat_id=session_id,
                message_id=bot_msg_id,
                content=output_text,
                sender='bot',
                metadata=None
            )

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
        


class FeedbackAPIView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)

            # 驗證必要欄位
            required_fields = ['feedback_id', 'message_id', 'chat_id', 'type', 'timestamp']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f'缺少必要欄位: {field}'
                    }, status=400)

            # 驗證回饋類型
            if data['type'] not in ['like', 'dislike']:
                return JsonResponse({
                    'success': False,
                    'error': '回饋類型必須是 like 或 dislike'
                }, status=400)

            # 將 timestamp 轉為 ISO 格式（若非字串）
            if isinstance(data['timestamp'], datetime):
                data['timestamp'] = data['timestamp'].isoformat()

            # 補全必要欄位
            data.setdefault('details', '')
            data.setdefault('session_id', data['chat_id'])

            feedback_graph = get_feedback_graph()


            # 根據回饋類型標記記憶節點或需要改進節點
            try:
                if data['type'] == 'like':
                    feedback_graph.mark_key_memory(
                        message_id=data['message_id'],
                        feedback_type='like',
                        details=data.get('details', '')
                    )
                elif data['type'] == 'dislike':
                    feedback_graph.mark_failed_response(
                        message_id=data['message_id'],
                        reason=data.get('details', '')
                    )
            except Exception as e:
                logger.warning(f"標記回饋節點失敗: {e}")

            # 儲存回饋資訊
            result = feedback_graph.save_feedback(data)

            if result:
                return JsonResponse({
                    'success': True,
                    'feedback_id': result['feedback_id'],
                    'message': '回饋已成功儲存',
                    'timestamp': str(result['timestamp'])
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': '儲存回饋失敗'
                }, status=500)

        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': '無效的 JSON 資料'
            }, status=400)
        except Exception as e:
            logger.exception("Feedback POST failed")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

class ConversationAPIView(View):
    """處理對話管理的 API 端點"""
    
    def post(self, request):
        """創建新對話"""
        try:
            data = json.loads(request.body)
            
            # 驗證必要欄位
            required_fields = ['chat_id', 'session_id']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f'缺少必要欄位: {field}'
                    }, status=400)
            
            feedback_graph = get_feedback_graph()
            
            # 創建對話會話
            result = feedback_graph.create_chat_session(
                chat_id=data['chat_id'],
                session_id=data['session_id'],
                metadata=data.get('metadata', {})
            )
            
            if result:
                logger.info(f"對話已創建: {data['chat_id']}")
                return JsonResponse({
                    'success': True,
                    'chat_id': data['chat_id'],
                    'created_at': str(result['created_at'])
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': '創建對話失敗'
                }, status=500)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': '無效的 JSON 資料'
            }, status=400)
            
        except Exception as e:
            logger.error(f"創建對話時發生錯誤: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': '伺服器內部錯誤'
            }, status=500)
    
    def get(self, request, chat_id=None):
        """獲取對話及其回饋"""
        try:
            if not chat_id:
                return JsonResponse({
                    'success': False,
                    'error': '需要提供 chat_id'
                }, status=400)
            
            feedback_graph = get_feedback_graph()
            conversation = feedback_graph.get_conversation_with_feedback(chat_id)
            
            return JsonResponse({
                'success': True,
                'chat_id': chat_id,
                'conversation': conversation
            })
            
        except Exception as e:
            logger.error(f"獲取對話時發生錯誤: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': '獲取對話失敗'
            }, status=500)
class MessageAPIView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            required_fields = ['message_id', 'chat_id', 'content', 'sender', 'timestamp']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({'success': False, 'error': f'缺少必要欄位: {field}'}, status=400)

            feedback_graph = get_feedback_graph()
            result = feedback_graph.save_message(
                chat_id=data['chat_id'],
                message_id=data['message_id'],
                content=data['content'],
                sender=data['sender'],
                metadata=data.get('metadata')
            )

            if result:
                return JsonResponse({'success': True, 'message': '訊息已儲存'})
            else:
                return JsonResponse({'success': False, 'error': '儲存訊息失敗'}, status=500)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': '無效的 JSON 資料'}, status=400)
        except Exception as e:
            logger.error(f"儲存訊息時發生錯誤: {str(e)}")
            return JsonResponse({'success': False, 'error': '伺服器內部錯誤'}, status=500)