# multi_agent.py - LangGraph Supervisor with Feedback Enhancement (English Version)

from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import sqlite3, time, os, json
from .llm import llm_GPT, llm_gemini

# Initialize Checkpoint
conn = sqlite3.connect("./agent_checkpoint.sqlite", check_same_thread=False)
memory = SqliteSaver(conn)

# Tool functions
@tool
def chronic_search(query: str) -> str:
    """Search for chronic disease knowledge graph information"""
    try:
        from .graph_rag import graphrag_chronic
    except:
        from graph_rag_agent.graph_rag import graphrag_chronic
    return str(graphrag_chronic(query))

@tool
def cardiovascular_search(query: str) -> str:
    """Search for cardiovascular disease knowledge graph information"""
    try:
        from .graph_rag import graphrag_cardiovascular
    except:
        from graph_rag_agent.graph_rag import graphrag_cardiovascular
    return str(graphrag_cardiovascular(query))

@tool
def fact_check_tool(query: str) -> str:
    """Search for health-related fact-checking results"""
    try:
        from .fact_check import search_fact_checks
    except:
        from graph_rag_agent.fact_check import search_fact_checks
    result = search_fact_checks(query)
    return f"Found {len(result.get('claims', []))} fact-check results" if result else "No results found"

@tool
def net_search(query: str) -> str:
    """Search online health information using Tavily"""
    try:
        from langchain_tavily import TavilySearch
        tavily = TavilySearch(country='taiwan')
        return str(tavily.invoke(query))[:2000]
    except:
        return "Online search currently unavailable"

@tool
def search_feedback_memories(query: str) -> str:
    """Search for similar positively rated feedback memories"""
    try:
        from myproject.feedback_graph import search_similar_keymemories
        memories = search_similar_keymemories(query, top_k=1)
        if not memories:
            return "No related feedback memory"
        positive_memories = [m for m in memories if m.get('feedback_type') in ['positive', 'like']]
        if not positive_memories:
            return "No positive feedback memory"
        memory = positive_memories[0]
        content = memory.get('content', '')[:100]
        return f"Reference example: {content}"
    except Exception as e:
        print(f"Error searching feedback memory: {e}")
        return "Feedback memory search currently unavailable"

class FeedbackEnhancedAgent:
    """Agent wrapper with feedback enhancement"""

    def __init__(self, agent, name):
        self.agent = agent
        self.name = name
        self.tools = getattr(agent, 'tools', [])
        self.model = getattr(agent, 'model', None)

    def invoke(self, state, config=None):
        try:
            start_time = time.time()
            enhanced_state = self._enhance_with_feedback(state)
            result = self.agent.invoke(enhanced_state, config)
            end_time = time.time()
            print(f"⏱️ [{self.name}] Generation Time: {end_time - start_time:.2f} sec")
            return result
        except Exception as e:
            print(f"FeedbackEnhancedAgent invoke error: {e}")
            return self.agent.invoke(state, config)

    def _enhance_with_feedback(self, state):
        try:
            user_messages = [m for m in state.get("messages", []) if isinstance(m, HumanMessage)]
            if not user_messages:
                return state
            latest_query = user_messages[-1].content

            # Step 1: 取得圖譜資料
            rag_context = None
            if self.name == "chronic_agent":
                from .graph_rag import graphrag_chronic
                rag_context = graphrag_chronic(latest_query)
            elif self.name == "cardiovascular_agent":
                from .graph_rag import graphrag_cardiovascular
                rag_context = graphrag_cardiovascular(latest_query)

            # Step 2: 搜尋回饋記憶（可選）
            from myproject.feedback_graph import search_similar_keymemories
            memories = search_similar_keymemories(latest_query, top_k=1)
            positive_memories = [m for m in memories if m.get('feedback_type') in ['positive', 'like']]
            memory_hint = None
            if positive_memories:
                memory_content = positive_memories[0].get('content', '')[:300]
                memory_hint = HumanMessage(content=f"💡 Highly rated past suggestion:\n{memory_content}")

            # Step 3: 注入 RAG 結果與記憶提示
            rag_hint = SystemMessage(content=f"📘 Based on graph knowledge:\n{rag_context}")
            new_messages = [rag_hint] + ([memory_hint] if memory_hint else []) + state["messages"]
            print(f"🧠 [GraphRAG] Injected knowledge: {rag_context[:40]}...")

            enhanced_state = state.copy()
            enhanced_state["messages"] = new_messages
            return enhanced_state
        except Exception as e:
            print(f"❌ Feedback + RAG boost error: {e}")
            return state

    def __getattr__(self, name):
        return getattr(self.agent, name)

print("🤖 Creating base agents...")

chronic_tools = [chronic_search, search_feedback_memories, net_search]
cardiovascular_tools = [cardiovascular_search, search_feedback_memories, net_search]
fact_check_tools = [fact_check_tool, net_search]

