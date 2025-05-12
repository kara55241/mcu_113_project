# 修正 views.py 文件的語法錯誤

from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
from django.conf import settings
import logging
import os
import uuid
from django.db import models

# 設置日誌記錄
logger = logging.getLogger(__name__)

# 簡單的聊天歷史模型 (可替代為實際的數據庫模型)
class ChatHistory:
    _chat_history = {}  # 用於內存儲存聊天記錄
    
    @classmethod
    def add_message(cls, chat_id, content, sender, metadata=None):
        """添加新消息到聊天歷史，支援額外元數據"""
        import time
        
        if chat_id not in cls._chat_history:
            cls._chat_history[chat_id] = []
            
        message = {
            'chat_id': chat_id,
            'content': content,
            'sender': sender,
            'timestamp': time.time()
        }
        
        # 添加元數據（如位置信息）
        if metadata:
            message['metadata'] = metadata
            
        cls._chat_history[chat_id].append(message)
    
    @classmethod
    def get_chat_history(cls, chat_id):
        """獲取特定對話的歷史記錄"""
        return cls._chat_history.get(chat_id, [])
    
    @classmethod
    def get_all_chats(cls):
        """獲取所有對話的摘要"""
        chat_summaries = []
        
        for chat_id, messages in cls._chat_history.items():
            if messages:
                # 獲取第一條消息作為標題
                first_message = next((m for m in messages if m['sender'] == 'user'), None)
                title = first_message['content'] if first_message else "無標題對話"
                
                # 獲取最後一條消息時間作為排序依據
                timestamp = messages[-1]['timestamp']
                
                chat_summaries.append({
                    'id': chat_id,
                    'title': title[:20] + '...' if len(title) > 20 else title,
                    'last_message': messages[-1]['content'],
                    'timestamp': timestamp
                })
        
        # 按時間降序排序
        chat_summaries.sort(key=lambda x: x['timestamp'], reverse=True)
        return chat_summaries
    
    @classmethod
    def delete_chat(cls, chat_id):
        """刪除對話記錄"""
        if chat_id in cls._chat_history:
            del cls._chat_history[chat_id]
            return True
        return False

# 這裡導入您的 Neo4j 連接和 RAG 系統
try:
    from neo4j import GraphDatabase
    # 修正導入路徑
    from graph_rag_agent.ai_agent import generate_response
except ImportError:
    logger.error("Neo4j driver 或 ai_agent 模組未安裝或路徑不正確")
    
    # 臨時替代函數，如果無法導入真實函數
    def generate_response(message, session_id="default", location_info=None):
        response = f"您的訊息已收到: {message}。"
        if location_info:
            response += f"\n您查詢的位置是：{location_info.get('name', '未知地點')}，位於 {location_info.get('address', '未知地址')}。"
        return response

