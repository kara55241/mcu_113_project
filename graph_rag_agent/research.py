from neo4j import GraphDatabase
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from vertexai.generative_models import GenerationConfig
from neo4j_graphrag.llm.vertexai_llm import VertexAILLM
from neo4j_graphrag.indexes import create_vector_index
from neo4j_graphrag.retrievers import VectorRetriever
from neo4j_graphrag.generation import RagTemplate
from neo4j_graphrag.generation.graphrag import GraphRAG
from neo4j_graphrag.llm import OpenAILLM
import os

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE= os.getenv("NEO4J_DATABASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")


driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD),database=NEO4J_DATABASE)
embedder = OpenAIEmbeddings(model="text-embedding-ada-002", api_key=OPENAI_API_KEY)
gen_config=GenerationConfig(temperature=0,response_mime_type="application/json")
llm = OpenAILLM(model_name='gpt-4.1-nano',model_params={'temperature':0,"response_format": {"type": "json_object"}})


create_vector_index(driver, name="text_embeddings", label="Chunk",
                   embedding_property="embedding", dimensions=1536, similarity_fn="cosine")


vector_retriever = VectorRetriever(
   driver,
   index_name="text_embeddings",
   embedder=embedder,
   return_properties=["text"],
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

rag  = GraphRAG(llm=llm, retriever=vector_retriever, prompt_template=rag_template)

def graph_rag(input:str):
   result = rag.search(input, retriever_config={'top_k':5})
   return result.answer



