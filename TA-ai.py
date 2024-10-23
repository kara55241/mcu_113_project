import tkinter as tk
import customtkinter as ctk
import subprocess
import sys
import asyncio
import os
import networkx as nx
from PIL import Image, ImageTk
from tkinter import scrolledtext
from tkinter import filedialog
from neo4j import GraphDatabase
import matplotlib.pyplot as plt
import matplotlib
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Neo4jVector
from langchain_core.prompts import PromptTemplate
from langchain_community.chains.graph_qa.cypher import GraphCypherQAChain
from langchain_community.graphs import Neo4jGraph
from langchain_openai import ChatOpenAI# 設置 Google API 密鑰
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
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
openai_api_key = os.getenv("OPENAI_API_KEY")

# 添加調試輸出
print("NEO4J_URL:", neo4j_url)
print("NEO4J_USERNAME:", neo4j_username)
print("NEO4J_PASSWORD:", neo4j_password)
print("GOOGLE_API_KEY:", google_api_key)
print("OPENAI_API_KEY:", openai_api_key)

Gpt_model = ChatOpenAI(model="gpt-4o-mini", temperature=0)
embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
driver = GraphDatabase.driver(neo4j_url, auth=(neo4j_username, neo4j_password))
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
image = Image.open("./TKinter/bot.png")
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
    image_load(image_path,button,30,30)
    button_image = ctk.CTkImage(light_image=image, dark_image=image, size=(30, 30))
    button.configure(image=button_image, compound="left")
    button.pack(pady=10, padx=20, fill="x")


def image_load(path,iteam,x,y):
    image = Image.open(path)
    chat_image = ctk.CTkImage(light_image=image, dark_image=image, size=(x, y))
    iteam.configure(image=chat_image, compound="left")

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
create_button("PDF  ", "./TKinter/pdf.png", show)
create_button("Audio", "./TKinter/mp3.png", show_MP3)
create_button("Web  ", "./TKinter/web.png", show_url_input)
create_button("Excel", "./TKinter/excel.png", show_Excel)


vector_index = Neo4jVector.from_existing_graph(
    embeddings,
    url=neo4j_url,
    username=neo4j_username,
    password=neo4j_password,
    node_label="Document",
    index_name="entity_embedding_index",
    text_node_properties=["text"],
    embedding_node_property="embedding"
)

# 創建 GraphCypherQAChain
def genarate_answer(question):
    cypher_prompt =PromptTemplate.from_template("""
    你是一個 Neo4j專家。根據以下資訊生成一個 Cypher 查詢：
    其中where請依照用戶提到的實體來撰寫，你的cypher查詢必須遵守範例中格式，但你可以根據用戶提問來調整cypher查詢。
    當用戶提到某些詞語時，請提取它並作為搜尋實體的依據。
    例如:
    MATCH (e1:Entity)-[r:Relationship]->(e2:Entity)
    WHERE e1.name = "name" 
    RETURN e1, r.type,e2
    請務必使用用戶提到的實體生成一個準確的 Cypher 查詢來回答問題。只返回 Cypher 查詢得到的所有數據。
    用戶問題：{question}
                                                                                                                                    

    """                                               
    )
    LLM_qa_prompt = """
    你是一個專家。專精於尋找資料庫中的資訊並結合自身知識來回答問題。
    將得到的實體關係模仿人類聊天的方式回答，請記得，你的回答必須是基於neo4j的實體關係，而且必須盡可能列出相關的實體，並利用這些實體組成句子。
    如果無法利用實體關係回答或訊息不足，則利用自身知識回答。
    如果還是不行，請說你不知道。

    Cypher 查詢結果：{context}
    用戶問題：{question}
    """
    prompt_qa = PromptTemplate(template=LLM_qa_prompt, input_variables=["question","context"])

    cypher_chain = GraphCypherQAChain.from_llm(
    llm=Gpt_model,
    graph=graph,
    verbose=True,
    cypher_prompt=cypher_prompt,
    qa_prompt=prompt_qa,
    validate_cypher=True,
    allow_dangerous_requests=True
    )
    response = cypher_chain.invoke({"query":question})
    return response
def delete_all_data():
        try:
           
            with driver.session() as session:
                # 刪除所有節點和關係
                session.run("MATCH (n) DETACH DELETE n")
            
            # 可以在這裡添加一個彈出窗口來通知用戶操作成功
            tk.messagebox.showinfo("成功", "所有數據已成功刪除")
        except Exception as e:
            
            # 可以在這裡添加一個彈出窗口來通知用戶操作失敗
            tk.messagebox.showerror("錯誤", f"刪除數據時發生錯誤: {e}")
        finally:
            if driver:
                driver.close()
