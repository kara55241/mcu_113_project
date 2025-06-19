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
    # 準備輸入資料
    input_text = user_input.strip()
    if location_info and "位置信息" not in input_text:
        input_text += (
            f"\n\n📍位置信息："
            f"\n- 名稱：{location_info.get('name', '未知')}"
            f"\n- 地址：{location_info.get('address', '未知')}"
            f"\n- 座標：{location_info.get('coordinates', '未知')}"
        )

    input_data = {"input": input_text}

    # 呼叫 Agent
    try:
        response = chat_agent.invoke(
            input_data,
            {"configurable": {"session_id": session_id}},
        )
    except Exception as e:
        return {
            "output": f"AI 回應失敗：{str(e)}",
            "location": location_info,
            "data": {}
        }

    # 統一解析輸出格式
    if isinstance(response, dict):
        # 獲取輸出文本
        output_text = response.get("output", "（未取得 AI 回應）")
        
        # 確保輸出包含Markdown語法標記
        # 嘗試添加明確的Markdown標記，比如列表的 * 前面確保有換行
        if not output_text.startswith('# ') and '\n# ' not in output_text:
            # 檢查是否有列表項但格式可能不正確
            if any(line.strip().startswith('*') or line.strip().startswith('-') or 
                   (line.strip() and line.strip()[0].isdigit() and line.strip()[1:].startswith('.')) 
                   for line in output_text.split('\n')):
                # 確保列表項前有換行
                output_text = output_text.replace('\n* ', '\n\n* ')
                output_text = output_text.replace('\n- ', '\n\n- ')
                # 處理數字列表
                import re
                output_text = re.sub(r'\n(\d+\.)', r'\n\n\1', output_text)
        
        return {
            "output": output_text,
            "is_markdown": True,  # 明確標記為Markdown
            "location": location_info,
            "data": response.get("data", {})
        }
    else:
        # 字符串響應處理
        output_text = str(response)
        return {
            "output": output_text,
            "is_markdown": True,  # 明確標記為Markdown
            "location": location_info,
            "data": {}
        }