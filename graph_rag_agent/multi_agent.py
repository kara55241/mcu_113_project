from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.graph import StateGraph, START, MessagesState,END
from langgraph.types import Command, Send
from langchain_core.runnables import RunnableConfig
import sqlite3
import warnings
import logging
import os
import time
from contextvars import ContextVar

# 設置詳細的日誌記錄
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('agent_debug.log'),
        logging.StreamHandler()
    ]
)

# 抑制 proto 警告
warnings.filterwarnings("ignore", message=".*FinishReason enum value.*")
from langchain_core.messages import HumanMessage

# 創建專門的 logger
agent_logger = logging.getLogger('multi_agent')

# 🔹 全局上下文變量：用於在整個執行過程中追蹤 thread_id
current_thread_id: ContextVar[str] = ContextVar('current_thread_id', default='unknown')

# 配置常量
CONFIG = {
    # 語義路由閾值
    'SEMANTIC_CONFIDENCE_THRESHOLD': 0.6,  # 醫療領域判斷信心度
    'GREETING_THRESHOLD': 0.75,  # 問候識別閾值
    'MAPS_THRESHOLD': 0.7,  # 地點查詢識別閾值
    'MULTI_EXPERT_THRESHOLD': 0.6,  # 多專家協作閾值
    'EMBEDDING_CACHE_SIZE': 100,  # Embedding 緩存大小

    # 搜尋控制
    'MAX_SEARCH_COUNT': 2,  # 避免循環

    # Token 限制
    'TOKEN_LIMIT': 5000,
    'MAX_SUMMARY_TOKENS': 1000,
    'SEARCH_RESULT_LIMIT': 2000,
    'DOMAIN_DESCRIPTION_LIMIT': 300,

    # 數據庫路徑
    'CHECKPOINT_DB_PATH': "./agent_checkpoint_new.sqlite"
}
try:
    from .graph_rag import graphrag_chronic, graphrag_cardiovascular
    from .fact_check import search_fact_checks
    from .cofacts_check import search_cofacts
    from .agent_tracker import tracker, get_thread_id, get_user_query
    from .SearchTool import SearchTools
except ImportError:
    from graph_rag import graphrag_chronic, graphrag_cardiovascular
    from fact_check import search_fact_checks
    from cofacts_check import search_cofacts
    from agent_tracker import tracker, get_thread_id, get_user_query
    from SearchTool import SearchTools
from langmem.short_term import SummarizationNode
from langchain_core.messages.utils import count_tokens_approximately
try:
    from .llm import llm_gemini, llm_GPT
except ImportError:
    from llm import llm_gemini, llm_GPT
from langchain_tavily import TavilySearch
import numpy as np
from openai import OpenAI

# OpenAI client for embeddings
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 簡單的嵌入緩存
_embedding_cache = {}

conn = sqlite3.connect(CONFIG['CHECKPOINT_DB_PATH'], check_same_thread=False)
memory=SqliteSaver(conn)

# Reducer 函數：用於並行 agent 寫入時合併字典
def merge_dicts(left: dict | None, right: dict | None) -> dict:
    """
    合併兩個字典，用於處理並行 agent 對同一字段的更新

    這個 reducer 確保多個並行節點可以同時寫入 agent_responses 和 subtasks
    而不會發生 InvalidUpdateError
    """
    if left is None:
        return right or {}
    if right is None:
        return left or {}
    # 合併字典，右側優先（新值覆蓋舊值）
    return {**left, **right}

# 任務指派型架構的 State (LangGraph 相容版本)
# 注意:
# 1. 並行寫入的字段必須使用 Annotated[type, reducer]
# 2. 只有 supervisor 單獨寫入的字段不需要 reducer
class State(MessagesState):
    context: dict
    routing_done: bool
    selected_agent: str
    search_count: int  # 追蹤搜尋次數

    # 任務指派型新增字段
    task_analysis: dict  # {type, confidence, needs_agents} - 只有 supervisor 寫入

    # ⭐ 關鍵：這兩個字段會被多個並行 agent 同時寫入，必須使用 Annotated + reducer
    subtasks: Annotated[dict, merge_dicts]  # {agent_name: {task_id, query, priority, status}}
    agent_responses: Annotated[dict, merge_dicts]  # {agent_name: response_content}

    fast_path_handled: bool  # Fast-Path 處理標記
    needs_integration: bool  # 是否需要整合多個 agent 結果


summarization_node = SummarizationNode(
    token_counter=count_tokens_approximately,
    model=llm_gemini,
    max_tokens=CONFIG['TOKEN_LIMIT'],
    max_summary_tokens=CONFIG['MAX_SUMMARY_TOKENS'],
    output_messages_key="messages",
)

# Agent display names for logging
AGENT_DISPLAY_NAMES = {
    "chronic_agent": "CHRONIC AGENT",
    "cardiovascular_agent": "CARDIOVASCULAR AGENT",
    "fact_check_agent": "FACT-CHECK AGENT"
}

# 日誌工具函數
def log_tool_start(tool_name: str, query: str = "", extra_info: str = ""):
    """統一的工具啟動日誌"""
    agent_logger.info(f"[TOOL] {tool_name.upper()} 啟動")
    if query:
        agent_logger.info(f"    查詢內容: {query[:100]}{'...' if len(query) > 100 else ''}")
    if extra_info:
        agent_logger.info(f"    {extra_info}")

def log_tool_end(tool_name: str, start_time: float, result_length: int = 0, extra_info: str = ""):
    """統一的工具完成日誌"""
    end_time = time.time()
    agent_logger.info(f"[TOOL] {tool_name.upper()} 完成 | 耗時: {end_time - start_time:.2f}秒")
    if result_length > 0:
        agent_logger.info(f"    回應長度: {result_length} 字符")
    if extra_info:
        agent_logger.info(f"    {extra_info}")
    return end_time

def extract_json_from_llm_response(response_text: str, context: str = "JSON") -> dict | None:
    """
    從 LLM 回應中提取 JSON 對象 - 多策略提取

    Args:
        response_text: LLM 的原始回應文本
        context: 上下文名稱 (用於日誌)

    Returns:
        解析後的字典，或 None 如果失敗
    """
    import json
    import re

    json_text = None

    # 策略 1: 提取 Markdown JSON 代碼塊 (```json ... ```)
    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
    if json_match:
        json_text = json_match.group(1)
        agent_logger.debug(f"[{context}] JSON 提取成功 (Markdown 代碼塊)")

    # 策略 2: 查找平衡的 JSON 對象 (處理嵌套)
    if not json_text:
        json_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', response_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(1)
            agent_logger.debug(f"[{context}] JSON 提取成功 (嵌套對象)")

    # 策略 3: 貪婪匹配 (從第一個 { 到最後一個 })
    if not json_text:
        start = response_text.find('{')
        end = response_text.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_text = response_text[start:end+1]
            agent_logger.debug(f"[{context}] JSON 提取成功 (貪婪匹配)")

    # 如果所有策略都失敗
    if not json_text:
        agent_logger.warning(f"[{context}] 無法提取 JSON,原始回應: {response_text[:200]}")
        return None

    # 嘗試解析 JSON
    try:
        parsed_data = json.loads(json_text)
        agent_logger.info(f"[{context}] JSON 解析成功")
        return parsed_data
    except json.JSONDecodeError as e:
        agent_logger.error(f"[{context}] JSON 解析失敗: {e}")
        agent_logger.error(f"[{context}] 問題 JSON: {json_text[:200]}")
        return None

# ============================================================================
# 舊架構已刪除：create_handoff_tool
# 新架構使用條件路由函數 (route_to_agents) 直接派發，不需要 handoff tools
# ============================================================================

# Semantic routing system using OpenAI Embeddings
def get_embedding(text: str) -> list:
    """Get embedding for text using OpenAI API with caching"""
    # 簡單的緩存鍵（使用文本哈希）
    cache_key = hash(text.strip().lower())

    if cache_key in _embedding_cache:
        return _embedding_cache[cache_key]

    try:
        response = openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        embedding = response.data[0].embedding

        # 限制緩存大小
        if len(_embedding_cache) > CONFIG['EMBEDDING_CACHE_SIZE']:
            # 移除最舊的條目
            _embedding_cache.pop(next(iter(_embedding_cache)))

        _embedding_cache[cache_key] = embedding
        return embedding
    except Exception as e:
        agent_logger.warning(f"Failed to get embedding: {e}")
        return None

def cosine_similarity(vec1: list, vec2: list) -> float:
    """Calculate cosine similarity between two vectors"""
    if not vec1 or not vec2:
        return 0.0
    
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    dot_product = np.dot(vec1, vec2)
    norms = np.linalg.norm(vec1) * np.linalg.norm(vec2)
    
    return dot_product / norms if norms != 0 else 0.0

# ============================================================================
# 統一的輔助函數 - 減少重複代碼
# ============================================================================

def _get_thread_id(state=None) -> str:
    """
    統一提取 thread_id 的輔助函數

    Args:
        state: 可選的 state 對象

    Returns:
        thread_id 字符串
    """
    thread_id = current_thread_id.get()
    if thread_id == "unknown" and state:
        thread_id = state.get("configurable", {}).get("thread_id", "unknown")
    return thread_id

