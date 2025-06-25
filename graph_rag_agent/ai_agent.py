"""準備棄用, 之後會用langgrpah替代"""
from .llm import llm_GPT, llm_gemini
from .graph import graph
from langchain_core.prompts import ChatPromptTemplate
from langchain.schema import StrOutputParser
from langchain_core.tools import Tool
from langchain_community.chat_message_histories import Neo4jChatMessageHistory
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain import hub
from langchain_core.prompts import PromptTemplate
from .research import graph_rag
from .SearchTool import SearchTools
from multi_agent import app  # 引入 Supervisor app
from langchain_core.messages import HumanMessage
import re

tools = [
    Tool.from_function(
        name="Medical Graph rag",
        description="you MUST use this tool when user ask medical question",
        func=graph_rag,
    ),
    Tool.from_function(
        name="Google Search",
        description="use this tool when other tool can't find the answer. If you use this tool, you're allowed to use your pre-trained knowledge to combine the answer",
        func=SearchTools.Google_Search,
    ),
    Tool.from_function(
        name="Google Map Search",
        description="Use this tool to search for nearby hospitals or clinics using Google Maps.",
        func=SearchTools.Google_Map
    ),
]

def get_memory(session_id):
    return Neo4jChatMessageHistory(session_id=session_id, graph=graph, window=20)

agent_prompt = PromptTemplate.from_template("""
You are a medical expert providing information about medical knowledge.
Be as helpful as possible and return as much information as possible.
Always response in Traditional Chinese.

If user is asking about medical question, you MUST use the Medical Graph rag tool to respond.

you can add your thought based on return context form tools.

Your response should be in a list.                                            

Only use the information provided in the context.

If you not sure user is asking medical question, check the last 5 conversations first.

{tools}

To use a tool, please follow the following format:

```
Thought: think what you should do.                                                                                                                                                                 
Thought: Do I need to use a tool? Yes             
Potential questions: list questions user may asking here[]                                                           
Action: the tool you should use, must be one of [{tool_names}]
Action Input: rewrite user question based on Potential questions
Observation: the result of the action
```    
 

Use the following format if u need to use another tool.                                   
```
Thought: Did I get the answer? No
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action(must be detailed)  
Observation: the result of the action                                         
```            
                                                                                                                                                                                                                                                                                          
When you have a response to say to the Human, or if you do not need to use a tool, you MUST use the format:
IMPORTANT: Judging the reasonableness of information from tools.
```
Thought: Do I have the answer? Yes
Thought: Do I used any tool? Yes/No
Final Answer: [your response here]
```

```
                                 
```                                            
Begin!

Previous conversation history:
{chat_history}

New input: {input}
{agent_scratchpad}
""")
agent = create_react_agent(llm_gemini, tools, agent_prompt)
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True
    )

chat_agent = RunnableWithMessageHistory(
    agent_executor,
    get_memory,
    input_messages_key="input",
    history_messages_key="chat_history",
)

# 修改 ai_agent.py 中的 generate_response 函數結尾部分
def generate_response(user_input, session_id="default", location_info=None):
    try:
        input_text = user_input.strip()
        if location_info and "位置信息" not in input_text:
            input_text += (
                f"\n\n📍位置信息："
                f"\n- 名稱：{location_info.get('name', '未知')}"
                f"\n- 地址：{location_info.get('address', '未知')}"
                f"\n- 座標：{location_info.get('coordinates', '未知')}"
            )

        result = app.invoke(
            input={"messages": [HumanMessage(content=input_text)]},
            config={"configurable": {"thread_id": session_id}},
        )

        # ✅ 使用過濾後訊息
        clean_messages = app.filter_messages(result.get("messages", []))
        output_text = "\n\n".join(clean_messages)

        return {
            "output": output_text,
            "is_markdown": True,
            "location": location_info,
            "data": {},
        }

    except Exception as e:
        return {
            "output": f"⚠️ 系統錯誤：{str(e)}",
            "location": location_info,
            "data": {},
        }
