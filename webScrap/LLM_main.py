import os
import asyncio
import sys
from dotenv import load_dotenv
from WebScrap import WebScrap
from Def_relationships import Def_relationships
from langchain_google_genai import GoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# 載入環境變量
load_dotenv()

# 獲取環境變量
google_api_key = os.getenv("GOOGLE_API_KEY")
neo4j_url = os.getenv("NEO4J_URL")
neo4j_username = os.getenv("NEO4J_USERNAME")
neo4j_password = os.getenv("NEO4J_PASSWORD")

if not all([google_api_key, neo4j_url, neo4j_username, neo4j_password]):
    raise ValueError("缺少必要的環境變量")

# 設置 Google API 密鑰
os.environ["GOOGLE_API_KEY"] = google_api_key

# 創建 Google Generative AI 實例
llm = GoogleGenerativeAI(model="gemini-1.5-flash")

async def generate_response(entities, relationships, user_input):
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
        response = await llm.ainvoke(template.format(input=prompt_text))
        if isinstance(response, str):
            print(f"Gemini 回應: {response}")
            return response
        else:
            print(f"意外的回應格式: {response}")
            return ""
    except Exception as e:
        print(f"在 generate_response 中發生錯誤: {e}")
        return ""

async def process_chunk(chunk, neo4j):
    result = await neo4j.extract_entities_and_relationships(chunk.page_content)
    entities = []
    relationships = []
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
    return entities, relationships

async def main():
    if len(sys.argv) <= 1:
        print("未提供網址。")
        return

    url = sys.argv[1]
    try:
        web = WebScrap(url)
        documents = await web.WebScrap()
        neo4j = Def_relationships(neo4j_url, neo4j_username, neo4j_password, "neo4j")
        
        all_entities = []
        all_relationships = []
        
        tasks = [process_chunk(chunk, neo4j) for chunk in documents]
        results = await asyncio.gather(*tasks)
        
        for entities, relationships in results:
            all_entities.extend(entities)
            all_relationships.extend(relationships)
        
        all_entities = list(set(all_entities))
        all_relationships = list(set(all_relationships))
        
        await neo4j.save_entities_and_relationships_batch(all_relationships)
        print("實體和關係已儲存到 Neo4j。")

        # 互動式問答（可選）
        """
        print("文件抓取完成，請輸入你的問題（輸入 'exit' 或 'quit' 結束）：")
        while True:
            user_input = input("你：")
            if user_input.lower() in ['exit', 'quit']:
                break
            response = await generate_response(all_entities, all_relationships, user_input)
            print(f"AI 回應：{response}")
        """
    except Exception as e:
        print(f"在 main 函數中發生錯誤: {e}")
    finally:
        if 'neo4j' in locals():
            await neo4j.close()

if __name__ == '__main__':
    asyncio.run(main())