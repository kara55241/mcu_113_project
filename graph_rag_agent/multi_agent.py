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

logger = logging.getLogger(__name__)
memory = MemorySaver()  # 不支援 window 參數，使用預設行為即可

class AgentState(MessagesState):
    FactChecked: bool = False

@tool
def graphrag_tool(query: str) -> str:
    """Use GraphRAG to answer the user's medical question."""
    logger.info(f"[GraphRAG Tool] 啟用圖譜問答工具，問題: {query}")
    return graph_rag(input=query)

@tool
def google_fact_check_tool(query: str, state: AgentState) -> str:
    """Check factual claims using Google FactCheck API."""
    logger.info(f"[FactCheck Tool] 啟用事實查核工具，查詢: {query}")
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

@tool
def cofacts_tool(query: str, state: AgentState) -> str:
    """Use Cofacts to find similar rumor reports and replies."""
    logger.info(f"[Cofacts Tool] 啟用共識查核工具，查詢: {query}")
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

@tool
def should_continue(state: AgentState) -> Literal["GraphRAG","__end__"]:
    """Decide whether to proceed. If already fact-checked, end the flow."""
    return "__end__" if state['FactChecked'] else "GraphRAG"

@tool
def google_map_search_tool(query: str) -> str:
    """Search for nearby clinics, hospitals, or pharmacies using Google Maps."""
    logger.info(f"[Google Map Tool] 查詢附近位置: {query}")
    return SearchTools.Google_Map(query)

@tool
def google_search_tool(query: str) -> str:
    """Use Google Search to retrieve general web information."""
    logger.info(f"[Google Search Tool] 查詢網頁資訊: {query}")
    return SearchTools.Google_Search(query)

graphrag_agent = create_react_agent(
    model=llm_gemini,
    tools=[graphrag_tool, google_map_search_tool, google_search_tool],
    name="graphrag_agent",
    prompt="""
    Role:
        You are a medical assistant responsible for answering user questions using medical graph and map/search tools.
    Requirements:
        - Only use the tools provided.
        - DO NOT rely on pretrained knowledge.
        - If the user's input contains address/location keywords (e.g., '附近', '哪裡'), prioritize using Google Map Tool.
        - Always reply in Traditional Chinese.
    Output:
        - Do NOT include agent transfer or routing messages in your response.
        - Only return the final helpful answer to the user.
    """
)

fact_check_agent = create_react_agent(
    model=llm_gemini,
    tools=[google_fact_check_tool, cofacts_tool],
    name="fact_check_agent",
    prompt="""
    Role:
        You are a fact-checking expert who verifies the authenticity of the user's claims.
    Requirements:
        - Use fact-check and cofacts tools.
        - Always reply in Traditional Chinese.
    Output:
        - Do NOT include agent transfer or routing messages in the final output.
        - Only return the final helpful answer to the user.
    """
)

supervisor = create_supervisor(
    agents=[graphrag_agent, fact_check_agent],
    tools=[should_continue],
    model=llm_gemini,
    prompt="""
    You are a supervisor coordinating multiple assistant agents.
    Task Flow:
        - First, delegate the question to graphrag_agent for a medical or location-based response.
        - Then, pass the response to fact_check_agent to verify factual accuracy.
        - Finally, compile and return the response to the user.
    Output:
        - Do NOT include agent routing or technical messages in the final output.
        - Only return a clear, helpful summary in Traditional Chinese.
    """
)

# Compile app
app = supervisor.compile(checkpointer=memory)

# Custom helper to filter response

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