try:
    chronic_agent_base = create_react_agent(
        model=llm_GPT,
        tools=chronic_tools,
        name="chronic_agent",
        prompt="You are a chronic disease expert, providing professional and practical advice on diabetes, hypertension, etc."
    )

    cardiovascular_agent_base = create_react_agent(
        model=llm_GPT,
        tools=cardiovascular_tools,
        name="cardiovascular_agent",
        prompt="You are a cardiovascular expert, specialized in heart and vascular diseases. Provide professional medical advice."
    )

    fact_check_agent_base = create_react_agent(
        model=llm_GPT,
        tools=fact_check_tools,
        name="fact_check_agent",
        prompt="You are a health fact-checking expert. Verify the truthfulness of health-related information objectively and accurately."
    )

    chronic_agent = FeedbackEnhancedAgent(chronic_agent_base, "chronic_agent")
    cardiovascular_agent = FeedbackEnhancedAgent(cardiovascular_agent_base, "cardiovascular_agent")
    fact_check_agent = FeedbackEnhancedAgent(fact_check_agent_base, "fact_check_agent")

    print("✅ Base agents created successfully")

except Exception as e:
    print(f"❌ Failed to create agents: {e}")
    chronic_agent = None
    cardiovascular_agent = None
    fact_check_agent = None

print("🔧 Creating Supervisor...")

try:
    supervisor_workflow = create_supervisor(
        agents=[chronic_agent, cardiovascular_agent, fact_check_agent],
        model=llm_GPT,
        prompt="""You are a health consultation dispatcher. Choose the most suitable agent based on the user's question:

chronic_agent: Handles general health issues, lifestyle, chronic diseases (e.g., diabetes, hypertension)
cardiovascular_agent: Handles cardiovascular and heart-related issues
fact_check_agent: Handles health information verification and rumor clarification

Please assign the most appropriate expert and let them respond.
""",
        output_mode="last_message"
    )

    app = supervisor_workflow.compile(checkpointer=memory)
    print("✅ Supervisor created successfully")

except Exception as e:
    print(f"❌ Supervisor creation failed: {e}")

    class FallbackApp:
        def invoke(self, input_data, config=None):
            try:
                user_messages = [m for m in input_data.get("messages", []) if isinstance(m, HumanMessage)]
                if user_messages:
                    query = user_messages[-1].content.lower()
                    if any(word in query for word in ['heart', 'cardio', 'blood pressure']):
                        response = "For cardiovascular issues, please consult a professional physician."
                    elif any(word in query for word in ['rumor', 'truth', 'verify']):
                        response = "For health fact-checking, we recommend referring to official medical sources."
                    else:
                        response = "To stay healthy, maintain a good lifestyle and regular checkups."
                    return {"messages": [AIMessage(content=response)]}
                else:
                    return {"messages": [AIMessage(content="Please provide your health-related question.")]}
            except Exception:
                return {"messages": [AIMessage(content="The system is temporarily unavailable.")]}

        def filter_messages(self, messages):
            if not messages:
                return ["Ready to assist you with health consultation."]
            agent_responses = []
            supervisor_responses = []
            for msg in messages:
                if isinstance(msg, AIMessage):
                    content = getattr(msg, 'content', '').strip()
                    msg_name = getattr(msg, 'name', '')
                    if content and len(content) > 15 and not content.startswith('Transferring'):
                        if msg_name in ['chronic_agent', 'cardiovascular_agent', 'fact_check_agent']:
                            agent_responses.append({'content': content, 'agent': msg_name, 'length': len(content)})
                        elif msg_name == 'supervisor':
                            supervisor_responses.append({'content': content, 'agent': msg_name, 'length': len(content)})
            if agent_responses:
                best = max(agent_responses, key=lambda x: x['length'])
                return [best['content']]
            elif supervisor_responses:
                best = max(supervisor_responses, key=lambda x: x['length'])
                return [best['content']]
            else:
                return ["Processing your question, please wait..."]

    app = FallbackApp()

print("📤 Multi-agent system ready")

if not hasattr(app, 'filter_messages'):
    def filter_messages(messages):
        if not messages:
            return ["Ready to assist you with health-related queries."]
        agent_responses = []
        supervisor_responses = []
        for msg in messages:
            if isinstance(msg, AIMessage):
                content = getattr(msg, 'content', '').strip()
                msg_name = getattr(msg, 'name', '')
                if content and len(content) > 20 and not content.startswith('Transferring'):
                    if msg_name in ['chronic_agent', 'cardiovascular_agent', 'fact_check_agent']:
                        agent_responses.append({'content': content, 'agent': msg_name, 'length': len(content)})
                    elif msg_name == 'supervisor':
                        supervisor_responses.append({'content': content, 'agent': msg_name, 'length': len(content)})
        if agent_responses:
            best = max(agent_responses, key=lambda x: x['length'])
            print(f"✅ Selected detailed response from {best['agent']} (length: {best['length']})")
            return [best['content']]
        elif supervisor_responses:
            best = max(supervisor_responses, key=lambda x: x['length'])
            print(f"📝 Using supervisor response (length: {best['length']})")
            return [best['content']]
        else:
            print("⚠️ No valid responses found")
            return ["Preparing professional advice for you, please wait..."]
    app.filter_messages = filter_messages

print("✅ Multi-agent system initialized")
