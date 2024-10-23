# 標準庫導入
import os
import sys
import subprocess
import tkinter as tk
#from tkinter import filedialog
# 第三方庫導入
import customtkinter as ctk
from PIL import Image, ImageTk
from neo4j import GraphDatabase
# Langchain 相關導入
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Neo4jVector
from langchain.chains import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph
from langchain_core.prompts import PromptTemplate
# ========== 初始化設置 ==========

# 配置
GOOGLE_API_KEY = "AIzaSyByxnWsalrjFdslxrJ6GHsIby_Sl30IXS8"
NEO4J_URL = "bolt://localhost:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "123456789"
# 設置 Google API and Model
os.environ["GOOGLE_API_KEY"] = GOOGLE_API_KEY
gemini_model = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.5)
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
# Neo4j 連接
graph = Neo4jGraph(
    url=NEO4J_URL,
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD
)
driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

# ========== Window 設定 ==========
window = tk.Tk()
window.title("app")
window.geometry("1000x600")  # 寬x高
window.attributes("-topmost", True)  # 視窗置頂

# ========== 布局設定 ==========

# 創建左側框架用於按鈕
left_frame = ctk.CTkFrame(window, fg_color="#2E2E2E", width=500)
left_frame.pack(side="left", fill="both")
# 創建右側框架用於聊天界面
right_frame = ctk.CTkFrame(window, fg_color="#1E1E1E", width=600)
right_frame.pack(side="right", fill="both", expand=True)

# ========== 標籤 ==========
logo_label = ctk.CTkLabel(
    left_frame, 
    text="AI", 
    font=ctk.CTkFont(size=30, weight="bold")
)
logo_label.pack(padx=20, pady=(40, 40))
image = Image.open("D:/ai/mcu_113_project/TKinter/bot.png")
chat_image = ctk.CTkImage(light_image=image, dark_image=image, size=(30, 30))
logo_label.configure(image=chat_image, compound="right")

# ========== 按鈕 ==========
def image_load(path, item, x, y): 
    """設置圖標"""
    image = Image.open(path)
    chat_image = ctk.CTkImage(light_image=image, dark_image=image, size=(x, y))
    item.configure(image=chat_image, compound="left")

def create_button(text, image_path, command): 
    """創建自訂按鈕"""
    button = ctk.CTkButton(
        left_frame,
        text=text,
        font=ctk.CTkFont(family="Arial", size=25, weight="bold"),
        fg_color="#759FB2",  
        text_color="white",  
        hover_color="#688F9F",
        corner_radius=30,    # 圓角
        command=command,
        height=60,          
        width=200,   
    )
    image_load(image_path, button, 30, 30)
    button.pack(pady=10, padx=20, fill="x")

# ========== 文件處理function ==========
def process_files(title, file_types, script_path):
    """通用文件處理函數"""
    display_message("資料處理中....") 
    files = ctk.filedialog.askopenfilenames(title=title, filetypes=[file_types])
    if files:
        for file in files:
            print(f"選擇的文件: {file}")
            subprocess.run([sys.executable, script_path, file])
        display_message("資料處理完畢") 

def display_message(message):
    """在聊天框顯示訊息"""
    chat_display.configure(state="normal")
    chat_display._textbox.insert("end", f"系統: {message}\n", "system")
    chat_display._textbox.insert("end", "\n")
    chat_display.configure(state="disabled")
    chat_display.see("end")

            
def show_PDF():
    """處理 PDF 文件"""
    process_files("選擇 PDF 文件", ("PDF files", "*.pdf"), 'C:/project/PDF/LLM_main.py')

def show_MP3():
   """處理音頻文件"""
   process_files("選擇音頻文件", ("Audio files", "*.wav"), 'C:/project/whisper/LLM_main.py')

def show_Excel():
    """處理 Excel 文件"""
    process_files("選擇 Excel 文件", ("Excel files", "*.xlsx"), 'C:/project/Excel_scrap/LLM_main.py')

# ========== 網頁處理function ==========

#全局變數
url_entry = None
url_frame = None

