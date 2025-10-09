
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
    os.environ["OPENAI_MODEL"] = "gpt-4.1-mini"

if not os.getenv("OPENAI_EMBEDDING_MODEL"):
    os.environ["OPENAI_EMBEDDING_MODEL"] = "text-embedding-ada-002"

# 建立 LLM 模型實例
llm_GPT = ChatOpenAI(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4o-mini",  # 使用穩定的模型版本
    max_retries=2,
    temperature=0
)

# 建立強制工具調用的 LLM 實例（用於醫療專家 agent）
llm_GPT_tool_required = ChatOpenAI(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4o-mini",
    max_retries=2,
    temperature=0,
    model_kwargs={
        "tool_choice": "required"  # 強制必須調用工具
    }
)

# 建立 Google 的 LLM 模型實例
llm_gemini = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.1,
    top_p=0.9,
    top_k=20,
    max_retries=2,
    cache=False,
    google_api_key=os.getenv("GOOGLE_API_KEY")  
)

# 建立 Embedding 模型
embeddings = OpenAIEmbeddings(
    api_key=os.getenv("OPENAI_API_KEY"),
    model=os.getenv("OPENAI_EMBEDDING_MODEL")
)