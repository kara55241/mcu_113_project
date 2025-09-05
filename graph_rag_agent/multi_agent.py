from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph.checkpoint.sqlite import SqliteSaver
from typing import Annotated
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.graph import StateGraph, START, MessagesState,END
from langgraph.types import Command
import sqlite3
import warnings
import logging
import os

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
from langchain_core.tools import tool

# 創建專門的 logger
agent_logger = logging.getLogger('multi_agent')
try:
    from .graph_rag import graphrag_chronic, graphrag_cardiovascular
    from .fact_check import search_fact_checks
    from .cofacts_check import search_cofacts
    from .browser_tools import (
        browser_navigate_and_extract,
        browser_search_and_analyze,
        browser_verify_medical_claim,
        browser_extract_hospital_info
    )
except ImportError:
    from graph_rag import graphrag_chronic, graphrag_cardiovascular
    from fact_check import search_fact_checks
    from cofacts_check import search_cofacts
    from browser_tools import (
        browser_navigate_and_extract,
        browser_search_and_analyze,
        browser_verify_medical_claim,
        browser_extract_hospital_info
    )
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

conn = sqlite3.connect("./agent_checkpoint.sqlite", check_same_thread=False)
memory=SqliteSaver(conn)
class State(MessagesState):
    context: dict[str,any]
    routing_done: bool = False
    selected_agent: str = ""


summarization_node = SummarizationNode(
    token_counter=count_tokens_approximately,
    model=llm_gemini,
    max_tokens=1500,
    max_summary_tokens=750,
    output_messages_key="messages",
)

# Official LangGraph delegation pattern
from langgraph.types import Send

def create_task_description_handoff_tool(*, agent_name: str):
    """Create handoff tool using official delegation pattern"""
    @tool(f"transfer_to_{agent_name}", description=f"Transfer task to {agent_name} with specific task description")
    def handoff_tool(
        task_description: Annotated[str, "Specific task description for the agent"],
        state: Annotated[MessagesState, InjectedState]
    ) -> Command:
        """Transfer a specific task to the designated agent"""
        agent_logger.info(f"[DELEGATION] Assigning task to {agent_name}: {task_description[:50]}...")
        
        # Create task description message
        task_message = {"role": "user", "content": task_description}
        agent_input = {**state, "messages": [task_message]}
        
        # Use direct goto without Command.PARENT to prevent recursion
        return Command(
            goto=agent_name
        )
    return handoff_tool

# Semantic routing system using OpenAI Embeddings
def get_embedding(text: str) -> list:
    """Get embedding for text using OpenAI API"""
    try:
        response = openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding
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
        慢性疾病醫療諮詢：糖尿病血糖控制胰島素注射、高血壓降血壓藥物、慢性腎臟病腎功能保護、
        關節炎關節疼痛治療、慢性阻塞性肺病呼吸困難、甲狀腺功能異常、慢性肝病、骨質疏鬆症、
        慢性病併發症預防、長期用藥管理、生活方式調整、飲食控制建議、運動處方、定期追蹤檢查、
        醫院診所資訊查詢、醫療機構推薦、網路醫療資訊搜尋、最新治療方法研究、醫療設施查詢
        """,
        
        "cardiovascular_agent": """
        心血管疾病醫療諮詢：心臟病冠心病心肌梗塞、中風腦血管疾病、血壓高血壓低血壓、胸痛心絞痛、
        心律不整心悸、動脈硬化血管疾病、心臟衰竭、靜脈曲張、周邊動脈疾病、心電圖異常、
        心臟導管檢查、血管支架手術、心血管風險評估、膽固醇三酸甘油脂控制、心臟復健運動、
        心血管專科醫院查詢、心臟科診所資訊、最新心血管治療技術、醫療機構心血管科介紹
        """,
        
        "fact_check_agent": """
        醫療資訊查證與澄清：健康謠言查證、醫學聲明真偽驗證、偏方療法安全性、網路健康資訊可信度、
        醫療廣告宣稱查核、保健食品功效驗證、治療方法科學根據、藥物副作用真實性、
        醫療機構資格查證、健康飲食迷思澄清、疾病預防方法正確性、網路醫療資訊驗證、
        醫療新聞真偽辨別、健康資訊事實查核、醫學研究報告驗證、網站醫療內容分析
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
        if semantic_result["confidence"] > 0.65:
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

