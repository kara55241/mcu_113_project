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
llm = OpenAILLM(model_name='gpt-4.1-mini',model_params={'temperature':0,"response_format": {"type": "json_object"}})

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


def parse_kg_relations_to_graph(kg_text: str) -> Dict[str, List]:
    """
    解析 knowledge graph 關係文本為結構化的圖譜數據

    輸入格式範例：
    "實體A - 關係類型(詳情) -> 實體B
    ---
    實體C - 關係類型() -> 實體D"

    Returns:
        Dict包含 nodes (節點列表) 和 relationships (關係列表)
    """
    nodes_dict = {}  # {node_name: node_obj}
    relationships = []
    node_id_counter = 1000  # 起始 ID
    rel_id_counter = 2000

    if not kg_text or kg_text.strip() == '':
        return {"nodes": [], "relationships": []}

    # 分割每一行關係 (處理 'n' 作為換行符的情況)
    lines = kg_text.split('n---n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # 解析格式：實體A - 關係類型(詳情) -> 實體B
        # 使用正則表達式匹配
        pattern = r'(.+?)\s*-\s*(.+?)\(([^)]*)\)\s*->\s*(.+)'
        match = re.match(pattern, line)

        if match:
            source_name = match.group(1).strip()
            rel_type = match.group(2).strip()
            rel_details = match.group(3).strip()
            target_name = match.group(4).strip()

            # 創建源節點（如果不存在）
            if source_name not in nodes_dict:
                nodes_dict[source_name] = {
                    "id": node_id_counter,
                    "labels": ["Entity"],  # 默認標籤
                    "properties": {"name": source_name}
                }
                node_id_counter += 1

            # 創建目標節點（如果不存在）
            if target_name not in nodes_dict:
                nodes_dict[target_name] = {
                    "id": node_id_counter,
                    "labels": ["Entity"],
                    "properties": {"name": target_name}
                }
                node_id_counter += 1

            # 創建關係
            relationship = {
                "id": str(rel_id_counter),
                "type": rel_type,
                "startNode": nodes_dict[source_name]["id"],
                "endNode": nodes_dict[target_name]["id"],
                "properties": {"details": rel_details} if rel_details else {}
            }
            relationships.append(relationship)
            rel_id_counter += 1

    return {
        "nodes": list(nodes_dict.values()),
        "relationships": relationships
    }
# 用於獲取完整圖譜數據的 retriever（慢性疾病）
graph_data_retriever_chronic = VectorCypherRetriever(
    driver,
    index_name="text_embeddings",
    embedder=embedder,
    retrieval_query="""
// 1) 從向量索引匹配到的 chunk 開始
WITH node AS chunk

// 2) 找到連接的實體和關係（2-3 跳）
MATCH (chunk)<-[:FROM_CHUNK]-(entity)-[rel*1..2]-(connected)
WHERE NOT connected:Chunk

// 3) 展開路徑以獲取所有節點和關係
WITH chunk, entity, rel, connected
UNWIND rel AS r

// 4) 收集唯一的節點
WITH collect(DISTINCT chunk) AS chunks,
     collect(DISTINCT entity) + collect(DISTINCT connected) AS all_entities,
     collect(DISTINCT r) AS all_relationships

// 5) 準備節點數據
UNWIND all_entities AS e
WITH chunks,
     collect(DISTINCT {
         id: id(e),
         labels: labels(e),
         properties: properties(e)
     }) AS nodes,
     all_relationships

// 6) 準備關係數據
UNWIND all_relationships AS rel
WITH chunks, nodes,
     collect(DISTINCT {
         id: toString(id(rel)),
         type: type(rel),
         startNode: id(startNode(rel)),
         endNode: id(endNode(rel)),
         properties: properties(rel)
     }) AS relationships

// 7) 返回結果
RETURN nodes,
       relationships AS rels,
       [c IN chunks | {text: c.text, id: id(c)}] AS chunks
LIMIT 1
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

// 2) 找到連接的實體和關係（2-3 跳）
MATCH (chunk)<-[:FROM_CHUNK]-(entity)-[rel*1..2]-(connected)
WHERE NOT connected:Chunk

// 3) 展開路徑以獲取所有節點和關係
WITH chunk, entity, rel, connected
UNWIND rel AS r

// 4) 收集唯一的節點
WITH collect(DISTINCT chunk) AS chunks,
     collect(DISTINCT entity) + collect(DISTINCT connected) AS all_entities,
     collect(DISTINCT r) AS all_relationships

// 5) 準備節點數據
UNWIND all_entities AS e
WITH chunks,
     collect(DISTINCT {
         id: id(e),
         labels: labels(e),
         properties: properties(e)
     }) AS nodes,
     all_relationships

// 6) 準備關係數據
UNWIND all_relationships AS rel
WITH chunks, nodes,
     collect(DISTINCT {
         id: toString(id(rel)),
         type: type(rel),
         startNode: id(startNode(rel)),
         endNode: id(endNode(rel)),
         properties: properties(rel)
     }) AS relationships

// 7) 返回結果
RETURN nodes,
       relationships AS rels,
       [c IN chunks | {text: c.text, id: id(c)}] AS chunks
LIMIT 1
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
    # 獲取 RAG 答案
    result = chronic_rag.search(input, retriever_config={'top_k': 5})
    answer = result.answer

    # 如果不需要圖譜數據，直接返回答案（向後兼容）
    if not return_graph_data:
        return answer

    # 獲取圖譜數據：直接從 retriever 獲取原始檢索結果
    try:
        # 使用原始 chronic_retriever 獲取包含 kg_rels 的文本
        retrieval_result = chronic_retriever.get_search_results(
            query_text=input,
            top_k=3
        )

        graph_data = {
            "nodes": [],
            "relationships": [],
            "chunks": []
        }

        # 解析檢索結果
        if retrieval_result.records and len(retrieval_result.records) > 0:
            for record in retrieval_result.records:
                # Neo4j Record: 使用 .data() 方法或直接括號訪問
                record_data = record.data()
                info_text = record_data.get('info')
                if info_text:
                    # 檢查並分割文本和關係部分
                    # Note: Neo4j retriever returns text with 'n' as newline markers
                    if 'nn=== kg_rels ===n' in info_text:
                        parts = info_text.split('nn=== kg_rels ===n')

                        # 文本塊
                        if len(parts) > 0 and parts[0].startswith('=== text ===n'):
                            text_content = parts[0].replace('=== text ===n', '')
                            text_chunks = text_content.split('n---n')
                            for i, chunk_text in enumerate(text_chunks):
                                if chunk_text.strip():
                                    graph_data['chunks'].append({
                                        "id": 500 + i,
                                        "text": chunk_text.strip()
                                    })

                        # 關係部分
                        if len(parts) > 1:
                            kg_rels_text = parts[1]
                            # 使用解析函數
                            parsed_graph = parse_kg_relations_to_graph(kg_rels_text)

                            # 合併節點（去重）
                            existing_node_names = {n['properties']['name'] for n in graph_data['nodes']}
                            for node in parsed_graph['nodes']:
                                if node['properties']['name'] not in existing_node_names:
                                    graph_data['nodes'].append(node)
                                    existing_node_names.add(node['properties']['name'])

                            # 合併關係
                            graph_data['relationships'].extend(parsed_graph['relationships'])

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
    # 獲取 RAG 答案
    result = cardiovascular_rag.search(input, retriever_config={'top_k': 5})
    answer = result.answer

    # 如果不需要圖譜數據，直接返回答案（向後兼容）
    if not return_graph_data:
        return answer

    # 獲取圖譜數據：直接從 retriever 獲取原始檢索結果
    try:
        # 使用原始 cardiovascular_retriever 獲取包含 kg_rels 的文本
        retrieval_result = cardiovascular_retriever.get_search_results(
            query_text=input,
            top_k=3
        )

        graph_data = {
            "nodes": [],
            "relationships": [],
            "chunks": []
        }

        # 解析檢索結果
        if retrieval_result.records and len(retrieval_result.records) > 0:
            for record in retrieval_result.records:
                # Neo4j Record: 使用 .data() 方法獲取字典
                record_data = record.data()
                if 'info' in record_data:
                    info_text = record_data['info']

                    # 檢查並分割文本和關係部分
                    # Note: Neo4j retriever returns text with 'n' as newline markers
                    if 'nn=== kg_rels ===n' in info_text:
                        parts = info_text.split('nn=== kg_rels ===n')

                        # 文本塊
                        if len(parts) > 0 and parts[0].startswith('=== text ===n'):
                            text_content = parts[0].replace('=== text ===n', '')
                            text_chunks = text_content.split('n---n')
                            for i, chunk_text in enumerate(text_chunks):
                                if chunk_text.strip():
                                    graph_data['chunks'].append({
                                        "id": 500 + i,
                                        "text": chunk_text.strip()
                                    })

                        # 關係部分
                        if len(parts) > 1:
                            kg_rels_text = parts[1]
                            # 使用解析函數
                            parsed_graph = parse_kg_relations_to_graph(kg_rels_text)

                            # 合併節點（去重）
                            existing_node_names = {n['properties']['name'] for n in graph_data['nodes']}
                            for node in parsed_graph['nodes']:
                                if node['properties']['name'] not in existing_node_names:
                                    graph_data['nodes'].append(node)
                                    existing_node_names.add(node['properties']['name'])

                            # 合併關係
                            graph_data['relationships'].extend(parsed_graph['relationships'])

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
      
    


