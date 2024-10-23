import os
import asyncio
from Def_relationships import *
from PDF import PDFscrap
from PyPDF2 import PdfReader
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

# 主函數
async def main():
    if __name__ == '__main__':
        # 接收傳入的 PDF 檔案路徑
        if len(sys.argv) > 1:
            pdf_file = sys.argv[1]
    documents = PDFscrap.Process_pdf(pdf_file)
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
    # 關閉 Neo4j 驅動程式
    neo4j.close()

# 運行主函數
if __name__ == '__main__':
    asyncio.run(main())