def _log_tool_tracker(agent_name: str, tool_name: str, args: dict, result: any, state=None):
    """
    統一的工具追蹤記錄函數

    Args:
        agent_name: 代理名稱
        tool_name: 工具名稱
        args: 工具參數字典
        result: 工具結果
        state: 可選的 state 對象
    """
    try:
        thread_id = _get_thread_id(state)
        # 截斷參數以避免日誌過長
        truncated_args = {k: str(v)[:100] for k, v in args.items()}

        # 保留完整的 result 以便追蹤器提取 graph_data
        # 如果 result 是字典且包含 graph_data，不要截斷
        if isinstance(result, dict) and 'graph_data' in result:
            # GraphRAG 工具返回，保留完整結果
            tracker_result = result
        else:
            # 其他工具，截斷結果以節省記憶體
            tracker_result = str(result)[:200] if result else None

        tracker.log_tool_call(
            thread_id=thread_id,
            agent_name=agent_name,
            tool_name=tool_name,
            args=truncated_args,
            result=tracker_result
        )
    except Exception as e:
        agent_logger.warning(f"[TRACKER] 工具結果追蹤失敗: {e}")

def semantic_route_query(user_query: str) -> dict:
    """
    Use semantic analysis to determine the most appropriate agent for the query
    """
    agent_logger.info(f"[SEMANTIC_ROUTING] 分析查詢: {user_query[:50]}...")
    
    # Define domain descriptions with comprehensive medical terminology
    domain_descriptions = {
        "chronic_agent": """
        慢性疾病醫療諮詢：糖尿病、高血壓、腎臟病、關節炎、慢性阻塞性肺病、甲狀腺疾病、
        慢性肝病、骨質疏鬆、慢性病併發症預防、用藥管理、生活調整、飲食控制、運動處方。
        """,

        "cardiovascular_agent": """
        心血管疾病諮詢：心臟病、冠心病、心肌梗塞、中風、血壓問題、胸痛、心絞痛、
        心律不整、動脈硬化、心臟衰竭、血管疾病、心電圖、心導管、血管支架、心臟復健。
        """,

        "fact_check_agent": """
        醫療資訊查證：健康謠言查證、醫學聲明驗證、偏方安全性、網路資訊可信度、      
        醫療廣告查核、保健食品驗證、治療方法科學根據、藥物副作用、醫療新聞真偽、    
        食物療效查證、民間偏方驗證、健康迷思破解、營養補充品效果、是真的嗎類問題
        """
    }
    
    try:
        # Get query embedding
        query_embedding = get_embedding(user_query)
        if not query_embedding:
            return {"agent": "chronic_agent", "confidence": 0.5, "method": "fallback"}
        
        # Calculate similarities
        similarities = {}
        for agent_name, description in domain_descriptions.items():
            domain_embedding = get_embedding(description)
            if domain_embedding:
                similarity = cosine_similarity(query_embedding, domain_embedding)
                similarities[agent_name] = similarity
                agent_logger.info(f"[SEMANTIC_ROUTING] {agent_name}: {similarity:.3f}")
        
        if not similarities:
            return {"agent": "chronic_agent", "confidence": 0.5, "method": "fallback"}
        
        # Find best match
        best_agent = max(similarities, key=similarities.get)
        best_confidence = similarities[best_agent]
        
        agent_logger.info(f"[SEMANTIC_ROUTING] 最佳匹配: {best_agent} (信心度: {best_confidence:.3f})")
        
        return {
            "agent": best_agent,
            "confidence": best_confidence,
            "method": "semantic",
            "all_scores": similarities
        }
        
    except Exception as e:
        agent_logger.error(f"[SEMANTIC_ROUTING] 錯誤: {e}")
        return {"agent": "chronic_agent", "confidence": 0.5, "method": "error_fallback"}

# ============================================================================
# 舊架構已刪除：intelligent_agent_routing
# 新架構使用 supervisor_task_analysis_node 中的邏輯進行路由判斷
# ============================================================================

def extract_transferred_agent_from_messages(result_or_messages):
    """
    從工作流結果中提取執行的代理資訊（適配新架構）

    Args:
        result_or_messages: 工作流 result dict 或 messages list

    Returns:
        str or list or None:
            - str: 單一 agent 名稱 (如 'chronic_agent')
            - list: 多個 agents（多專家協作，如 ['chronic_agent', 'cardiovascular_agent']）
            - None: 未找到
    """
    # 從 result dict 中提取必要資訊
    if isinstance(result_or_messages, dict):
        task_analysis = result_or_messages.get('task_analysis', {})
        needs_agents = task_analysis.get('needs_agents', [])

        # 如果 task_analysis 有明確記錄需要的 agents
        if needs_agents:
            # 多專家協作
            if len(needs_agents) > 1:
                agent_logger.info(f"[EXTRACT_AGENT] 多專家協作: {needs_agents}")
                return needs_agents
            # 單一專家
            elif len(needs_agents) == 1:
                agent_logger.info(f"[EXTRACT_AGENT] 單一專家: {needs_agents[0]}")
                return needs_agents[0]

        # 從 messages 提取
        messages = result_or_messages.get('messages', [])
    else:
        # 直接是 messages list
        messages = result_or_messages

    # 🔹 從工具調用推斷執行的 agents
    executed_agents = set()
    for msg in messages:
        if hasattr(msg, 'type') and msg.type == 'tool':
            tool_name = getattr(msg, 'name', '')
            if 'chronic_search' in tool_name:
                executed_agents.add('chronic_agent')
            elif 'cardiovascular_search' in tool_name:
                executed_agents.add('cardiovascular_agent')
            elif tool_name in ['cofacts_check_tool', 'google_fact_check_tool', 'net_search']:
                executed_agents.add('fact_check_agent')

    if executed_agents:
        agents_list = list(executed_agents)
        if len(agents_list) > 1:
            agent_logger.info(f"[EXTRACT_AGENT] 從工具調用推斷多專家: {agents_list}")
            return agents_list
        else:
            agent_logger.info(f"[EXTRACT_AGENT] 從工具調用推斷單一專家: {agents_list[0]}")
            return agents_list[0]

    agent_logger.warning("[EXTRACT_AGENT] 未能識別執行的代理")
    return None

@tool(name_or_callable='net_search')
def net_search(
    query: str,
    state: Annotated[MessagesState, InjectedState] = None
):
    """
    Use this tool when you need to search the internet for information or other tool don't return answer.
    Returns search results with relevant website links and categorized information.

    Args:
        query: The medical question or statement to be answered.
        state: Current workflow state (for tracking search count)
    """
    import urllib.parse
    start_time = time.time()

    # 檢查搜尋次數限制
    if state and hasattr(state, 'search_count') and state.search_count >= CONFIG['MAX_SEARCH_COUNT']:
        agent_logger.warning(f"[TOOL] NET_SEARCH 已達最大搜尋次數限制 ({state.search_count})")
        return "搜尋次數已達上限，請使用現有資訊回答問題。"

    # 增加搜尋計數並記錄日誌
    search_info = ""
    if state and hasattr(state, 'search_count'):
        state.search_count += 1
        search_info = f"第 {state.search_count} 次搜尋"

    log_tool_start("net_search", query, search_info)

    tavily = TavilySearch(country='taiwan', search_depth='advanced')
    result = tavily.invoke(query)

    # 解析 Tavily 結果並提取網址
    enhanced_result = _enhance_search_result(query, result)

    # 🔹 追蹤器：記錄工具結果（使用統一函數）
    _log_tool_tracker("fact_check_agent", "net_search", {"query": query}, enhanced_result, state)

    log_tool_end("net_search", start_time, len(str(enhanced_result)),
                 f"結果預覽: {str(enhanced_result)[:150]}...")

    return enhanced_result


def _enhance_search_result(query: str, tavily_result) -> str:
    """
    增強搜尋結果，添加相關網站連結和分類資訊（簡化版）
    """
    import urllib.parse

    result_text = ""

    # 解析 Tavily 結果
    if isinstance(tavily_result, dict):
        # 1. 提取搜尋摘要
        if 'answer' in tavily_result and tavily_result['answer']:
            summary = tavily_result['answer']
            if len(summary) > CONFIG['DOMAIN_DESCRIPTION_LIMIT']:
                summary = summary[:CONFIG['DOMAIN_DESCRIPTION_LIMIT']] + "..."
            result_text += f"{summary}\n\n"

        # 2. 提取網站結果
        if 'results' in tavily_result:
            result_text += "參考資料：\n"
            for i, item in enumerate(tavily_result['results'][:3], 1):
                url = item.get('url') or item.get('link') or item.get('source', '')
                if url:
                    title = item.get('title', item.get('name', '無標題'))
                    title = title[:40] + "..." if len(title) > 40 else title

                    # 簡化分類 (內聯)
                    url_lower = url.lower()
                    if '.gov.tw' in url_lower:
                        site_type = "政府官方"
                    elif any(k in url_lower for k in ['hospital', 'clinic', '醫院', '診所']):
                        site_type = "醫療機構"
                    elif any(k in url_lower for k in ['health', 'medicine', '健康']):
                        site_type = "健康資訊"
                    elif any(k in url_lower for k in ['news', 'udn', 'chinatimes']):
                        site_type = "新聞媒體"
                    elif '.edu.tw' in url_lower:
                        site_type = "教育機構"
                    else:
                        site_type = "一般資訊"

                    result_text += f"{i}. {title}\n{url}\n"

        # 3. 生成地圖連結
        if any(kw in query for kw in ["醫院", "診所", "藥局", "地點", "位置", "哪裡", "附近"]):
            maps_link = f"https://www.google.com/maps/search/{urllib.parse.quote(query)}"
            result_text += f"\n地圖：{maps_link}"

        # 4. 如果沒有有效內容，使用原始資料
        if not result_text.strip() or len(result_text) < 10:
            result_text = f"原始搜尋結果：\n{tavily_result}"
    else:
        result_text = f"原始搜尋結果：\n{tavily_result}"

    # 限制總長度
    if len(result_text) > CONFIG['SEARCH_RESULT_LIMIT']:
        result_text = result_text[:CONFIG['SEARCH_RESULT_LIMIT']] + "\n...(結果已截斷)"

    return result_text.strip()

