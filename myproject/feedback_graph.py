# feedback_graph.py - 修正後的版本

import os
import logging
import json
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from neo4j import GraphDatabase
from neo4j.time import DateTime as Neo4jDateTime

logger = logging.getLogger(__name__)

# 簡化的 embedding 函數
def compute_embedding(text: str) -> list:
    """計算文本的嵌入向量"""
    try:
        from langchain_openai import OpenAIEmbeddings
        embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
        return embeddings.embed_query(text)
    except Exception as e:
        logger.error(f"計算嵌入向量失敗: {e}")
        # 返回默認的空向量
        return [0.0] * 1536

def convert_neo4j_types(obj):
    """轉換 Neo4j 特殊類型為 JSON 可序列化的類型"""
    if isinstance(obj, Neo4jDateTime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_neo4j_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_neo4j_types(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        if hasattr(obj, '_properties'):
            return convert_neo4j_types(dict(obj._properties))
        else:
            return convert_neo4j_types(obj.__dict__)
    else:
        return obj

class FeedbackGraph:
    """修正後的回饋圖數據庫管理器"""
    
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
        self.username = os.getenv("NEO4J_USERNAME", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        self.database = os.getenv("NEO4J_DATABASE2", "feedbacktest")
        
        print(f"🔗 初始化 FeedbackGraph - 數據庫: {self.database}")
        
        try:
            # 修正：創建 driver 時不指定 database
            self.driver = GraphDatabase.driver(
                self.uri, 
                auth=(self.username, self.password)
            )
            
            # 測試連接並創建向量索引
            self._initialize_database()
            print(f"✅ Neo4j 連接成功 - 數據庫: {self.database}")
                    
        except Exception as e:
            print(f"❌ Neo4j 連接失敗: {e}")
            raise e
    
    def _initialize_database(self):
        """初始化資料庫和向量索引"""
        try:
            with self.driver.session(database=self.database) as session:
                # 測試連接
                result = session.run("RETURN 1 as test")
                test_result = result.single()
                
                if test_result:
                    # 創建向量索引
                    self._create_vector_index(session)
                        
        except Exception as e:
            print(f"⚠️ 初始化資料庫時的警告: {e}")
    
    def _create_vector_index(self, session):
        """創建向量索引 - 修正版本"""
        try:
            # 檢查索引是否已存在
            check_result = session.run("""
            SHOW INDEXES 
            WHERE name = 'key_memory_embeddings'
            """)
            
            existing_indexes = list(check_result)
            if existing_indexes:
                print("✅ KeyMemory 向量索引已存在")
                return
            
            # 修正的創建語法 - 使用正確的語法格式
            session.run("""
            CREATE VECTOR INDEX key_memory_embeddings IF NOT EXISTS
            FOR (k:KeyMemory) ON k.embedding
            OPTIONS {
                indexConfig: {
                    `vector.dimensions`: 1536,
                    `vector.similarity_function`: 'cosine'
                }
            }
            """)
            print("✅ KeyMemory 向量索引創建成功")
            
        except Exception as e:
            print(f"⚠️ 向量索引創建失敗: {e}")
            # 嘗試備用方法
            try:
                session.run("""
                CALL db.index.vector.createNodeIndex(
                    'key_memory_embeddings',
                    'KeyMemory',
                    'embedding',
                    1536,
                    'cosine'
                )
                """)
                print("✅ KeyMemory 向量索引創建成功 (備用方法)")
            except Exception as e2:
                print(f"❌ 所有向量索引創建方法都失敗: {e2}")
    
    def close(self):
        """關閉數據庫連接"""
        if hasattr(self, 'driver'):
            self.driver.close()
    
    def save_keymemory(self, content: str, embedding: list, feedback_type: str, source_message_id: str = "", metadata: Dict = None) -> Dict:
        """修正後的 KeyMemory 存儲方法"""
        try:
            # 驗證 embedding 格式
            if not isinstance(embedding, list) or len(embedding) == 0:
                print(f"⚠️ 無效的 embedding 格式: {type(embedding)}, 長度: {len(embedding) if isinstance(embedding, list) else 'N/A'}")
                return {"status": "error", "error": "無效的 embedding 格式"}
            
            # 確保 embedding 是 float 列表
            try:
                embedding = [float(x) for x in embedding]
            except (ValueError, TypeError) as e:
                print(f"⚠️ embedding 轉換失敗: {e}")
                return {"status": "error", "error": f"embedding 轉換失敗: {e}"}
            
            # 生成唯一 ID
            keymemory_id = f"km_{int(datetime.now().timestamp()*1000)}_{hash(content) % 10000}"
            metadata_json = json.dumps(metadata) if metadata else "{}"
            
            print(f"💾 準備存儲 KeyMemory: {content[:50]}... (embedding維度: {len(embedding)})")
            
            with self.driver.session(database=self.database) as session:
                # 檢查是否已存在相同內容
                existing_check = session.run("""
                MATCH (k:KeyMemory {content: $content})
                RETURN k.keymemory_id as existing_id
                LIMIT 1
                """, {"content": content})
                
                existing_record = existing_check.single()
                if existing_record:
                    print(f"⚠️ KeyMemory 內容已存在: {existing_record['existing_id']}")
                    return {
                        "status": "exists",
                        "keymemory_id": existing_record['existing_id'],
                        "message": "內容已存在"
                    }
                
                # 創建新的 KeyMemory
                result = session.run("""
                    CREATE (k:KeyMemory {
                        keymemory_id: $keymemory_id,
                        content: $content,
                        embedding: $embedding,
                        feedback_type: $feedback_type,
                        source_message_id: $source_message_id,
                        created_at: datetime(),
                        metadata_json: $metadata_json
                    })
                    RETURN k
                """, {
                    "keymemory_id": keymemory_id,
                    "content": content,
                    "embedding": embedding,
                    "feedback_type": feedback_type,
                    "source_message_id": source_message_id,
                    "metadata_json": metadata_json,
                })
                
                record = result.single()
                if record:
                    saved_data = convert_neo4j_types(dict(record["k"]))
                    print(f"✅ KeyMemory 已成功存儲: {keymemory_id}")
                    return {
                        "status": "saved", 
                        "keymemory_id": keymemory_id,
                        "data": saved_data
                    }
                else:
                    print("❌ KeyMemory 存儲失敗 - 無回傳記錄")
                    return {"status": "error", "error": "無法保存 KeyMemory - 無回傳記錄"}
                    
        except Exception as e:
            logger.error(f"保存 KeyMemory 錯誤: {e}")
            print(f"❌ KeyMemory 存儲異常: {e}")
            import traceback
            traceback.print_exc()
            return {"status": "error", "error": str(e)}
    
    def create_chat_session(self, chat_id: str, session_id: str = None, metadata: Dict = None) -> Dict:
        """創建或獲取聊天會話"""
        if not session_id:
            session_id = chat_id
            
        metadata_json = json.dumps(metadata) if metadata else "{}"
            
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MERGE (c:ChatSession {chat_id: $chat_id})
                ON CREATE SET 
                    c.session_id = $session_id,
                    c.created_at = datetime(),
                    c.metadata_json = $metadata_json,
                    c.updated_at = datetime()
                ON MATCH SET
                    c.updated_at = datetime()
                RETURN c
                """, {
                    'chat_id': chat_id,
                    'session_id': session_id,
                    'metadata_json': metadata_json
                })
                
                record = result.single()
                if record:
                    chat_data = convert_neo4j_types(dict(record['c']))
                    if 'metadata_json' in chat_data:
                        try:
                            chat_data['metadata'] = json.loads(chat_data['metadata_json'])
                            del chat_data['metadata_json']
                        except:
                            chat_data['metadata'] = {}
                    
                    logger.info(f"聊天會話已創建/更新: {chat_id}")
                    return {
                        'status': 'success',
                        'chat_id': chat_id,
                        'data': chat_data
                    }
                else:
                    return {'status': 'error', 'error': '無法創建聊天會話'}
                    
        except Exception as e:
            logger.error(f"創建聊天會話錯誤: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def save_message(self, chat_id: str, message_id: str, content: str, sender: str, metadata: Dict = None) -> Dict:
        """保存訊息"""
        metadata_json = json.dumps(metadata) if metadata else "{}"
            
        try:
            with self.driver.session(database=self.database) as session:
                # 檢查訊息是否已存在
                existing = session.run("""
                MATCH (m:Message {message_id: $message_id})
                RETURN m
                """, {'message_id': message_id})
                
                if existing.single():
                    return {
                        'status': 'skipped',
                        'message': '訊息已存在',
                        'message_id': message_id
                    }
                
                result = session.run("""
                MERGE (c:ChatSession {chat_id: $chat_id})
                CREATE (m:Message {
                    message_id: $message_id,
                    content: $content,
                    sender: $sender,
                    timestamp: datetime(),
                    metadata_json: $metadata_json
                })
                CREATE (c)-[:HAS_MESSAGE]->(m)
                
                WITH c, m
                OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(prev:Message)
                WHERE prev.timestamp < m.timestamp AND prev <> m
                WITH c, m, prev
                ORDER BY prev.timestamp DESC
                LIMIT 1
                FOREACH (p IN CASE WHEN prev IS NOT NULL THEN [prev] ELSE [] END |
                    CREATE (p)-[:NEXT]->(m)
                )
                
                RETURN m
                """, {
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'content': content,
                    'sender': sender,
                    'metadata_json': metadata_json
                })
                
                record = result.single()
                if record:
                    message_data = convert_neo4j_types(dict(record['m']))
                    if 'metadata_json' in message_data:
                        try:
                            message_data['metadata'] = json.loads(message_data['metadata_json'])
                            del message_data['metadata_json']
                        except:
                            message_data['metadata'] = {}
                    
                    return {
                        'status': 'saved',
                        'message_id': message_id,
                        'timestamp': message_data.get('timestamp'),
                        'data': message_data
                    }
                else:
                    return {'status': 'error', 'error': '無法保存訊息'}
                    
        except Exception as e:
            logger.error(f"保存訊息錯誤: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def save_feedback(self, feedback_data: Dict) -> Dict:
        """保存回饋"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (m:Message {message_id: $message_id})
                MERGE (f:Feedback {feedback_id: $feedback_id})
                ON CREATE SET
                    f.type = $type,
                    f.details = $details,
                    f.timestamp = datetime(),
                    f.session_id = $session_id,
                    f.chat_id = $chat_id
                CREATE (m)-[:HAS_FEEDBACK]->(f)
                RETURN f
                """, {
                    'message_id': feedback_data['message_id'],
                    'feedback_id': feedback_data['feedback_id'],
                    'type': feedback_data['type'],
                    'details': feedback_data.get('details', ''),
                    'session_id': feedback_data.get('session_id', ''),
                    'chat_id': feedback_data.get('chat_id', '')
                })
                
                record = result.single()
                if record:
                    feedback_info = convert_neo4j_types(dict(record['f']))
                    return {
                        'status': 'saved',
                        'feedback_id': feedback_data['feedback_id'],
                        'timestamp': feedback_info.get('timestamp'),
                        'data': feedback_info
                    }
                else:
                    return {'status': 'error', 'error': '無法保存回饋'}
                    
        except Exception as e:
            logger.error(f"保存回饋錯誤: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def get_message_by_id(self, message_id: str) -> Optional[Dict]:
        """根據 message_id 取得訊息內容"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (m:Message {message_id: $message_id})
                RETURN m
                """, {'message_id': message_id})
                
                record = result.single()
                if record:
                    return convert_neo4j_types(dict(record['m']))
                return None
                
        except Exception as e:
            logger.error(f"取得訊息錯誤: {e}")
            return None

    def get_message(self, message_id: str, *args, **kwargs) -> Optional[Dict]:
        """根據 message_id 取得訊息內容 (允許多餘參數相容各種呼叫情境)"""
        return self.get_message_by_id(message_id)
    
    def _check_vector_index_exists(self, session) -> bool:
        """檢查向量索引是否存在 - 改進版本"""
        try:
            # 方法1: 檢查 VECTOR 類型索引
            result = session.run("""
            SHOW INDEXES 
            WHERE name = 'key_memory_embeddings' AND type = 'VECTOR'
            """)
            indexes = list(result)
            if indexes:
                print("✅ 向量索引存在 (VECTOR類型)")
                return True
            
            # 方法2: 檢查所有包含該名稱的索引
            result = session.run("""
            SHOW INDEXES 
            WHERE name = 'key_memory_embeddings'
            """)
            indexes = list(result)
            if indexes:
                index_info = indexes[0]
                print(f"✅ 找到索引: {index_info}")
                return True
            
            # 方法3: 嘗試直接使用向量查詢來測試
            try:
                test_embedding = [0.1] * 1536
                session.run("""
                CALL db.index.vector.queryNodes('key_memory_embeddings', 1, $test_embedding)
                YIELD node, score
                RETURN count(*) as count
                """, {'test_embedding': test_embedding})
                print("✅ 向量索引可用 (通過查詢測試)")
                return True
            except:
                pass
            
            print("❌ 向量索引不存在或不可用")
            return False
            
        except Exception as e:
            print(f"⚠️ 檢查向量索引時出錯: {e}")
            return False
    
    def _vector_search_direct(self, session, query: str, top_k: int) -> List[Dict]:
        """直接向量搜尋 - 不依賴索引檢查"""
        try:
            # 計算查詢的 embedding
            query_embedding = compute_embedding(query)
            
            if not query_embedding or len(query_embedding) == 0:
                raise Exception("查詢 embedding 計算失敗")
            
            print(f"📊 查詢向量維度: {len(query_embedding)}")
            
            # 嘗試多種向量搜尋方法
            methods = [
                # 方法1: 標準向量查詢
                """
                CALL db.index.vector.queryNodes('key_memory_embeddings', $top_k, $query_embedding)
                YIELD node, score
                RETURN node.content as content, 
                       node.feedback_type as feedback_type,
                       node.metadata_json as metadata_json,
                       node.created_at as timestamp,
                       score
                ORDER BY score DESC
                """,
                
                # 方法2: 使用 cosine similarity 計算
                """
                MATCH (k:KeyMemory)
                WHERE k.embedding IS NOT NULL
                WITH k, gds.similarity.cosine(k.embedding, $query_embedding) AS score
                WHERE score > 0.7
                RETURN k.content as content,
                       k.feedback_type as feedback_type,
                       k.metadata_json as metadata_json,
                       k.created_at as timestamp,
                       score
                ORDER BY score DESC
                LIMIT $top_k
                """
            ]
            
            for i, method in enumerate(methods):
                try:
                    print(f"🔬 嘗試向量搜尋方法 {i+1}")
                    result = session.run(method, {
                        'query_embedding': query_embedding, 
                        'top_k': top_k
                    })
                    
                    memories = []
                    for record in result:
                        memory_data = convert_neo4j_types(dict(record))
                        # 解析 metadata
                        if memory_data.get('metadata_json'):
                            try:
                                memory_data['metadata'] = json.loads(memory_data['metadata_json'])
                                del memory_data['metadata_json']
                            except:
                                memory_data['metadata'] = {}
                        memories.append(memory_data)
                    
                    if memories:
                        print(f"✅ 方法 {i+1} 成功，找到 {len(memories)} 個記憶")
                        return memories
                        
                except Exception as method_error:
                    print(f"⚠️ 方法 {i+1} 失敗: {method_error}")
                    continue
            
            raise Exception("所有向量搜尋方法都失敗")
            
        except Exception as e:
            print(f"❌ 向量搜尋失敗: {e}")
            raise e
    
    def search_similar_keymemories(self, query: str, top_k: int = 5) -> List[Dict]:
        """搜尋相似的 KeyMemory - 強制使用向量搜尋版本"""
        try:
            with self.driver.session(database=self.database) as session:
                print(f"🔍 開始搜尋相似記憶: '{query}'")
                
                # 先嘗試向量搜尋
                try:
                    result = self._vector_search_direct(session, query, top_k)
                    if result:
                        print(f"✅ 向量搜尋成功，找到 {len(result)} 個結果")
                        return result
                except Exception as e:
                    print(f"⚠️ 向量搜尋失敗: {e}")
                
                # 降級到文本搜尋
                print("🔄 降級到文本搜尋...")
                return self._fallback_text_search(session, query, top_k)
                    
        except Exception as e:
            logger.error(f"搜尋 KeyMemory 錯誤: {e}")
            print(f"❌ 搜尋完全失敗: {e}")
            return []
    
    def _fallback_text_search(self, session, query: str, top_k: int) -> List[Dict]:
        """降級文本搜尋"""
        try:
            result = session.run("""
            MATCH (k:KeyMemory)
            WHERE toLower(k.content) CONTAINS toLower($query)
            RETURN k.content as content, 
                   k.feedback_type as feedback_type,
                   k.metadata_json as metadata_json,
                   k.created_at as timestamp
            ORDER BY k.created_at DESC
            LIMIT $top_k
            """, {'query': query, 'top_k': top_k})
            
            memories = []
            for record in result:
                memory_data = convert_neo4j_types(dict(record))
                if memory_data.get('metadata_json'):
                    try:
                        memory_data['metadata'] = json.loads(memory_data['metadata_json'])
                        del memory_data['metadata_json']
                    except:
                        memory_data['metadata'] = {}
                memories.append(memory_data)
            
            print(f"📝 文本搜尋找到 {len(memories)} 個記憶")
            return memories
            
        except Exception as e:
            logger.error(f"文本搜尋錯誤: {e}")
            return []
    
    def get_all_chat_sessions(self) -> List[Dict]:
        """獲取所有聊天會話"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (c:ChatSession)
                OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:Message)
                WITH c, max(m.timestamp) as last_message_at, count(m) as message_count
                RETURN c, last_message_at, message_count
                ORDER BY coalesce(last_message_at, c.created_at) DESC
                """)
                
                chats = []
                for record in result:
                    chat_data = convert_neo4j_types(dict(record['c']))
                    
                    # 解析 metadata_json
                    if 'metadata_json' in chat_data:
                        try:
                            chat_data['metadata'] = json.loads(chat_data['metadata_json'])
                            del chat_data['metadata_json']
                        except:
                            chat_data['metadata'] = {}
                    
                    # 添加統計信息
                    chat_data['message_count'] = record['message_count']
                    chat_data['last_message_at'] = convert_neo4j_types(record['last_message_at'])
                    
                    # 生成標題（如果沒有的話）
                    if 'title' not in chat_data or not chat_data['title']:
                        chat_data['title'] = f"對話 {chat_data.get('chat_id', 'unknown')[:8]}"
                    
                    chats.append(chat_data)
                
                return chats
                
        except Exception as e:
            logger.error(f"獲取所有聊天會話錯誤: {e}")
            return []
    
    def get_chat_session(self, chat_id: str) -> Optional[Dict]:
        """獲取特定聊天會話"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (c:ChatSession {chat_id: $chat_id})
                RETURN c
                """, {'chat_id': chat_id})
                
                record = result.single()
                if record:
                    chat_data = convert_neo4j_types(dict(record['c']))
                    # 解析 metadata_json
                    if 'metadata_json' in chat_data:
                        try:
                            chat_data['metadata'] = json.loads(chat_data['metadata_json'])
                            del chat_data['metadata_json']
                        except:
                            chat_data['metadata'] = {}
                    return chat_data
                return None
                
        except Exception as e:
            logger.error(f"獲取聊天會話錯誤: {e}")
            return None
    
    def get_chat_messages(self, chat_id: str) -> List[Dict]:
        """獲取聊天訊息"""
        try:
            with self.driver.session(database=self.database) as session:
                result = session.run("""
                MATCH (c:ChatSession {chat_id: $chat_id})-[:HAS_MESSAGE]->(m:Message)
                RETURN m
                ORDER BY m.timestamp ASC
                """, {'chat_id': chat_id})
                
                messages = []
                for record in result:
                    message_data = convert_neo4j_types(dict(record['m']))
                    # 解析 metadata_json
                    if 'metadata_json' in message_data:
                        try:
                            message_data['metadata'] = json.loads(message_data['metadata_json'])
                            del message_data['metadata_json']
                        except:
                            message_data['metadata'] = {}
                    messages.append(message_data)
                
                return messages
                
        except Exception as e:
            logger.error(f"獲取聊天訊息錯誤: {e}")
            return []
    
    def delete_chat_session(self, chat_id: str) -> Dict:
        """刪除聊天會話及相關數據"""
        try:
            with self.driver.session(database=self.database) as session:
                # 刪除聊天會話及其相關的訊息和回饋
                result = session.run("""
                MATCH (c:ChatSession {chat_id: $chat_id})
                OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:Message)
                OPTIONAL MATCH (m)-[:HAS_FEEDBACK]->(f:Feedback)
                
                WITH c, collect(m) as messages, collect(f) as feedbacks
                
                DETACH DELETE c
                FOREACH (m IN messages | DETACH DELETE m)
                FOREACH (f IN feedbacks | DETACH DELETE f)
                
                RETURN size(messages) as deleted_messages, 
                       size(feedbacks) as deleted_feedbacks
                """, {'chat_id': chat_id})
                
                record = result.single()
                if record:
                    return {
                        'status': 'success',
                        'deleted_chats': 1,
                        'deleted_messages': record['deleted_messages'],
                        'deleted_feedbacks': record['deleted_feedbacks']
                    }
                else:
                    return {
                        'status': 'success',
                        'deleted_chats': 0,
                        'deleted_messages': 0,
                        'deleted_feedbacks': 0
                    }
                    
        except Exception as e:
            logger.error(f"刪除聊天會話錯誤: {e}")
            return {'status': 'error', 'error': str(e)}

# 全局實例和便捷函數
_feedback_graph_instance = None

def get_feedback_graph() -> FeedbackGraph:
    """獲取 FeedbackGraph 單例實例"""
    global _feedback_graph_instance
    
    if _feedback_graph_instance is None:
        _feedback_graph_instance = FeedbackGraph()
    
    return _feedback_graph_instance

def search_similar_keymemories(query: str, top_k: int = 5) -> List[Dict]:
    """搜尋相似的關鍵記憶 - 便捷函數"""
    feedback_graph = get_feedback_graph()
    return feedback_graph.search_similar_keymemories(query, top_k)

def store_feedback_memory(feedback_data: Dict) -> Dict:
    """修正後的回饋記憶存儲函數"""
    try:
        fg = get_feedback_graph()
        message_id = feedback_data.get("message_id", f"msg_{int(feedback_data.get('timestamp', time.time()))}")
        chat_id = feedback_data.get("chat_id", "unknown")
        response = feedback_data.get("response", "")
        query = feedback_data.get("query", "")
        feedback_type = feedback_data.get("feedback_type", "positive")
        rating = feedback_data.get("rating", 0)

        print(f"[store_feedback_memory] 處理回饋: {feedback_type}")

        # 1. 確保訊息存在
        fg.save_message(
            chat_id=chat_id,
            message_id=message_id,
            content=response,
            sender="bot"
        )

        # 2. 存回饋
        result = fg.save_feedback({
            "message_id": message_id,
            "feedback_id": f"fb_{int(feedback_data.get('timestamp', time.time()))}",
            "type": feedback_type,
            "details": f"rating={rating}, query={query}",
            "chat_id": chat_id
        })

        # 3. 如果是正面回饋，存 KeyMemory
        if feedback_type.lower() in ("like", "positive") and response:
            print("[store_feedback_memory] 正在計算並保存 KeyMemory")
            try:
                embedding = compute_embedding(response)
                if embedding and len(embedding) > 0:
                    keymemory_result = fg.save_keymemory(
                        content=response,
                        embedding=embedding,
                        feedback_type=feedback_type,
                        source_message_id=message_id,
                        metadata={"query": query, "chat_id": chat_id, "rating": rating}
                    )
                    print(f"[store_feedback_memory] KeyMemory 結果: {keymemory_result.get('status')}")
                else:
                    print("[store_feedback_memory] ⚠️ embedding 計算失敗或為空")
            except Exception as e:
                logger.error(f"KeyMemory 存儲失敗: {e}")
                print(f"[store_feedback_memory] ❌ KeyMemory 異常: {e}")
        
        return result
    except Exception as e:
        logger.error(f"store_feedback_memory 失敗: {e}")
        return {"status": "error", "error": str(e)}

# 測試函數
def test_keymemory_storage():
    """測試 KeyMemory 存儲功能"""
    try:
        print("🧪 開始測試 KeyMemory 存儲...")
        fg = get_feedback_graph()
        
        # 測試存儲
        test_content = "這是一個關於健康飲食的建議：多吃蔬菜水果，少吃加工食品。"
        test_embedding = compute_embedding(test_content)
        
        result = fg.save_keymemory(
            content=test_content,
            embedding=test_embedding,
            feedback_type="positive",
            source_message_id="test_msg_123",
            metadata={"test": True, "query": "健康飲食建議"}
        )
        
        print(f"存儲結果: {result}")
        
        # 測試搜尋
        search_results = fg.search_similar_keymemories("健康飲食", top_k=3)
        print(f"搜尋結果: {len(search_results)} 條記錄")
        
        for i, memory in enumerate(search_results):
            print(f"記憶 {i+1}: {memory.get('content', '')[:50]}...")
        
        print("✅ KeyMemory 測試完成")
        
    except Exception as e:
        print(f"❌ KeyMemory 測試失敗: {e}")
        import traceback
        traceback.print_exc()

def test_feedback_graph():
    """測試 FeedbackGraph 功能"""
    try:
        fg = get_feedback_graph()
        
        # 測試創建聊天會話
        print("🧪 測試創建聊天會話...")
        test_chat_id = f"test_{int(datetime.now().timestamp())}"
        result = fg.create_chat_session(test_chat_id, metadata={'test': True})
        print(f"結果: {result}")
        
        # 測試保存訊息
        print("🧪 測試保存訊息...")
        message_result = fg.save_message(
            chat_id=test_chat_id,
            message_id=f"msg_{test_chat_id}",
            content="測試訊息",
            sender="user"
        )
        print(f"結果: {message_result}")
        
        # 測試獲取所有聊天會話
        print("🧪 測試獲取所有聊天會話...")
        all_chats = fg.get_all_chat_sessions()
        print(f"找到 {len(all_chats)} 個聊天會話")
        
        # 清理測試數據
        print("🧪 清理測試數據...")
        delete_result = fg.delete_chat_session(test_chat_id)
        print(f"刪除結果: {delete_result}")
        
        print("✅ FeedbackGraph 測試完成")
        
    except Exception as e:
        print(f"❌ FeedbackGraph 測試失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_keymemory_storage()
    test_feedback_graph()