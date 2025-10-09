from neo4j import GraphDatabase
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from neo4j_graphrag.indexes import create_vector_index
from neo4j_graphrag.retrievers import VectorCypherRetriever
from neo4j_graphrag.generation import RagTemplate
from neo4j_graphrag.generation.graphrag import GraphRAG
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.llm import OpenAILLM
import os
import re
from dotenv import load_dotenv
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
chronic= os.getenv("NEO4J_CHRONIC")
cardiovascular=os.getenv("NEO4J_CARDIOVASCULAR")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
embedder = OpenAIEmbeddings(model="text-embedding-ada-002", api_key=OPENAI_API_KEY)
llm = OpenAILLM(model_name='gpt-4.1-mini',model_params={'temperature':0})



create_vector_index(driver, name="text_embeddings", label="Chunk",
                   embedding_property="embedding", dimensions=1536, similarity_fn="cosine",neo4j_database=cardiovascular)



cardiovascular_retriever = VectorCypherRetriever(
   driver,
   index_name="text_embeddings",
   embedder=embedder,
   retrieval_query="""
//1) Go out 2-3 hops in the entity graph and get relationships
WITH node AS chunk
MATCH (chunk)<-[:FROM_CHUNK]-()-[relList:!FROM_CHUNK]-{1,1}()
UNWIND relList AS rel

//2) collect relationships and text chunks
WITH collect(DISTINCT chunk) AS chunks,
 collect(DISTINCT rel) AS rels

//3) format and return context
RETURN '=== text ===n' + apoc.text.join([c in chunks | c.text], 'n---n') + 'nn=== kg_rels ===n' +
 apoc.text.join([r in rels | startNode(r).name + ' - ' + type(r) + '(' + coalesce(r.details, '') + ')' +  ' -> ' + endNode(r).name ], 'n---n') AS info
""",
neo4j_database=cardiovascular)

cardiovascular_retriever_graph = VectorCypherRetriever(
   driver,
   index_name="text_embeddings",
   embedder=embedder,
   retrieval_query="""
//1) Go out 2-3 hops in the entity graph and get relationships
WITH node AS chunk
MATCH (chunk)<-[:FROM_CHUNK]-()-[relList:!FROM_CHUNK]-{1,1}()
UNWIND relList AS rel

//2) collect relationships and text chunks
WITH collect(DISTINCT chunk) AS chunks,
 collect(DISTINCT rel) AS rels

//3) format and return context
RETURN '\n=== 第一篇如下 ===\n' +
       apoc.text.join([c in chunks | 'id = ' + toString(Id(c)) + '|' + c.text], '\n---\n')
       + '\n 本篇圖譜關係式如下: \n' +
       apoc.text.join([r in rels | startNode(r).name + '**' + type(r) + '**' + endNode(r).name],'     ')
                     + '\n--  這是下一篇  --\n' AS info
""",neo4j_database=cardiovascular)

vector_retriever = VectorRetriever(
   driver,
   index_name="text_embeddings",
   embedder=embedder,
   return_properties=None,
   neo4j_database=cardiovascular
)
rag_template = RagTemplate(template=
'''
Answer the Question using the following Context. 
To answer the question, you must follow these rules: 
```
Focus on providing useful information for elders.
response should be in Traditional Chinese.
response should be in plain text.
response should be detailed and relevant to the question.
Only respond with information mentioned in the Context.
Don't use your pre-trained knowledge.
If you are not sure about the answer, just say "I do not know the answer, please use another tool."
"
```
# Question:
{query_text}

# Context:
{context}

# Answer:
''', system_instructions="You are an expert in medcial field, your goal is provide imformation for elders using Neo4j.",expected_inputs=['query_text', 'context'])


cardiovascular_rag=GraphRAG(llm=llm, retriever=cardiovascular_retriever, prompt_template=rag_template)
vector_rag=GraphRAG(llm=llm, retriever=vector_retriever, prompt_template=rag_template)

def graphrag_cardiovascular(input: str):
   
   vc_res = cardiovascular_retriever_graph.get_search_results(query_text=input, top_k=1)
   
    # 取出第一筆 record 的 info 字串
   records = getattr(vc_res, "records", None)
   if not records or len(records) == 0:
        return []

   first = records[0]
   info = first.get('info') if isinstance(first, dict) else first['info']

   
   print("info:")
   print(info)        

   

   return cardiovascular_rag.search(input, retriever_config={'top_k':1}).answer

def graphrag_vector(input: str):
   """
   vc_res = cardiovascular_retriever_graph.get_search_results(query_text=input, top_k=1)
   
    # 取出第一筆 record 的 info 字串
   records = getattr(vc_res, "records", None)
   if not records or len(records) == 0:
        return []

   first = records[0]
   info = first.get('info') if isinstance(first, dict) else first['info']

   
   print("info:")
   print(info)        

   """

   return vector_rag.search(input, retriever_config={'top_k':1}).answer

if __name__ == "__main__":
      # 測試輸入
      test_input = """請列出與『糖尿病』直接相關的疾病或風險因子。"""
      answer =graphrag_cardiovascular(test_input)
      #answer =graphrag_vector(test_input)
      print("RAG Answer:", answer)
      
    