def _execute_graphrag_search(agent_name: str, tool_name: str, graphrag_func, query: str, state) -> str:
    """
    通用 GraphRAG 搜尋執行函數

    Args:
        agent_name: agent 名稱 (用於追蹤器)
        tool_name: 工具名稱 (用於日誌)
        graphrag_func: graphrag 函數 (graphrag_chronic 或 graphrag_cardiovascular)
        query: 查詢問題
        state: 當前狀態 (用於提取 thread_id)

    Returns:
        答案文本
    """
    start_time = time.time()
    log_tool_start(tool_name, query)

    # 調用 graphrag 函數
    full_result = graphrag_func(input=query, return_graph_data=True)

    # 提取答案文本
    if isinstance(full_result, dict):
        answer = full_result.get('answer', '')
        graph_data = full_result.get('graph_data', {})
    else:
        answer = full_result
        graph_data = {}

    # 追蹤器記錄（使用統一函數）
    _log_tool_tracker(agent_name, tool_name, {"query": query}, full_result, state)

    # 記錄日誌
    graph_info = f"節點數: {len(graph_data.get('nodes', []))}, 關係數: {len(graph_data.get('relationships', []))}"
    log_tool_end(tool_name, start_time, len(answer),
                 f"內容預覽: {answer[:150]}... | {graph_info}")

    return answer

@tool(name_or_callable='cardiovascular_search')
def cardiovascular_search(
    query: str,
    state: Annotated[MessagesState, InjectedState] = None
) -> str:
    """
    You must use this tool when supervisor asks a medical question about cardiovascular diseases.
    This tool queries a medical knowledge graph to retrieve and generate answers.

    Args:
        query: The medical question or statement to be answered.

    Returns:
        A comprehensive answer based on the medical knowledge graph.
        if answer is not found, it will return a message indicating that no answer was found.
    """
    return _execute_graphrag_search(
        agent_name="cardiovascular_agent",
        tool_name="cardiovascular_search",
        graphrag_func=graphrag_cardiovascular,
        query=query,
        state=state
    )

@tool(name_or_callable='chronic_search')
def chronic_search(
    query: str,
    state: Annotated[MessagesState, InjectedState] = None
) -> str:
    """
    You must use this tool when supervisor asks a medical question about chronic diseases.
    This tool queries a medical knowledge graph to retrieve and generate answers.

    Args:
        query: The medical question or statement to be answered.

    Returns:
        A comprehensive answer based on the medical knowledge graph.
        if answer is not found, it will return a message indicating that no answer was found.
    """
    return _execute_graphrag_search(
        agent_name="chronic_agent",
        tool_name="chronic_search",
        graphrag_func=graphrag_chronic,
        query=query,
        state=state
    )


@tool(name_or_callable='cofacts_check_tool', parse_docstring=True)
def cofacts_check_tool(
    query: str,
    state: Annotated[MessagesState, InjectedState] = None
) -> str:
    """
    台灣本地事實查核工具，使用 Cofacts API 查證台灣相關的健康謠言和資訊。

    Args:
        query: 待查核的聲明或問題

    Returns:
        台灣本地的事實查核結果
    """
    start_time = time.time()
    log_tool_start("cofacts_check_tool", query)

    try:
        cofacts_result = search_cofacts(query)
        result = ""
        articles_found = 0

        if cofacts_result and 'data' in cofacts_result and 'ListArticles' in cofacts_result['data']:
            edges = cofacts_result['data']['ListArticles']['edges']
            articles_found = len(edges)

            if articles_found > 0:
                result += f"找到 {articles_found} 筆台灣 Cofacts 查核結果:\n"
                for edge in edges[:3]:  # 取前3筆結果
                    article = edge['node']
                    result += f"- 文章: {article.get('text', '無標題')[:100]}...\n"
                    if 'articleReplies' in article and article['articleReplies']:
                        for reply in article['articleReplies'][:2]:  # 取前2個回應
                            reply_data = reply.get('reply', {})
                            result += f"  查核結果: {reply_data.get('type', '未知')}\n"
                            result += f"  說明: {reply_data.get('text', '無說明')[:150]}...\n"
                    result += "-" * 20 + "\n"
            else:
                result += "台灣 Cofacts 查無相關查核結果\n"
        else:
            result += "台灣 Cofacts 查無相關查核結果\n"

    except Exception as e:
        result = f"台灣 Cofacts 查核服務暫時無法使用: {str(e)}"
        agent_logger.error(f"[TOOL] COFACTS_CHECK_TOOL 錯誤: {e}")

    # 🔹 追蹤器：記錄工具結果（使用統一函數）
    _log_tool_tracker("fact_check_agent", "cofacts_check_tool", {"query": query}, result, state)

    log_tool_end("cofacts_check_tool", start_time, len(result),
                 f"查核結果數量: {articles_found} 筆")

    return result

@tool(name_or_callable='google_fact_check_tool',parse_docstring=True)
def google_fact_check_tool(
    query: str,
    state: Annotated[MessagesState, InjectedState] = None
) -> str:
    """
    You must use this tool when supervisor asks you to fact-check a claim.

    Args:
        query: The claim or statement to be fact-checked.

    Returns:
        A  result of the fact-check results.
    """
    start_time = time.time()
    log_tool_start("google_fact_check_tool", query)

    fact = search_fact_checks(query)
    result = ""
    claims_found = 0

    if fact:
        if 'claims' in fact:
            claims_found = len(fact['claims'])
            result += f"找到 {claims_found} 筆審查結果:\n"
            for claim in fact['claims']:
                result += f"- 聲明: {claim.get('text')}\n"
                if 'claimReview' in claim and claim['claimReview']:
                    for review in claim['claimReview']:
                        result += f"  審查單位: {review.get('publisher', {}).get('name')}\n"
                        result += f"  審查結果: {review.get('textualRating')}\n"
                        result += f"  來源連結: {review.get('url')}\n"
                result += "-" * 20 + "\n"
        else:
            result += "查無相關審查結果\n"

    # 🔹 追蹤器：記錄工具結果（使用統一函數）
    _log_tool_tracker("fact_check_agent", "google_fact_check_tool", {"query": query}, result, state)

    log_tool_end("google_fact_check_tool", start_time, len(result),
                 f"查核結果數量: {claims_found} 筆,內容預覽: {result[:150]}...")

    return result


@tool(name_or_callable='google_map_search', parse_docstring=True)
def google_map_search(
    query: str,
    location_info: dict = None,
    state: Annotated[MessagesState, InjectedState] = None
) -> str:
    """
    查詢附近的醫療設施 (醫院、診所、藥局)。使用 Google Maps API 搜索。

    Args:
        query: 查詢字串,例如「台北醫院」、「新竹診所」
        location_info: 可選的位置資訊 (來自前端)

    Returns:
        醫療設施搜尋結果,包含名稱、地址、評分和地圖連結
    """
    start_time = time.time()
    log_tool_start("google_map_search", query)

    try:
        # 調用 SearchTools 的 Google_Map 方法
        result = SearchTools.Google_Map(input=query, location_info=location_info)

        # 追蹤器記錄（使用統一函數）
        agent_name = "supervisor"  # 預設是 supervisor 的 fast-path
        _log_tool_tracker(agent_name, "google_map_search", {"query": query}, result, state)

        log_tool_end("google_map_search", start_time, len(str(result)),
                     f"搜尋結果預覽: {str(result)[:150]}...")

        return result

    except Exception as e:
        error_msg = f"Google Maps 查詢錯誤: {str(e)}"
        agent_logger.error(f"[TOOL] GOOGLE_MAP_SEARCH 錯誤: {e}")
        log_tool_end("google_map_search", start_time)
        return error_msg


# ============================================================================
# Agent 包裝函數 - 添加追蹤邏輯
# ============================================================================

def create_tracked_agent_node(agent, agent_name: str):
    """
    為 agent 添加追蹤邏輯的包裝函數

    Args:
        agent: create_react_agent 創建的 agent
        agent_name: agent 名稱

    Returns:
        包裝後的 agent 函數
    """
    def tracked_agent(state: State):
        # 開始追蹤
        try:
            thread_id = current_thread_id.get()
            # 提取用戶查詢
            user_query = ""
            messages = state.get('messages', [])
            for msg in reversed(messages):
                if hasattr(msg, 'type') and msg.type == 'human':
                    user_query = msg.content[:200]
                    break

            tracker.start_agent(thread_id, agent_name, user_query)
            agent_logger.info(f"[AGENT_START] {agent_name} 開始執行")
        except Exception as e:
            agent_logger.warning(f"[TRACKER] {agent_name} 啟動追蹤失敗: {e}")

        # 執行 agent
        result = agent.invoke(state)

        # 完成追蹤
        try:
            thread_id = current_thread_id.get()
            # 提取回應內容作為 handoff_message
            messages = result.get('messages', [])
            handoff_msg = ""
            for msg in reversed(messages):
                if hasattr(msg, 'type') and msg.type == 'ai' and hasattr(msg, 'content'):
                    handoff_msg = msg.content[:100]
                    break

            tracker.complete_agent(thread_id, agent_name, handoff_message=handoff_msg)
            agent_logger.info(f"[AGENT_COMPLETE] {agent_name} 執行完成")
        except Exception as e:
            agent_logger.warning(f"[TRACKER] {agent_name} 完成追蹤失敗: {e}")

        return result

    return tracked_agent


