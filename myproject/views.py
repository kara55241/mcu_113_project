# views.py - 修正導入路徑版本

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
import json
import uuid
from datetime import datetime
from langchain_core.messages import HumanMessage
from django.core.serializers.json import DjangoJSONEncoder
from myproject.feedback_graph import store_feedback_memory

# 自定義 JSON 編碼器處理 Neo4j 類型
class CustomJSONEncoder(DjangoJSONEncoder):
    def default(self, obj):
        # 處理 Neo4j DateTime 類型
        from neo4j.time import DateTime as Neo4jDateTime
        if isinstance(obj, Neo4jDateTime):
            return obj.isoformat()
        # 處理其他 Neo4j 類型
        elif hasattr(obj, '__dict__') and hasattr(obj, '_properties'):
            return dict(obj._properties)
        return super().default(obj)

# 修復導入路徑 - 使用相對導入避免循環依賴
try:
    from .feedback_graph import get_feedback_graph
    print("✅ 成功導入 feedback_graph")
except ImportError as e1:
    print(f"⚠️ 相對導入失敗: {e1}")
    try:
        from myproject.feedback_graph import get_feedback_graph
        print("✅ 成功從 myproject 導入 feedback_graph")
    except ImportError as e2:
        print(f"❌ feedback_graph 導入失敗: {e2}")
        # 創建 fallback 函數
        def get_feedback_graph():
            from myproject.feedback_graph import FeedbackGraph
            return FeedbackGraph()

# 導入 multi_agent app - 延遲導入避免初始化錯誤
app = None

def get_multiagent_app():
    """延遲載入 multi-agent app"""
    global app
    if app is None:
        try:
            from graph_rag_agent.multi_agent import app as multi_app
            app = multi_app
            print("✅ 成功導入 multi-agent app")
        except ImportError as e:
            print(f"❌ multi-agent 導入失敗: {e}")
            # 創建 fallback 回應
            class FallbackApp:
                def invoke(self, input_data, config=None):
                    return {
                        "messages": [
                            type('Message', (), {
                                'content': "系統正在初始化中，請稍後再試。"
                            })()
                        ]
                    }
                
                def filter_messages(self, messages):
                    return [msg.content if hasattr(msg, 'content') else str(msg) for msg in messages]
            
            app = FallbackApp()
    return app

