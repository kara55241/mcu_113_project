from PyPDF2 import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
class PDFscrap:
    def __init__(self):
        pass

    def Process_pdf(pdf_path):
        with open(pdf_path, 'rb') as f:
        # 創建 PDF 閱讀器
            pdf = PdfReader(f)
        # 初始化變數以存儲提取的文字
            text_content = ""
        # 遍歷每一頁並提取文字
            for page in range(len(pdf.pages)):
                text_content += pdf.pages[page].extract_text()
        docs = Document(page_content=text_content)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=250, chunk_overlap=24)
        documents = text_splitter.split_documents([docs])
        return documents

            