from neo4j import GraphDatabase
from neo4j_graphrag.embeddings import OpenAIEmbeddings
from neo4j_graphrag.indexes import create_vector_index
from neo4j_graphrag.retrievers import VectorCypherRetriever
from neo4j_graphrag.generation import RagTemplate
from neo4j_graphrag.generation.graphrag import GraphRAG
from neo4j_graphrag.llm import OpenAILLM
import os
import json
import re
from typing import Dict, List, Tuple
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
llm = OpenAILLM(model_name='gpt-4.1-mini-2025-04-14', model_params={'temperature':0, "response_format": {"type": "json_object"}})

create_vector_index(driver, name="text_embeddings", label="Chunk",
                   embedding_property="embedding", dimensions=1536, similarity_fn="cosine",neo4j_database=chronic)

create_vector_index(driver, name="text_embeddings", label="Chunk",
                   embedding_property="embedding", dimensions=1536, similarity_fn="cosine",neo4j_database=cardiovascular)

chronic_retriever = VectorCypherRetriever(
   driver,
   index_name="text_embeddings",
   embedder=embedder,
   retrieval_query="""
// 1) 從向量索引匹配的 chunk 找到連接的實體節點
WITH node AS chunk
MATCH (chunk)<-[:FROM_CHUNK]-(entity)
WHERE NOT entity:Chunk

// 2) 從實體擴展 1-2 跳關係網絡（排除 Chunk 節點和 FROM_CHUNK 關係）
MATCH path = (entity)-[*1..2]-(connected)
WHERE NOT connected:Chunk
  AND ALL(n IN nodes(path) WHERE NOT n:Chunk)
  AND NONE(r IN relationships(path) WHERE type(r) = 'FROM_CHUNK')

// 3) 收集並去重 chunks 和路徑關係
WITH collect(DISTINCT chunk) AS chunks,
     collect(path) AS all_paths

// 4) 展開路徑，提取所有關係
UNWIND all_paths AS p
WITH chunks, collect(DISTINCT relationships(p)) AS path_rels

// 5) 展平嵌套的關係列表並去重
UNWIND path_rels AS rel_list
UNWIND rel_list AS r
WITH chunks, collect(DISTINCT r) AS rels

// 6) 格式化返回上下文（文本 + 知識圖譜關係）
RETURN '=== text ===\\n' +
       apoc.text.join([c in chunks | c.text], '\\n---\\n') +
       '\\n\\n=== kg_rels ===\\n' +
       apoc.text.join([rel in rels |
         startNode(rel).name + ' - ' + type(rel) +
         '(' + coalesce(rel.details, '') + ')' +
         ' -> ' + endNode(rel).name
       ], '\\n---\\n') AS info
""",
   neo4j_database=chronic)

cardiovascular_retriever = VectorCypherRetriever(
   driver,
   index_name="text_embeddings",
   embedder=embedder,
   retrieval_query="""
// 1) 從向量索引匹配的 chunk 找到連接的實體節點
WITH node AS chunk
MATCH (chunk)<-[:FROM_CHUNK]-(entity)
WHERE NOT entity:Chunk

// 2) 從實體擴展 1-2 跳關係網絡（排除 Chunk 節點和 FROM_CHUNK 關係）
MATCH path = (entity)-[*1..2]-(connected)
WHERE NOT connected:Chunk
  AND ALL(n IN nodes(path) WHERE NOT n:Chunk)
  AND NONE(r IN relationships(path) WHERE type(r) = 'FROM_CHUNK')

// 3) 收集並去重 chunks 和路徑關係
WITH collect(DISTINCT chunk) AS chunks,
     collect(path) AS all_paths

// 4) 展開路徑，提取所有關係
UNWIND all_paths AS p
WITH chunks, collect(DISTINCT relationships(p)) AS path_rels

// 5) 展平嵌套的關係列表並去重
UNWIND path_rels AS rel_list
UNWIND rel_list AS r
WITH chunks, collect(DISTINCT r) AS rels

// 6) 格式化返回上下文（文本 + 知識圖譜關係）
RETURN '=== text ===\\n' +
       apoc.text.join([c in chunks | c.text], '\\n---\\n') +
       '\\n\\n=== kg_rels ===\\n' +
       apoc.text.join([rel in rels |
         startNode(rel).name + ' - ' + type(rel) +
         '(' + coalesce(rel.details, '') + ')' +
         ' -> ' + endNode(rel).name
       ], '\\n---\\n') AS info
""",
   neo4j_database=cardiovascular)

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

chronic_rag  = GraphRAG(llm=llm, retriever=chronic_retriever, prompt_template=rag_template)
cardiovascular_rag=GraphRAG(llm=llm, retriever=cardiovascular_retriever, prompt_template=rag_template)


