from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langchain_core.tools import tool
from research import graph_rag
from fact_check import search_fact_checks
from llm import llm_GPT, llm_gemini
import langchain
langchain.cache = None

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
    #print(f"Graph RAG result: {result}")
    result = graph_rag(input=query)
    return result

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
            result += "查維相關審查結果\n"
    
    return result


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
            1.Languages ​​other than Traditional Chinese are not allowed
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
    """
    )
    


supervisor = create_supervisor(
    agents=[graphrag_agent, fact_check_agent],
    model=llm_gemini,
    prompt=(
        """
        You are a supervisor who manages multiple agents.
        First,you need to use the `graphrag_agent` to answer medical questions.
        then, you need to use the `fact_check_agent` to check the user query for factual accuracy.
        Lastlt,you need to tell anout `fact_check_agent` and `graphrag_agent` both answer to  user.
        """
    )
)


# Compile and run
app = supervisor.compile()
result = app.invoke({
    "messages": [
        {
            "role": "user",
            "content": "糖尿病可以吃甜食嗎?"
        }
    ]
})

for m in result["messages"]:
    m.pretty_print()