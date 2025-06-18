from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langchain_core.tools import tool
from research import graph_rag
from llm import llm_GPT, llm_gemini
import langchain
langchain.cache = None

@tool
def graphrag_tool(query: str) -> str:
    """
    You MUST use this tool when the user asks a medical question.
    This tool queries a medical knowledge graph to retrieve and generate answers.

    Args:
        query: The medical question or statement to be answered.

    Returns:
        A comprehensive answer based on the medical knowledge graph.
    """
    result = graph_rag(query)
    print(f"graph_rag result: {result}")
    return result
def co

grahrag_agent = create_react_agent(
    model=llm_gemini,  
    tools=[graphrag_tool], 
    name="graph_rag_agent",
    prompt=
    """
    Role:
        You are a medical expert providing information about medical knowledge.
    Task:
        Your main task is to use the provided tool to search for answers whenever you receive a user inquiry, and return the search results.
    Specific Requirements:
        **Prohibitions**:
            1.Languages ​​other than Traditional Chinese are not allowed
            2. Do not use pre-trained knowledge, only use the information provided in the context.
    """
    
)

googel_serch_agent = create_react_agent(
    model=llm_gemini,
    tools=[SearchTools.Google_Search], 
    )
    


supervisor = create_supervisor(
    agents=[grahrag_agent],
    model=llm_gemini,
    prompt=(
        """
        You are a supervisor for a medical knowledge retrieval agent.
        Your role is to ensure that the agent uses the graphrag_tool correctly and efficiently.
        If the agent fails to use the tool or provides an incorrect response, you should guide it to correct its approach.
        """
    )
).compile()


for chunk in supervisor.stream(
    {
        "messages": [
            {
                "role": "user",
                "content": "我最近肚子痛，請問可能是什麼原因？"
            }
        ]
    }
):
    print(chunk)
    print("\n")