# 用於獲取完整圖譜數據的 retriever（慢性疾病）
graph_data_retriever_chronic = VectorCypherRetriever(
    driver,
    index_name="text_embeddings",
    embedder=embedder,
    retrieval_query="""
// 1) 從向量索引匹配到的 chunk 開始
WITH node AS chunk

// 2) 找到連接到 chunk 的實體節點（排除 Chunk 類型）
MATCH (chunk)<-[:FROM_CHUNK]-(entity)
WHERE NOT entity:Chunk

// 3) 從實體出發，擴展關係網絡（1-2 跳）
MATCH path = (entity)-[*1..2]-(connected)
WHERE NOT connected:Chunk
  AND ALL(n IN nodes(path) WHERE NOT n:Chunk)  // 確保路徑中沒有 Chunk 節點
  AND NONE(r IN relationships(path) WHERE type(r) = 'FROM_CHUNK')  // 排除 FROM_CHUNK 關係

// 4) 收集路徑和關係
WITH collect(DISTINCT chunk) AS chunks,
     collect(path) AS all_paths

// 5) 展開路徑，提取關係
UNWIND all_paths AS p
WITH chunks, collect(DISTINCT relationships(p)) AS path_rels

// 6) 展平嵌套的關係列表
UNWIND path_rels AS rel_list
UNWIND rel_list AS r
WITH chunks, collect(DISTINCT r) AS all_relationships

// 7) 從關係中提取節點（確保只收集有關係的節點）
WITH chunks, all_relationships,
     apoc.coll.toSet(
         [rel IN all_relationships | startNode(rel)] +
         [rel IN all_relationships | endNode(rel)]
     ) AS all_entities

// 8) 過濾孤立節點（度數 = 0），保留所有有連接的節點
WITH chunks, all_relationships,
     [e IN all_entities WHERE
       size([rel IN all_relationships WHERE
         startNode(rel) = e OR endNode(rel) = e
       ]) >= 1
     ] AS filtered_entities

// 9) 格式化返回（再次確保沒有 Chunk 節點）
RETURN
  [e IN filtered_entities WHERE NOT e:Chunk | {
      id: elementId(e),
      labels: labels(e),
      properties: properties(e)
  }] AS nodes,
  [rel IN all_relationships WHERE
    startNode(rel) IN filtered_entities AND
    endNode(rel) IN filtered_entities AND
    type(rel) <> 'FROM_CHUNK'  // 再次確保沒有 FROM_CHUNK 關係
  | {
      id: elementId(rel),
      type: type(rel),
      startNode: elementId(startNode(rel)),
      endNode: elementId(endNode(rel)),
      properties: properties(rel)
  }] AS rels,
  [c IN chunks | {
      text: c.text,
      id: elementId(c)
  }] AS chunks
""",
    neo4j_database=chronic
)

