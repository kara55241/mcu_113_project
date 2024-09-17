import os
import asyncio
import sys
from dotenv import load_dotenv
from Def_relationships import Def_relationships
from whisperai import whisperai
from langchain_google_genai import GoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# 載入環境變數
load_dotenv()

# 獲取環境變數
google_api_key = os.getenv("GOOGLE_API_KEY")
neo4j_url = os.getenv("NEO4J_URL")
neo4j_username = os.getenv("NEO4J_USERNAME")
neo4j_password = os.getenv("NEO4J_PASSWORD")

if not all([google_api_key, neo4j_url, neo4j_username, neo4j_password]):
    raise ValueError("缺少必要的環境變數")

# 設置 Google API 密鑰
os.environ["GOOGLE_API_KEY"] = google_api_key

# 創建 Google Generative AI 實例
llm = GoogleGenerativeAI(model="gemini-1.5-flash")

# 定義生成回應的函數
def generate_response(entities, relationships, user_input):
    try:
        if entities and relationships:
            prompt_text = (
                f"根據以下實體和關係，回答問題：\n"
                f"實體: {', '.join(entities)}\n"
                f"關係: {', '.join([f'{rel[0]} {rel[1]} {rel[2]}' for rel in relationships])}\n\n"
                f"問題: {user_input}"
            )
        else:
            prompt_text = f"根據以下問題生成有用的回應：{user_input}"

        template = ChatPromptTemplate.from_messages([
            ("system", "根據以下文本生成一個有用的回應："),
            ("user", "{input}")
        ])
        response = llm.invoke(template.format(input=prompt_text))
        if isinstance(response, str):
            print(f"Gemini 回應: {response}")
            return response
        else:
            print(f"意外的回應格式: {response}")
            return ""
    except Exception as e:
        print(f"在 generate_response 中發生錯誤: {e}")
        return ""

# 主函數
async def main():
    if len(sys.argv) <= 1:
        print("未提供音頻文件路徑。")
        return

    mp3_file = sys.argv[1]
    try:
        whisper = whisperai(mp3_file)
        text_content = whisper.Speech_Scrap()
        documents = whisper.text_splitter(text_content)
        
        neo4j = Def_relationships(neo4j_url, neo4j_username, neo4j_password, "neo4j")
        entities = []
        relationships = []
        
        # 處理每個文本片段
        for chunk in documents:
            result = neo4j.extract_entities_and_relationships(chunk.page_content)
            lines = result.splitlines()
            for line in lines:
                if '@@' in line:
                    try:
                        entity1, relationship, entity2 = line.split('@@')
                        entity1, relationship, entity2 = entity1.strip(), relationship.strip(), entity2.strip()
                        entities.append(entity1)
                        relationships.append((entity1, relationship, entity2))
                    except ValueError:
                        print(f"無法解析行: {line}")
        
        # 存儲到 Neo4j
        neo4j.save_entities_and_relationships_batch(relationships)
        print("實體和關係已儲存到 Neo4j。")

    except Exception as e:
        print(f"在 main 函數中發生錯誤: {e}")
    finally:
        if 'neo4j' in locals():
            neo4j.close()

# 運行主函數
if __name__ == '__main__':
    asyncio.run(main())