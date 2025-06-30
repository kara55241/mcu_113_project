from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from langgraph_supervisor import create_supervisor
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from langchain_core.tools import tool
from graph_rag import graphrag_chronic,graphrag_cardiovascular
from fact_check import search_fact_checks
from cofacts_check import search_cofacts
from langchain_core.messages import HumanMessage
from llm import llm_gemini
from langchain_tavily import TavilySearch
conn = sqlite3.connect("mcu_113_project/agent_checkpoint.sqlite", check_same_thread=False)
memory=SqliteSaver(conn)
class State(AgentState):
    summary: dict[str,any]

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
    tools=[net_search], 
    name="chronic_agent",
    prompt=
    """
    Role:
        You are a medical expert providing information about medical knowledge.
    Task:
        Your main task is to use the provided tool to search for answers whenever you receive a user inquiry about chronic, and return the search results.
    Specific Requirements:
        **Prohibitions**:
            1.Languages other than Traditional Chinese are not allowed
            2. Do not use pre-trained knowledge, only use the information provided in the context.
            3. add source(the tool you used) at the end of your response.
    """
)

cardiovascular_agent = create_react_agent(
    model=llm_gemini,  
    tools=[cardiovascular_search,net_search], 
    name="cardiovascular_agent",
    prompt=
    """
    Role:
        You are a medical expert providing information about medical knowledge.
    Task:
        Your main task is to use the provided tool to search for answers whenever you receive a user inquiry about cardiovascular, and return the search results.
    Specific Requirements:
        **Prohibitions**:
            1.Languages other than Traditional Chinese are not allowed
            2. Do not use pre-trained knowledge, only use the information provided in the context.
            3. add source(the tool you used) at the end of your response.
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
    Rules:
        **Prohibitions**:   
            1. Languages ​​other than Traditional Chinese are not allowed
            2. Do not use pre-trained knowledge, only use the information provided in the context.
            3. Only use the provided tool to fact-check claims, do not use any other methods.
    """
    )
    


supervisor = create_supervisor(
    agents=[chronic_agent, cardiovascular_agent,fact_check_agent],
    tools=[],
    model=llm_gemini,
    prompt=(
        """
        Role:
        You are the central coordinator (Supervisor) for a smart health consultation system. 
        Your main responsibility is to precisely understand the user's health query and route it to the most suitable specialized agent for handling that specific problem.

        Available Agents / Tools and Their Calling Conditions:

        chronic_Agent:

        Calling Condition: 
        Invoke when the user asks questions related to general chronic diseases (e.g., diabetes, hypertension, chronic kidney disease, osteoporosis, gout, thyroid conditions) concerning their definition, symptoms, prevention, diet, lifestyle management, or general medication principles.

        cardiovascular_Agent:

        Calling Condition: 
        Invoke when the user asks questions specifically related to heart and vascular system diseases (e.g., heart disease, stroke, myocardial infarction, arrhythmia, coronary artery disease, hyperlipidemia if strongly linked to cardiovascular risk, thrombosis) concerning their symptoms, risks, initial emergency assessment, or directly related cardiovascular health advice (diet/exercise).

        fact_check_agent:

        Calling Condition: 
        Invoke when the user explicitly expresses doubt about the truthfulness of certain health information (e.g., "Is this true?", "Is this statement correct?", "I heard that... is that right?"), or when asking for the definition or source of a health concept.
        """
    )
)

# Compile and run

app = supervisor.compile(checkpointer=memory)
config = {"configurable": {"thread_id": "1"}}
while True:
    message=HumanMessage(content=input("輸入你的問題: "))
    for chunk,metadata in app.stream(input={'messages':message},config=config,stream_mode='messages'):
        print(chunk.content)
