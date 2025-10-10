from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.graph import StateGraph, START, MessagesState,END
from langgraph.types import Command
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
    'SEMANTIC_CONFIDENCE_THRESHOLD': 0.6,#信心度
    'MAX_SEARCH_COUNT': 2, #避免循環
    'TOKEN_LIMIT': 5000,
    'MAX_SUMMARY_TOKENS': 1000,
    'SEARCH_RESULT_LIMIT': 2000,
    'DOMAIN_DESCRIPTION_LIMIT': 300,
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
    from .llm import llm_gemini, llm_GPT, llm_GPT_tool_required
except ImportError:
    from llm import llm_gemini, llm_GPT, llm_GPT_tool_required
from langchain_tavily import TavilySearch
import numpy as np
from openai import OpenAI

# OpenAI client for embeddings
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 簡單的嵌入緩存
_embedding_cache = {}

conn = sqlite3.connect(CONFIG['CHECKPOINT_DB_PATH'], check_same_thread=False)
memory=SqliteSaver(conn)
class State(MessagesState):
    context: dict[str,any]
    routing_done: bool = False
    selected_agent: str = ""
    search_count: int = 0  # 追蹤搜尋次數


summarization_node = SummarizationNode(
    token_counter=count_tokens_approximately,
    model=llm_gemini,
    max_tokens=CONFIG['TOKEN_LIMIT'],
    max_summary_tokens=CONFIG['MAX_SUMMARY_TOKENS'],
    output_messages_key="messages",
)

