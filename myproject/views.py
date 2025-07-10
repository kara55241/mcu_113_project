from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from langchain_core.messages import HumanMessage, AIMessage
from graph_rag_agent.multi_agent import app
from .feedback_graph import get_feedback_graph
import json
import logging
import os
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)
feedback_graph = get_feedback_graph()

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

            # 獲取或創建 session_id
            session_id = chat_id or request.session.session_key
            if not session_id:
                request.session.create()
                session_id = request.session.session_key

            logger.info(f"[ChatView] 處理會話 {session_id} 的訊息: {user_message[:50]}...")

            # 確保對話會話存在
            try:
                feedback_graph.create_chat_session(
                    chat_id=session_id, 
                    metadata={"created_by": "chat_view"}
                )
            except Exception as e:
                logger.warning(f"創建對話會話可能失敗（可能已存在）: {e}")

            # 處理位置資訊
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

            # 儲存用戶訊息
            metadata = {"location": location_info} if location_info else None
            user_msg_id = f"msg_{session_id}_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
            
            try:
                feedback_graph.save_message(
                    chat_id=session_id,
                    message_id=user_msg_id,
                    content=user_message,
                    sender='user',
                    metadata=metadata
                )
                logger.info(f"[ChatView] 用戶訊息已儲存: {user_msg_id}")
            except Exception as e:
                logger.error(f"儲存用戶訊息失敗: {e}")

            # 準備 AI 處理
            is_location_query = any(k in user_message.lower() for k in ['位置', '附近', '醫院', '診所', '地點', '地圖'])
            context_prefix = ""
            if is_location_query and location_info:
                context_prefix += f"使用者正在詢問與地點有關的問題，其目前的位置資訊如下：\n" \
                                  f"名稱：{location_info.get('name', '')}\n" \
                                  f"地址：{location_info.get('address', '')}\n" \
                                  f"座標：{location_info.get('coordinates', '')}\n\n"

            # 調用 AI
            try:
                result = app.invoke(
                    input={"messages": [HumanMessage(content=context_prefix + user_message)]},
                    config={"configurable": {"thread_id": session_id}},
                )
                messages = result.get("messages", [])
                ai_messages = [m for m in messages if isinstance(m, AIMessage) and m.content]
                output_text = ai_messages[-1].content if ai_messages else "（無有效回應）"
                
                logger.info(f"[ChatView] AI 回應: {output_text[:100]}...")
            except Exception as e:
                logger.error(f"AI 處理失敗: {e}")
                output_text = "抱歉，處理您的請求時發生錯誤。"

            # 儲存 AI 回應
            bot_msg_id = f"msg_{session_id}_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
            
            try:
                feedback_graph.save_message(
                    chat_id=session_id,
                    message_id=bot_msg_id,
                    content=output_text,
                    sender='bot',
                    metadata=None
                )
                logger.info(f"[ChatView] AI 回應已儲存: {bot_msg_id}")
            except Exception as e:
                logger.error(f"儲存 AI 回應失敗: {e}")

            return JsonResponse({
                "output": output_text,
                "is_markdown": True,
                "location": location_info,
                "data": {
                    "user_message_id": user_msg_id,
                    "bot_message_id": bot_msg_id,
                    "chat_id": session_id
                }
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
            
            # 在 Neo4j 中創建新對話
            try:
                feedback_graph.create_chat_session(
                    chat_id=chat_id, 
                    metadata={"created_by": "new_chat_view"}
                )
                logger.info(f"[NewChatView] 新對話已創建: {chat_id}")
            except Exception as e:
                logger.warning(f"創建新對話可能失敗: {e}")
            
            return JsonResponse({
                "success": True, 
                "message": "會話已重置", 
                "chat_id": chat_id
            })
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
                # 返回所有對話的摘要（這裡可以從 Neo4j 獲取）
                return JsonResponse({"chats": []})
            
            # 從 Neo4j 獲取對話歷史
            try:
                conversation = feedback_graph.get_conversation_with_feedback(chat_id)
                return JsonResponse({
                    "chat_id": chat_id, 
                    "messages": conversation
                })
            except Exception as e:
                logger.error(f"獲取對話歷史失敗: {e}")
                return JsonResponse({
                    "chat_id": chat_id, 
                    "messages": []
                })
                
        except Exception as e:
            logger.exception("獲取聊天歷史時發生錯誤")
            return JsonResponse({"error": f"獲取聊天歷史時發生錯誤: {str(e)}"}, status=500)

    def delete(self, request, chat_id, *args, **kwargs):
        try:
            # 這裡可以添加從 Neo4j 刪除對話的邏輯
            return JsonResponse({
                "success": True, 
                "message": "對話已刪除"
            })
        except Exception as e:
            logger.exception("刪除聊天歷史時發生錯誤")
            return JsonResponse({
                "success": False, 
                "error": f"刪除聊天歷史時發生錯誤: {str(e)}"
            }, status=500)

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

            # 儲存文件上傳消息到 Neo4j
            upload_msg_id = f"msg_{chat_id}_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
            try:
                feedback_graph.save_message(
                    chat_id=chat_id,
                    message_id=upload_msg_id,
                    content=f"上傳檔案：{original_filename}",
                    sender='user',
                    metadata={"file_info": file_info}
                )
            except Exception as e:
                logger.warning(f"儲存文件上傳訊息失敗: {e}")

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
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

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

            # 將 timestamp 轉為 ISO 格式
            if isinstance(data['timestamp'], datetime):
                data['timestamp'] = data['timestamp'].isoformat()

            # 補全必要欄位
            data.setdefault('details', '')
            data.setdefault('session_id', data['chat_id'])

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
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        """創建新對話"""
        try:
            data = json.loads(request.body)
            
            required_fields = ['chat_id', 'session_id']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False,
                        'error': f'缺少必要欄位: {field}'
                    }, status=400)
            
            result = feedback_graph.create_chat_session(
                chat_id=data['chat_id'],
                session_id=data['session_id'],
                metadata=data.get('metadata', {})
            )
            
            if result:
                logger.info(f"對話已創建: {data['chat_id']}")
                return JsonResponse({
                    'success': True,
                    'chat_id': data['chat_id']
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
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request):
        try:
            data = json.loads(request.body)
            required_fields = ['message_id', 'chat_id', 'content', 'sender']
            for field in required_fields:
                if field not in data:
                    return JsonResponse({
                        'success': False, 
                        'error': f'缺少必要欄位: {field}'
                    }, status=400)

            result = feedback_graph.save_message(
                chat_id=data['chat_id'],
                message_id=data['message_id'],
                content=data['content'],
                sender=data['sender'],
                metadata=data.get('metadata')
            )

            if result:
                return JsonResponse({
                    'success': True, 
                    'message': '訊息已儲存'
                })
            else:
                return JsonResponse({
                    'success': False, 
                    'error': '儲存訊息失敗'
                }, status=500)
                
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False, 
                'error': '無效的 JSON 資料'
            }, status=400)
        except Exception as e:
            logger.error(f"儲存訊息時發生錯誤: {str(e)}")
            return JsonResponse({
                'success': False, 
                'error': '伺服器內部錯誤'
            }, status=500)