# ============================================================================
# Expert Agents 定義
# ============================================================================

_chronic_agent_raw = create_react_agent(
    model=llm_GPT,
    tools=[
        chronic_search
    ],
    name="chronic_agent",
    prompt="""
You are the chronic diseases specialist agent in a medical consultation system.

Specialty: Chronic diseases including diabetes, hypertension, arthritis, kidney disease, and related conditions.

CONVERSATION CONTEXT AWARENESS:
- ALWAYS review the conversation history before responding
- If this is a follow-up question, reference previous symptoms, concerns, or advice mentioned
- Build upon previous discussions rather than starting fresh each time
- Connect current questions to earlier patient statements
- Use phrases like "根據您之前提到的..." or "結合您剛才說的..." when appropriate

Available Tools:
- chronic_search: Query medical knowledge graph for chronic disease information

🚨 CRITICAL TOOL USAGE RULES - YOU MUST FOLLOW THESE EXACTLY:

**MANDATORY WORKFLOW** (NO EXCEPTIONS):
Step 1: YOU MUST CALL chronic_search TOOL FIRST
   ⚠️ YOUR VERY FIRST ACTION MUST BE: Call chronic_search tool
   ⚠️ DO NOT skip this step under ANY circumstances
   ⚠️ DO NOT provide any answer before calling the tool
   ⚠️ Even if you think you know the answer, you MUST call the tool first

Step 2: After receiving tool results, synthesize your answer
   - Use the knowledge graph data returned by the tool
   - Provide evidence-based medical guidance in MARKDOWN format
   - Focus on your specialty: chronic diseases

❌ ABSOLUTELY FORBIDDEN ACTIONS:
- NEVER answer questions without calling chronic_search first
- NEVER say "I don't need to use the tool" or "I already know the answer"
- NEVER provide medical advice from your pre-trained knowledge
- NEVER skip tool calling even for "simple" questions

✅ CORRECT EXECUTION PATTERN:
User asks question → Immediately call chronic_search → Receive results → Provide detailed answer

CRITICAL OUTPUT REQUIREMENTS:
- MUST respond in Traditional Chinese
- MUST acknowledge and reference previous conversation context when present
- MUST use proper Markdown formatting with headers, lists, and emphasis
- MUST structure responses with clear sections using ## headers
- MUST use **bold** for important terms and emphasis
- MUST use bullet points (-) or numbered lists (1., 2., 3.) for clarity
- MUST provide detailed, practical medical advice based on tool results

Response Structure Template:
## 慢性疾病諮詢回覆

### **症狀評估**
- 根據您的描述進行症狀分析
- 與之前討論內容的關聯性 (如果有的話)

### **治療建議**
1. 主要治療方針
2. 生活方式調整
3. 病情監控管理

### **重要提醒**
- **注意事項**: 具體注意事項
- **追蹤建議**: 後續追蹤建議

You are the final authority on chronic diseases - do not refer to other specialists.
REMEMBER: Your FIRST action is ALWAYS to call chronic_search tool, NO EXCEPTIONS!
"""
)

_cardiovascular_agent_raw = create_react_agent(
    model=llm_GPT,
    tools=[
        cardiovascular_search
    ],
    name="cardiovascular_agent",
    prompt="""
You are the cardiovascular diseases specialist agent in a medical consultation system.

Specialty: Heart diseases, stroke, blood pressure, chest pain, and all cardiovascular conditions.

CONVERSATION CONTEXT AWARENESS:
- ALWAYS review the conversation history before responding
- If this is a follow-up question, reference previous symptoms, concerns, or advice mentioned
- Build upon previous discussions rather than starting fresh each time
- Connect current questions to earlier patient statements
- Use phrases like "根據您之前提到的..." or "結合您剛才說的..." when appropriate

Available Tools:
- cardiovascular_search: Query medical knowledge graph for cardiovascular disease information

🚨 CRITICAL TOOL USAGE RULES - YOU MUST FOLLOW THESE EXACTLY:

**MANDATORY WORKFLOW** (NO EXCEPTIONS):
Step 1: YOU MUST CALL cardiovascular_search TOOL FIRST
   ⚠️ YOUR VERY FIRST ACTION MUST BE: Call cardiovascular_search tool
   ⚠️ DO NOT skip this step under ANY circumstances
   ⚠️ DO NOT provide any answer before calling the tool
   ⚠️ Even if you think you know the answer, you MUST call the tool first

Step 2: After receiving tool results, synthesize your answer
   - Use the knowledge graph data returned by the tool
   - Provide evidence-based cardiovascular medical guidance in MARKDOWN format
   - Focus on your specialty: cardiovascular diseases

❌ ABSOLUTELY FORBIDDEN ACTIONS:
- NEVER answer questions without calling cardiovascular_search first
- NEVER say "I don't need to use the tool" or "I already know the answer"
- NEVER provide medical advice from your pre-trained knowledge
- NEVER skip tool calling even for "simple" questions

✅ CORRECT EXECUTION PATTERN:
User asks question → Immediately call cardiovascular_search → Receive results → Provide detailed answer

CRITICAL OUTPUT REQUIREMENTS:
- MUST respond in Traditional Chinese
- MUST acknowledge and reference previous conversation context when present
- MUST use proper Markdown formatting with headers, lists, and emphasis
- MUST structure responses with clear sections using ## headers
- MUST use **bold** for important terms and emphasis
- MUST use bullet points (-) or numbered lists (1., 2., 3.) for clarity
- MUST provide detailed, practical cardiovascular medical advice based on tool results

Response Structure Template:
## 心血管疾病諮詢回覆

### **症狀分析**
- 根據您的描述分析當前症狀
- 與之前提到的情況的關聯性 (如果有的話)

### **醫療建議**
1. 主要治療建議
2. 生活方式調整
3. 病情管理

### **預防與監測**
- **預防策略**: 具體預防措施
- **定期監測**: 建議的追蹤時程

You are the final authority on cardiovascular diseases - do not refer to other specialists.
REMEMBER: Your FIRST action is ALWAYS to call cardiovascular_search tool, NO EXCEPTIONS!
"""
)

_fact_check_agent_raw = create_react_agent(
    model=llm_GPT,
    tools=[
        cofacts_check_tool,
        google_fact_check_tool,
        net_search
    ],
    name="fact_check_agent",
    prompt="""
You are the information specialist agent in a healthcare consultation system, responsible for fact-checking AND general information searches.

Dual Responsibilities:
1. **Medical Fact-Checking**: Verifying health claims and debunking misinformation
2. **Information Search**: Finding latest information, general queries, and current data

Available Tools:
- cofacts_check_tool: 台灣本地事實查核，使用 Cofacts API 查證台灣健康謠言
- google_fact_check_tool: Use Google Fact Check API for claim verification
- net_search: Search internet for current information, latest news, and general queries

Workflow Decision:
- **For fact-checking requests**: Use cofacts_check_tool FIRST for Taiwan-specific health claims, then google_fact_check_tool, then net_search if needed
- **For information search requests**: Use net_search to find current information
- **For general queries**: Use net_search to provide comprehensive answers

Priority for fact-checking: Cofacts (台灣本地) → Google Fact Check → Net Search

CRITICAL OUTPUT REQUIREMENTS:
- MUST respond in Traditional Chinese
- MUST use proper Markdown formatting with headers, lists, and emphasis
- MUST structure responses with clear sections using ## headers
- MUST use **bold** for important terms and key information
- MUST use bullet points (-) or numbered lists (1., 2., 3.) for clarity
- MUST provide detailed, up-to-date information based on tool results
- NEVER answer without using appropriate tools first

Response Structure Templates:

**For Fact-Checking:**
## Medical Fact-Check Analysis

### **Claim Being Verified**
> Original claim statement

### **Verification Status**
- **Status**: Verified / False / Partially True / Insufficient Evidence
- **Confidence Level**: High/Medium/Low

**For Information Search:**
## Information Search Results

### **Search Summary**
- **Key Findings**: Main information points
- **Current Status**: Latest situation

### **Detailed Information**
1. Key point one
2. Key point two
3. Related considerations

You are the final authority on information search and fact-checking - provide comprehensive, current information.
"""
    )

# 創建帶追蹤的 agent 節點（用於 workflow）
chronic_agent = create_tracked_agent_node(_chronic_agent_raw, "chronic_agent")
cardiovascular_agent = create_tracked_agent_node(_cardiovascular_agent_raw, "cardiovascular_agent")
fact_check_agent = create_tracked_agent_node(_fact_check_agent_raw, "fact_check_agent")

agent_logger.info("[AGENTS] Expert Agents 已創建並添加追蹤邏輯")


