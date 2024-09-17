import aiohttp
from bs4 import BeautifulSoup
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
import asyncio
class WebScrap:
    def __init__(self,url):
        self.url=url

    async def fetch(self,url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                return await response.text()
            
    async def WebScrap(self):
        url=self.url
        html = await self.fetch(url)
        soup = BeautifulSoup(html, "lxml")
        text_content = soup.get_text()

        # 將文本轉換為 Document 對象並拆分
        docs = Document(page_content=text_content)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=250, chunk_overlap=24)
        documents = text_splitter.split_documents([docs])
        return documents