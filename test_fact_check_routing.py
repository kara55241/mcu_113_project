from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI

# 載入環境變數
load_dotenv()

# 初始化模型
llm_GPT = ChatOpenAI(
    openai_api_key=os.getenv("OPENAI_API_KEY"),
    model="gpt-4o",  # 使用穩定版本
    max_retries=2,
    temperature=0
)

# 設定紀錄檔
log_file = "chat_log.txt"

print("💬 已啟動 ChatGPT 對話模式（輸入 'exit' 結束）")

while True:
    user_input = input("你：")
    if user_input.lower() in ["exit", "quit", "bye"]:
        print("👋 結束對話，感謝使用！")
        break

    response = llm_GPT.invoke(user_input).content
    print("AI：", response)

    # 將問答寫入文字檔
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"你：{user_input}\n")
        f.write(f"AI：{response}\n")
        f.write("-" * 40 + "\n")