def get_graph_data():
    def fetch_data(tx):
        result = tx.run("MATCH (n)-[r]->(m) RETURN n.name, type(r), m.name")
        return [(record["n.name"], record["m.name"], record["type(r)"]) for record in result]

    try:
        with driver.session() as session:
            graph_data = session.read_transaction(fetch_data)

        if not graph_data:
            tk.messagebox.showinfo("提示", "數據庫中沒有數據可顯示")
            return

        # 設置 Matplotlib 使用的繁體中文字體
        matplotlib.rcParams['font.family'] = 'sans-serif'
        matplotlib.rcParams['font.sans-serif'] = ['Microsoft JhengHei']
        matplotlib.rcParams['axes.unicode_minus'] = False

        # 創建 NetworkX 圖形
        G = nx.Graph()
        for source, target, relationship in graph_data:
            G.add_edge(source, target, relationship=relationship)

        # 限制節點數量
        max_nodes = 100
        if len(G) > max_nodes:
            degrees = dict(G.degree())
            top_nodes = sorted(degrees, key=degrees.get, reverse=True)[:max_nodes]
            G = G.subgraph(top_nodes)

        # 創建新窗口來顯示圖形
        graph_window = tk.Toplevel()
        graph_window.attributes("-topmost", True)
        graph_window.title("Database Visualization")
        graph_window.geometry("1000x800")

        # 創建 Matplotlib 圖形
        fig, ax = plt.subplots(figsize=(20, 16))
        pos = nx.circular_layout(G)  # 使用圓形佈局，不帶 k 參數
        node_sizes = [100 + 50 * G.degree(node) for node in G.nodes()]
        node_colors = [G.degree(node) for node in G.nodes()]

        nx.draw(G, pos, with_labels=True, node_color=node_colors, cmap=plt.cm.viridis,
                node_size=node_sizes, font_size=6, font_weight='bold', ax=ax)
        
        # 繪製邊標籤
        edge_labels = nx.get_edge_attributes(G, 'relationship')
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=4, ax=ax)

        plt.title("Database Visualization", fontsize=20)
        plt.axis('off')

        canvas = FigureCanvasTkAgg(fig, master=graph_window)
        canvas.draw()

        # 添加導航工具欄
        toolbar = NavigationToolbar2Tk(canvas, graph_window)
        toolbar.update()

        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        close_button = tk.Button(graph_window, text="關閉", command=graph_window.destroy)
        close_button.pack(pady=10)

    except Exception as e:
        tk.messagebox.showerror("錯誤", f"獲取或顯示圖形時發生錯誤：{str(e)}")

    finally:
        plt.close(fig)
def create_chat_interface(parent_frame):

    ai_chat = ctk.CTkLabel(parent_frame, text="AI Chat", 
                                 font=ctk.CTkFont(size=20,weight="bold"))
    ai_chat.pack(padx=40)
    # 載入圖片
    image = Image.open("./TKinter/ai.png")
    chat_image = ctk.CTkImage(light_image=image, dark_image=image, size=(20, 20))
    ai_chat.configure(image=chat_image, compound="left")
    #創建一個框架來容納標題和按鈕
    header_frame = ctk.CTkFrame(parent_frame, fg_color="transparent")
    header_frame.pack(fill="x", padx=40, pady=(10, 0))
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
    send_image = Image.open("./TKinter/upload.png")
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
    #刪除database按鈕
    delDatabase_button = ctk.CTkButton(header_frame, text="DB deletion", 
                               font=ctk.CTkFont(family="Arial", size=14,weight="bold"),
                               width=80, height=30,
                               fg_color="#FF0000",
                               hover_color="#D63026",
                               command=delete_all_data
                               )
    delDatabase_button.pack(side="right")
    image_load("./TKinter/trash.png", delDatabase_button, 20, 20)

    #database圖形化button
    viewDatabase_button = ctk.CTkButton(header_frame, text="DB view", 
                               font=ctk.CTkFont(family="Arial", size=14,weight="bold"),
                               width=80, height=30,
                               fg_color="#00CED1",
                               hover_color="#20B2AA",
                               command=get_graph_data
                               )
    viewDatabase_button.pack(side="right",padx=10)
    image_load("./TKinter/view.png", viewDatabase_button, 20, 20)

    return chat_display, chat_input

def send_message(input_widget, display_widget):
    message = input_widget.get()
    if message:
        display_widget.configure(state="normal")
        display_widget.insert("end", f"您: {message}\n")
        # 使用cypher_chain獲取AI回應
        response = genarate_answer(message)
        print(response)
        ai_response=response.get('result', '抱歉,我無法理解您的問題。')
        
        display_widget.insert("end", f"AI: {ai_response}\n\n")
        display_widget.configure(state="disabled")
        display_widget.see("end")
        input_widget.delete(0, "end")
    else:
        display_widget.insert("end", f"訊息發送失敗，請再試一次\n")

# 在右側框架中創建聊天界面
chat_display, chat_input = create_chat_interface(right_frame)

window.mainloop()