# Create delegation tools using official pattern
transfer_to_chronic_agent = create_task_description_handoff_tool(agent_name="chronic_agent")
transfer_to_cardiovascular_agent = create_task_description_handoff_tool(agent_name="cardiovascular_agent") 
transfer_to_fact_check_agent = create_task_description_handoff_tool(agent_name="fact_check_agent")

@tool(name_or_callable='net_search')
def net_search(query: str):
    """
    Use this tool when you need to search the internet for information or other tool don't return answer.

    Args:
        query: The medical question or statement to be answered.
    """
    import time
    start_time = time.time()
    agent_logger.info(f"[TOOL] NET_SEARCH 啟動")
    agent_logger.info(f"    搜尋查詢: {query[:100]}...")
    
    tavily=TavilySearch(country='taiwan',search_depth='advanced')
    result=tavily.invoke(query)
    
    end_time = time.time()
    agent_logger.info(f"[TOOL] NET_SEARCH 完成 | 耗時: {end_time - start_time:.2f}秒")
    agent_logger.info(f"    搜尋結果長度: {len(str(result))} 字符")
    agent_logger.info(f"    結果預覽: {str(result)[:150]}...")
    
    return result

@tool(name_or_callable='cardiovascular_search')
def cardiovascular_search(query: str) -> str:
    """
    You must use this tool when supervisor asks a medical question about cardiovascular diseases.
    This tool queries a medical knowledge graph to retrieve and generate answers.

    Args:
        query: The medical question or statement to be answered.

    Returns:
        A comprehensive answer based on the medical knowledge graph.
        if answer is not found, it will return a message indicating that no answer was found.
    """
    import time
    start_time = time.time()
    agent_logger.info(f"[TOOL] CARDIOVASCULAR_SEARCH 啟動")
    agent_logger.info(f"    查詢內容: {query[:100]}...")
    
    result = graphrag_cardiovascular(input=query)
    
    end_time = time.time()
    agent_logger.info(f"[TOOL] CARDIOVASCULAR_SEARCH 完成 | 耗時: {end_time - start_time:.2f}秒")
    agent_logger.info(f"    回應長度: {len(result)} 字符")
    agent_logger.info(f"    內容預覽: {result[:150]}...")
    
    return result

@tool(name_or_callable='chronic_search')
def chronic_search(query: str) -> str:
    """
    You must use this tool when supervisor asks a medical question about chronic diseases.
    This tool queries a medical knowledge graph to retrieve and generate answers.

    Args:
        query: The medical question or statement to be answered.

    Returns:
        A comprehensive answer based on the medical knowledge graph.
        if answer is not found, it will return a message indicating that no answer was found.
    """
    import time
    start_time = time.time()
    agent_logger.info(f"[TOOL] CHRONIC_SEARCH 啟動")
    agent_logger.info(f"    查詢內容: {query[:100]}...")
    
    result = graphrag_chronic(input=query)
    
    end_time = time.time()
    agent_logger.info(f"[TOOL] CHRONIC_SEARCH 完成 | 耗時: {end_time - start_time:.2f}秒")
    agent_logger.info(f"    回應長度: {len(result)} 字符")
    agent_logger.info(f"    內容預覽: {result[:150]}...")
    
    return result


@tool(name_or_callable='google_fact_check_tool',parse_docstring=True)
def google_fact_check_tool(query: str) -> str:
    """
    You must use this tool when supervisor asks you to fact-check a claim.

    Args:
        query: The claim or statement to be fact-checked.

    Returns:
        A  result of the fact-check results.
    """
    import time
    start_time = time.time()
    agent_logger.info(f"[TOOL] FACT_CHECK_TOOL 啟動")
    agent_logger.info(f"    待查核聲明: {query[:100]}...")
    
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
    
    end_time = time.time()
    agent_logger.info(f"[TOOL] FACT_CHECK_TOOL 完成 | 耗時: {end_time - start_time:.2f}秒")
    agent_logger.info(f"    查核結果數量: {claims_found} 筆")
    agent_logger.info(f"    回應長度: {len(result)} 字符")
    agent_logger.info(f"    內容預覽: {result[:150]}...")
    
    return result
    


