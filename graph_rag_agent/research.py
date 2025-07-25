# research.py - 移除JSON格式限制的版本

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

# 🔧 修正：移除 JSON 格式限制，使用自然文字回應
llm = OpenAILLM(
    model_name='gpt-4.1-mini',
    model_params={'temperature': 0}  # 移除 JSON 格式要求
)

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

# 🔧 修正：簡化並改善 RAG 模板
rag_template = RagTemplate(
    template='''
請根據以下資料回答問題，並為長輩提供清晰易懂的健康資訊：

問題：{query_text}

參考資料：
{context}

請遵循以下回答原則：
- 使用繁體中文回答
- 提供詳細且實用的資訊
- 只根據提供的參考資料回答
- 以清晰的段落和適當的標題組織內容
- 如果資料不足以回答問題，請誠實說明

回答：
''', 
    system_instructions="您是專業的醫療健康顧問，專門為長輩提供易懂的健康資訊和建議。",
    expected_inputs=['query_text', 'context']
)

rag = GraphRAG(llm=llm, retriever=vc_retriever, prompt_template=rag_template)

def graph_rag(input: str):
    """執行圖形RAG查詢並返回清理後的結果"""
    try:
        # 執行RAG查詢
        result = rag.search(input, retriever_config={'top_k': 5})
        
        # 獲取答案
        answer = result.answer
        
        # 🔧 清理可能的JSON格式回應
        if isinstance(answer, str) and answer.strip().startswith('{'):
            try:
                import json
                parsed = json.loads(answer)
                if isinstance(parsed, dict):
                    # 將JSON轉換為自然文字格式
                    answer = convert_json_to_text(parsed)
            except json.JSONDecodeError:
                # 如果解析失敗，保持原始文字
                pass
        
        return answer
        
    except Exception as e:
        error_msg = f"知識圖譜查詢遇到問題：{str(e)}"
        print(f"❌ graph_rag 錯誤: {error_msg}")
        return error_msg

def convert_json_to_text(data):
    """將JSON結構轉換為自然文字格式"""
    if isinstance(data, dict):
        result_parts = []
        
        # 處理主要標題
        for main_key, main_value in data.items():
            result_parts.append(f"## {main_key}")
            
            if isinstance(main_value, dict):
                for key, value in main_value.items():
                    if isinstance(value, dict):
                        result_parts.append(f"\n**{key}：**")
                        for sub_key, sub_value in value.items():
                            if isinstance(sub_value, list):
                                result_parts.append(f"- **{sub_key}：** {', '.join(map(str, sub_value))}")
                            else:
                                result_parts.append(f"- **{sub_key}：** {sub_value}")
                    elif isinstance(value, list):
                        result_parts.append(f"\n**{key}：**")
                        for item in value:
                            result_parts.append(f"- {item}")
                    else:
                        result_parts.append(f"\n**{key}：** {value}")
            elif isinstance(main_value, list):
                for item in main_value:
                    result_parts.append(f"- {item}")
            else:
                result_parts.append(str(main_value))
        
        return '\n'.join(result_parts)
    
    elif isinstance(data, list):
        return '\n'.join([f"- {item}" for item in data])
    
    else:
        return str(data)