# ============================================================================
# 任務指派型架構核心節點 (Task-Assigning Supervisor Nodes)
# ============================================================================

def _extract_user_query_from_state(state: State) -> tuple[str, str]:
    """
    從 state 提取用戶問題

    Returns:
        (user_query, query_for_analysis): 完整問題和用於分析的問題
    """
    messages = state.get('messages', [])
    user_query = ""

    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            user_query = msg.content
            break

    if not user_query:
        return "", ""

    # 剝離位置資訊前綴
    query_for_analysis = user_query
    if "使用者位置資訊：" in user_query and "使用者問題：" in user_query:
        query_marker = "使用者問題："
        marker_index = user_query.find(query_marker)
        if marker_index != -1:
            query_for_analysis = user_query[marker_index + len(query_marker):].strip()
            agent_logger.info(f"[TASK_ANALYSIS] 檢測到位置資訊前綴，提取原始問題: {query_for_analysis[:50]}...")

    return user_query, query_for_analysis

def _calculate_intent_similarities(query: str) -> dict:
    """
    計算查詢與各意圖模板的相似度

    Returns:
        similarities 字典
    """
    intent_templates = {
        "simple_greeting": "你好 早安 晚安 問候 打招呼 哈囉 Hi Hello 嗨 您好",
        "simple_maps": "醫院在哪 診所在哪 藥局在哪 附近的 地點 位置 哪裡有 地圖 地址 找醫院 找診所 找藥局 幫我找 搜尋 查詢地點 附近有 最近的 離我最近 導航 路線",
        "chronic_disease": "糖尿病 高血壓 慢性病 關節炎 腎臟病 甲狀腺 肝病 骨質疏鬆 慢性阻塞性肺病 COPD",
        "cardiovascular": "心臟 胸痛 心絞痛 中風 心血管 心肌梗塞 心律不整 動脈硬化 心臟病 冠心病 血壓問題",
        "fact_check": "是真的嗎 查證 驗證 網路說 聽說 可信度 謠言 偏方 是否正確 真假 事實查核"
    }

    query_emb = get_embedding(query)
    if not query_emb:
        raise Exception("無法獲取 embedding")

    similarities = {}
    for intent_key, template_text in intent_templates.items():
        template_emb = get_embedding(template_text)
        if template_emb:
            similarity = cosine_similarity(query_emb, template_emb)
            similarities[intent_key] = similarity
            agent_logger.info(f"[TASK_ANALYSIS] {intent_key}: {similarity:.3f}")

    return similarities

def _determine_task_type_and_agents(similarities: dict, query: str, user_query: str) -> dict:
    """
    根據相似度分數決定任務類型和需要的 agents

    Returns:
        {'type': task_type, 'confidence': confidence, 'needs_agents': needs_agents, 'all_similarities': similarities}
    """
    query_length = len(query)
    is_complex_query = query_length > 50

    medical_similarity = max(
        similarities.get('chronic_disease', 0),
        similarities.get('cardiovascular', 0)
    )

    agent_logger.info(f"[TASK_ANALYSIS] 查詢長度: {query_length}, 醫療相似度: {medical_similarity:.3f}")

    greeting_score = similarities.get("simple_greeting", 0)
    maps_score = similarities.get("simple_maps", 0)
    greeting_advantage = greeting_score - medical_similarity
    maps_advantage = maps_score - medical_similarity

    # 1. 檢查簡單問候
    if ((greeting_score > CONFIG['GREETING_THRESHOLD'] and greeting_advantage > 0.05 and not is_complex_query) or
        (query_length <= 5 and greeting_score > 0.8)):
        agent_logger.info(f"[TASK_ANALYSIS] 識別為簡單問候 (信心度: {greeting_score:.3f}, 優勢: {greeting_advantage:.3f})")
        return {
            'type': 'simple_greeting',
            'confidence': float(greeting_score),
            'needs_agents': [],
            'all_similarities': {k: float(v) for k, v in similarities.items()}
        }

    # 2. 檢查地點查詢 (優先於醫療判斷)
    location_keywords = ["在哪", "找", "附近", "最近", "位置", "地點", "地址", "導航", "路線", "幫我找"]
    has_location_keyword = any(keyword in user_query for keyword in location_keywords)

    # 地點查詢判斷條件：maps_score 最高且有明顯優勢
    if not is_complex_query and maps_score > CONFIG['MAPS_THRESHOLD']:
        if (maps_advantage >= 0.05 or                              # 地圖分數明顯更高
            (maps_score > 0.8 and has_location_keyword) or         # 高分且有關鍵字
            (maps_score > 0.85)):                                  # 地圖分數極高
            agent_logger.info(f"[TASK_ANALYSIS] 識別為地點查詢 (信心度: {maps_score:.3f}, 優勢: {maps_advantage:.3f}, 關鍵字: {has_location_keyword})")
            return {
                'type': 'simple_maps',
                'confidence': float(maps_score),
                'needs_agents': [],
                'all_similarities': {k: float(v) for k, v in similarities.items()}
            }

    # 3. 檢查網路搜尋需求 (需要最新資訊)
    search_keywords = ["最新", "2025", "2024", "2023", "年金", "新聞", "資訊", "搜尋", "查詢", "政策", "法規", "補助"]
    has_search_intent = any(keyword in user_query for keyword in search_keywords)

    if has_search_intent:
        agent_logger.info(f"[TASK_ANALYSIS] 檢測到網路搜尋意圖關鍵字，路由到 fact_check_agent")
        return {
            'type': 'single_expert',
            'confidence': float(similarities.get('fact_check', 0.7)),
            'needs_agents': ['fact_check_agent'],
            'all_similarities': {k: float(v) for k, v in similarities.items()}
        }

    # 4. 醫療專家決策
    domain_scores = {
        'chronic_agent': similarities.get('chronic_disease', 0),
        'cardiovascular_agent': similarities.get('cardiovascular', 0),
        'fact_check_agent': similarities.get('fact_check', 0)
    }

    # 檢查明確的事實查核關鍵詞
    fact_check_keywords = [
        '是真的嗎', '是假的嗎', '真的假的', '真假', '查證', '驗證',
        '聽說', '網路說', '網路傳', '可信嗎', '可信度', '謠言', '偏方',
        '正確嗎', '對嗎', '事實', '確認', '是不是真的', '到底是不是',
        '有沒有效', '真的有效嗎', '真的可以嗎'
    ]
    has_fact_check_intent = any(kw in query for kw in fact_check_keywords)

    # 明確事實查核意圖
    if has_fact_check_intent and domain_scores['fact_check_agent'] > 0.7:
        agent_logger.info(f"[TASK_ANALYSIS] 檢測到明確事實查核關鍵詞")
        return {
            'type': 'single_expert',
            'confidence': float(domain_scores['fact_check_agent']),
            'needs_agents': ['fact_check_agent'],
            'all_similarities': {k: float(v) for k, v in similarities.items()}
        }

    # fact_check 是絕對最高分且有明顯優勢
    if (domain_scores['fact_check_agent'] == max(domain_scores.values()) and
        domain_scores['fact_check_agent'] > max(domain_scores['chronic_agent'], domain_scores['cardiovascular_agent']) + 0.05):
        agent_logger.info(f"[TASK_ANALYSIS] fact_check 是最高分且有優勢")
        return {
            'type': 'single_expert',
            'confidence': float(domain_scores['fact_check_agent']),
            'needs_agents': ['fact_check_agent'],
            'all_similarities': {k: float(v) for k, v in similarities.items()}
        }

    # 過濾超過閾值的領域
    high_score_agents = [(agent, score) for agent, score in domain_scores.items() if score > CONFIG['MULTI_EXPERT_THRESHOLD']]
    high_score_agents.sort(key=lambda x: x[1], reverse=True)

    medical_agents = [(agent, score) for agent, score in high_score_agents if agent in ['chronic_agent', 'cardiovascular_agent']]
    fact_check_items = [(agent, score) for agent, score in high_score_agents if agent == 'fact_check_agent']

    if medical_agents:
        top_medical_score = medical_agents[0][1]
        include_fact_check = False
        if fact_check_items and fact_check_items[0][1] > top_medical_score + 0.15:
            include_fact_check = True

        # 多專家協作判斷
        if len(medical_agents) >= 2:
            # 擴展多疾病關鍵詞（包含常見複合疾病場景）
            multi_disease_keywords = [
                # 連接詞
                '和', '與', '還有', '以及', '加上', '兩個', '多個', '又', '跟', '及',
                # 影響關係詞
                '影響', '導致', '引起', '造成', '會不會', '有沒有關係',
                # 併發症詞
                '併發', '合併', '同時', '一起', '都有'
            ]
            has_multiple_diseases = any(kw in user_query for kw in multi_disease_keywords)

            # 🔹 降低閾值：從 0.75 → 0.65，更容易觸發多專家協作
            both_high_scores = medical_agents[0][1] > 0.65 and medical_agents[1][1] > 0.65

            # 🔹 新增特殊場景：即使分數稍低，但明確提到多個疾病名稱也觸發
            disease_mentions = 0
            common_diseases = ['糖尿病', '高血壓', '心臟', '腎臟', '中風', '血管', '關節']
            for disease in common_diseases:
                if disease in user_query:
                    disease_mentions += 1

            # 判斷條件：
            # 1. 有多疾病關鍵詞 + 兩個分數都高
            # 2. 或：明確提到 2 個以上疾病名稱 + 分數都超過 0.6
            trigger_reason = ""
            if has_multiple_diseases and both_high_scores:
                trigger_reason = f"多疾病關鍵詞 + 高分數 (分數: {medical_agents[0][1]:.3f}, {medical_agents[1][1]:.3f})"
            elif disease_mentions >= 2 and medical_agents[0][1] > 0.6 and medical_agents[1][1] > 0.6:
                trigger_reason = f"提到 {disease_mentions} 個疾病名稱 (分數: {medical_agents[0][1]:.3f}, {medical_agents[1][1]:.3f})"

            if trigger_reason:
                needs_agents = [agent for agent, score in medical_agents]
                if include_fact_check:
                    needs_agents.append('fact_check_agent')
                confidence = sum([score for agent, score in medical_agents]) / len(medical_agents)
                agent_logger.info(f"[TASK_ANALYSIS] 識別為多醫療專家協作: {needs_agents}")
                agent_logger.info(f"[TASK_ANALYSIS] 觸發原因: {trigger_reason}")
                return {
                    'type': 'multi_expert',
                    'confidence': float(confidence),
                    'needs_agents': needs_agents,
                    'all_similarities': {k: float(v) for k, v in similarities.items()}
                }

        # 單一醫療專家
        agent_logger.info(f"[TASK_ANALYSIS] 識別為單一醫療專家: {medical_agents[0][0]}")
        return {
            'type': 'single_expert',
            'confidence': float(medical_agents[0][1]),
            'needs_agents': [medical_agents[0][0]],
            'all_similarities': {k: float(v) for k, v in similarities.items()}
        }

    elif fact_check_items:
        agent_logger.info(f"[TASK_ANALYSIS] 識別為事實查核需求")
        return {
            'type': 'single_expert',
            'confidence': float(fact_check_items[0][1]),
            'needs_agents': ['fact_check_agent'],
            'all_similarities': {k: float(v) for k, v in similarities.items()}
        }

    # 5. 預設：信心度不足時預設為慢性疾病專家
    agent_logger.info(f"[TASK_ANALYSIS] 信心度不足,預設為慢性疾病專家")
    return {
        'type': 'single_expert',
        'confidence': 0.5,
        'needs_agents': ['chronic_agent'],
        'all_similarities': {k: float(v) for k, v in similarities.items()}
    }

