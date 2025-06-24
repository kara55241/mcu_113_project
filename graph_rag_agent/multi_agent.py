from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langchain_core.tools import tool
from research import graph_rag
from fact_check import search_fact_checks
from word_similarity import find_most_similar_cofacts_article
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import MessagesState
from langchain_core.messages import SystemMessage, HumanMessage
from llm import llm_GPT, llm_gemini
from typing import Literal
memory=MemorySaver()
class AgentState(MessagesState):
    FactChecked: bool=False

@tool
def graphrag_tool(query: str) -> str:
    """
    You must use this tool when supervisor asks a medical question.
    This tool queries a medical knowledge graph to retrieve and generate answers.

    Args:
        query: The medical question or statement to be answered.

    Returns:
        A comprehensive answer based on the medical knowledge graph.
        if answer is not found, it will return a message indicating that no answer was found.
    """

    result = graph_rag(input=query)
    return result

@tool
def google_fact_check_tool(query: str,state: AgentState) -> str:
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
            state["FactChecked"]=True
        else:
            result += "查無相關審查結果\n"
    
    return result

@tool
def cofacts_tool(query: str) -> str:
    """
    You must use this tool when supervisor asks you to fact-check a claim
    Args:
        query (str): The claim or statement to be fact-checked.

    Returns:
         A  result of the fact-check results.
    """
    node, score = find_most_similar_cofacts_article(query)
    if node:
        result = f"最相關的文章內容：{node['text']}\n"
        result += f"AI 回覆：{node.get('aiReplies', [])}\n"
        result += f"人工回覆：{node.get('articleReplies', [])}\n"
        result += f"相似度：{score}\n"
       
    else:
        result = "查無相關文章"
    return result 
    
@tool
def should_continue(state: AgentState) -> Literal["GraphRAG","__end__"]:
    """
    Defined the condition to continue the workflow.
    """
    if state['FactChecked'] == True:
        return "__end__"
    else:
        return "GraphRAG"
    
graphrag_agent = create_react_agent(
    model=llm_gemini,  
    tools=[graphrag_tool], 
    name="graphrag_agent",
    prompt=
    """
    Role:
        You are a medical expert providing information about medical knowledge.
    Task:
        Your main task is to use the provided tool to search for answers whenever you receive a user inquiry, and return the search results.
    Specific Requirements:
        **Prohibitions**:
            1.Languages other than Traditional Chinese are not allowed
            2. Do not use pre-trained knowledge, only use the information provided in the context.
    """
    
)

fact_check_agent = create_react_agent(
    model=llm_gemini,
    tools=[google_fact_check_tool], 
    name="fact_check_agent",
    prompt=
    """
    Role:
        You are a fact-checking expert.
    Task:
        Your main task is to fact-check claims using the provided tool and return the results.
    Specific Requirements:
        **Prohibitions**:   
            1. Languages ​​other than Traditional Chinese are not allowed
            2. Do not use pre-trained knowledge, only use the information provided in the context.
            3. Only use the provided tool to fact-check claims, do not use any other methods.
    """
    )

cofact_agent = create_react_agent(
    model=llm_gemini,
    tools=[cofacts_tool],
    name="cofacts_agent",   
    prompt=
    """
    Role:
        You are a fact-checking expert.
    Task:
        Your main task is to fact-check claims using the provided tool and return the results.
    Specific Requirements:
        **Prohibitions**:   
            1. Languages ​​other than Traditional Chinese are not allowed
            2. Do not use pre-trained knowledge, only use the information provided in the context.
            3. Only use the provided tool to fact-check claims, do not use any other methods.     
    """
)    


supervisor = create_supervisor(
    agents=[graphrag_agent, fact_check_agent,cofact_agent],
    tools=[should_continue],
    model=llm_gemini,
    prompt=(
        """
        You are a supervisor who manages multiple agents.
        First,you need to use the `graphrag_agent` to answer medical questions.
        Second, you need to use the `fact_check_agent` to check the user query for factual accuracy.
        Third, you need to use the `cofacts_agent` to check the user query for factual accuracy.
        Last,you need to `fact_check_agent` and `graphrag_agent` and 'cofact_agent'respond to user.
        """
    )
)


# Compile and run
app = supervisor.compile(checkpointer=memory)
config = {"configurable": {"thread_id": "1"}}
while True:
    message=HumanMessage(content=input("輸入你的問題: "))
    result = app.invoke(input={'messages':message},config=config)
    for m in result["messages"]:
        m.pretty_print()