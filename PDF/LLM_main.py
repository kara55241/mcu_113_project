import os
import sys
from dotenv import load_dotenv
from Def_relationships import Def_relationships
from PDF import PDFscrap
from langchain_google_genai import GoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# 載入環境變數
load_dotenv()

# 獲取 Google API 密鑰
google_api_key = os.getenv("GOOGLE_API_KEY")
if not google_api_key:
    raise ValueError("在 .env 檔案中未設置 GOOGLE_API_KEY")

# 設置 Google API 密鑰
os.environ["GOOGLE_API_KEY"] = google_api_key

# 創建 Google Generative AI 實例
llm = GoogleGenerativeAI(model="gemini-pro")

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
            print(f"Gemini 回應: {response}")  # 如果是字符串，直接輸出
            return response
        else:
            print(f"意外的回應格式: {response}")
            return ""
    except Exception as e:
        print(f"在 generate_response 中發生錯誤: {e}")
        return ""

# 主函數
def main(pdf_file):
    try:
        documents = PDFscrap.Process_pdf(pdf_file)
        if not documents:
            print("從 PDF 中未提取到文檔。")
            return

        neo4j_url = os.getenv("NEO4J_URL")
        neo4j_username = os.getenv("NEO4J_USERNAME")
        neo4j_password = os.getenv("NEO4J_PASSWORD")
        
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
        
        # 儲存到 Neo4j
        neo4j.save_entities_and_relationships_batch(relationships)
        print("實體和關係已儲存到 Neo4j。")
    except Exception as e:
        print(f"在 main 函數中發生錯誤: {e}")
    finally:
        if 'neo4j' in locals():
            neo4j.close()

# 運行主函數
if __name__ == '__main__':
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        main(pdf_file)
    else:
        print("未提供 PDF 檔案路徑。")