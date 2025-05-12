from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from langchain_openai import OpenAIEmbeddings
from langchain_google_genai import ChatGoogleGenerativeAI


# 確保環境變數已載入
load_dotenv()

# 檢查並設定默認環境變數值
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY 環境變數未設定！")

if not os.getenv("OPENAI_MODEL"):
    os.environ["OPENAI_MODEL"] = "gpt-4o"

if not os.getenv("OPENAI_EMBEDDING_MODEL"):
    os.environ["OPENAI_EMBEDDING_MODEL"] = "text-embedding-3-small"

# 建立 LLM 模型實例
llm_GPT = ChatOpenAI(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    model=os.getenv("OPENAI_MODEL"),
    max_retries=2,
    temperature=0
)

# 建立 Google 的 LLM 模型實例
llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-preview-04-17",
    temperature=0,
    max_retries=2,
    cache=True
)

# 建立 Embedding 模型
embeddings = OpenAIEmbeddings(
    api_key=os.getenv("OPENAI_API_KEY"),
    model=os.getenv("OPENAI_EMBEDDING_MODEL")
)