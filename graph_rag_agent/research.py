
from neo4j import GraphDatabase
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from vertexai.generative_models import GenerationConfig
from neo4j_graphrag.llm.vertexai_llm import VertexAILLM
from neo4j_graphrag.indexes import create_vector_index
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.retrievers import VectorCypherRetriever
from neo4j_graphrag.generation import RagTemplate
from neo4j_graphrag.generation.graphrag import GraphRAG
from neo4j_graphrag.llm import OpenAILLM
import os
from dotenv import load_dotenv



load_dotenv()
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE= os.getenv("NEO4J_DATABASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")


driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD),database=NEO4J_DATABASE)
embedder = OpenAIEmbeddings(model="text-embedding-ada-002", api_key=OPENAI_API_KEY)
gen_config=GenerationConfig(temperature=0,response_mime_type="application/json")
llm = OpenAILLM(model_name='gpt-4.1-mini',model_params={'temperature':0,"response_format": {"type": "json_object"}})


create_vector_index(driver, name="text_embeddings", label="Chunk",
                   embedding_property="embedding", dimensions=1536, similarity_fn="cosine")


vc_retriever = VectorCypherRetriever(
   driver,
   index_name="text_embeddings",
   embedder=embedder,
   
   retrieval_query="""
//1) Go out 2-3 hops in the entity graph and get relationships
WITH node AS chunk
MATCH (chunk)<-[:FROM_CHUNK]-()-[relList:!FROM_CHUNK]-{1,2}()
UNWIND relList AS rel

//2) collect relationships and text chunks
WITH collect(DISTINCT chunk) AS chunks,
 collect(DISTINCT rel) AS rels

//3) format and return context
RETURN '=== text ===n' + apoc.text.join([c in chunks | c.text], 'n---n') + 'nn=== kg_rels ===n' +
 apoc.text.join([r in rels | startNode(r).name + ' - ' + type(r) + '(' + coalesce(r.details, '') + ')' +  ' -> ' + endNode(r).name ], 'n---n') AS info
"""
)

rag_template = RagTemplate(template=
'''
Answer the Question using the following Context. 
To answer the question, you must follow these rules: 
```
Focus on providing useful information for elders.
List all imformation may with answer the question as much as you can.
response should be in Traditional Chinese.
response should be in JSON format.
response should be detailed and relevant to the question.
Only respond with information mentioned in the Context.
Don't use your pre-trained knowledge.
If you are not sure about the answer, just say "I do not know the answer, please use another tool."
```
# Question:
{query_text}

# Context:
{context}

# Answer:
''', system_instructions="You are an expert in medcial field, your goal is provide imformation for elders using Neo4j.",expected_inputs=['query_text', 'context'])

rag  = GraphRAG(llm=llm, retriever=vc_retriever, prompt_template=rag_template)

def graph_rag(input:str):
   
   vc_res = vc_retriever.get_search_results(query_text=input, top_k=3)
   kg_rel_pos = vc_res.records[0]['info'].find('nn=== kg_rels ===n')
    
    
   kg_result_chunk = vc_res.records[0]['info'][:kg_rel_pos]
   kg_result_relationships = vc_res.records[0]['info'][kg_rel_pos+len('nn=== kg_rels ===n'):]  
    
    # RAG answer
   result = rag.search(input, retriever_config={'top_k':5})
    
    # 整理輸出
   #answer_with_source = f"{result.answer}\n資料來源:\n{kg_result_chunk}{kg_result_relationships}"
   answer_with_source = result.answer
   return answer_with_source
if __name__ == "__main__":
      # 測試輸入
      test_input = "糖尿病可以吃甜食嗎?"
      answer = graph_rag(test_input)
      print("RAG Answer:", answer)
      
    