@method_decorator(csrf_exempt, name='dispatch')
class ChatView(View):
    """聊天主視圖 - 修正版本"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            chat_id = data.get('chat_id')
            user_message_id = data.get('user_message_id')
            location_info = data.get('location_info')
            
            if not user_message:
                return JsonResponse({'error': '訊息內容不能為空'}, status=400)
            
            if not chat_id:
                return JsonResponse({'error': '聊天ID必須提供'}, status=400)
            
            print(f"🤖 Multi-agent 處理聊天請求: {chat_id}")
            
            # 獲取 feedback_graph 實例
            feedback_graph = get_feedback_graph()
            
            # 🔧 修正：使用 MERGE 確保對話存在，避免重複創建錯誤
            try:
                feedback_graph.create_chat_session(chat_id, session_id=chat_id, metadata={
                    'created_by': 'multi_agent_chat',
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                print(f"⚠️ 創建對話會話時的警告（可能已存在）: {e}")
                # 繼續執行，不讓這個錯誤阻止聊天功能
            
            # 🔧 修正：生成唯一的 user_message_id（如果沒有提供）
            if not user_message_id:
                user_message_id = f"msg_{chat_id}_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
            
            # 保存用戶訊息到統一資料庫
            final_user_message_id = self.save_user_message(
                feedback_graph, chat_id, user_message, user_message_id
            )
            
            # 🚀 使用 multi-agent 生成回應
            ai_response = self.generate_multiagent_response(
                user_message, chat_id, location_info
            )
            
            # 處理AI回應
            bot_content = ai_response.get('output', 'Multi-agent 暫時無法回應')
            is_markdown = ai_response.get('is_markdown', True)
            
            # 🔧 修正：生成唯一的 bot_message_id
            bot_message_id = f"bot_{chat_id}_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"
            
            # 保存AI回應到統一資料庫
            final_bot_message_id = self.save_bot_message(
                feedback_graph, chat_id, bot_content, bot_message_id
            )
            
            return JsonResponse({
                'output': bot_content,
                'is_markdown': is_markdown,
                'user_message_id': final_user_message_id,
                'bot_message_id': final_bot_message_id,
                'chat_id': chat_id,
                'location': ai_response.get('location'),
                'data': ai_response.get('data', {}),
                'should_refresh_history': False,
                'success': True
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '無效的JSON格式'}, status=400)
        except Exception as e:
            print(f"Multi-agent 聊天處理錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'Multi-agent 系統錯誤: {str(e)}'}, status=500)
    
    def generate_multiagent_response(self, user_input, session_id, location_info=None):
        """使用 multi-agent 系統生成回應"""
        try:
            # 準備輸入文本
            input_text = user_input.strip()
            if location_info and "位置信息" not in input_text:
                input_text += (
                    f"\n\n📍位置信息："
                    f"\n- 名稱：{location_info.get('name', '未知')}"
                    f"\n- 地址：{location_info.get('address', '未知')}"
                    f"\n- 座標：{location_info.get('coordinates', '未知')}"
                )
            
            print(f"🔧 Multi-agent 處理輸入: {input_text[:100]}...")
            
            # 使用 multi-agent app 處理請求
            multiagent_app = get_multiagent_app()
            result = multiagent_app.invoke(
                {"messages": [HumanMessage(content=input_text)]},
                config={"configurable": {"thread_id": session_id}},
            )
            
            print(f"📤 Multi-agent 原始回應: {result}")
            
            # 處理回應訊息
            if hasattr(multiagent_app, 'filter_messages'):
                # 使用過濾後訊息
                clean_messages = multiagent_app.filter_messages(result.get("messages", []))
                output_text = "\n\n".join(clean_messages)
            else:
                # 直接處理訊息
                messages = result.get("messages", [])
                if messages:
                    # 提取最後一條AI訊息
                    last_message = messages[-1]
                    if hasattr(last_message, 'content'):
                        output_text = last_message.content
                    else:
                        output_text = str(last_message)
                else:
                    output_text = "Multi-agent 系統沒有返回回應"
            
            print(f"✅ Multi-agent 處理後輸出: {output_text[:200]}...")
            
            return {
                "output": output_text,
                "is_markdown": True,
                "location": location_info,
                "data": {},
            }
            
        except Exception as e:
            print(f"❌ Multi-agent 生成回應錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return {
                "output": f"⚠️ Multi-agent 系統錯誤：{str(e)}",
                "location": location_info,
                "data": {},
            }
    
    def save_user_message(self, feedback_graph, chat_id, content, message_id):
        """保存用戶訊息到統一資料庫"""
        try:
            result = feedback_graph.save_message(
                chat_id=chat_id,
                message_id=message_id,
                content=content,
                sender='user'
            )
            
            status = result.get('status', 'unknown')
            if status == 'skipped':
                print(f"⚠️ 用戶訊息ID重複，已跳過: {message_id}")
            elif status == 'saved':
                print(f"💾 用戶訊息已保存: {message_id}")
            elif status == 'error':
                print(f"⚠️ 保存用戶訊息失敗: {result.get('error', 'unknown')}")
                
            return result.get('message_id', message_id)
            
        except Exception as e:
            print(f"⚠️ 保存用戶訊息失敗: {e}")
            return message_id
    
    def save_bot_message(self, feedback_graph, chat_id, content, message_id=None):
        """保存AI回應到統一資料庫"""
        if not message_id:
            message_id = f"bot_{chat_id}_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}"

        try:
            # 內容長度安全檢查
            max_length = 50000
            if content and len(content) > max_length:
                print("⚠️ Bot 回應過長，自動截斷")
                content = content[:max_length] + "\n...(已截斷)"

            # 測試 JSON 序列化 - 使用自定義編碼器
            try:
                json.dumps({"test": content}, ensure_ascii=False, cls=CustomJSONEncoder)
            except Exception as json_error:
                print(f"⚠️ JSON 序列化測試失敗: {json_error}")
                # 如果序列化失敗，清理內容
                content = str(content)[:10000] + "...(內容已清理)" if len(str(content)) > 10000 else str(content)

            # 保存到 feedback_graph
            result = feedback_graph.save_message(
                chat_id=chat_id,
                message_id=message_id,
                content=content,
                sender='bot'
            )
            
            status = result.get('status', 'unknown')
            if status == 'skipped':
                print(f"⚠️ Bot訊息ID重複，已跳過: {message_id}")
            elif status == 'saved':
                print(f"💾 Bot訊息已保存: {message_id}")
            elif status == 'error':
                print(f"⚠️ 保存Bot訊息失敗: {result.get('error', 'unknown')}")
                
            return result.get('message_id', message_id)

        except Exception as e:
            print(f"❌ 保存Bot訊息失敗: {e}")
            import traceback
            traceback.print_exc()
            return message_id

@method_decorator(csrf_exempt, name='dispatch')
class ConversationView(View):
    """對話管理視圖"""
    
    def post(self, request):
        """創建新對話"""
        try:
            data = json.loads(request.body)
            chat_id = data.get('chat_id')
            session_id = data.get('session_id', chat_id)
            metadata = data.get('metadata', {})
            
            if not chat_id:
                return JsonResponse({'error': '聊天ID必須提供'}, status=400)
            
            feedback_graph = get_feedback_graph()
            
            try:
                result = feedback_graph.create_chat_session(
                    chat_id=chat_id,
                    session_id=session_id,
                    metadata={**metadata, 'created_by': 'multi_agent_api'}
                )
                
                print(f"✅ Multi-agent 對話已創建/獲取: {chat_id}")
                
                return JsonResponse({
                    'chat_id': chat_id,
                    'session_id': session_id,
                    'message': 'Multi-agent 對話創建成功',
                    'success': True
                })
                
            except Exception as e:
                print(f"⚠️ 創建對話時的警告: {str(e)}")
                # 即使有警告，也返回成功，因為對話可能已存在
                return JsonResponse({
                    'chat_id': chat_id,
                    'session_id': session_id,
                    'message': 'Multi-agent 對話已存在或創建成功',
                    'success': True,
                    'warning': str(e)
                })
            
        except Exception as e:
            print(f"創建 Multi-agent 對話錯誤: {str(e)}")
            return JsonResponse({'error': f'創建 Multi-agent 對話失敗: {str(e)}'}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class ConversationDetailView(View):
    """對話詳情視圖"""
    
    def get(self, request, chat_id):
        """獲取特定對話的詳情"""
        try:
            feedback_graph = get_feedback_graph()
            
            # 獲取對話信息
            chat_info = feedback_graph.get_chat_session(chat_id)
            if not chat_info:
                return JsonResponse({'error': '找不到指定的對話'}, status=404)
            
            # 獲取對話中的所有訊息
            messages = feedback_graph.get_chat_messages(chat_id)
            
            return JsonResponse({
                'chat': chat_info,
                'messages': messages,
                'success': True
            })
            
        except Exception as e:
            print(f"獲取對話詳情錯誤: {str(e)}")
            return JsonResponse({'error': f'獲取對話詳情失敗: {str(e)}'}, status=500)
    
    def delete(self, request, chat_id):
        """刪除對話"""
        try:
            feedback_graph = get_feedback_graph()
            
            # 刪除對話及其相關數據
            result = feedback_graph.delete_chat_session(chat_id)
            
            return JsonResponse({
                'message': '對話已刪除',
                'deleted_chats': result.get('deleted_chats', 0),
                'deleted_messages': result.get('deleted_messages', 0),
                'deleted_feedbacks': result.get('deleted_feedbacks', 0),
                'success': True
            })
            
        except Exception as e:
            print(f"刪除對話錯誤: {str(e)}")
            return JsonResponse({'error': f'刪除對話失敗: {str(e)}'}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class MessageView(View):
    """訊息管理視圖"""
    
    def post(self, request):
        """保存訊息"""
        try:
            data = json.loads(request.body)
            message_id = data.get('message_id')
            chat_id = data.get('chat_id')
            content = data.get('content')
            sender = data.get('sender')
            
            if not all([message_id, chat_id, content, sender]):
                return JsonResponse({'error': '缺少必要參數'}, status=400)
            
            feedback_graph = get_feedback_graph()
            
            # 使用修正後的保存訊息方法
            result = feedback_graph.save_message(
                chat_id=chat_id,
                message_id=message_id,
                content=content,
                sender=sender,
                metadata=data.get('metadata', {})
            )
            
            status = result.get('status', 'unknown')
            return JsonResponse({
                'message': f'Multi-agent 訊息處理完成 ({status})',
                'message_id': result.get('message_id', message_id),
                'timestamp': result.get('timestamp'),
                'status': status,
                'success': True
            })
            
        except Exception as e:
            print(f"保存 Multi-agent 訊息錯誤: {str(e)}")
            return JsonResponse({'error': f'保存訊息失敗: {str(e)}'}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class FeedbackView(View):
    """修正後的回饋管理視圖"""
    
    def post(self, request):
        """保存回饋並自動創建 KeyMemory"""
        try:
            data = json.loads(request.body)
            feedback_id = data.get('feedback_id')
            message_id = data.get('message_id')
            chat_id = data.get('chat_id')
            feedback_type = data.get('type')
            details = data.get('details', '')
            
            if not all([feedback_id, message_id, feedback_type]):
                return JsonResponse({'error': '缺少必要參數'}, status=400)
            
            print(f"💾 處理回饋: {feedback_type} for message: {message_id}")
            
            feedback_graph = get_feedback_graph()
            
            # 準備回饋資料
            feedback_data = {
                'feedback_id': feedback_id,
                'message_id': message_id,
                'chat_id': chat_id or 'default',
                'type': feedback_type,
                'details': details,
                'timestamp': datetime.now().isoformat(),
                'session_id': data.get('session_id', chat_id)
            }
            
            # 保存回饋
            result = feedback_graph.save_feedback(feedback_data)
            
            if 'error' in result:
                return JsonResponse({'error': result['error']}, status=500)
            
            print(f"✅ 回饋已保存: {feedback_type}")
            
            # 🔧 修正：如果是 like 回饋，創建 KeyMemory
            if feedback_type == "like":
                print(f"👍 檢測到 like 回饋，準備創建 KeyMemory...")
                
                try:
                    # 獲取該訊息的內容
                    message = feedback_graph.get_message_by_id(message_id)
                    print(f"📄 獲取到訊息: {message is not None}")
                    
                    if message and message.get('sender') == 'bot':
                        content = message.get('content', '')
                        print(f"🤖 Bot訊息內容: {content[:50]}...")
                        
                        if content:
                            # 準備 KeyMemory 數據
                            keymemory_data = {
                                "query": details or "用戶查詢",  # 使用詳情作為查詢
                                "response": content,
                                "feedback_type": "positive",
                                "rating": 1,
                                "timestamp": str(int(datetime.now().timestamp())),
                                "message_id": message_id,
                                "chat_id": chat_id or 'default'
                            }
                            
                            print(f"🔄 調用 store_feedback_memory...")
                            keymemory_result = store_feedback_memory(keymemory_data)
                            print(f"📝 KeyMemory 結果: {keymemory_result.get('status', 'unknown')}")
                            
                            if keymemory_result.get('status') == 'saved':
                                print("✅ KeyMemory 創建成功")
                            else:
                                print(f"⚠️ KeyMemory 創建可能失敗: {keymemory_result}")
                        else:
                            print("⚠️ 訊息內容為空，跳過 KeyMemory 創建")
                    else:
                        print(f"⚠️ 訊息不是bot回應或不存在，跳過 KeyMemory 創建")
                        print(f"    訊息存在: {message is not None}")
                        if message:
                            print(f"    發送者: {message.get('sender')}")
                            
                except Exception as km_error:
                    print(f"❌ KeyMemory 創建異常: {km_error}")
                    import traceback
                    traceback.print_exc()
                    # 不讓 KeyMemory 錯誤影響回饋保存的成功回應
            
            return JsonResponse({
                'message': 'Multi-agent 回饋已保存',
                'feedback_id': result.get('feedback_id', feedback_id),
                'timestamp': result.get('timestamp'),
                'keymemory_created': feedback_type == "like",
                'success': True
            })
            
        except Exception as e:
            print(f"❌ 保存 Multi-agent 回饋錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': f'保存回饋失敗: {str(e)}'}, status=500)
@method_decorator(csrf_exempt, name='dispatch')
class ChatHistoryListView(View):
    """聊天歷史列表視圖"""
    
    def get(self, request):
        """獲取所有聊天歷史"""
        try:
            feedback_graph = get_feedback_graph()
            
            # 獲取所有聊天會話
            chats = feedback_graph.get_all_chat_sessions()
            
            return JsonResponse({
                'chats': chats,
                'total': len(chats),
                'success': True
            })
            
        except Exception as e:
            print(f"獲取聊天歷史列表錯誤: {str(e)}")
            return JsonResponse({'error': f'獲取聊天歷史失敗: {str(e)}'}, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class ChatHistoryDetailView(View):
    """聊天歷史詳情視圖"""
    
    def get(self, request, chat_id):
        """獲取特定聊天的歷史記錄"""
        try:
            feedback_graph = get_feedback_graph()
            
            # 獲取聊天會話信息
            chat_info = feedback_graph.get_chat_session(chat_id)
            if not chat_info:
                return JsonResponse({'error': '找不到指定的聊天記錄'}, status=404)
            
            # 獲取聊天訊息
            messages = feedback_graph.get_chat_messages(chat_id)
            
            return JsonResponse({
                'chat': chat_info,
                'messages': messages,
                'success': True
            })
            
        except Exception as e:
            print(f"獲取聊天歷史詳情錯誤: {str(e)}")
            return JsonResponse({'error': f'獲取聊天歷史詳情失敗: {str(e)}'}, status=500)
    
    def delete(self, request, chat_id):
        """刪除特定聊天記錄"""
        try:
            feedback_graph = get_feedback_graph()
            
            # 刪除聊天記錄
            result = feedback_graph.delete_chat_session(chat_id)
            
            return JsonResponse({
                'message': 'Multi-agent 聊天記錄已刪除',
                'deleted_chats': result.get('deleted_chats', 0),
                'deleted_messages': result.get('deleted_messages', 0),
                'deleted_feedbacks': result.get('deleted_feedbacks', 0),
                'success': True
            })
            
        except Exception as e:
            print(f"刪除 Multi-agent 聊天記錄錯誤: {str(e)}")
            return JsonResponse({'error': f'刪除聊天記錄失敗: {str(e)}'}, status=500)

def home(request):
    """主頁視圖"""
    from django.shortcuts import render
    return render(request, 'index.html')

@csrf_exempt
def health_check(request):
    """健康檢查端點"""
    if request.method == 'GET':
        try:
            feedback_graph = get_feedback_graph()
            # 簡單的Neo4j連接測試
            with feedback_graph.driver.session() as session:
                result = session.run("RETURN 1 as test")
                test_result = result.single()
            
            # 測試 multi-agent 是否可用
            try:
                multiagent_app = get_multiagent_app()
                # 簡單測試 multi-agent app
                test_response = multiagent_app.invoke(
                {"messages": [HumanMessage(content="健康檢查")]},
                config={"configurable": {"thread_id": "health_check"}},
            )
                multiagent_status = 'available'
            except Exception as e:
                print(f"Multi-agent 健康檢查失敗: {e}")
                multiagent_status = f'unavailable: {str(e)[:100]}'
            
            return JsonResponse({
                'status': 'healthy',
                'neo4j': 'connected',
                'database': 'feedbacktest',
                'agent_type': 'multi_agent',
                'multiagent_status': multiagent_status,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            return JsonResponse({
                'status': 'unhealthy',
                'error': str(e),
                'agent_type': 'multi_agent',
                'timestamp': datetime.now().isoformat()
            }, status=503)
    
    return JsonResponse({'error': '只支持GET請求'}, status=405)