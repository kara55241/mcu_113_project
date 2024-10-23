import os
import asyncio
from Def_relationships import *
from whisperai import whisperai
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain_google_genai import GoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from neo4j import GraphDatabase
import sys
from dotenv import load_dotenv
# 設置 Google API 密鑰
google_api_key = os.getenv("GOOGLE_API_KEY")

# 創建 Google Generative AI 實例
llm = GoogleGenerativeAI(model="gemini-1.5-flash")
'''
# 定義生成回應的函數
def generate_response(entities, relationships, user_input):
    try:
        if entities and relationships:
            # 當有實體和關係時，使用它們作為上下文
            prompt_text = (
                f"根據以下實體和關係，回答問題：\n"
                f"實體: {', '.join(entities)}\n"
                f"關係: {', '.join([f'{rel[0]} {rel[1]} {rel[2]}' for rel in relationships])}\n\n"
                f"問題: {user_input}"
            )
        else:
            # 當沒有相關實體和關係時，給出更通用的提示
            prompt_text = f"根據以下問題生成有用的回應：{user_input}"

        template = ChatPromptTemplate.from_messages([
            ("system", "根據以下文本生成一個有用的回應："),
            ("user", "{input}")
        ])
        response = llm.invoke(template.format(input=prompt_text))
        if isinstance(response, str):
            print(f"Gemini Response: {response}")  # 如果是字符串，直接输出
            return response
        else:
            print(f"Unexpected response format: {response}")
            return ""
    except Exception as e:
        print(f"An error occurred: {e}")
        return ""
'''
# 主函數
async def main():
    if __name__ == '__main__':
        # 接收傳入的 音樂 檔案路徑
        if len(sys.argv) > 1:
            wish = sys.argv[1]
    wishper = whisperai(wish)
    text_content = wishper.Speech_Scrap()
    documents = wishper.text_splitter(text_content)
    neo4j = Def_relationships("bolt://localhost:7687","neo4j","11050371","neo4j")
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
                    print(f"Failed to parse line: {line}")
    # 存儲到 Neo4j
    neo4j.save_entities_and_relationships_batch(relationships)

    # 提供用戶互動
    '''
    print("文件抓取完成，請輸入你的問題：")
    while True:
        user_input = input("你：")
        if user_input.lower() in ['exit', 'quit']:
            break
        # 使用實體和關係生成回應
        response = generate_response(entities, relationships, user_input)
        print(f"AI 回應：{response}")
    '''

    # 關閉 Neo4j 驅動程式
    neo4j.close()

# 運行主函數
if __name__ == '__main__':
    asyncio.run(main())