# graph_rag.py - 修正版本，移除強制JSON格式

from neo4j import GraphDatabase
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from neo4j_graphrag.indexes import create_vector_index
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
chronic= os.getenv("NEO4J_CHRONIC")
cardiovascular=os.getenv("NEO4J_CARDIOVASCULAR")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
embedder = OpenAIEmbeddings(model="text-embedding-ada-002", api_key=OPENAI_API_KEY)

# 🔧 修正：移除強制 JSON 格式，改為自然文字回應
llm = OpenAILLM(
    model_name='gpt-4.1-mini',
    model_params={'temperature': 0}  # 移除 JSON 格式限制
)

create_vector_index(driver, name="text_embeddings", label="Chunk",
                   embedding_property="embedding", dimensions=1536, similarity_fn="cosine",neo4j_database=chronic)

create_vector_index(driver, name="text_embeddings", label="Chunk",
                   embedding_property="embedding", dimensions=1536, similarity_fn="cosine",neo4j_database=cardiovascular)

chronic_retriever = VectorCypherRetriever(
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
""",
neo4j_database=chronic)

cardiovascular_retriever = VectorCypherRetriever(
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
""",
neo4j_database=chronic)

# 🔧 修正：簡化 RAG 模板，避免 JSON 格式要求
rag_template = RagTemplate(
    template='''
請根據以下資料回答問題，並遵循這些規則：
- 專注於為長輩提供有用的資訊
- 使用繁體中文回答
- 提供詳細且相關的回答
- 只根據提供的資料回答，不要使用預訓練知識
- 如果不確定答案，請說"我無法根據現有資料回答，請使用其他工具"
- 回答格式應該清晰易懂，使用適當的段落和重點標示

問題：{query_text}

資料來源：
{context}

回答：
''', 
    system_instructions="您是醫療領域專家，專門為長輩提供健康資訊。",
    expected_inputs=['query_text', 'context']
)

chronic_rag  = GraphRAG(llm=llm, retriever=chronic_retriever, prompt_template=rag_template)
cardiovascular_rag=GraphRAG(llm=llm, retriever=cardiovascular_retriever, prompt_template=rag_template)

def graphrag_chronic(input:str):
    """慢性病知識圖譜查詢"""
    try:
        result = chronic_rag.search(input, retriever_config={'top_k':5})
        return result.answer
    except Exception as e:
        return f"慢性病知識圖譜查詢失敗：{str(e)}"

def graphrag_cardiovascular(input: str):
    """心血管疾病知識圖譜查詢"""
    try:
        result = cardiovascular_rag.search(input, retriever_config={'top_k':5})
        return result.answer
    except Exception as e:
        return f"心血管疾病知識圖譜查詢失敗：{str(e)}"
