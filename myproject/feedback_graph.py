from dotenv import load_dotenv
import os
from neo4j import GraphDatabase
from datetime import datetime
import json
import logging

# 載入環境變數
load_dotenv()

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FeedbackNeo4jManager:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI")
        self.username = os.getenv("NEO4J_USERNAME")
        self.password = os.getenv("NEO4J_PASSWORD")
        self.database = os.getenv("NEO4J_DATABASE2", "feedbacktest")

        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password),
            database=self.database
        )

        logger.info(f"FeedbackNeo4jManager 初始化完成，使用資料庫: {self.database}")
        self._init_database_structure()

    def _init_database_structure(self):
        with self.driver.session() as session:
            constraints = [
                "CREATE CONSTRAINT chat_id_unique IF NOT EXISTS FOR (c:Chat) REQUIRE c.chat_id IS UNIQUE",
                "CREATE CONSTRAINT message_id_unique IF NOT EXISTS FOR (m:Message) REQUIRE m.message_id IS UNIQUE",
                "CREATE CONSTRAINT feedback_id_unique IF NOT EXISTS FOR (f:Feedback) REQUIRE f.feedback_id IS UNIQUE",
                "CREATE CONSTRAINT user_session_unique IF NOT EXISTS FOR (u:User) REQUIRE u.session_id IS UNIQUE",
                "CREATE INDEX message_timestamp_idx IF NOT EXISTS FOR (m:Message) ON (m.timestamp)",
                "CREATE INDEX feedback_timestamp_idx IF NOT EXISTS FOR (f:Feedback) ON (f.timestamp)",
                "CREATE INDEX chat_created_at_idx IF NOT EXISTS FOR (c:Chat) ON (c.created_at)"
            ]
            for c in constraints:
                session.run(c)

    def create_chat_session(self, chat_id, session_id=None, metadata=None):
        with self.driver.session() as session:
            result = session.run("""
            MERGE (u:User {session_id: $session_id})
            ON CREATE SET u.created_at = datetime()
            
            WITH u
            OPTIONAL MATCH (u)-[:HAS_CHAT]->(existing:Chat)
            
            WITH u, existing, 
                 CASE WHEN existing IS NULL THEN true ELSE false END AS should_create
            
            FOREACH (x IN CASE WHEN should_create THEN [1] ELSE [] END |
                CREATE (c:Chat {chat_id: $chat_id})
                SET c.created_at = datetime(),
                    c.metadata = $metadata,
                    c.message_count = 0
                MERGE (u)-[:HAS_CHAT]->(c)
            )
            
            WITH u, existing
            OPTIONAL MATCH (u)-[:HAS_CHAT]->(new_chat:Chat {chat_id: $chat_id})
            
            RETURN coalesce(new_chat.chat_id, existing.chat_id) AS chat_id
            """, {
                'chat_id': chat_id,
                'session_id': session_id or chat_id,
                'metadata': json.dumps(metadata or {}, ensure_ascii=False)
            })
            return result.single()

    def save_message(self, chat_id, message_id, content, sender, metadata=None):
        with self.driver.session() as session:
            # 檢查消息是否已存在
            exists_result = session.run("""
                MATCH (m:Message {message_id: $message_id})
                RETURN count(m) > 0 AS exists
            """, {'message_id': message_id})
            
            if exists_result.single()['exists']:
                logger.warning(f"[Neo4j] 訊息已存在，跳過: {message_id}")
                return {"message_id": message_id, "timestamp": "existing"}

            # 檢查是否為第一個消息
            first_check = session.run("""
                MATCH (c:Chat {chat_id: $chat_id})
                OPTIONAL MATCH (c)-[:STARTS_WITH]->(first:Message)
                RETURN first IS NULL AS is_first
            """, {'chat_id': chat_id})
            
            is_first = first_check.single()['is_first']
            
            if is_first:
                # 創建第一個消息
                session.run("""
                    MATCH (c:Chat {chat_id: $chat_id})
                    CREATE (m:Message {
                        message_id: $message_id,
                        content: $content,
                        sender: $sender,
                        timestamp: datetime(),
                        metadata: $metadata
                    })
                    CREATE (c)-[:STARTS_WITH]->(m)
                """, {
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'content': content,
                    'sender': sender,
                    'metadata': json.dumps(metadata or {}, ensure_ascii=False)
                })
            else:
                # 添加到鏈末端
                session.run("""
                    MATCH (c:Chat {chat_id: $chat_id})-[:STARTS_WITH]->(first:Message)
                    MATCH path = (first)-[:NEXT*0..]->(last:Message)
                    WHERE NOT EXISTS((last)-[:NEXT]->())
                    CREATE (m:Message {
                        message_id: $message_id,
                        content: $content,
                        sender: $sender,
                        timestamp: datetime(),
                        metadata: $metadata
                    })
                    CREATE (last)-[:NEXT]->(m)
                """, {
                    'chat_id': chat_id,
                    'message_id': message_id,
                    'content': content,
                    'sender': sender,
                    'metadata': json.dumps(metadata or {}, ensure_ascii=False)
                })

            # 更新聊天統計
            session.run("""
                MATCH (c:Chat {chat_id: $chat_id})-[:STARTS_WITH]->(first:Message)
                MATCH path = (first)-[:NEXT*0..]->(m:Message)
                WITH c, count(m) AS messageCount
                SET c.message_count = messageCount,
                    c.last_message_at = datetime()
            """, {'chat_id': chat_id})

        return {"message_id": message_id, "timestamp": datetime.utcnow().isoformat() + "Z"}

    def save_feedback(self, feedback_data):
        with self.driver.session() as session:
            result = session.run("""
            MATCH (m:Message {message_id: $message_id})
            MATCH (c:Chat {chat_id: $chat_id})
            CREATE (f:Feedback {
                feedback_id: $feedback_id,
                type: $type,
                details: $details,
                timestamp: datetime($timestamp),
                session_id: $session_id
            })
            CREATE (m)-[:HAS_FEEDBACK]->(f)
            CREATE (c)-[:CONTAINS_FEEDBACK]->(f)
            SET m.has_feedback = true,
                m.feedback_type = $type,
                m.feedback_timestamp = datetime($timestamp)
            RETURN f.feedback_id as feedback_id, f.timestamp as timestamp
            """, feedback_data)
            record = result.single()

        if feedback_data['type'] == "like":
            self.mark_key_memory(feedback_data['message_id'], feedback_data['type'], feedback_data['details'])
        elif feedback_data['type'] == "dislike":
            self.mark_failed_response(feedback_data['message_id'], feedback_data['details'])

        return record

    def mark_key_memory(self, message_id, feedback_type, details):
        with self.driver.session() as session:
            session.run("""
            MATCH (m:Message {message_id: $message_id})
            MERGE (k:KeyMemory {message_id: $message_id})
            SET k.content = m.content,
                k.created_at = datetime(),
                k.feedback_type = $feedback_type,
                k.details = $details
            MERGE (m)-[:KEY_MEMORY]->(k)
            """, {
                'message_id': message_id,
                'feedback_type': feedback_type,
                'details': details
            })

    def mark_failed_response(self, message_id, reason):
        with self.driver.session() as session:
            session.run("""
            MATCH (m:Message {message_id: $message_id})
            MERGE (f:FailureFlag {message_id: $message_id})
            SET f.reason = $reason,
                f.created_at = datetime()
            MERGE (m)-[:NEEDS_IMPROVEMENT]->(f)
            """, {
                'message_id': message_id,
                'reason': reason
            })

    def get_conversation_with_feedback(self, chat_id):
        """獲取完整對話鏈"""
        with self.driver.session() as session:
            result = session.run("""
            MATCH (c:Chat {chat_id: $chat_id})-[:STARTS_WITH]->(first:Message)
            MATCH path = (first)-[:NEXT*0..]->(m:Message)
            WITH m, length(path) as order_num
            ORDER BY order_num
            OPTIONAL MATCH (m)-[:HAS_FEEDBACK]->(f:Feedback)
            RETURN 
                m.message_id as message_id,
                m.content as content,
                m.sender as sender,
                m.timestamp as timestamp,
                m.metadata as metadata,
                collect({
                    feedback_id: f.feedback_id,
                    type: f.type,
                    details: f.details,
                    timestamp: f.timestamp
                }) as feedbacks
            """, {'chat_id': chat_id})
            
            conversation = []
            for record in result:
                metadata_raw = record['metadata']
                metadata = json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
                conversation.append({
                    'message_id': record['message_id'],
                    'content': record['content'],
                    'sender': record['sender'],
                    'timestamp': record['timestamp'],
                    'metadata': metadata,
                    'feedbacks': [f for f in record['feedbacks'] if f['feedback_id'] is not None]
                })
            return conversation

    def clean_duplicate_messages(self, chat_id):
        """清理重複的消息節點"""
        with self.driver.session() as session:
            # 找出重複的消息並只保留一個
            result = session.run("""
            MATCH (c:Chat {chat_id: $chat_id})
            MATCH (m:Message)
            WHERE (c)-[:STARTS_WITH]->(m) OR (c)-[:CONTAINS]->(m) OR 
                  EXISTS((:Message)-[:NEXT]->(m)) OR EXISTS((m)-[:NEXT]->(:Message))
            WITH m.message_id as msg_id, collect(m) as duplicates
            WHERE size(duplicates) > 1
            UNWIND duplicates[1..] as duplicate
            DETACH DELETE duplicate
            RETURN count(*) as deleted_count
            """, {'chat_id': chat_id})
            
            deleted = result.single()['deleted_count'] if result.single() else 0
            if deleted > 0:
                logger.info(f"清理了 {deleted} 個重複消息節點")
            
            # 重建正確的鏈結構
            self.rebuild_message_chain(chat_id)
            return deleted

    def rebuild_message_chain(self, chat_id):
        """重建消息鏈結構"""
        with self.driver.session() as session:
            # 移除所有舊的關係
            session.run("""
            MATCH (c:Chat {chat_id: $chat_id})
            OPTIONAL MATCH (c)-[r:STARTS_WITH|CONTAINS]->()
            DELETE r
            """, {'chat_id': chat_id})
            
            session.run("""
            MATCH (m:Message)-[r:NEXT]->()
            WHERE EXISTS((:Chat {chat_id: $chat_id})) // 確保是相關的消息
            DELETE r
            """, {'chat_id': chat_id})
            
            # 按時間戳獲取所有相關消息
            messages_result = session.run("""
            MATCH (m:Message)
            WHERE m.message_id CONTAINS $chat_id OR 
                  EXISTS((:Chat {chat_id: $chat_id})-[:CONTAINS]->(m)) OR
                  EXISTS((:Chat {chat_id: $chat_id})-[:STARTS_WITH]->(m))
            RETURN m.message_id as message_id
            ORDER BY m.timestamp ASC, m.message_id ASC
            """, {'chat_id': chat_id})
            
            message_ids = [record['message_id'] for record in messages_result]
            
            if not message_ids:
                logger.info(f"沒有找到 Chat {chat_id} 的相關消息")
                return
            
            # 創建 STARTS_WITH 關係
            session.run("""
            MATCH (c:Chat {chat_id: $chat_id})
            MATCH (first:Message {message_id: $first_id})
            CREATE (c)-[:STARTS_WITH]->(first)
            """, {'chat_id': chat_id, 'first_id': message_ids[0]})
            
            # 創建 NEXT 關係鏈
            for i in range(len(message_ids) - 1):
                session.run("""
                MATCH (m1:Message {message_id: $msg1_id})
                MATCH (m2:Message {message_id: $msg2_id})
                CREATE (m1)-[:NEXT]->(m2)
                """, {
                    'msg1_id': message_ids[i],
                    'msg2_id': message_ids[i + 1]
                })
            
            logger.info(f"重建了 Chat {chat_id} 的消息鏈，共 {len(message_ids)} 個消息")

    def get_feedback_statistics(self, chat_id=None, time_range_hours=24):
        with self.driver.session() as session:
            base_query = """
            MATCH (f:Feedback)
            WHERE f.timestamp >= datetime() - duration({hours: $hours})
            """
            if chat_id:
                base_query += " AND EXISTS((c:Chat {chat_id: $chat_id})-[:CONTAINS_FEEDBACK]->(f))"
            query = base_query + """
            RETURN 
                f.type as feedback_type,
                count(f) as count,
                collect(f.feedback_id)[0..5] as recent_feedback_ids
            ORDER BY count DESC
            """
            params = {'hours': time_range_hours}
            if chat_id:
                params['chat_id'] = chat_id
            result = session.run(query, params)
            stats = {}
            for record in result:
                stats[record['feedback_type']] = {
                    'count': record['count'],
                    'recent_ids': record['recent_feedback_ids']
                }
            return stats

    def close(self):
        if self.driver:
            self.driver.close()

feedback_graph = FeedbackNeo4jManager()

def get_feedback_graph():
    return feedback_graph