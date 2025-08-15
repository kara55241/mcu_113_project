# memory_store.py - 統一的記憶管理器，對齊 LangGraph 設計

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass
from enum import Enum

from langchain_core.messages import BaseMessage
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langgraph.store import InMemoryStore
from langgraph.store.base import Item

logger = logging.getLogger(__name__)

class MemoryType(Enum):
    """記憶類型枚舉"""
    SEMANTIC = "semantic"      # 語意記憶（事實、偏好）
    EPISODIC = "episodic"      # 情節記憶（重要對話）
    PROCEDURAL = "procedural"  # 程序記憶（系統指令）

@dataclass
class Memory:
    """統一的記憶資料結構"""
    id: str
    type: MemoryType
    content: str
    metadata: Dict[str, Any]
    timestamp: str
    embedding: Optional[List[float]] = None

class UnifiedMemoryStore:
    """統一的記憶存儲管理器"""
    
    def __init__(self, embeddings: Optional[Embeddings] = None):
        """初始化記憶存儲"""
        self.embeddings = embeddings or OpenAIEmbeddings()
        
        # 初始化 LangGraph Memory Store
        self.store = InMemoryStore(
            index={
                "embed": self._embed_content,
                "dims": 1536  # OpenAI embedding 維度
            }
        )
        
        logger.info("統一記憶管理器初始化完成")
    
    def _embed_content(self, items: List[Item]) -> List[List[float]]:
        """為內容生成嵌入向量"""
        texts = []
        for item in items:
            # 從 item.value 中提取文本內容
            if isinstance(item.value, dict):
                text = item.value.get("content", "")
            else:
                text = str(item.value)
            texts.append(text)
        
        return self.embeddings.embed_documents(texts)
    
    def save_memory(
        self,
        user_id: str,
        memory_type: MemoryType,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """保存記憶到存儲"""
        memory_id = f"{memory_type.value}_{datetime.now().timestamp()}"
        
        memory_data = {
            "id": memory_id,
            "type": memory_type.value,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        
        # 使用使用者 ID 作為命名空間
        namespace = (user_id,)
        
        # 保存到 Memory Store
        self.store.put(namespace, memory_id, memory_data)
        
        logger.info(f"記憶已保存: {memory_id} (類型: {memory_type.value})")
        return memory_id
    
    def search_memories(
        self,
        user_id: str,
        query: str,
        top_k: int = 5,
        memory_types: Optional[List[MemoryType]] = None
    ) -> List[Memory]:
        """搜尋相關記憶"""
        namespace = (user_id,)
        
        # 執行向量搜尋
        results = self.store.search(namespace, query=query, top_k=top_k * 2)
        
        # 過濾和轉換結果
        memories = []
        for item in results:
            memory_data = item.value
            
            # 類型過濾
            if memory_types:
                if memory_data.get("type") not in [t.value for t in memory_types]:
                    continue
            
            # 轉換為 Memory 物件
            memory = Memory(
                id=memory_data.get("id"),
                type=MemoryType(memory_data.get("type")),
                content=memory_data.get("content"),
                metadata=memory_data.get("metadata", {}),
                timestamp=memory_data.get("timestamp")
            )
            memories.append(memory)
            
            if len(memories) >= top_k:
                break
        
        return memories
    
    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """獲取使用者檔案（語意記憶）"""
        memories = self.search_memories(
            user_id,
            query="user profile preferences facts",
            top_k=10,
            memory_types=[MemoryType.SEMANTIC]
        )
        
        profile = {
            "facts": [],
            "preferences": [],
            "medical_history": []
        }
        
        for memory in memories:
            metadata = memory.metadata
            category = metadata.get("category", "facts")
            
            if category in profile:
                profile[category].append(memory.content)
        
        return profile
    
    def save_conversation_summary(
        self,
        user_id: str,
        conversation_summary: str,
        key_points: List[str]
    ) -> str:
        """保存對話摘要（情節記憶）"""
        return self.save_memory(
            user_id=user_id,
            memory_type=MemoryType.EPISODIC,
            content=conversation_summary,
            metadata={
                "key_points": key_points,
                "conversation_date": datetime.now().isoformat()
            }
        )
    
    def update_system_instructions(
        self,
        user_id: str,
        new_instructions: str,
        reason: str
    ) -> str:
        """更新系統指令（程序記憶）"""
        # 保存新的系統指令，覆蓋舊的
        return self.save_memory(
            user_id=user_id,
            memory_type=MemoryType.PROCEDURAL,
            content=new_instructions,
            metadata={
                "update_reason": reason,
                "version": datetime.now().timestamp()
            }
        )
    
    def prepare_context(
        self,
        user_id: str,
        current_query: str,
        include_profile: bool = True
    ) -> str:
        """準備包含記憶的上下文"""
        context_parts = []
        
        # 搜尋相關記憶
        relevant_memories = self.search_memories(user_id, current_query, top_k=3)
        
        if include_profile:
            # 加入使用者檔案
            profile = self.get_user_profile(user_id)
            if profile["facts"]:
                context_parts.append("使用者資訊：")
                context_parts.extend(f"- {fact}" for fact in profile["facts"])
            
            if profile["preferences"]:
                context_parts.append("\n使用者偏好：")
                context_parts.extend(f"- {pref}" for pref in profile["preferences"])
        
        # 加入相關記憶
        if relevant_memories:
            context_parts.append("\n相關記憶：")
            for memory in relevant_memories:
                if memory.type == MemoryType.EPISODIC:
                    context_parts.append(f"- 過往對話: {memory.content}")
                elif memory.type == MemoryType.SEMANTIC:
                    context_parts.append(f"- 已知事實: {memory.content}")
        
        return "\n".join(context_parts)

# 工具函數：從現有 feedback_graph 遷移資料
def migrate_from_feedback_graph(feedback_graph, memory_store: UnifiedMemoryStore):
    """從現有的 feedback_graph 遷移資料到統一記憶存儲"""
    try:
        with feedback_graph.driver.session(database=feedback_graph.database) as session:
            # 遷移 KeyMemory 資料
            result = session.run("""
                MATCH (k:KeyMemory)
                RETURN k
            """)
            
            for record in result:
                keymemory = dict(record["k"])
                
                # 解析 metadata
                metadata = {}
                if keymemory.get("metadata_json"):
                    try:
                        metadata = json.loads(keymemory["metadata_json"])
                    except:
                        pass
                
                # 保存為語意記憶
                memory_store.save_memory(
                    user_id=metadata.get("chat_id", "default"),
                    memory_type=MemoryType.SEMANTIC,
                    content=keymemory.get("content", ""),
                    metadata={
                        "source": "keymemory",
                        "original_id": keymemory.get("keymemory_id"),
                        **metadata
                    }
                )
            
            logger.info("KeyMemory 資料遷移完成")
            
    except Exception as e:
        logger.error(f"資料遷移失敗: {e}")

# 整合到現有系統的輔助函數
def create_memory_enhanced_state(memory_store: UnifiedMemoryStore):
    """建立包含記憶功能的 LangGraph State"""
    from typing import TypedDict, Annotated
    from langchain_core.messages import BaseMessage
    from langgraph.graph.message import add_messages
    
    class MemoryEnhancedState(TypedDict):
        messages: Annotated[List[BaseMessage], add_messages]
        user_id: str
        relevant_memories: List[Memory]
        user_profile: Dict[str, Any]
    
    return MemoryEnhancedState

# 單例模式
_memory_store_instance: Optional[UnifiedMemoryStore] = None

def get_memory_store() -> UnifiedMemoryStore:
    """獲取記憶存儲單例"""
    global _memory_store_instance
    if _memory_store_instance is None:
        _memory_store_instance = UnifiedMemoryStore()
    return _memory_store_instance