chronic_agent = create_react_agent(
    model=llm_GPT,  
    tools=[
        chronic_search, 
        net_search, 
        browser_navigate_and_extract,
        browser_search_and_analyze,
        browser_extract_hospital_info
    ], 
    name="chronic_agent",
    prompt="""
You are the chronic diseases specialist agent in a medical consultation system.

Specialty: Chronic diseases including diabetes, hypertension, arthritis, kidney disease, and related conditions.

Available Tools:
- chronic_search: Query medical knowledge graph for chronic disease information
- net_search: Search internet for current medical information
- browser_navigate_and_extract: Visit specific medical websites to extract information
- browser_search_and_analyze: Search and analyze medical information from multiple sources
- browser_extract_hospital_info: Get information about medical facilities

Workflow:
1. ALWAYS use the chronic_search tool first to query the medical knowledge graph
2. If additional current information is needed, use net_search tool
3. For specific website information or hospital details, use browser tools
4. Use browser_verify_medical_claim when claims need web-based verification
5. Provide comprehensive, evidence-based medical guidance in MARKDOWN format
6. Focus only on your specialty area - chronic diseases

CRITICAL OUTPUT REQUIREMENTS:
- MUST respond in Traditional Chinese
- MUST use proper Markdown formatting with headers, lists, and emphasis
- MUST structure responses with clear sections using ## headers
- MUST use **bold** for important terms and emphasis
- MUST use bullet points (-) or numbered lists (1., 2., 3.) for clarity
- MUST provide detailed, practical medical advice
- MUST base all responses on tool results
- NEVER answer without using tools first

Response Structure Template:
## Chronic Disease Consultation Response

### **Main Recommendations**
- Important recommendation 1
- Important recommendation 2

### **Detailed Explanation** 
1. First key point
2. Second key point

### **Important Notes**
- **Important Reminder**: Specific precautions
- **Follow-up Recommendations**: Follow-up advice

You are the final authority on chronic diseases - do not refer to other specialists.
"""
)

cardiovascular_agent = create_react_agent(
    model=llm_GPT,  
    tools=[
        cardiovascular_search, 
        net_search, 
        browser_navigate_and_extract,
        browser_search_and_analyze,
        browser_extract_hospital_info
    ], 
    name="cardiovascular_agent",
    prompt="""
You are the cardiovascular diseases specialist agent in a medical consultation system.

Specialty: Heart diseases, stroke, blood pressure, chest pain, and all cardiovascular conditions.

Available Tools:
- cardiovascular_search: Query medical knowledge graph for cardiovascular disease information
- net_search: Search internet for current medical information
- browser_navigate_and_extract: Visit specific medical websites to extract information
- browser_search_and_analyze: Search and analyze medical information from multiple sources
- browser_extract_hospital_info: Get information about medical facilities

Workflow:
1. ALWAYS use the cardiovascular_search tool first to query the medical knowledge graph
2. If additional current information is needed, use net_search tool
3. For specific website information or hospital details, use browser tools
4. Use browser tools to find specialized cardiovascular clinics or hospitals
5. Provide comprehensive, evidence-based cardiovascular guidance in MARKDOWN format
6. Focus only on your specialty area - cardiovascular diseases

CRITICAL OUTPUT REQUIREMENTS:
- MUST respond in Traditional Chinese
- MUST use proper Markdown formatting with headers, lists, and emphasis
- MUST structure responses with clear sections using ## headers
- MUST use **bold** for important terms and emphasis
- MUST use bullet points (-) or numbered lists (1., 2., 3.) for clarity
- MUST provide detailed, practical cardiovascular medical advice
- MUST base all responses on tool results
- NEVER answer without using tools first

Response Structure Template:
## Cardiovascular Disease Consultation Response

### **Risk Assessment**
- Current risk factors
- Important warnings

### **Treatment Recommendations** 
1. Primary interventions
2. Lifestyle modifications
3. Medical management

### **Prevention & Monitoring**
- **Prevention Strategies**: Specific prevention measures
- **Regular Monitoring**: Recommended follow-up schedule

You are the final authority on cardiovascular diseases - do not refer to other specialists.
"""
)