def show_url_input():
    """在右側框架顯示網址輸入框"""
    global url_entry, url_frame, input_frame
    
     # 隱藏原本的聊天輸入框
    if input_frame:
        input_frame.pack_forget()
    # 如果已存在輸入框，先移除它
    if url_frame:
        url_frame.destroy()
    
    # 創建框架來容納輸入框和按鈕
    url_frame = ctk.CTkFrame(right_frame,fg_color="transparent")
    url_frame.pack(fill="x", padx=20, pady=(10, 0))
    
    # 創建輸入框
    url_entry = ctk.CTkEntry(url_frame, 
                             fg_color="#2E2E2E", 
                             text_color="white",
                             corner_radius=10,
                             height=50,
                             width=400,
                             placeholder_text="請輸入網址",
                             placeholder_text_color="#808080",
                             font=ctk.CTkFont(size=15, weight="bold") )
    url_entry.pack(side="left", expand=True, fill="x", padx=(0, 10))
  
    # 創建確認按鈕
    confirm_button = ctk.CTkButton(
        url_frame,
        text="確認",
        font=ctk.CTkFont(size=12),
        fg_color="#759FB2",
        text_color="white",
        hover_color="#688F9F",
        corner_radius=10,
        command=lambda: (display_message("資料處理中...."), window.update(), process_url()),
        width=100,
        height=40
    )
    confirm_button.pack(side="left")
    
    # 綁定 Enter 鍵到 process_url 函數
    url_entry.bind("<Return>", lambda event: (display_message("資料處理中...."), window.update(), process_url()))

def process_url():
    """處理輸入的網址"""
    global url_frame, input_frame
    url = url_entry.get()
    
    print(f"輸入的網址是：{url}")
    try:
        result = subprocess.run([sys.executable, 'C:/project/webScrap/LLM_main.py', url], 
                                 capture_output=True, text=True, check=True)
        display_message("資料處理完畢")              
    except subprocess.CalledProcessError as e:
        display_message(f"處理過程中發生錯誤")
    # 處理完成後移除輸入框
    if url_frame:
        url_frame.destroy()
        url_frame = None  
    # 重新顯示原本的聊天輸入框
    if input_frame:
        input_frame.pack(fill="x", padx=20, pady=(0, 20))      
    
# ========== 按鈕創建 ==========
create_button("PDF  ", "D:/ai/mcu_113_project/TKinter/pdf.png", show_PDF)
create_button("Audio", "D:/ai/mcu_113_project/TKinter/mp3.png", show_MP3)
create_button("Web  ", "D:/ai/mcu_113_project/TKinter/web.png", show_url_input)
create_button("Excel", "D:/ai/mcu_113_project/TKinter/excel.png", show_Excel)
# ========== 頂部標題 ==========
ai_chat = ctk.CTkLabel(right_frame, 
                       text="AI Chat", 
                       font=ctk.CTkFont(size=20,weight="bold"))
ai_chat.pack(padx=40, pady=(20, 10))
# 載入圖片
image = Image.open("D:/ai/mcu_113_project/TKinter/ai.png")
chat_image = ctk.CTkImage(light_image=image, dark_image=image, size=(20, 20))
ai_chat.configure(image=chat_image, compound="left")
image_load("D:/ai/mcu_113_project/TKinter/ai.png",ai_chat,20,20)
# ========== 右邊聊天框 ==========

#聊天框創建
chat_display = ctk.CTkTextbox(right_frame, 
                              wrap="word", 
                              fg_color="#2E2E2E",  
                              text_color="#D3D3D3",  
                              corner_radius=10,  
                              font=ctk.CTkFont(size=18, weight="bold") )
chat_display.pack(expand=True, fill="both", padx=20, pady=(0,10))
chat_display.configure(state=tk.DISABLED)

# 創建輸入框
input_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
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
send_image = Image.open("D:/ai/mcu_113_project/TKinter/upload.png")
send_icon = ctk.CTkImage(light_image=send_image, dark_image=send_image, size=(30, 30))

#cypher查詢
cypher_chain = GraphCypherQAChain.from_llm(
    cypher_llm=gemini_model,
    qa_llm=gemini_model,
    graph=graph,
    verbose=True,
    allow_dangerous_requests=True
)

def send_message(event=None):
    """輸入訊息處理"""
    message = chat_input.get()
    
    if message:
        chat_display.configure(state="normal")
        
        # 插入用戶消息，並應用右對齊標籤
        chat_display._textbox.tag_configure("user", justify="right", lmargin2=50)
        chat_display.insert("end", f" {message}\n", "user")
        chat_display.insert("end", "\n")  # 添加額外的換行以分隔消息
        cypher_response = cypher_chain.invoke({"query": message})
        final_response = cypher_response.get('result', '抱歉，我無法回答這個問題。')
        
        # 插入AI回應，並應用左對齊標籤
        chat_display._textbox.tag_configure("ai", justify="left", rmargin=50)
        chat_display.insert("end", f"AI: {final_response}\n", "ai")
        chat_display.insert("end", "\n")  
        chat_display.configure(state="disabled")
       
        chat_input.delete(0, "end")



chat_input.bind("<Return>", send_message)
#發送按鈕
send_button = ctk.CTkButton(input_frame, 
                            image=send_icon,
                            text="",
                            fg_color="transparent",
                            hover_color="#3E3E3E",  
                            corner_radius=20, 
                            width=50,
                            height=50,
                            command=lambda: send_message())   
send_button.pack(side="right")

window.mainloop()  