class ChatView(View):
    """處理聊天請求的視圖類"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, *args, **kwargs):
        """處理 GET 請求 - 返回聊天頁面"""
        from django.shortcuts import render
        return render(request, 'myapp/index.html')
    
    def post(self, request, *args, **kwargs):
        """處理 POST 請求 - 處理用戶訊息並返回回應"""
        try:
            # 解析 JSON 請求
            data = json.loads(request.body)
            user_message = data.get("message")
            chat_id = data.get("chat_id")
            location_info = data.get("location_info")  # 獲取位置信息
            
            if not user_message:
                return JsonResponse({"error": "請提供訊息"}, status=400)
            
            # 記錄用戶訊息
            logger.info(f"收到用戶訊息: {user_message}, 對話ID: {chat_id}")
            if location_info:
                logger.info(f"包含位置信息: {location_info}")
            
            # 獲取或創建會話 ID (同時支持 chat_id 和 session)
            session_id = chat_id or request.session.session_key
            if not session_id:
                request.session.create()
                session_id = request.session.session_key
            
            # 處理位置信息 - 確保座標格式正確
            if location_info and isinstance(location_info, dict):
                # 提取並標準化座標
                coords = location_info.get('coordinates')
                if coords and isinstance(coords, str):
                    # 如果座標是字符串，確保格式正確
                    coords_parts = coords.replace(' ', '').split(',')
                    if len(coords_parts) == 2:
                        try:
                            latitude = float(coords_parts[0])
                            longitude = float(coords_parts[1])
                            # 更新位置信息中的座標
                            location_info['coordinates'] = f"{latitude},{longitude}"
                            # 確保有經緯度屬性用於 AI 模型
                            location_info['latitude'] = latitude
                            location_info['longitude'] = longitude
                            logger.info(f"位置座標已格式化: {latitude}, {longitude}")
                        except (ValueError, TypeError):
                            logger.warning(f"無法解析座標: {coords}")
            
            # 將用戶消息添加到歷史記錄，包含位置元數據
            metadata = {"location": location_info} if location_info else None
            ChatHistory.add_message(session_id, user_message, 'user', metadata)
            
            # 呼叫 RAG Agent 模型，傳入會話 ID 和位置信息
            # 若是位置相關問題，可將提示一併傳入
            is_location_query = any(k in user_message.lower() for k in ['位置', '附近', '醫院', '診所', '地點', '地圖'])

            # 建立 prompt context
            context_prefix = ""
            if is_location_query and location_info:
                context_prefix += f"使用者正在詢問與地點有關的問題，其目前的位置資訊如下：\n" \
                                f"名稱：{location_info.get('name', '')}\n" \
                                f"地址：{location_info.get('address', '')}\n" \
                                f"座標：{location_info.get('coordinates', '')}\n\n"

            response_data = generate_response(context_prefix + user_message, session_id, location_info)

            ChatHistory.add_message(session_id, response_data.get('output', ''), 'bot')

            return JsonResponse({
                "output": response_data.get('output', ''),
                "location": response_data.get('location', location_info),
                "data": response_data.get('data', {})
            })

            
        except json.JSONDecodeError:
            return JsonResponse({"error": "無效的JSON格式"}, status=400)
        except Exception as e:
            logger.exception("處理聊天請求時發生錯誤")
            return JsonResponse({"error": f"處理請求時發生錯誤: {str(e)}"}, status=500)

class NewChatView(View):
    """處理新對話請求的視圖類"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """處理新對話請求 - 重置會話"""
        try:
            # 解析 JSON 請求
            data = json.loads(request.body)
            chat_id = data.get('chat_id')
            
            # 重新生成會話 ID 或使用提供的 chat_id
            if not chat_id:
                request.session.flush()
                request.session.create()
                chat_id = request.session.session_key
            
            logger.info(f"創建新對話: {chat_id}")
            
            return JsonResponse({"success": True, "message": "會話已重置", "chat_id": chat_id})
        except Exception as e:
            logger.exception("重置會話時發生錯誤")
            return JsonResponse({"error": f"重置會話時發生錯誤: {str(e)}"}, status=500)

class ChatHistoryView(View):
    """處理聊天歷史請求的視圖類"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, chat_id=None, *args, **kwargs):
        """獲取特定對話的歷史記錄"""
        try:
            if not chat_id:
                # 如果沒有提供 chat_id，返回所有對話摘要
                chats = ChatHistory.get_all_chats()
                return JsonResponse({"chats": chats})
            
            # 獲取特定對話的歷史記錄
            messages = ChatHistory.get_chat_history(chat_id)
            
            # 格式化為前端需要的格式
            formatted_messages = []
            for msg in messages:
                message_data = {
                    'content': msg['content'],
                    'sender': msg['sender'],
                    'timestamp': msg['timestamp']
                }
                
                # 如果有元數據，添加到響應中
                if 'metadata' in msg:
                    message_data['metadata'] = msg['metadata']
                
                formatted_messages.append(message_data)
            
            return JsonResponse({"chat_id": chat_id, "messages": formatted_messages})
            
        except Exception as e:
            logger.exception("獲取聊天歷史時發生錯誤")
            return JsonResponse({"error": f"獲取聊天歷史時發生錯誤: {str(e)}"}, status=500)
            
    def delete(self, request, chat_id, *args, **kwargs):
        """刪除特定對話"""
        try:
            # 刪除對話記錄
            success = ChatHistory.delete_chat(chat_id)
            
            if success:
                logger.info(f"已刪除對話: {chat_id}")
                return JsonResponse({"success": True, "message": "對話已刪除"})
            else:
                return JsonResponse({"success": False, "error": "找不到指定的對話"}, status=404)
                
        except Exception as e:
            logger.exception("刪除聊天歷史時發生錯誤")
            return JsonResponse({"success": False, "error": f"刪除聊天歷史時發生錯誤: {str(e)}"}, status=500)

class FileUploadView(View):
    """處理檔案上傳的視圖類"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """處理文件上傳請求"""
        try:
            if 'file' not in request.FILES:
                return JsonResponse({"success": False, "error": "未提供檔案"}, status=400)
            
            # 取得聊天 ID
            chat_id = request.POST.get('chat_id')
            if not chat_id:
                chat_id = request.session.session_key
                if not chat_id:
                    request.session.create()
                    chat_id = request.session.session_key
            
            uploaded_file = request.FILES['file']

            # 驗證檔名避免安全問題
            original_filename = os.path.basename(uploaded_file.name)
            filename = f"{uuid.uuid4()}_{original_filename}"

            # 準備儲存路徑
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', chat_id)
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)

            # 儲存檔案
            with open(file_path, 'wb+') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            # 儲存檔案資訊到 session
            file_info = {
                'original_name': original_filename,
                'saved_path': file_path,
                'chat_id': chat_id
            }

            uploaded_files = request.session.get('uploaded_files', [])
            uploaded_files.append(file_info)
            request.session['uploaded_files'] = uploaded_files
            request.session.modified = True

            # 記錄到聊天歷史
            upload_message = f"上傳檔案：{original_filename}"
            ChatHistory.add_message(chat_id, upload_message, 'user')

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