fact_check_agent = create_react_agent(
    model=llm_GPT,
    tools=[
        google_fact_check_tool, 
        browser_verify_medical_claim,
        browser_navigate_and_extract,
        browser_search_and_analyze
    ], 
    name="fact_check_agent",
    prompt="""
You are the medical fact-checking specialist agent in a healthcare consultation system.

Specialty: Verifying health and medical claims, debunking misinformation, providing evidence-based assessments.

Available Tools:
- google_fact_check_tool: Use Google Fact Check API for claim verification
- browser_verify_medical_claim: Verify claims using browser automation to check authoritative sources
- browser_navigate_and_extract: Visit specific websites to extract verification information
- browser_search_and_analyze: Search and analyze information from multiple web sources

Workflow:
1. ALWAYS use the google_fact_check_tool first to verify the medical claim
2. If additional verification is needed, use browser_verify_medical_claim for web-based checking
3. Use browser tools to visit authoritative medical sources for cross-verification
4. Analyze all fact-checking results thoroughly
5. Provide comprehensive verification analysis with clear verdicts in MARKDOWN format
6. Focus only on fact-checking and verification

CRITICAL OUTPUT REQUIREMENTS:
- MUST respond in Traditional Chinese
- MUST use proper Markdown formatting with headers, lists, and emphasis
- MUST structure responses with clear sections using ## headers
- MUST use **bold** for important terms and verification status
- MUST use bullet points (-) or numbered lists (1., 2., 3.) for clarity
- MUST provide detailed analysis based on tool results
- MUST give clear verdicts on claim accuracy with supporting evidence
- NEVER answer without using google_fact_check_tool first

Response Structure Template:
## Medical Fact-Check Analysis

### **Claim Being Verified**
> Original claim statement

### **Verification Status**
- **Status**: Verified / False / Partially True / Insufficient Evidence
- **Confidence Level**: High/Medium/Low

### **Evidence Analysis**
1. Source 1 findings
2. Source 2 findings
3. Expert consensus

### **Final Verdict**
- **Conclusion**: Clear statement of accuracy
- **Recommendations**: What users should know/do

You are the final authority on medical fact-checking - do not refer to other verification services.
"""
    )
    
@tool(name_or_callable='intelligent_routing_tool')
def intelligent_routing_tool(
    user_query: str,
    state: Annotated[State, InjectedState]
) -> str:
    """
    Intelligent routing tool that uses semantic analysis to determine the best agent for a medical query.
    Includes loop prevention mechanism.
    
    Args:
        user_query: The user's medical question or statement
        state: Current conversation state
        
    Returns:
        The name of the most appropriate agent (chronic_agent, cardiovascular_agent, or fact_check_agent)
    """
    return intelligent_agent_routing(user_query, state)

supervisor = create_react_agent(
    model=llm_GPT,
    tools=[transfer_to_chronic_agent, transfer_to_cardiovascular_agent, transfer_to_fact_check_agent, intelligent_routing_tool],
    name="supervisor",
    checkpointer=memory,
    prompt="""
You are a thoughtful supervisor managing specialized medical agents in a healthcare consultation system.

THINKING PROCESS - Follow these steps for EVERY query:

STEP 1: ANALYZE the user's query carefully
- What type of question is this? (medical consultation, general information, fact-checking)
- What specific information does the user need?
- Are there any keywords indicating this is non-medical information request?

STEP 2: ROUTE intelligently  
- Use intelligent_routing_tool to determine the best agent
- Think: Does this routing make sense for this specific query?
- Remember: The tool has loop prevention - it will return the same agent if already routed

STEP 3: DELEGATE with precision
- Transfer to the selected agent with a clear, specific task description
- Include all relevant context from the user's original question
- Be explicit about what type of response is needed

STEP 4: COMPLETE the task
- Once you delegate, your job is DONE
- Do NOT attempt to route again or call additional tools
- Trust the specialist agent to handle the complete response

Available specialized agents:
- chronic_agent: Chronic diseases, general medical info, hospital information, contact details
- cardiovascular_agent: Heart diseases, stroke, blood pressure, cardiovascular conditions  
- fact_check_agent: Medical claim verification, health misinformation checking

CRITICAL RULES:
- ALWAYS use intelligent_routing_tool FIRST before any delegation
- ONLY delegate to ONE agent per conversation
- NEVER attempt to answer questions yourself
- Provide task descriptions in Traditional Chinese for consistency
- After delegation, STOP - do not continue processing

Example thought process:
User asks: "台灣大學的聯絡電話"
STEP 1: This is a general information request about contact details, not medical
STEP 2: Use intelligent_routing_tool → returns "chronic_agent" (handles general info)  
STEP 3: Transfer with task: "請協助查詢台灣大學的聯絡電話資訊"
STEP 4: Task complete - specialist will handle the full response

Think step-by-step and be decisive in your actions.
"""
)

