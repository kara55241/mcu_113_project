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
    """處理回饋資料的 Neo4j 管理器"""

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
            constraints_and_indexes = [
                "CREATE CONSTRAINT chat_id_unique IF NOT EXISTS FOR (c:Chat) REQUIRE c.chat_id IS UNIQUE",
                "CREATE CONSTRAINT message_id_unique IF NOT EXISTS FOR (m:Message) REQUIRE m.message_id IS UNIQUE",
                "CREATE CONSTRAINT feedback_id_unique IF NOT EXISTS FOR (f:Feedback) REQUIRE f.feedback_id IS UNIQUE",
                "CREATE CONSTRAINT user_session_unique IF NOT EXISTS FOR (u:User) REQUIRE u.session_id IS UNIQUE",
                "CREATE INDEX message_timestamp_idx IF NOT EXISTS FOR (m:Message) ON (m.timestamp)",
                "CREATE INDEX feedback_timestamp_idx IF NOT EXISTS FOR (f:Feedback) ON (f.timestamp)",
                "CREATE INDEX chat_created_at_idx IF NOT EXISTS FOR (c:Chat) ON (c.created_at)"
            ]
            for constraint in constraints_and_indexes:
                try:
                    session.run(constraint)
                    logger.debug(f"執行成功: {constraint}")
                except Exception as e:
                    logger.warning(f"執行約束/索引時出錯: {e}")

    def create_chat_session(self, chat_id, session_id=None, metadata=None):
        with self.driver.session() as session:
            result = session.run("""
            MERGE (u:User {session_id: $session_id})
            ON CREATE SET u.created_at = datetime()

            MERGE (c:Chat {chat_id: $chat_id})
            ON CREATE SET 
                c.created_at = datetime(),
                c.metadata = $metadata,
                c.message_count = 0

            MERGE (u)-[:HAS_CHAT]->(c)

            RETURN c.chat_id as chat_id, c.created_at as created_at
            """, {
                'chat_id': chat_id,
                'session_id': session_id or chat_id,
                'metadata': json.dumps(metadata or {}, ensure_ascii=False)
            })
            return result.single()

    def save_message(self, chat_id, message_id, content, sender, metadata=None):
        with self.driver.session() as session:
            session.run("""
                MATCH (c:Chat {chat_id: $chat_id})
                CREATE (m:Message {
                    message_id: $message_id,
                    content: $content,
                    sender: $sender,
                    timestamp: datetime(),
                    metadata: $metadata
                })
                CREATE (c)-[:CONTAINS]->(m)
            """, {
                'chat_id': chat_id,
                'message_id': message_id,
                'content': content,
                'sender': sender,
                'metadata': json.dumps(metadata or {}, ensure_ascii=False)
            })

            session.run("""
                MATCH (c:Chat {chat_id: $chat_id})
                SET c.message_count = coalesce(c.message_count, 0) + 1,
                    c.last_message_at = datetime()
            """, {'chat_id': chat_id})

        self._link_last_two_messages(chat_id)

        return {"message_id": message_id, "timestamp": datetime.utcnow().isoformat() + "Z"}

    def _link_last_two_messages(self, chat_id):
        with self.driver.session() as session:
            session.run("""
            MATCH (c:Chat {chat_id: $chat_id})-[:CONTAINS]->(m:Message)
            WITH m ORDER BY m.timestamp DESC
            WITH collect(m)[0..2] AS lastTwo
            WHERE size(lastTwo) = 2
            WITH lastTwo[1] AS prev, lastTwo[0] AS curr
            MERGE (prev)-[:NEXT]->(curr)
            """, {'chat_id': chat_id})

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

    def get_conversation_with_feedback(self, chat_id):
        with self.driver.session() as session:
            result = session.run("""
            MATCH (c:Chat {chat_id: $chat_id})-[:CONTAINS]->(m:Message)
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
            ORDER BY m.timestamp ASC
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

    def close(self):
        if self.driver:
            self.driver.close()

feedback_graph = FeedbackNeo4jManager()

def get_feedback_graph():
    return feedback_graph
