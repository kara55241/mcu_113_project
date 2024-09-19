import tkinter as tk
import customtkinter as ctk
import subprocess
import sys
import os
#from neo4j import GraphDatabase
#from tkinter import PhotoImage
from PIL import Image, ImageTk
from tkinter import scrolledtext
from tkinter import filedialog
#from langchain_google_genai import GoogleGenerativeAI
#from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
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
left_frame = tk.Frame(window, bg="#2E2E2E", width=500)
left_frame.pack(side="left", fill="both")

# 創建右側框架用於聊天界面
right_frame = tk.Frame(window, bg="#1E1E1E", width=600)
right_frame.pack(side="right", fill="both", expand=True)

# 創建標籤
logo_label = ctk.CTkLabel(left_frame, text="AI助教", 
                                 font=ctk.CTkFont(size=30,weight="bold"))
logo_label.pack(padx=20, pady=(40, 40))
image = Image.open("C:/Users/harri/OneDrive/桌面/TkAPP/bot.png")
chat_image = ctk.CTkImage(light_image=image, dark_image=image, size=(30, 30))
logo_label.configure(image=chat_image, compound="right")

# 在左側框架中創建按鈕
def create_button(text, image_path, command):
    button = ctk.CTkButton(
        left_frame,
        text=text,
        font=ctk.CTkFont(family="Arial", size=25,weight="bold"),
        fg_color="#759FB2",  
        text_color="white",  
        hover_color="#688F9F",
        corner_radius=30,    # 圓角
        command=command,
        height=60,           # 設置按鈕高度
        width=200,   
    )
    
    # 載入圖片
    image = Image.open(image_path)
    button_image = ctk.CTkImage(light_image=image, dark_image=image, size=(30, 30))
    button.configure(image=button_image, compound="left")
    
    
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
create_button("PDF  ", "C:/Users/harri/OneDrive/桌面/TkAPP/pdf.png", show)
create_button("Audio", "C:/Users/harri/OneDrive/桌面/TkAPP/mp3.png", show_MP3)
create_button("Web  ", "C:/Users/harri/OneDrive/桌面/TkAPP/web.png", show_url_input)
create_button("Excel", "C:/Users/harri/OneDrive/桌面/TkAPP/excel.png", show_Excel)

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
    verbose=True,
    allow_dangerous_requests=True
)

def create_chat_interface(parent_frame):

    ai_chat = ctk.CTkLabel(parent_frame, text="AI Chat", 
                                 font=ctk.CTkFont(size=20,weight="bold"))
    ai_chat.pack(padx=40)
    # 載入圖片
    image = Image.open("C:/Users/harri/OneDrive/桌面/TkAPP/ai.png")
    chat_image = ctk.CTkImage(light_image=image, dark_image=image, size=(20, 20))
    ai_chat.configure(image=chat_image, compound="left")
    # 創建聊天顯示區域
    chat_display = ctk.CTkTextbox(parent_frame, 
                                  wrap=tk.WORD, 
                                  fg_color="#2E2E2E",  
                                  text_color="#D3D3D3",  
                                  corner_radius=10,  
                                  font=ctk.CTkFont(size=15, weight="bold") )
    chat_display.pack(expand=True, fill="both", padx=20, pady=(0,10))
    chat_display.configure(state=tk.DISABLED)

    # 創建輸入框
    input_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
    input_frame.pack(fill="x", padx=20, pady=(0, 20))

    chat_input = ctk.CTkEntry(input_frame, 
                              fg_color="#2E2E2E", 
                              text_color="white",
                              corner_radius=10,
                              height=50,
                              placeholder_text="傳訊息給AI助教",
                              placeholder_text_color="#808080",
                              font=ctk.CTkFont(size=15, weight="bold") )
    chat_input.pack(side="left", expand=True, fill="x")

    # 創建發送按鈕
    send_image = Image.open("C:/Users/harri/OneDrive/桌面/TkAPP/upload.png")
    send_icon = ctk.CTkImage(light_image=send_image, dark_image=send_image, size=(30, 30))

    send_button = ctk.CTkButton(input_frame, 
                                image=send_icon,
                                text="",
                                fg_color="transparent",  # 透明背景
                                hover_color="#3E3E3E",  # 懸停時的顏色，與輸入框背景相同
                                corner_radius=20, 
                                width=50,
                                height=50,
                                command=lambda: send_message(chat_input, chat_display))
    send_button.pack(side="right")
    
    return chat_display, chat_input

def send_message(input_widget, display_widget):
    message = input_widget.get()
    
    if message:
        display_widget.configure(state="normal")
        display_widget.insert("end", f"您: {message}\n")
        # 使用cypher_chain獲取AI回應
        response = cypher_chain.invoke({"query": message})
        ai_response = response.get('result', '抱歉,我無法理解您的問題。')
        
        display_widget.insert("end", f"AI: {ai_response}\n\n")
        display_widget.configure(state="disabled")
        display_widget.see("end")
        input_widget.delete(0, "end")

# 在右側框架中創建聊天界面
chat_display, chat_input = create_chat_interface(right_frame)

window.mainloop()