# Simple router function to replace supervisor agent
def route_to_agent(state: State) -> str:
    """Simple routing function that directs to appropriate agent"""
    messages = state.get('messages', [])
    if not messages:
        return 'chronic_agent'
    
    # Get the latest user message
    user_message = None
    for msg in reversed(messages):
        if hasattr(msg, 'type') and msg.type == 'human':
            user_message = msg.content
            break
    
    if not user_message:
        return 'chronic_agent'
    
    # Use intelligent routing with loop prevention
    selected_agent = intelligent_agent_routing(user_message, state)
    agent_logger.info(f"[ROUTER] 路由決策: {user_message[:50]}... -> {selected_agent}")
    
    return selected_agent

# Rebuild workflow with simple conditional routing - no supervisor agent to cause loops
workflow = (
    StateGraph(State)
    .add_node(chronic_agent)
    .add_node(cardiovascular_agent)
    .add_node(fact_check_agent)
    .add_edge(START, 'chronic_agent')  # Default start with chronic_agent for simplicity
    .add_conditional_edges(
        START,
        route_to_agent,
        {
            'chronic_agent': 'chronic_agent',
            'cardiovascular_agent': 'cardiovascular_agent',
            'fact_check_agent': 'fact_check_agent'
        }
    )
    # All agents end directly
    .add_edge('chronic_agent', END)
    .add_edge('cardiovascular_agent', END)
    .add_edge('fact_check_agent', END)
    .compile(checkpointer=memory)
)

def generate_response(message: str, session_id: str = "default", location_info: dict = None) -> dict:
    """
    Simplified response generation using official LangGraph delegation pattern
    
    Args:
        message: User input message
        session_id: Session ID for conversation context  
        location_info: Optional location information dictionary
    
    Returns:
        dict: Response dictionary containing output, location, and data fields
    """
    import logging
    import time
    logger = logging.getLogger(__name__)
    
    start_time = time.time()
    logger.info(f"=== WORKFLOW START ===")
    logger.info(f"User input: '{message}' | Session ID: {session_id}")
    
    # Build complete user message (including location info if provided)
    user_message = message
    if location_info:
        location_context = f"User location information:\n"
        location_context += f"Name: {location_info.get('name', 'Unknown')}\n"
        location_context += f"Address: {location_info.get('address', 'Unknown')}\n"
        location_context += f"Coordinates: {location_info.get('coordinates', 'Unknown')}\n\n"
        user_message = location_context + "User question: " + message
        logger.info(f"Message with location info: {len(user_message)} characters")
    
    # Use session_id as thread_id to maintain conversation context
    config = {"configurable": {"thread_id": session_id}}
    
    logger.info(f"Starting LangGraph Workflow execution...")
    workflow_start = time.time()
    
    try:
        # Execute workflow
        result = workflow.invoke(
            input={'messages': [HumanMessage(content=user_message.strip())]},
            config=config
        )
        
        workflow_end = time.time()
        logger.info(f"=== WORKFLOW COMPLETE === Duration: {workflow_end - workflow_start:.2f}s")
        logger.info(f"Workflow result: Generated {len(result.get('messages', []))} messages")
        
        # Simple message extraction: Get the last AI message
        messages = result.get('messages', [])
        final_response = ""
        
        # Find the last AI message that contains substantial content
        for msg in reversed(messages):
            if (hasattr(msg, 'type') and msg.type == 'ai' and 
                hasattr(msg, 'content') and msg.content and 
                msg.content.strip() and 
                len(msg.content.strip()) > 20):  # Filter out short/empty responses
                
                final_response = msg.content.strip()
                logger.info(f"Selected final AI response: {len(final_response)} characters")
                logger.info(f"Response preview: {final_response[:100]}...")
                break
        
        # Fallback if no valid response found
        if not final_response:
            final_response = "抱歉，系統無法處理您的請求。請稍後再試。"
            logger.warning("No valid AI response found, using fallback message")
    
    except Exception as e:
        logger.error(f"Workflow execution error: {str(e)}")
        final_response = "抱歉，系統處理您的請求時發生錯誤。請稍後再試。"
    
    total_time = time.time() - start_time
    logger.info(f"=== PROCESSING COMPLETE === Total time: {total_time:.2f}s")
    logger.info(f"Final response: {len(final_response)} characters")
    
    # Build unified response format
    response_data = {
        'output': final_response,
        'location': location_info,
        'data': {
            'session_id': session_id,
            'message_processed': True,
            'response_length': len(final_response)
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