# 用於獲取完整圖譜數據的 retriever（心血管疾病）
graph_data_retriever_cardiovascular = VectorCypherRetriever(
    driver,
    index_name="text_embeddings",
    embedder=embedder,
    retrieval_query="""
// 1) 從向量索引匹配到的 chunk 開始
WITH node AS chunk

// 2) 找到連接到 chunk 的實體節點（排除 Chunk 類型）
MATCH (chunk)<-[:FROM_CHUNK]-(entity)
WHERE NOT entity:Chunk

// 3) 從實體出發，擴展關係網絡（1-2 跳）
MATCH path = (entity)-[*1..2]-(connected)
WHERE NOT connected:Chunk
  AND ALL(n IN nodes(path) WHERE NOT n:Chunk)  // 確保路徑中沒有 Chunk 節點
  AND NONE(r IN relationships(path) WHERE type(r) = 'FROM_CHUNK')  // 排除 FROM_CHUNK 關係

// 4) 收集路徑和關係
WITH collect(DISTINCT chunk) AS chunks,
     collect(path) AS all_paths

// 5) 展開路徑，提取關係
UNWIND all_paths AS p
WITH chunks, collect(DISTINCT relationships(p)) AS path_rels

// 6) 展平嵌套的關係列表
UNWIND path_rels AS rel_list
UNWIND rel_list AS r
WITH chunks, collect(DISTINCT r) AS all_relationships

// 7) 從關係中提取節點（確保只收集有關係的節點）
WITH chunks, all_relationships,
     apoc.coll.toSet(
         [rel IN all_relationships | startNode(rel)] +
         [rel IN all_relationships | endNode(rel)]
     ) AS all_entities

// 8) 過濾孤立節點（度數 = 0），保留所有有連接的節點
WITH chunks, all_relationships,
     [e IN all_entities WHERE
       size([rel IN all_relationships WHERE
         startNode(rel) = e OR endNode(rel) = e
       ]) >= 1
     ] AS filtered_entities

// 9) 格式化返回（再次確保沒有 Chunk 節點）
RETURN
  [e IN filtered_entities WHERE NOT e:Chunk | {
      id: elementId(e),
      labels: labels(e),
      properties: properties(e)
  }] AS nodes,
  [rel IN all_relationships WHERE
    startNode(rel) IN filtered_entities AND
    endNode(rel) IN filtered_entities AND
    type(rel) <> 'FROM_CHUNK'  // 再次確保沒有 FROM_CHUNK 關係
  | {
      id: elementId(rel),
      type: type(rel),
      startNode: elementId(startNode(rel)),
      endNode: elementId(endNode(rel)),
      properties: properties(rel)
  }] AS rels,
  [c IN chunks | {
      text: c.text,
      id: elementId(c)
  }] AS chunks
""",
    neo4j_database=cardiovascular
)
def graphrag_chronic(input: str, return_graph_data: bool = True):
    """
    查詢慢性疾病知識圖譜

    Args:
        input: 用戶查詢問題
        return_graph_data: 是否返回完整圖譜數據（默認 True）

    Returns:
        如果 return_graph_data=True:
            dict: {"answer": str, "graph_data": {...}}
        否則:
            str: 僅返回答案文本（向後兼容）
    """
    # 統一 top_k 配置（增加以獲取更多相關 chunks）
    TOP_K = 10

    # 獲取 RAG 答案
    result = chronic_rag.search(input, retriever_config={'top_k': TOP_K})
    answer = result.answer

    # 如果不需要圖譜數據，直接返回答案（向後兼容）
    if not return_graph_data:
        return answer

    # 使用專門的 graph_data_retriever 獲取結構化圖譜數據
    try:
        graph_result = graph_data_retriever_chronic.get_search_results(
            query_text=input,
            top_k=TOP_K  # 與 RAG 保持一致
        )

        graph_data = {
            "nodes": [],
            "relationships": [],
            "chunks": []
        }

        # 直接使用 Neo4j 返回的結構化數據（無需解析）
        if graph_result.records and len(graph_result.records) > 0:
            record = graph_result.records[0].data()
            graph_data = {
                "nodes": record.get('nodes', []),
                "relationships": record.get('rels', []),
                "chunks": record.get('chunks', [])
            }

        return {
            "answer": answer,
            "graph_data": graph_data,
            "database": f"{chronic}"
        }

    except Exception as e:
        # 如果圖譜數據獲取失敗，仍返回答案
        print(f"Warning: Failed to retrieve graph data: {e}")
        import traceback
        traceback.print_exc()
        return {
            "answer": answer,
            "graph_data": {"nodes": [], "relationships": [], "chunks": []},
            "database": f"{chronic}",
            "error": str(e)
        }


def graphrag_cardiovascular(input: str, return_graph_data: bool = True):
    """
    查詢心血管疾病知識圖譜

    Args:
        input: 用戶查詢問題
        return_graph_data: 是否返回完整圖譜數據（默認 True）

    Returns:
        如果 return_graph_data=True:
            dict: {"answer": str, "graph_data": {...}}
        否則:
            str: 僅返回答案文本（向後兼容）
    """
    # 統一 top_k 配置（增加以獲取更多相關 chunks）
    TOP_K = 10

    # 獲取 RAG 答案
    result = cardiovascular_rag.search(input, retriever_config={'top_k': TOP_K})
    answer = result.answer

    # 如果不需要圖譜數據，直接返回答案（向後兼容）
    if not return_graph_data:
        return answer

    # 使用專門的 graph_data_retriever 獲取結構化圖譜數據
    try:
        graph_result = graph_data_retriever_cardiovascular.get_search_results(
            query_text=input,
            top_k=TOP_K  # 與 RAG 保持一致
        )

        graph_data = {
            "nodes": [],
            "relationships": [],
            "chunks": []
        }

        # 直接使用 Neo4j 返回的結構化數據（無需解析）
        if graph_result.records and len(graph_result.records) > 0:
            record = graph_result.records[0].data()
            graph_data = {
                "nodes": record.get('nodes', []),
                "relationships": record.get('rels', []),
                "chunks": record.get('chunks', [])
            }

        return {
            "answer": answer,
            "graph_data": graph_data,
            "database": f"{cardiovascular}"
        }

    except Exception as e:
        # 如果圖譜數據獲取失敗，仍返回答案
        print(f"Warning: Failed to retrieve graph data: {e}")
        import traceback
        traceback.print_exc()
        return {
            "answer": answer,
            "graph_data": {"nodes": [], "relationships": [], "chunks": []},
            "database": f"{cardiovascular}",
            "error": str(e)
        }


if __name__ == "__main__":
      # 測試輸入
      test_input = "糖尿病可以吃甜食嗎?"
      result = graphrag_chronic(test_input, return_graph_data=True)
      print("RAG Answer:", result.get('answer'))
      print("\nGraph Data:")
      print(f"  Nodes: {len(result.get('graph_data', {}).get('nodes', []))}")
      print(f"  Relationships: {len(result.get('graph_data', {}).get('relationships', []))}")
      print(f"  Chunks: {len(result.get('graph_data', {}).get('chunks', []))}")
      
    