# Agent display names for logging
AGENT_DISPLAY_NAMES = {
    "chronic_agent": "慢性疾病專家",
    "cardiovascular_agent": "心血管疾病專家",
    "fact_check_agent": "資訊搜尋專家"
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

# Handoff tool set define
def create_handoff_tool(*, agent_name: str, description: str | None = None):
    name = f"transfer_to_{agent_name}"
    description = description or f"Ask {agent_name} for the answer."

    @tool(name, description=description)
    def handoff_tool(
        state: Annotated[MessagesState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
        config: RunnableConfig = None,
    ) -> Command:
        # 詳細的轉交日誌記錄
        display_name = AGENT_DISPLAY_NAMES.get(agent_name, agent_name)

        # 從state中提取用戶問題
        user_query = ""
        if state.get("messages"):
            for msg in reversed(state["messages"]):
                if hasattr(msg, 'type') and msg.type == 'human':
                    user_query = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
                    break

        agent_logger.info(f"[SUPERVISOR_ROUTING] 用戶問題: {user_query}")
        agent_logger.info(f"[SUPERVISOR_ROUTING] 路由決策: 轉交至 {display_name} ({agent_name})")
        agent_logger.info(f"[SUPERVISOR_ROUTING] 轉交工具: {name}")

        # 🔹 追蹤器：從多個來源嘗試提取 thread_id
        try:
            thread_id = "unknown"

            # 方法 1: 從全局上下文變量獲取（最可靠）
            thread_id = current_thread_id.get()

            # 方法 2: 從 config 提取（備用）
            if thread_id == "unknown" and config and "configurable" in config:
                thread_id = config["configurable"].get("thread_id", "unknown")

            # 方法 3: 從 state 的 configurable 提取（備用）
            if thread_id == "unknown" and isinstance(state, dict):
                if "configurable" in state:
                    thread_id = state["configurable"].get("thread_id", "unknown")

            agent_logger.info(f"[TRACKER] 提取到 thread_id: {thread_id}")
            tracker.start_agent(thread_id, agent_name, user_query)
        except Exception as e:
            agent_logger.warning(f"[TRACKER] 追蹤器記錄失敗: {e}")

        tool_message = {
            "role": "tool",
            "content": f"Successfully transferred to {agent_name}",
            "name": name,
            "tool_call_id": tool_call_id,
        }
        return Command(
            goto=agent_name,
            update={**state, "messages": state["messages"] + [tool_message]},
            graph=Command.PARENT,
        )

    return handoff_tool

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
        if len(_embedding_cache) > 100:
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
        醫療資訊查證與地點查詢：健康謠言查證、醫學聲明驗證、偏方安全性、網路資訊可信度、
        醫療廣告查核、保健食品驗證、治療方法科學根據、藥物副作用、醫療新聞真偽、
        食物療效查證、民間偏方驗證、健康迷思破解、營養補充品效果、是真的嗎類問題、
        醫療設施地點查詢、醫院位置、診所地址、藥局地點、附近醫療機構、哪裡有醫院、
        地點搜尋、位置查詢、醫療設施導航、附近診所、附近藥局
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

def intelligent_agent_routing(user_query: str, state: State = None) -> str:
    """
    Semantic-based intelligent routing system with loop prevention
    """
    # Check if routing was already done to prevent loops
    if state and hasattr(state, 'routing_done') and state.routing_done:
        selected = getattr(state, 'selected_agent', 'chronic_agent')
        agent_logger.info(f"[INTELLIGENT_ROUTING] 路由已完成，避免重複: {selected}")
        return selected
    
    agent_logger.info(f"[INTELLIGENT_ROUTING] 開始語意路由分析")
    
    # Check if this is a general information query (non-medical)
    general_info_keywords = [
        '聯絡電話', '電話號碼', '聯繫方式', '地址', '營業時間', '開放時間',
        '怎麼去', '交通', '位置', '網址', '網站', '官網', '電子郵件', 'email'
    ]
    
    is_general_info = any(keyword in user_query.lower() for keyword in general_info_keywords)
    
    if is_general_info:
        agent_logger.info(f"[INTELLIGENT_ROUTING] 識別為一般資訊查詢，導向 chronic_agent 處理")
        selected = "chronic_agent"
    else:
        # Use semantic analysis for medical routing
        semantic_result = semantic_route_query(user_query)
        
        # Use semantic result with confidence threshold
        if semantic_result["confidence"] > CONFIG['SEMANTIC_CONFIDENCE_THRESHOLD']:
            agent_logger.info(f"[INTELLIGENT_ROUTING] 語意分析結果: {semantic_result['agent']} (信心度: {semantic_result['confidence']:.3f})")
            selected = semantic_result["agent"]
        else:
            # Default to chronic_agent for general health queries when confidence is low
            agent_logger.info(f"[INTELLIGENT_ROUTING] 信心度不足，使用預設路由: chronic_agent (語意信心度: {semantic_result['confidence']:.3f})")
            selected = "chronic_agent"
    
    # Mark routing as done in state (only if state exists and has these attributes)
    if state and hasattr(state, 'routing_done'):
        state.routing_done = True
        if hasattr(state, 'selected_agent'):
            state.selected_agent = selected
    
    return selected

handoff_to_chronic_agent=create_handoff_tool(agent_name='chronic_agent',description='assign task to chronic agent')
handoff_to_cardiovascular_agent=create_handoff_tool(agent_name='cardiovascular_agent',description='assign task to cardiovascular agent')
handoff_to_fact_check_agent=create_handoff_tool(agent_name='fact_check_agent',description='assign task to fact check agent')

def extract_transferred_agent_from_messages(messages):
    """
    從消息歷史中提取轉交的代理資訊，改進版本確保正確識別最終處理的代理
    """
    # 從最新的消息開始向前查找，找到最後一次轉交
    for msg in reversed(messages):
        if (hasattr(msg, 'type') and msg.type == 'tool' and
            hasattr(msg, 'content') and 'Successfully transferred to' in msg.content):
            # 提取代理名稱
            content = msg.content
            if 'chronic_agent' in content:
                return 'chronic_agent'
            elif 'cardiovascular_agent' in content:
                return 'cardiovascular_agent'
            elif 'fact_check_agent' in content:
                return 'fact_check_agent'

    # 如果沒有找到轉交消息，嘗試從工具調用推斷
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'ai' and hasattr(msg, 'tool_calls'):
            for tool_call in msg.tool_calls:
                tool_name = tool_call.get('name', '')
                if 'chronic_search' in tool_name:
                    return 'chronic_agent'
                elif 'cardiovascular_search' in tool_name:
                    return 'cardiovascular_agent'
                elif 'google_map_search' in tool_name:
                    # google_map_search 可能被 supervisor 直接調用（fast-path）
                    # 或被 fact_check_agent 調用（complex query）
                    # 這裡標記為 fact_check_agent 以保持一致性
                    return 'fact_check_agent'
                elif any(tool in tool_name for tool in ['cofacts_check_tool', 'google_fact_check_tool', 'net_search']):
                    return 'fact_check_agent'

    return None

@tool(name_or_callable='google_map_search')
def google_map_search(
    query: str,
    state: Annotated[MessagesState, InjectedState] = None
):
    """
    搜尋附近的醫院、診所、藥局等醫療設施。使用 Google Maps API 提供精確的地點資訊。

    適用場景：
    - 使用者詢問特定地點附近的醫療設施（例如：「台北醫院」、「新竹診所」）
    - 使用者詢問「哪裡有」、「附近有」等地點相關問題
    - 需要提供醫療設施的地址、評分、地圖連結

    Args:
        query: 包含地點和醫療設施類型的查詢字串
        state: 工作流狀態（可選，用於獲取 location_info）

    Returns:
        混合格式：Markdown 格式的醫療設施列表 + JSON 結構化數據
    """
    start_time = time.time()

    log_tool_start("google_map_search", query)

    try:
        # 嘗試從 state 中提取 location_info（如果使用者在前端地圖點選了位置）
        location_info = None
        if state and hasattr(state, 'context') and isinstance(state.context, dict):
            location_info = state.context.get('location_info')

        # 呼叫 SearchTools.Google_Map 工具
        result = SearchTools.Google_Map(query, location_info)

        # 🔹 追蹤器：記錄工具結果
        try:
            thread_id = current_thread_id.get()
            if thread_id == "unknown" and state:
                thread_id = state.get("configurable", {}).get("thread_id", "unknown")

            # 提取簡短結果預覽（不包含完整 JSON）
            result_preview = result.split('[HOSPITAL_DATA]')[0][:200] if '[HOSPITAL_DATA]' in result else result[:200]

            tracker.log_tool_call(
                thread_id=thread_id,
                agent_name="fact_check_agent",
                tool_name="google_map_search",
                args={"query": query[:100], "has_location_info": location_info is not None},
                result=result_preview
            )
        except Exception as e:
            agent_logger.warning(f"[TRACKER] 工具結果追蹤失敗: {e}")

        log_tool_end("google_map_search", start_time, len(result),
                     f"找到醫療設施數量: {result.count('**')}")

        return result

    except Exception as e:
        error_msg = f"❌ Google Maps 搜尋失敗：{str(e)}"
        agent_logger.error(f"[TOOL] GOOGLE_MAP_SEARCH 錯誤: {e}")
        log_tool_end("google_map_search", start_time, 0, f"錯誤: {str(e)}")
        return error_msg

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

    # 🔹 追蹤器：記錄工具結果
    try:
        # 從上下文變量或 state 提取 thread_id
        thread_id = current_thread_id.get()
        if thread_id == "unknown" and state:
            thread_id = state.get("configurable", {}).get("thread_id", "unknown")

        tracker.log_tool_call(
            thread_id=thread_id,
            agent_name="fact_check_agent",
            tool_name="net_search",
            args={"query": query[:100]},
            result=str(enhanced_result)[:200] if enhanced_result else None
        )
    except Exception as e:
        agent_logger.warning(f"[TRACKER] 工具結果追蹤失敗: {e}")

    log_tool_end("net_search", start_time, len(str(enhanced_result)),
                 f"結果預覽: {str(enhanced_result)[:150]}...")

    return enhanced_result


def _generate_maps_link(query: str) -> str:
    """生成地圖連結"""
    import urllib.parse
    location_keywords = ["醫院", "診所", "藥局", "地點", "位置", "哪裡", "附近"]
    if any(keyword in query for keyword in location_keywords):
        maps_query = urllib.parse.quote(query)
        return f"https://www.google.com/maps/search/{maps_query}"
    return None

def _extract_search_summary(tavily_result: dict) -> str:
    """提取並限制搜尋摘要長度"""
    if 'answer' in tavily_result and tavily_result['answer']:
        summary = tavily_result['answer']
        if len(summary) > CONFIG['DOMAIN_DESCRIPTION_LIMIT']:
            summary = summary[:CONFIG['DOMAIN_DESCRIPTION_LIMIT']] + "..."
        return summary
    return ""

def _extract_website_results(tavily_result: dict, query: str) -> list:
    """提取並分類網站結果"""
    websites = []
    if 'results' in tavily_result:
        for result_item in tavily_result['results'][:3]:  # 取前3個結果
            # 支援多種可能的 URL 欄位名稱
            url = None
            for url_field in ['url', 'link', 'source']:
                if url_field in result_item:
                    url = result_item[url_field]
                    break

            if url:
                # 限制標題長度
                title = result_item.get('title', result_item.get('name', '無標題'))
                if len(title) > 40:
                    title = title[:40] + "..."

                # 分類網站類型
                site_type = _categorize_website(url, query)

                websites.append({
                    "標題": title,
                    "網址": url,
                    "類型": site_type
                })
    return websites

def _enhance_search_result(query: str, tavily_result) -> str:
    """
    增強搜尋結果，添加相關網站連結和分類資訊
    """
    # 初始化結果結構
    enhanced_info = {
        "搜尋摘要": "",
        "相關網站": [],
        "地圖連結": None,
        "原始資料": tavily_result
    }

    # 生成地圖連結
    enhanced_info["地圖連結"] = _generate_maps_link(query)

    # 解析 Tavily 結果
    if isinstance(tavily_result, dict):
        enhanced_info["搜尋摘要"] = _extract_search_summary(tavily_result)
        enhanced_info["相關網站"] = _extract_website_results(tavily_result, query)

    # 格式化輸出並限制總長度
    formatted_result = _format_enhanced_result(enhanced_info)

    # 如果結果太長，進一步截斷
    if len(formatted_result) > CONFIG['SEARCH_RESULT_LIMIT']:
        formatted_result = formatted_result[:CONFIG['SEARCH_RESULT_LIMIT']] + "\n...(結果已截斷)"

    return formatted_result


def _categorize_website(url: str, query: str) -> str:
    """
    根據網址和查詢內容分類網站類型
    """
    url_lower = url.lower()
    query_lower = query.lower()

    # 政府官方網站
    if '.gov.tw' in url_lower or 'mohw.gov.tw' in url_lower:
        return "政府官方"

    # 醫療機構
    elif any(keyword in url_lower for keyword in ['hospital', 'clinic', 'medical', '醫院', '診所']):
        return "醫療機構"

    # 健康資訊網站
    elif any(keyword in url_lower for keyword in ['health', 'medicine', '健康', '醫療']):
        return "健康資訊"

    # 新聞媒體
    elif any(keyword in url_lower for keyword in ['news', 'udn', 'chinatimes', 'cna', 'tvbs']):
        return "新聞媒體"

    # 教育機構
    elif '.edu.tw' in url_lower:
        return "教育機構"

    else:
        return "一般資訊"


def _format_enhanced_result(enhanced_info: dict) -> str:
    """
    格式化增強的搜尋結果
    """
    result_text = ""

    # 添加搜尋摘要
    if enhanced_info["搜尋摘要"]:
        result_text += f"{enhanced_info['搜尋摘要']}\n\n"

    # 添加相關網站（優先顯示）
    if enhanced_info["相關網站"]:
        result_text += "參考資料：\n"
        for i, site in enumerate(enhanced_info["相關網站"], 1):
            result_text += f"{i}. {site['標題']}\n{site['網址']}\n"

    # 添加地圖連結（如果有）
    if enhanced_info["地圖連結"]:
        result_text += f"\n地圖：{enhanced_info['地圖連結']}"

    # 如果沒有摘要，回退到原始資料
    if not enhanced_info["搜尋摘要"] and enhanced_info["原始資料"]:
        result_text += f"原始搜尋結果：\n{enhanced_info['原始資料']}"

    return result_text.strip()

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
    start_time = time.time()
    log_tool_start("cardiovascular_search", query)

    # 調用 graphrag_cardiovascular，獲取包含圖譜數據的完整結果
    full_result = graphrag_cardiovascular(input=query, return_graph_data=True)

    # 提取答案文本（給 LLM 使用）
    if isinstance(full_result, dict):
        answer = full_result.get('answer', '')
        graph_data = full_result.get('graph_data', {})
    else:
        # 向後兼容：如果返回的是字符串
        answer = full_result
        graph_data = {}

    # 🔹 追蹤器：記錄完整的工具結果（包含圖譜數據）
    try:
        # 從上下文變量或 state 提取 thread_id
        thread_id = current_thread_id.get()
        if thread_id == "unknown" and state:
            thread_id = state.get("configurable", {}).get("thread_id", "unknown")

        tracker.log_tool_call(
            thread_id=thread_id,
            agent_name="cardiovascular_agent",
            tool_name="cardiovascular_search",
            args={"query": query[:100]},
            result=full_result  # 傳遞完整結果（包含 graph_data）
        )
    except Exception as e:
        agent_logger.warning(f"[TRACKER] 工具結果追蹤失敗: {e}")

    # 記錄日誌
    graph_info = f"節點數: {len(graph_data.get('nodes', []))}, 關係數: {len(graph_data.get('relationships', []))}"
    log_tool_end("cardiovascular_search", start_time, len(answer),
                 f"內容預覽: {answer[:150]}... | {graph_info}")

    return answer

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
    start_time = time.time()
    log_tool_start("chronic_search", query)

    # 調用 graphrag_chronic，獲取包含圖譜數據的完整結果
    full_result = graphrag_chronic(input=query, return_graph_data=True)

    # 提取答案文本（給 LLM 使用）
    if isinstance(full_result, dict):
        answer = full_result.get('answer', '')
        graph_data = full_result.get('graph_data', {})
    else:
        # 向後兼容：如果返回的是字符串
        answer = full_result
        graph_data = {}

    # 🔹 追蹤器：記錄完整的工具結果（包含圖譜數據）
    try:
        # 從上下文變量或 state 提取 thread_id
        thread_id = current_thread_id.get()
        if thread_id == "unknown" and state:
            thread_id = state.get("configurable", {}).get("thread_id", "unknown")

        tracker.log_tool_call(
            thread_id=thread_id,
            agent_name="chronic_agent",
            tool_name="chronic_search",
            args={"query": query[:100]},
            result=full_result  # 傳遞完整結果（包含 graph_data）
        )
    except Exception as e:
        agent_logger.warning(f"[TRACKER] 工具結果追蹤失敗: {e}")

    # 記錄日誌
    graph_info = f"節點數: {len(graph_data.get('nodes', []))}, 關係數: {len(graph_data.get('relationships', []))}"
    log_tool_end("chronic_search", start_time, len(answer),
                 f"內容預覽: {answer[:150]}... | {graph_info}")

    return answer


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

    # 🔹 追蹤器：記錄工具結果
    try:
        # 從上下文變量或 state 提取 thread_id
        thread_id = current_thread_id.get()
        if thread_id == "unknown" and state:
            thread_id = state.get("configurable", {}).get("thread_id", "unknown")

        tracker.log_tool_call(
            thread_id=thread_id,
            agent_name="fact_check_agent",
            tool_name="cofacts_check_tool",
            args={"query": query[:100]},
            result=result[:200] if result else None
        )
    except Exception as e:
        agent_logger.warning(f"[TRACKER] 工具結果追蹤失敗: {e}")

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

    # 🔹 追蹤器：記錄工具結果
    try:
        # 從上下文變量或 state 提取 thread_id
        thread_id = current_thread_id.get()
        if thread_id == "unknown" and state:
            thread_id = state.get("configurable", {}).get("thread_id", "unknown")

        tracker.log_tool_call(
            thread_id=thread_id,
            agent_name="fact_check_agent",
            tool_name="google_fact_check_tool",
            args={"query": query[:100]},
            result=result[:200] if result else None
        )
    except Exception as e:
        agent_logger.warning(f"[TRACKER] 工具結果追蹤失敗: {e}")

    log_tool_end("google_fact_check_tool", start_time, len(result),
                 f"查核結果數量: {claims_found} 筆，內容預覽: {result[:150]}...")

    return result
    


chronic_agent = create_react_agent(
    model=llm_GPT,  # 恢復使用標準版本
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

Workflow:
1. Review any previous conversation context in the message history
2. **MANDATORY FIRST STEP**: Call chronic_search tool to query the medical knowledge graph
   - You MUST call the tool before providing any answer
   - Even if you think you know the answer, ALWAYS query the knowledge graph first
   - This ensures all information is accurate and tracked
3. After receiving tool results, synthesize a comprehensive answer
4. Reference previous patient statements when relevant
5. Provide evidence-based medical guidance in MARKDOWN format
6. Focus only on your specialty area - chronic diseases

CRITICAL TOOL USAGE RULES:
- **ABSOLUTE REQUIREMENT**: MUST call chronic_search tool as your first action for EVERY new user question
- **NO EXCEPTIONS**: Do not provide any medical advice without first querying the knowledge graph
- **ONE TOOL CALL PER QUESTION**: After calling the tool once and receiving results, provide your final answer
- **DO NOT LOOP**: After providing your answer, stop - do not call tools again unless user asks a new question

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
"""
)

cardiovascular_agent = create_react_agent(
    model=llm_GPT,  # 恢復使用標準版本
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

Workflow:
1. Review any previous conversation context in the message history
2. **MANDATORY FIRST STEP**: Call cardiovascular_search tool to query the medical knowledge graph
   - You MUST call the tool before providing any answer
   - Even if you think you know the answer, ALWAYS query the knowledge graph first
   - This ensures all information is accurate and tracked
3. After receiving tool results, synthesize a comprehensive answer
4. Reference previous patient statements when relevant
5. Provide evidence-based cardiovascular guidance in MARKDOWN format
6. Focus only on your specialty area - cardiovascular diseases

CRITICAL TOOL USAGE RULES:
- **ABSOLUTE REQUIREMENT**: MUST call cardiovascular_search tool as your first action for EVERY new user question
- **NO EXCEPTIONS**: Do not provide any cardiovascular advice without first querying the knowledge graph
- **ONE TOOL CALL PER QUESTION**: After calling the tool once and receiving results, provide your final answer
- **DO NOT LOOP**: After providing your answer, stop - do not call tools again unless user asks a new question

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
"""
)

fact_check_agent = create_react_agent(
    model=llm_GPT,
    tools=[
        google_map_search,      # 新增：地點查詢工具（優先使用）
        cofacts_check_tool,
        google_fact_check_tool,
        net_search
    ],
    name="fact_check_agent",
    prompt="""
You are the information specialist agent in a healthcare consultation system, responsible for fact-checking, information searches, AND location-based queries.

Triple Responsibilities:
1. **Location-Based Queries**: Finding nearby hospitals, clinics, and pharmacies
2. **Medical Fact-Checking**: Verifying health claims and debunking misinformation
3. **Information Search**: Finding latest information, general queries, and current data

Available Tools:
- google_map_search: 搜尋附近的醫院、診所、藥局等醫療設施（使用 Google Maps API）
- cofacts_check_tool: 台灣本地事實查核，使用 Cofacts API 查證台灣健康謠言
- google_fact_check_tool: Use Google Fact Check API for claim verification
- net_search: Search internet for current information, latest news, and general queries

Workflow Decision:
- **For location queries** (包含：醫院、診所、藥局、附近、哪裡、地點): **MUST use google_map_search FIRST**
  - Examples: "台北哪裡有醫院？", "新竹附近的診所", "台中藥局"
  - This tool provides precise location data, addresses, ratings, and map links
  - DO NOT use net_search for location queries - it provides less accurate results
- **For fact-checking requests**: Use cofacts_check_tool FIRST for Taiwan-specific health claims, then google_fact_check_tool, then net_search if needed
- **For information search requests**: Use net_search to find current information
- **For general queries**: Use net_search to provide comprehensive answers

Priority for location queries: google_map_search (ALWAYS FIRST)
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

**For Location Queries (MOST IMPORTANT - Use google_map_search):**
When user asks about hospital/clinic/pharmacy locations:
1. ALWAYS use google_map_search tool first
2. The tool will return results with [HOSPITAL_DATA] JSON - keep this intact in your response
3. Present the tool results naturally in Traditional Chinese
4. Mention that users can click the Google Maps links for directions
Example response pattern:
"根據您的查詢，我為您找到以下醫療設施：
[Tool results will appear here with hospital listings]
您可以點擊上方的 Google Maps 連結查看詳細位置和路線規劃。"

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

IMPORTANT: For location-based queries, ALWAYS use google_map_search and preserve the [HOSPITAL_DATA] JSON in your response.
You are the final authority on information search and fact-checking - provide comprehensive, current information.
"""
    )
    

supervisor = create_react_agent(
    model=llm_GPT,
    tools=[
        google_map_search,              # 🚀 Fast-path: 直接處理簡單地點查詢
        handoff_to_chronic_agent,
        handoff_to_cardiovascular_agent,
        handoff_to_fact_check_agent
    ],
    pre_model_hook=summarization_node,
    name="supervisor",
    checkpointer=memory,
    prompt="""
        Role:
        You are the Supervisor Agent for a medical health consultation system with fast-path capability for simple queries.

        🚀 FAST PATH - Direct Tool Usage (Highest Priority):
        For SIMPLE location queries, DIRECTLY use google_map_search WITHOUT transferring:
        - Pattern: [地名] + [醫院/診所/藥局/附近/哪裡]
        - Examples:
          ✓ "台北哪裡有醫院？" → DIRECTLY use google_map_search
          ✓ "新竹診所" → DIRECTLY use google_map_search
          ✓ "台中附近的藥局" → DIRECTLY use google_map_search
        - This is the FASTEST way - skip agent transfer for simple location queries
        - After getting results, provide summary in Traditional Chinese

        🔀 AGENT ROUTING - Transfer to Specialists (When needed):
        - Chronic diseases (diabetes, hypertension, arthritis, etc.): MUST use handoff_to_chronic_agent
        - Cardiovascular/heart issues (heart disease, stroke, chest pain, etc.): MUST use handoff_to_cardiovascular_agent
        - Complex information queries requiring multiple tools: handoff_to_fact_check_agent
          Examples: "台北醫院評價好嗎？" (needs location + reviews)
        - Fact-checking health claims: handoff_to_fact_check_agent
        - When in doubt about medical topics: Default to chronic_agent

        Decision Logic:
        1. Read user question
        2. Check if it's a SIMPLE location query:
           - YES → DIRECTLY use google_map_search (fast path 🚀)
           - NO → Determine which specialist agent is needed
        3. If using fast path, summarize results in Traditional Chinese
        4. If transferring, wait for specialist response and provide final summary

        Critical Rules:
        - For simple location queries: USE google_map_search DIRECTLY (don't transfer)
        - For medical questions: ALWAYS transfer to specialist agent first
        - For complex queries: Transfer to appropriate agent (they have more tools)
        - Provide all responses in Traditional Chinese
"""
)


workflow=(
    StateGraph(State)
    # destinations是為了方便視覺化用的
    .add_node(supervisor,destinations=('chronic_agent','cardiovascular_agent','fact_check_agent',END))
    .add_node(chronic_agent)
    .add_node(cardiovascular_agent)
    .add_node(fact_check_agent)
    .add_edge(START,'supervisor')
    .add_edge('chronic_agent', END)
    .add_edge('cardiovascular_agent', END)
    .add_edge('fact_check_agent', END)
    .compile(checkpointer=memory)
)

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

    # 建立初始 State，包含 location_info
    initial_state = {
        'messages': [HumanMessage(content=user_message)],
        'context': {'location_info': location_info} if location_info else {}
    }

    result = workflow.invoke(
        input=initial_state,
        config=config
    )

    workflow_end = time.time()
    agent_logger.info(f"[WORKFLOW_EXECUTION] 工作流執行完成，耗時: {workflow_end - workflow_start:.2f}秒")

    # 🔹 追蹤器：記錄 Supervisor 完成
    tracker.complete_agent(session_id, "supervisor")

    # 提取最終的 AI 回應（supervisor的最終總結）
    messages = result.get('messages', [])

    # 提取並記錄轉交資訊
    transferred_agent = extract_transferred_agent_from_messages(messages)
    if transferred_agent:
        display_name = AGENT_DISPLAY_NAMES.get(transferred_agent, transferred_agent)
        agent_logger.info(f"[WORKFLOW_ROUTING] 最終處理代理: {display_name} ({transferred_agent})")
    else:
        agent_logger.warning(f"[WORKFLOW_ROUTING] 未能識別轉交的代理")

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

    # 🔹 追蹤器：完成轉交的 Agent 並標記 Thread 完成
    if transferred_agent:
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