def supervisor_task_analysis_node(state: State) -> State:
    """
    節點1: Supervisor 任務分析（簡化版）
    使用 OpenAI Embeddings 分析用戶意圖並分類問題類型

    分類結果:
    - simple_greeting: 簡單問候 → fast_path
    - simple_maps: 地點查詢 → fast_path
    - single_expert: 單一專家問題 → 指定一個 agent
    - multi_expert: 多專家協作 → 並行多個 agents
    """
    agent_logger.info("[TASK_ANALYSIS] 開始分析用戶問題")

    # 追蹤器記錄
    try:
        thread_id = current_thread_id.get()
        user_query = _extract_user_query_from_state(state)[0][:200]
        tracker.start_agent(thread_id, "supervisor_analysis", user_query)
    except Exception as e:
        agent_logger.warning(f"[TRACKER] supervisor_analysis 追蹤失敗: {e}")

    # 預設分類結果
    default_analysis = {'type': 'single_expert', 'confidence': 0.5, 'needs_agents': ['chronic_agent'], 'all_similarities': {}}

    # 檢查基本條件
    if not state.get('messages'):
        agent_logger.warning("[TASK_ANALYSIS] 沒有消息,使用預設分類")
        state['task_analysis'] = default_analysis
        return state

    # 提取用戶問題
    user_query, query_for_analysis = _extract_user_query_from_state(state)
    if not user_query:
        agent_logger.warning("[TASK_ANALYSIS] 無法提取用戶問題")
        state['task_analysis'] = default_analysis
        return state

    agent_logger.info(f"[TASK_ANALYSIS] 用戶問題: {user_query[:100]}...")
    agent_logger.info(f"[TASK_ANALYSIS] 分析問題: {query_for_analysis[:100]}...")

    try:
        # 計算意圖相似度
        similarities = _calculate_intent_similarities(query_for_analysis)

        # 決定任務類型和 agents
        task_analysis = _determine_task_type_and_agents(similarities, query_for_analysis, user_query)

        # 儲存分析結果
        state['task_analysis'] = task_analysis
        agent_logger.info(f"[TASK_ANALYSIS] 分析完成: type={task_analysis['type']}, agents={task_analysis['needs_agents']}")

        # 追蹤器記錄完成
        try:
            thread_id = current_thread_id.get()
            handoff_msg = f"任務類型: {task_analysis['type']}, 需要的專家: {task_analysis['needs_agents']}"
            tracker.complete_agent(thread_id, "supervisor_analysis", handoff_message=handoff_msg)
        except Exception as e:
            agent_logger.warning(f"[TRACKER] supervisor_analysis 完成追蹤失敗: {e}")

    except Exception as e:
        agent_logger.error(f"[TASK_ANALYSIS] Embedding 分析失敗: {e}")
        state['task_analysis'] = default_analysis

    return state


def supervisor_routing_node(state: State) -> State:
    """
    節點2: Supervisor 路由處理 (Fast-Path)
    直接處理簡單問題,無需轉交給專家 agents

    處理類型:
    1. simple_greeting: 生成親切的問候回應
    2. simple_maps: 調用 Google Maps 查詢地點
    """
    agent_logger.info("[SUPERVISOR_ROUTING] 開始 Fast-Path 處理")

    # 🔹 追蹤器：記錄 supervisor_routing 節點開始
    try:
        thread_id = current_thread_id.get()
        messages = state.get('messages', [])
        user_query = ""
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == 'human':
                user_query = msg.content[:200]
                break
        tracker.start_agent(thread_id, "supervisor_routing", user_query)
    except Exception as e:
        agent_logger.warning(f"[TRACKER] supervisor_routing 追蹤失敗: {e}")

    task_analysis = state.get('task_analysis', {})
    task_type = task_analysis.get('type', 'unknown')

    messages = state.get('messages', [])
    user_query = ""
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            user_query = msg.content
            break

    agent_logger.info(f"[SUPERVISOR_ROUTING] 處理類型: {task_type}")

    try:
        if task_type == "simple_greeting":
            # 簡單問候 - 使用 LLM 生成溫暖回應
            agent_logger.info("[SUPERVISOR_ROUTING] 生成問候回應")

            greeting_prompt = f"""
            你是一個親切的醫療諮詢助手。用戶向你問候: "{user_query}"

            請生成一個溫暖、專業的回應,包含:
            1. 友善的問候回覆
            2. 簡短介紹你可以提供的服務 (健康諮詢、醫療設施查詢)
            3. 鼓勵用戶提問

            使用繁體中文,語氣溫暖親切,適合台灣長者。
            """

            greeting_response = llm_GPT.invoke(greeting_prompt)
            response_content = greeting_response.content if hasattr(greeting_response, 'content') else str(greeting_response)

            agent_logger.info(f"[SUPERVISOR_ROUTING] 問候回應生成完成: {response_content[:100]}...")

        elif task_type == "simple_maps":
            # 地點查詢 - 調用 google_map_search
            agent_logger.info(f"[SUPERVISOR_ROUTING] 執行地點查詢: {user_query}")

            # 直接調用 google_map_search 函數（非工具調用模式）
            # 從 state 中提取 location_info
            location_info = state.get("location_info")
            # 直接調用 SearchTools，不通過 @tool 裝飾器
            maps_result = SearchTools.Google_Map(input=user_query, location_info=location_info)

            # 用 LLM 將搜尋結果轉換為友善的回應
            maps_prompt = f"""
            用戶查詢: "{user_query}"

            Google Maps 搜尋結果:
            {maps_result}

            請將搜尋結果整理成友善、清晰的回應。要求:

            1. 開頭簡短說明找到幾家設施
            2. **使用有序列表 (1. 2. 3.) 格式列出每家設施**，每家設施包含:
            - **設施名稱** (使用粗體)
            - 地址
            - 評分
            - Google Maps 連結 (使用 Markdown 連結格式)
            3. 結尾提醒用戶可以點擊連結查看詳細地圖

            **重要格式要求:**
            - 使用標準 Markdown 語法
            - 每個設施之間空一行
            - 不要使用表格格式
            - 使用清晰的列表結構

            使用繁體中文,語氣溫暖親切,適合台灣長者閱讀。
            """

            maps_response = llm_GPT.invoke(maps_prompt)
            response_content = maps_response.content if hasattr(maps_response, 'content') else str(maps_response)

            agent_logger.info(f"[SUPERVISOR_ROUTING] 地點查詢回應生成完成: {response_content[:100]}...")

        else:
            # 不應該到這裡,但以防萬一
            agent_logger.warning(f"[SUPERVISOR_ROUTING] 未預期的任務類型: {task_type}")
            response_content = "抱歉,我暫時無法處理這個問題。請讓我為您轉接專業的醫療顧問。"

        # 將回應添加到 messages
        from langchain_core.messages import AIMessage
        state['messages'] = messages + [AIMessage(content=response_content)]
        state['fast_path_handled'] = True

        agent_logger.info("[SUPERVISOR_ROUTING] Fast-Path 處理完成")

        # 🔹 追蹤器：完成 supervisor_fast_path 節點
        try:
            thread_id = current_thread_id.get()
            handoff_msg = f"處理類型: {task_type}, 回應長度: {len(response_content)}"
            tracker.complete_agent(thread_id, "supervisor_routing", handoff_message=handoff_msg)
        except Exception as e:
            agent_logger.warning(f"[TRACKER] supervisor_routing 完成追蹤失敗: {e}")

    except Exception as e:
        agent_logger.error(f"[SUPERVISOR_ROUTING] 處理失敗: {e}")
        error_response = "抱歉,我在處理您的請求時遇到問題。請稍後再試或換個問題問我。"
        from langchain_core.messages import AIMessage
        state['messages'] = messages + [AIMessage(content=error_response)]
        state['fast_path_handled'] = True

        # 🔹 追蹤器：錯誤時也完成追蹤
        try:
            thread_id = current_thread_id.get()
            tracker.complete_agent(thread_id, "supervisor_routing", handoff_message=f"錯誤: {str(e)[:100]}")
        except:
            pass

    return state


