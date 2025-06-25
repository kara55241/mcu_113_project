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

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("Supervisor")
memory = MemorySaver()
graphrag_logger = logging.getLogger("GraphRAG_Agent")
factcheck_logger = logging.getLogger("FactCheck_Agent")

# Agent State
class AgentState(MessagesState):
    FactChecked: bool = False

# Tools
@tool("graphrag_tool", description="Use GraphRAG to answer the user's medical question. Fallbacks to Google Search if GraphRAG has no result.")
def graphrag_tool(query: str) -> str:
    graphrag_logger.info(f"[TOOL] 啟用圖譜問答工具，問題: {query}")
    result = graph_rag(input=query)
    if not result.strip():
        graphrag_logger.warning("[TOOL] 無資料回傳，改由 Google Search 查詢")
        return google_search_tool(query)
    return result

@tool("google_fact_check_tool", description="Use Google FactCheck API to verify the input claim.")
def google_fact_check_tool(query: str, state: AgentState) -> str:
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

@tool("cofacts_tool", description="Use Cofacts to retrieve similar rumor articles and fact-check replies.")
def cofacts_tool(query: str, state: AgentState) -> str:
    factcheck_logger.info(f"[TOOL] 啟用共議查核工具，查詢: {query}")
    node, score = find_most_similar_cofacts_article(query)
    if not node:
        return "查無與此訊息相符的資料"
    response = f"最相似的Cofacts文章：\n{node['text']}\n\n"
    if node.get("aiReplies"):
        response += "AI 回應：\n"
        for r in node['aiReplies']:
            response += f"- {r['text']}\n"
    if node.get("articleReplies"):
        response += "人工回應：\n"
        for r in node['articleReplies']:
            response += f"- {r['reply']['text']}\n"
    state["FactChecked"] = True
    return response

@tool("should_continue", description="Control whether to continue to medical agent or end.")
def should_continue(state: AgentState) -> Literal["GraphRAG", "__end__"]:
    logger.info(f"[SUPERVISOR] FactChecked = {state['FactChecked']}")
    return "__end__" if state["FactChecked"] else "GraphRAG"

@tool("google_map_search_tool", description="Search for nearby clinics or hospitals using Google Maps.")
def google_map_search_tool(query: str) -> str:
    return SearchTools.Google_Map(query)

@tool("google_search_tool", description="Search general health information from the web.")
def google_search_tool(query: str) -> str:
    return SearchTools.Google_Search(query)

# Agents
graphrag_agent = create_react_agent(
    model=llm_gemini,
    tools=[graphrag_tool, google_map_search_tool, google_search_tool],
    name="graphrag_agent",
    prompt="""
    You are a medical expert providing information about medical symptoms and chronic conditions.
    Be as helpful as possible and return as much information as possible.
    Always respond in Traditional Chinese.

    You MUST use at least one tool to answer every question.
    You MUST use the GraphRAG tool first for all health-related questions.
    If the GraphRAG tool returns no result, you MUST use Google Search to provide helpful fallback information.
    Never rely solely on your internal knowledge.
    Never say '我無法提供醫療建議' unless it's an actual emergency.

    When replying:
    - Use paragraphs to explain causes or conditions
    - Use bullet points for actions, remedies, or self-care tips
    - Use markdown tables when comparing or listing structured advice
    - Ask a relevant follow-up question to encourage continued dialogue
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
    You must always call at least one tool before replying.
    Do not answer based on your own pre-trained knowledge.
    """
)

# Supervisor
supervisor = create_supervisor(
    agents=[graphrag_agent, fact_check_agent],
    tools=[should_continue],
    model=llm_gemini,
    prompt="""
    You are the supervisor managing multi-agent interaction.
    Task:
        - Always delegate to fact_check_agent first for verification.
        - Then delegate to graphrag_agent for medical guidance.
        - Ensure every agent uses at least one tool before responding.
        - Output only the final helpful message.
    """
)

app = supervisor.compile(checkpointer=memory)

# Filter
def filter_agent_messages(message_list):
    ignore_prefixes = [
        "Successfully transferred", "Transferring back", "Entering new AgentExecutor chain..."
    ]
    fallback_flags = ["我是一個大型語言模型", "無法提供醫療建議", "請諮詢醫療專業人員"]
    return [
        m.content for m in message_list
        if isinstance(m, AIMessage)
        and m.content
        and not any(m.content.strip().startswith(p) for p in ignore_prefixes)
        and not any(b in m.content for b in fallback_flags)
    ]

app.filter_messages = filter_agent_messages
