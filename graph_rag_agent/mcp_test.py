from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.tools import tool, InjectedToolCallId
from langgraph.prebuilt import InjectedState
from langgraph.graph import StateGraph, START, MessagesState,END
from langgraph.types import Command
from langchain_core.tools import tool
from langchain_core.messages.utils import count_tokens_approximately
from langchain_tavily import TavilySearch
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import ToolNode
from langmem.short_term import SummarizationNode
import sqlite3
import asyncio
import os
from graph_rag import graphrag_chronic,graphrag_cardiovascular
from llm import llm_gemini
from fact_check import search_fact_checks
from cofacts_check import search_cofacts
from typing import Annotated

class State(MessagesState):
    context: dict[str,any]


summarization_node = SummarizationNode(
    token_counter=count_tokens_approximately,
    model=llm_gemini,
    max_tokens=5000,
    max_summary_tokens=2500,
    output_messages_key="messages"
)

# Handoff tool set define
def create_handoff_tool(*, agent_name: str, description: str | None = None):
    name = f"transfer_to_{agent_name}"
    description = description or f"Ask {agent_name} for the answer."

    @tool(name, description=description)
    def handoff_tool(
        state: Annotated[MessagesState, InjectedState],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
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


handoff_to_chronic_agent=create_handoff_tool(agent_name='chronic_agent',description='assign task to chronic agent')
handoff_to_cardiovascular_agent=create_handoff_tool(agent_name='cardiovascular_agent',description='assign task to cardiovascular agent')
handoff_to_fact_check_agent=create_handoff_tool(agent_name='fact_check_agent',description='assign task to fact check agent')
handoff_to_mcp_agent=create_handoff_tool(agent_name='mcp_agent',description='assign task to mcp agent when need to search web.')

async def get_mcp_tools():
    client=MultiServerMCPClient(
        {
        "browser_use":{
            "command": "uv",
            "args": [
               "--directory",
                "C:\\Users\\USER\\Desktop\\Easy care\\mcp-browser-use",
                "run",
                "mcp-server-browser-use"
            ],
            "transport":"stdio",
            "env": {
                "MCP_LLM_GOOGLE_API_KEY": "AIzaSyA4ui2etBNEhVOq9P4pkaVNDJw_QQUItd0",
                "MCP_AGENT_TOOL_MAX_INPUT_TOKENS": "20000",
                "MCP_AGENT_TOOL_MAX_STEPS": "20",
                "MCP_AGENT_TOOL_MAX_ACTIONS_PER_STEP":"4",
                "MCP_LLM_PROVIDER": "google",
                "MCP_LLM_MODEL_NAME": "gemini-2.5-flash",
                "MCP_BROWSER_HEADLESS": "false",
                "MCP_LLM_TEMPERATURE": "0.5",
                "MCP_RESEARCH_TOOL_SAVE_DIR":".\graph_rag_agent\mcp_log",
                "MCP_SERVER_LOGGING_LEVEL": "DEBUG",
                "MCP_SERVER_LOG_FILE":"C:\\Users\\USER\\Desktop\\Easy care\\mcu_113_project\\graph_rag_agent\\mcp_log\\browserlog.log",
                }
            }
        }
    )
    mcp_tools= await client.get_tools()
    print("got tools:",mcp_tools)
    return mcp_tools

@tool(name_or_callable='net_search')
def net_search(query: str):
    """
    Use this tool when you need to search the internet for information or other tool don't return answer.

    Args:
        query: The medical question or statement to be answered.
    """
    tavily=TavilySearch(country='taiwan',search_depth='advanced')
    result=tavily.invoke(query)
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

    result = graphrag_cardiovascular(input=query)
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

    result = graphrag_chronic(input=query)
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
        else:
            result += "查無相關審查結果\n"
    
    return result
    


chronic_agent = create_react_agent(
    model=llm_gemini,  
    tools=[net_search,chronic_search], 
    name="chronic_agent",
    prompt="""
    Role:
        You are a medical expert providing information about medical knowledge.
    Task:
        Your main task is to use the provided tool to search for answers whenever you receive a user inquiry about chronic, and return the search results.
    Specific Requirements:
        **Prohibitions**:
            1.Languages other than Traditional Chinese are not allowed
            2. Do not use pre-trained knowledge, only use the information provided in the context.
            3. If you can't any useful information, just say that you don't know.
    """
)

cardiovascular_agent = create_react_agent(
    model=llm_gemini,  
    tools=[cardiovascular_search,net_search], 
    name="cardiovascular_agent",
    prompt="""
    Role:
        You are a medical expert providing information about medical knowledge.
    Task:
        Your main task is to use the provided tool to search for answers whenever you receive a user inquiry about cardiovascular, and return the search results.
    Specific Requirements:
        **Prohibitions**:
            1.Languages other than Traditional Chinese are not allowed
            2. Do not use pre-trained knowledge, only use the information provided in the context.
            3. If you can't any useful information, just say that you don't know.
    """
)

fact_check_agent = create_react_agent(
    model=llm_gemini,
    tools=[google_fact_check_tool], 
    name="fact_check_agent",
    prompt="""
    Role:
        You are a fact-checking expert.
    Task:
        Your main task is to fact-check claims using the provided tool and return the results.
    Rules:
        **Prohibitions**:   
            1. Languages ​​other than Traditional Chinese are not allowed
            2. Do not use pre-trained knowledge, only use the information provided in the context.
            3. Only use the provided tool to fact-check claims, do not use any other methods.
            4. If nothing returned, just say that you don't know.
    """
    )

mcp_node =asyncio.run(get_mcp_tools())
mcp_agent =create_react_agent(
    model=llm_gemini,
    tools=mcp_node,
    name="mcp_agent",
    prompt="""
    Role:
        You are expert in using MCP tools.
    Task:
        Your main task is to use the provided MCP tools to complete user requests.
    Rules:
        1. Prioritize searching for information from Taiwanese media.
        2. Use Traditional Chinese for searching, if no useful info found, use English.
        3. Do not use pre-trained knowledge, only use the information provided in the context.
    """
)

supervisor= create_react_agent(
    model=llm_gemini,
    tools=[handoff_to_cardiovascular_agent,handoff_to_chronic_agent,handoff_to_fact_check_agent,handoff_to_mcp_agent],
    pre_model_hook=summarization_node,
    name="supervisor",
    prompt="""
        Role:
        You are the Supervisor for a medical health system. 
        Your main task is understand the user's question and route it to the most suitable specialized agent for handling that specific problem.

        Rules:
        - Only use the information provided by the agents, do not use pre-trained knowledge.
        - Your response should be in Traditional Chinese.
        - You can only use tools once per response.
        - Assign work to one agent at a time, do not call agents in parallel.
        - Do not do any work yourself.
        """
)




config = {"configurable": {"thread_id": "1"}}

async def main():
    workflow=StateGraph(State)
    # destinations是為了方便視覺化用的
    workflow.add_node(supervisor,destinations=('chronic_agent','cardiovascular_agent','fact_check_agent','mcp_agent',END))
    workflow.add_node(chronic_agent)
    workflow.add_node(cardiovascular_agent)
    workflow.add_node(fact_check_agent)
    workflow.add_node(mcp_agent)
    workflow.add_edge(START,'supervisor')
    workflow.add_edge('chronic_agent','supervisor')
    workflow.add_edge('cardiovascular_agent','supervisor')
    workflow.add_edge('fact_check_agent','supervisor')
    workflow.add_edge('mcp_agent','supervisor')
    async with AsyncSqliteSaver.from_conn_string("agent_checkpoint.sqlite") as memory:
        graph=workflow.compile(checkpointer=memory)
        while True:
            message=input("輸入你的問題: ")
            respond=await graph.ainvoke(input={'messages':[{'role': 'human','content': message}]},config=config,stream_mode='messages')
            print(respond)
if __name__ == "__main__":
    asyncio.run(main())