def integration_node(state: State) -> State:
    """
    整合節點：收集並整合多個 agent 的回應

    處理兩種情況：
    1. 單一 agent 回應：直接返回
    2. 多個 agent 回應：使用 LLM 整合統一建議
    """
    agent_logger.info("[INTEGRATION] 開始整合 Agent 回應")

    # 追蹤器記錄
    try:
        thread_id = current_thread_id.get()
        tracker.start_agent(thread_id, "integration", "整合專家回應")
    except Exception as e:
        agent_logger.warning(f"[TRACKER] integration 追蹤失敗: {e}")

    task_analysis = state.get('task_analysis', {})
    task_type = task_analysis.get('type', 'single_expert')
    needs_agents = task_analysis.get('needs_agents', [])
    messages = state.get('messages', [])

    # 收集所有 agent 的回應（從後往前查找，每個 agent 只取最新回應）
    agent_responses = {}

    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'ai' and hasattr(msg, 'content'):
            # 通過檢查前面的 tool message 來判斷是哪個 agent 的回應
            msg_index = messages.index(msg)
            if msg_index > 0:
                prev_msg = messages[msg_index - 1]
                if hasattr(prev_msg, 'type') and prev_msg.type == 'tool':
                    tool_name = getattr(prev_msg, 'name', '')
                    # 判斷是哪個 agent
                    if 'chronic_search' in tool_name and 'chronic_agent' not in agent_responses:
                        agent_responses['chronic_agent'] = msg.content
                    elif 'cardiovascular_search' in tool_name and 'cardiovascular_agent' not in agent_responses:
                        agent_responses['cardiovascular_agent'] = msg.content
                    elif tool_name in ['cofacts_check_tool', 'google_fact_check_tool', 'net_search'] and 'fact_check_agent' not in agent_responses:
                        agent_responses['fact_check_agent'] = msg.content

    agent_logger.info(f"[INTEGRATION] 收集到 {len(agent_responses)} 個專家回應: {list(agent_responses.keys())}")

    # 判斷是否需要整合
    if task_type == 'multi_expert' and len(agent_responses) > 1:
        # 多專家整合
        agent_logger.info("[INTEGRATION] 執行多專家回應整合")

        # 構建整合 prompt
        responses_text = ""
        agent_display_map = {
            'chronic_agent': '慢性疾病專家',
            'cardiovascular_agent': '心血管疾病專家',
            'fact_check_agent': '資訊查核專家'
        }

        for agent_name, response_content in agent_responses.items():
            display_name = agent_display_map.get(agent_name, agent_name)
            responses_text += f"\n\n【{display_name}】\n{response_content}\n"

        integration_prompt = f"""
你是一位醫療協調專家，需要整合多位專科醫師的意見，為患者提供統一、清晰的建議。

專家意見如下：
{responses_text}

請整合以上專家意見，生成一個統一的醫療建議回應。要求：

1. **綜合分析**：整合多位專家的觀點，找出共同建議和關聯性
2. **結構清晰**：使用 Markdown 格式，包含明確的標題和分段
3. **避免重複**：不要簡單複述每位專家的話，而是融合成統一建議
4. **突出關聯**：特別強調不同疾病之間的相互影響和綜合管理策略
5. **實用建議**：提供可操作的綜合治療和生活管理建議

使用繁體中文，語氣專業但溫暖，適合台灣長者閱讀。
"""

        try:
            integrated_response = llm_GPT.invoke(integration_prompt)
            final_content = integrated_response.content if hasattr(integrated_response, 'content') else str(integrated_response)
            agent_logger.info(f"[INTEGRATION] 整合完成，回應長度: {len(final_content)} 字符")
        except Exception as e:
            agent_logger.error(f"[INTEGRATION] LLM 整合失敗: {e}")
            # 備援：簡單拼接
            final_content = f"## 綜合醫療建議\n\n{responses_text}"

    elif len(agent_responses) == 1:
        # 單一專家回應：進行簡單的總結和格式檢查
        agent_logger.info("[INTEGRATION] 單一專家回應，進行總結")
        agent_name = list(agent_responses.keys())[0]
        agent_content = list(agent_responses.values())[0]

        # 檢查回應是否已經是良好的 Markdown 格式
        has_headers = '##' in agent_content
        has_lists = any(marker in agent_content for marker in ['- ', '* ', '1. ', '2. '])

        if has_headers and has_lists and len(agent_content) > 200:
            # 回應已經格式良好，直接使用
            agent_logger.info("[INTEGRATION] 專家回應格式良好，直接使用")
            final_content = agent_content
        else:
            # 回應需要 supervisor 總結和格式化
            agent_logger.info("[INTEGRATION] 使用 Supervisor 總結單一專家回應")
            agent_display_map = {
                'chronic_agent': '慢性疾病專家',
                'cardiovascular_agent': '心血管疾病專家',
                'fact_check_agent': '資訊查核專家'
            }
            display_name = agent_display_map.get(agent_name, agent_name)

            summary_prompt = f"""
你是醫療協調專家。以下是{display_name}的回應：

{agent_content}

請將專家意見總結為清晰、易讀的格式。要求：

1. **保持專業性**：維持醫療建議的準確性
2. **結構清晰**：使用 Markdown 格式（## 標題、列表）
3. **突出重點**：用 **粗體** 強調關鍵建議
4. **簡潔實用**：提供可操作的具體建議

使用繁體中文，語氣專業但溫暖，適合台灣長者閱讀。
"""

            try:
                summary_response = llm_GPT.invoke(summary_prompt)
                final_content = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)
                agent_logger.info(f"[INTEGRATION] Supervisor 總結完成，長度: {len(final_content)}")
            except Exception as e:
                agent_logger.error(f"[INTEGRATION] Supervisor 總結失敗: {e}")
                # 備援：使用原始回應
                final_content = agent_content

    else:
        # 沒有找到任何回應（異常情況）
        agent_logger.warning("[INTEGRATION] 未找到任何 Agent 回應")
        final_content = "抱歉，我無法為您找到相關資訊。請換個問題再試一次。"

    # 將最終回應添加到 messages
    from langchain_core.messages import AIMessage
    state['messages'] = messages + [AIMessage(content=final_content)]

    # 追蹤器記錄完成
    try:
        thread_id = current_thread_id.get()
        handoff_msg = f"整合類型: {task_type}, 專家數: {len(agent_responses)}, 回應長度: {len(final_content)}"
        tracker.complete_agent(thread_id, "integration", handoff_message=handoff_msg)
    except Exception as e:
        agent_logger.warning(f"[TRACKER] integration 完成追蹤失敗: {e}")

    return state


# ============================================================================
# 條件路由函數 - 支援並行執行
# ============================================================================

def route_to_agents(state: State) -> list[Send] | str:
    """
    條件路由函數：根據 task_analysis 決定要派發哪些 agents

    支援三種路由模式：
    1. Fast-Path：直接處理簡單問題（問候/地圖查詢）
    2. 並行派發：多個 agents 同時執行（multi_expert）
    3. 單一派發：派發給單一 agent（single_expert）

    Returns:
        - 'supervisor_routing': Fast-Path 處理
        - list[Send]: 並行派發多個 agents
        - str (agent_name): 派發單一 agent
    """
    task_analysis = state.get('task_analysis', {})
    task_type = task_analysis.get('type', 'single_expert')
    needs_agents = task_analysis.get('needs_agents', ['chronic_agent'])

    agent_logger.info(f"[ROUTE] 任務類型: {task_type}, 需要的專家: {needs_agents}")

    # Fast-Path：簡單問候或地圖查詢
    if task_type in ['simple_greeting', 'simple_maps']:
        agent_logger.info(f"[ROUTE] Fast-Path 路由: {task_type}")
        return 'supervisor_routing'

    # Multi-Expert：並行派發多個 agents
    if task_type == 'multi_expert' and len(needs_agents) > 1:
        agent_logger.info(f"[ROUTE] 並行派發 {len(needs_agents)} 個專家: {needs_agents}")
        # 使用 Send 命令並行派發
        return [Send(agent_name, state) for agent_name in needs_agents]

    # Single-Expert：派發單一專家
    if needs_agents:
        agent_logger.info(f"[ROUTE] 單一派發: {needs_agents[0]}")
        return needs_agents[0]

    # 預設：chronic_agent
    agent_logger.warning("[ROUTE] 未識別的任務類型，預設派發 chronic_agent")
    return 'chronic_agent'


