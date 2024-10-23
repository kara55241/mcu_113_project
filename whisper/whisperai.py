<<<<<<< HEAD

from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
import whisper
=======
import whisper
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
>>>>>>> ver1023
class whisperai:
    def __init__(self,path):
        self.model = whisper.load_model("medium")
        self.path = path

    def Speech_Scrap(self):
<<<<<<< HEAD
=======
        
>>>>>>> ver1023
        result = self.model.transcribe(self.path, verbose = True)
        return result["text"]
    
    def text_splitter(self,text_content):
        docs = Document(page_content=text_content)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=250, chunk_overlap=24)
        documents = text_splitter.split_documents([docs])
        return documents