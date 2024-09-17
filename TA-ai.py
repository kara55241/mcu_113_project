import tkinter as tk
import subprocess
import sys
import os
from neo4j import GraphDatabase
from tkinter import PhotoImage
from PIL import Image, ImageTk
from tkinter import scrolledtext
from tkinter import filedialog
from langchain_google_genai import GoogleGenerativeAI, ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.prompts import ChatPromptTemplate
from langchain_community.vectorstores import Neo4jVector
from langchain.chains import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph
from dotenv import load_dotenv

# 獲取當前腳本的目錄
current_dir = os.path.dirname(os.path.abspath(__file__))

# 打印當前工作目錄
print("當前工作目錄:", current_dir)

# 嘗試手動載入 .env 文件
env_path = os.path.join(current_dir, '.env')
print("嘗試從以下位置載入 .env 文件:", env_path)
load_dotenv(env_path)

# 獲取環境變量
neo4j_url = os.getenv("NEO4J_URL")
neo4j_username = os.getenv("NEO4J_USERNAME")
neo4j_password = os.getenv("NEO4J_PASSWORD")
google_api_key = os.getenv("GOOGLE_API_KEY")

# 添加調試輸出
print("NEO4J_URL:", neo4j_url)
print("NEO4J_USERNAME:", neo4j_username)
print("NEO4J_PASSWORD:", neo4j_password)
print("GOOGLE_API_KEY:", google_api_key)

# 檢查 GOOGLE_API_KEY 是否為 None
if google_api_key is None:
    raise ValueError("在 .env 文件中未設置 GOOGLE_API_KEY")

# 視窗設置
window = tk.Tk()
window.title("TA-ai")
window.geometry("1000x600")  # 寬x高
window.resizable(False, False)  # 禁止視窗縮放
window.config(bg="#2E2E2E")  # 背景顏色
window.attributes("-topmost", True)  # 視窗置頂

graph = Neo4jGraph(
    url=neo4j_url,
    username=neo4j_username,
    password=neo4j_password
)

# 創建左側框架用於按鈕
left_frame = tk.Frame(window, bg="#2E2E2E", width=400)
left_frame.pack(side="left", fill="both")

# 創建右側框架用於聊天界面
right_frame = tk.Frame(window, bg="#2E2E2E", width=600)
right_frame.pack(side="right", fill="both", expand=True)

# 在左側框架中創建按鈕
def create_button(text, image_path, command):
    button = tk.Button(left_frame, text=text, font=("Arial", 20, "bold"), bg="#4CAFEC", fg="white",
                       activebackground="#357ABD", activeforeground="white", 
                       compound="left", padx=20, pady=20, relief="flat", borderwidth=0, command=command)
    
    folder_image = Image.open(image_path)
    folder_image = folder_image.resize((30, 30), Image.Resampling.LANCZOS)
    folder_icon = ImageTk.PhotoImage(folder_image)
    
    button.config(image=folder_icon)
    button.image = folder_icon
    
    button.pack(pady=10, padx=20, fill="x")

def show():
    files = filedialog.askopenfilenames(
        title="選擇 PDF 文件", 
        filetypes=[("PDF 文件", "*.pdf")])
    if files:
        for file in files:
            print(f"選擇的文件: {file}")
            subprocess.run([sys.executable, os.path.join(current_dir, 'PDF', 'LLM_main.py'), file])

def show_MP3():
    files = filedialog.askopenfilenames(
    title="選擇音頻文件", 
    filetypes=[("音頻文件", "*.wav")])
    if files:
        for file in files:
            print(f"選擇的文件: {file}")
            subprocess.run([sys.executable, os.path.join(current_dir, 'whisper', 'LLM_main.py'), file])

def show_url_input():
    input_window = tk.Toplevel(window)
    input_window.title("輸入網址")
    input_window.geometry("400x100")
    input_window.attributes("-topmost", True)
    url_entry = tk.Entry(input_window, width=50)
    url_entry.pack(pady=10)
    confirm_button = tk.Button(input_window, text="確認", command=lambda: process_url(url_entry.get(), input_window))
    confirm_button.pack()

def process_url(url, input_window):
    print(f"輸入的網址是：{url}")
    subprocess.run([sys.executable, os.path.join(current_dir, 'webScrap', 'LLM_main.py'), url])
    input_window.destroy()

def show_Excel():
    files = filedialog.askopenfilenames(
    title="選擇 Excel 文件", 
    filetypes=[("Excel 文件", "*.xlsx")])
    if files:
        for file in files:
            print(f"選擇的文件: {file}")
            subprocess.run([sys.executable, os.path.join(current_dir, 'Excel_scrap', 'LLM_main.py'), file])

# 創建按鈕
create_button("添加 PDF", os.path.join(current_dir, "picture", "pdf.png"), show)
create_button("添加音頻", os.path.join(current_dir, "picture", "mp3.png"), show_MP3)
create_button("添加網頁", os.path.join(current_dir, "picture", "pdf.png"), show_url_input)
create_button("添加 Excel", os.path.join(current_dir, "picture", "pdf.png"), show_Excel)

gemini_model = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0.5)
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

vector_index = Neo4jVector.from_existing_graph(
    embeddings,
    url=neo4j_url,
    username=neo4j_username,
    password=neo4j_password,
    search_type="hybrid",
    node_label="Document",
    text_node_properties=["text"],
    embedding_node_property="embedding"
)

# 創建 GraphCypherQAChain
cypher_chain = GraphCypherQAChain.from_llm(
    cypher_llm=gemini_model,
    qa_llm=gemini_model,
    graph=graph,
    verbose=True
)

def create_chat_interface(parent_frame):
    chat_display = scrolledtext.ScrolledText(parent_frame, wrap=tk.WORD, bg="#3E3E3E", fg="white")
    chat_display.pack(expand=True, fill="both", padx=10, pady=10)
    chat_display.config(state=tk.DISABLED)

    input_frame = tk.Frame(parent_frame, bg="#2E2E2E")
    input_frame.pack(fill="x", padx=10, pady=(0, 10))

    chat_input = tk.Entry(input_frame, bg="#4E4E4E", fg="white")
    chat_input.pack(side="left", expand=True, fill="x")

    send_button = tk.Button(input_frame, text="發送", command=lambda: send_message(chat_input, chat_display))
    send_button.pack(side="right", padx=(10, 0))

    return chat_display, chat_input

def send_message(input_widget, display_widget):
    message = input_widget.get()
    
    if message:
        display_widget.config(state=tk.NORMAL)
        display_widget.insert(tk.END, f"您: {message}\n")
        response = cypher_chain.invoke({"query": message})
        ai_response = response.get('result', '抱歉，我無法理解您的問題。')
        
        display_widget.insert(tk.END, f"AI: {ai_response}\n\n")
        display_widget.config(state=tk.DISABLED)
        display_widget.see(tk.END)
        input_widget.delete(0, tk.END)

# 在右側框架中創建聊天界面
chat_display, chat_input = create_chat_interface(right_frame)

window.mainloop()