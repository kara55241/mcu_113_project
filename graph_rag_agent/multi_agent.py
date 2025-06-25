from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langchain_core.tools import tool
from .research import graph_rag
from .fact_check import search_fact_checks
from .cofacts_check import search_cofacts
from .word_similarity import find_most_similar_cofacts_article
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import MessagesState
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from .llm import llm_GPT, llm_gemini
from .SearchTool import SearchTools
import logging
from typing import Literal
import sys

if sys.platform == "win32":
    import os
    os.system("chcp 65001 >nul")

# Setup logging for detailed agent activity tracing
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Supervisor")
memory = MemorySaver()

graphrag_logger = logging.getLogger("GraphRAG_Agent")
factcheck_logger = logging.getLogger("FactCheck_Agent")

class AgentState(MessagesState):
    FactChecked: bool = False

@tool("graphrag_tool")
def graphrag_tool(query: str) -> str:
    """Use GraphRAG to answer the user's medical question."""
    graphrag_logger.info(f"[TOOL] 啟用圖譜問答工具，問題: {query}")
    result = graph_rag(input=query)
    if not result.strip():
        fallback = (
            "目前找不到具體資料，但根據常見情況，這可能與以下因素有關："
            "腸胃不適、壓力、食習不規則等。"
            "建議：補充水份、清淡食習、適當休息。"
            "若症狀悪化或持續，請儘速尋治。"
        )
        graphrag_logger.warning("[TOOL] 無資料回傳，提供 fallback 建議")
        return fallback
    return result

@tool("google_fact_check_tool")
def google_fact_check_tool(query: str, state: AgentState) -> str:
    """Check factual claims using Google FactCheck API."""
    factcheck_logger.info(f"[TOOL] 啟用事實查核工具，查詢: {query}")
    fact = search_fact_checks(query)
    result = ""
    if fact:
        if 'claims' in fact:
            result += f"找到 {len(fact['claims'])} 筆審查結果:\n"
            for claim in fact['claims']:
                result += f"- 聲明: {claim.get('text')}\n"
                if 'claimReview' in claim and claim['claimReview']:
                    for review in claim['claimReview']:
                        result += f"  審查單位: {review.get('publisher', {}).get('name')}\n"
                        result += f"  審查結果: {review.get('textualRating')}\n"
                        result += f"  來源連結: {review.get('url')}\n"
                result += "-" * 20 + "\n"
            state["FactChecked"] = True
        else:
            result += "查無相關審查結果\n"
    return result

@tool("cofacts_tool")
def cofacts_tool(query: str, state: AgentState) -> str:
    """Use Cofacts to find similar rumor reports and replies."""
    factcheck_logger.info(f"[TOOL] 啟用共議查核工具，查詢: {query}")
    node, score = find_most_similar_cofacts_article(query)
    if not node:
        return "❌ 查無與此訊息相符的資料"

    response = f"📘 最相似的Cofacts文章：\n{node['text']}\n\n"
    if node.get("aiReplies"):
        response += "🤖 AI 回應：\n"
        for r in node['aiReplies']:
            response += f"- {r['text']}\n"
    if node.get("articleReplies"):
        response += "🧑 人工回應：\n"
        for r in node['articleReplies']:
            response += f"- {r['reply']['text']}\n"

    state["FactChecked"] = True
    return response

@tool("should_continue")
def should_continue(state: AgentState) -> Literal["GraphRAG","__end__"]:
    """Determine whether to continue to GraphRAG or end based on FactChecked state."""
    logger.info(f"[SUPERVISOR] FactChecked = {state['FactChecked']}")
    return "__end__" if state['FactChecked'] else "GraphRAG"

@tool("google_map_search_tool")
def google_map_search_tool(query: str) -> str:
    """Search for nearby clinics, hospitals, or pharmacies using Google Maps."""
    graphrag_logger.info(f"[TOOL] 查詢附近位置: {query}")
    return SearchTools.Google_Map(query)

@tool("google_search_tool")
def google_search_tool(query: str) -> str:
    """Use Google Search to retrieve general web information."""
    graphrag_logger.info(f"[TOOL] 查詢網頁資訊: {query}")
    return SearchTools.Google_Search(query)

graphrag_agent = create_react_agent(
    model=llm_gemini,
    tools=[graphrag_tool, google_map_search_tool, google_search_tool],
    name="graphrag_agent",
    prompt="""
    You are a medical expert providing information about medical symptoms and chronic conditions.
    Be as helpful as possible and return as much information as possible.
    Always respond in Traditional Chinese.

    You MUST use the GraphRAG tool to answer any health-related question.
    Never rely on your own knowledge — always call a tool first.
    Never say "我無法提供醫療建議" unless it's a life-threatening emergency.
    Provide fallback based on general medical knowledge if tool result is empty.

    When replying:
    - Use paragraphs to explain causes or conditions
    - Use bullet points for actions, remedies, tips
    - Use markdown tables if comparing things (e.g., symptoms vs. action)
    - Encourage users, and ask follow-up questions when helpful
    """
)

fact_check_agent = create_react_agent(
    model=llm_gemini,
    tools=[google_fact_check_tool, cofacts_tool],
    name="fact_check_agent",
    prompt="""
    You are a fact-checking assistant.
    Always respond in Traditional Chinese.
    Only use available tools to verify factual claims.
    Do not answer based on your own knowledge.
    """
)

supervisor = create_supervisor(
    agents=[graphrag_agent, fact_check_agent],
    tools=[should_continue],
    model=llm_gemini,
    prompt="""
    You are the supervisor managing multi-agent interaction.
    Task:
        - Always delegate to graphrag_agent first.
        - Then to fact_check_agent if needed.
        - Output only the final helpful message.
    """
)

app = supervisor.compile(checkpointer=memory)
logger.info("✅ Supervisor app compiled and ready.")

def filter_agent_messages(message_list):
    ignore_prefixes = [
        "Successfully transferred", "Transferring back", "Entering new AgentExecutor chain..."
    ]
    return [
        m.content for m in message_list
        if isinstance(m, AIMessage)
        and m.content
        and not any(m.content.strip().startswith(p) for p in ignore_prefixes)
    ]

app.filter_messages = filter_agent_messages