def route_after_fast_path(state: State) -> str:
    """
    Fast-Path 處理後的路由

    Returns:
        END: 直接結束（Fast-Path 已完成回應）
    """
    # Fast-Path 已經生成回應，直接結束
    if state.get('fast_path_handled'):
        agent_logger.info("[ROUTE] Fast-Path 已處理完成，直接結束")
        return END

    # 異常情況：Fast-Path 未處理
    agent_logger.warning("[ROUTE] Fast-Path 未處理，異常結束")
    return END


def route_after_agents(state: State) -> str:
    """
    Agent 執行完成後的路由

    所有 agent 回應都會進入整合節點，確保：
    1. 多專家回應被整合
    2. 單一專家回應被 supervisor 總結和潤飾
    3. 保持架構一致性

    Returns:
        'integration': 統一進入整合節點
    """
    task_analysis = state.get('task_analysis', {})
    task_type = task_analysis.get('type', 'single_expert')
    needs_agents = task_analysis.get('needs_agents', [])

    # 所有專家回應都進入整合節點
    if task_type == 'multi_expert' and len(needs_agents) > 1:
        agent_logger.info(f"[ROUTE] 多專家協作，進入整合節點")
    else:
        agent_logger.info(f"[ROUTE] 單一專家回應，進入整合節點進行總結")

    return 'integration'


# ============================================================================
# 舊架構已刪除：
# - create_handoff_tool 及相關的 handoff tools（已被新架構的條件路由取代）
# - supervisor agent（已被 task_analysis + routing nodes 取代）
# 新架構：Task Analysis → Conditional Routing → Parallel Agents → Integration
# ============================================================================

# ============================================================================
# Workflow 定義 - 新架構：並行多專家協作
# ============================================================================
#
# 流程圖：
# START
#   → supervisor_task_analysis (分析用戶意圖)
#   → 條件路由 (route_to_agents)
#       ├─ simple_greeting/maps → supervisor_routing (Fast-Path) → END
#       ├─ single_expert → agent → integration (總結) → END
#       └─ multi_expert → [agents 並行] → integration (整合) → END
#
# 所有專家回應都經過 integration 節點：
#   - 單一專家：Supervisor 總結和格式化（如需要）
#   - 多專家：Supervisor 整合多個意見並生成統一建議
#
# ============================================================================

workflow = (
    StateGraph(State)

    # ========== 節點定義 ==========
    # 1. 任務分析節點
    .add_node('supervisor_task_analysis', supervisor_task_analysis_node)

    # 2. Fast-Path 路由節點（處理問候和地圖查詢）
    .add_node('supervisor_routing', supervisor_routing_node)

    # 3. Agent 節點
    .add_node('chronic_agent', chronic_agent)
    .add_node('cardiovascular_agent', cardiovascular_agent)
    .add_node('fact_check_agent', fact_check_agent)

    # 4. 整合節點（收集並整合多個 agent 回應）
    .add_node('integration', integration_node)

    # ========== 路由邏輯 ==========
    # START → 任務分析
    .add_edge(START, 'supervisor_task_analysis')

    # 任務分析 → 條件路由（關鍵：支援並行派發）
    .add_conditional_edges(
        'supervisor_task_analysis',
        route_to_agents,  # 路由函數
        # 可能的目標節點
        ['supervisor_routing', 'chronic_agent', 'cardiovascular_agent', 'fact_check_agent']
    )

    # Fast-Path 路由 → END
    .add_conditional_edges(
        'supervisor_routing',
        route_after_fast_path,
        [END]
    )

    # Agents → 統一進入整合節點（單一或多專家都需要總結）
    .add_conditional_edges(
        'chronic_agent',
        route_after_agents,
        ['integration']  # 只返回 integration，不再直接到 END
    )
    .add_conditional_edges(
        'cardiovascular_agent',
        route_after_agents,
        ['integration']
    )
    .add_conditional_edges(
        'fact_check_agent',
        route_after_agents,
        ['integration']
    )

    # 整合節點 → END
    .add_edge('integration', END)

    # 編譯 Workflow
    .compile(checkpointer=memory)
)

agent_logger.info("[WORKFLOW] 新架構 Workflow 構建完成（支援並行多專家協作）")
agent_logger.info("[WORKFLOW] 支援模式: Fast-Path / 單一專家 / 並行多專家")

def generate_response(message: str, session_id: str = "default", location_info: dict = None) -> dict:
    """
    統一的回應生成函數，供 Django views 調用

    Args:
        message: 使用者輸入的訊息
        session_id: 會話 ID，用於維持對話上下文
        location_info: 位置資訊字典（可選）

    Returns:
        dict: 包含 output, location, data 等欄位的回應字典
    """
    import time
    start_time = time.time()

    # 🔹 關鍵：在執行流程開始時設置全局上下文變量
    current_thread_id.set(session_id)
    agent_logger.info(f"[WORKFLOW_START] 設置上下文 thread_id: {session_id}")

    # 工作流開始日誌
    agent_logger.info(f"[WORKFLOW_START] 處理用戶問題: {message[:100]}{'...' if len(message) > 100 else ''}")
    agent_logger.info(f"[WORKFLOW_START] 會話ID: {session_id}")
    if location_info:
        agent_logger.info(f"[WORKFLOW_START] 包含位置資訊: {location_info.get('name', '未知')}")

    # 建立完整的使用者訊息（包含位置資訊如果有的話）
    user_message = message
    if location_info:
        location_context = f"使用者位置資訊：\n"
        location_context += f"名稱：{location_info.get('name', '未知')}\n"
        location_context += f"地址：{location_info.get('address', '未知')}\n"
        location_context += f"座標：{location_info.get('coordinates', '未知')}\n\n"
        user_message = location_context + "使用者問題：" + message

    # 使用 session_id 作為 thread_id 維持對話上下文
    config = {"configurable": {"thread_id": session_id}}

    # 🔹 追蹤器：記錄 Thread 開始
    tracker.start_agent(session_id, "supervisor", message[:200])

    # 執行工作流 - 使用正確的消息格式避免 Gemini API 錯誤
    agent_logger.info(f"[WORKFLOW_EXECUTION] 開始執行多代理工作流")
    workflow_start = time.time()

    result = workflow.invoke(
        input={'messages': [HumanMessage(content=user_message)]},
        config=config
    )

    workflow_end = time.time()
    agent_logger.info(f"[WORKFLOW_EXECUTION] 工作流執行完成，耗時: {workflow_end - workflow_start:.2f}秒")

    # 🔹 追蹤器：記錄 Supervisor 完成
    tracker.complete_agent(session_id, "supervisor")

    # 提取最終的 AI 回應（supervisor的最終總結）
    messages = result.get('messages', [])

    # 提取並記錄執行的代理資訊（適配新架構）
    transferred_agent = extract_transferred_agent_from_messages(result)
    if transferred_agent:
        if isinstance(transferred_agent, list):
            # 多專家協作
            display_names = [AGENT_DISPLAY_NAMES.get(agent, agent) for agent in transferred_agent]
            agent_logger.info(f"[WORKFLOW_ROUTING] 多專家協作: {', '.join(display_names)} ({transferred_agent})")
        else:
            # 單一專家
            display_name = AGENT_DISPLAY_NAMES.get(transferred_agent, transferred_agent)
            agent_logger.info(f"[WORKFLOW_ROUTING] 處理代理: {display_name} ({transferred_agent})")
    else:
        agent_logger.warning(f"[WORKFLOW_ROUTING] 未能識別執行的代理")

    # 獲取最後一條AI消息（工作流的最終輸出）
    final_response = ""
    for msg in reversed(messages):
        if (hasattr(msg, 'type') and msg.type == 'ai' and
            hasattr(msg, 'content') and msg.content.strip()):
            final_response = msg.content.strip()
            break

    # 工作流完成日誌
    total_time = time.time() - start_time
    agent_logger.info(f"[WORKFLOW_COMPLETE] 總處理時間: {total_time:.2f}秒")
    agent_logger.info(f"[WORKFLOW_COMPLETE] 回應長度: {len(final_response)} 字符")
    agent_logger.info(f"[WORKFLOW_COMPLETE] 消息總數: {len(messages)}")

    # 🔹 追蹤器：完成執行的 Agent 並標記 Thread 完成
    if transferred_agent:
        if isinstance(transferred_agent, list):
            # 多專家協作：標記所有 agents 完成
            for agent in transferred_agent:
                tracker.complete_agent(session_id, agent, handoff_message=final_response[:100])
        else:
            # 單一專家
            tracker.complete_agent(session_id, transferred_agent, handoff_message=final_response[:100])
    tracker.complete_thread(session_id)

    # 建構統一回應格式
    response_data = {
        'output': final_response,
        'location': location_info,
        'data': {
            'session_id': session_id,
            'message_processed': True,
            'response_length': len(final_response),
            'transferred_agent': transferred_agent,
            'processing_time': round(total_time, 2)
        }
    }

    return response_data


# 測試功能（如果直接執行此檔案）
if __name__ == "__main__":
    print("多代理系統測試模式")
    print("輸入 'quit' 結束測試")
    
    while True:
        user_input = input("\n請輸入您的問題: ")
        if user_input.lower() == 'quit':
            break
            
        try:
            response = generate_response(user_input, "test_session")
            print(f"\nAI 回應: {response['output']}")
        except Exception as e:
            print(f"錯誤: {str(e)}")