# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 項目概要

這是一個基於 Django 5.2 的 AI 聊天助手系統，專門為台灣長者提供健康諮詢和醫療設施查詢服務。系統整合了多種 AI 模型（OpenAI、Google Gemini）、Neo4j 圖數據庫、Google Maps API，以及事實查核功能。

## 核心架構

### 後端架構 (Django)
- **主項目**: `myproject/` - Django 項目配置和路由
  - `settings.py`: 配置 Neo4j 連接、中文本地化、安全中間件、靜態文件處理
  - `urls.py`: 定義聊天、文件上傳、歷史記錄等 API 端點
  - `views.py`: 實現 ChatView、FileUploadView 等視圖類，處理聊天邏輯
  - `middleware.py`: 自定義安全中間件，設置 CSP 和緩存策略

- **應用模組**: `myapp/` - 主要應用邏輯
  - `utils/chatgpt.py`: OpenAI API 封裝（需要更新到新版本）
  - `templates/myapp/index.html`: 響應式聊天界面模板

### AI 代理系統 (`graph_rag_agent/`)
核心 AI 功能模組，採用多代理架構：

- **`graph_rag.py`**: Neo4j GraphRAG 實現，連接慢性病和心血管疾病知識圖譜
- **`multi_agent.py`**: LangGraph 多代理編排，使用 SQLite 檢查點存儲
- **`llm.py`**: 統一 LLM 接口（OpenAI GPT-4.1、Google Gemini-2.5-flash）
- **`research.py`**: 研究和事實查核功能
- **`fact_check.py`** & **`cofacts_check.py`**: 台灣本地事實查核整合
- **`SearchTool.py`**: Google Maps 和 Google Search 工具類

### 前端架構 (模組化 JavaScript)
採用命名空間模式的模組化架構：

- **`static/js/app-core.js`**: 全域 `MedApp` 命名空間和應用初始化
- **`static/js/loader.js`**: 動態模組載入器，管理依賴關係
- **`static/js/chat/`**: 聊天功能模組（core, display, history, input）
- **`static/js/maps/`**: 地圖功能模組（預期）

### 數據庫和外部服務
- **SQLite**: Django 主數據庫 (`db.sqlite3`)，會話管理
- **SQLite Checkpoint**: AI 代理狀態存儲 (`agent_checkpoint.sqlite`)
- **Neo4j**: 醫療知識圖譜，支援慢性病和心血管疾病查詢
- **外部 APIs**:
  - OpenAI GPT-4.1 & Embeddings
  - Google Gemini 2.5-flash
  - Google Maps API (地圖和地點搜索)
  - Tavily Search (網頁搜索)
  - Cofacts API (台灣事實查核)

## 常用開發命令

### 環境設置
```bash
# 啟動虛擬環境 (Windows)
venv\Scripts\activate

# 安裝依賴 - 使用最新 requirements.txt
pip install -r requirements.txt

```

### Django 開發命令
```bash
# 數據庫遷移
python manage.py makemigrations
python manage.py migrate

# 啟動開發服務器 (預設 http://127.0.0.1:8000/)
python manage.py runserver

# 收集靜態文件 (用於生產環境)
python manage.py collectstatic --noinput

# 創建超級用戶 (訪問 Django admin)
python manage.py createsuperuser

# Django shell (互動式調試)
python manage.py shell

# 檢查項目配置和潛在問題
python manage.py check

# 監控代理系統運行狀態 (自定義命令)
python manage.py monitor_agents
```

### AI 系統測試命令
```bash
# 測試 GraphRAG 功能
cd graph_rag_agent
python graph_rag.py

# 測試研究功能
python research.py

# 測試多代理系統
python multi_agent.py

# 測試聊天監控系統
python test_chat_monitoring.py
```

### 開發調試工具
```bash
# 檢視靜態文件位置
python manage.py findstatic <filename>

# 清理過期會話
python manage.py clearsessions

# 運行 Django 測試 (如果有)
python manage.py test
```

## 環境配置要求

需要在 `.env` 文件中配置以下環境變量：

### Neo4j 配置
```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
NEO4J_DATABASE=diseases-tw
NEO4J_CHRONIC=diseases-tw
NEO4J_CARDIOVASCULAR=diseases-tw
```

### API 金鑰
```bash
# AI 模型服務
OPENAI_API_KEY=your_openai_api_key
GOOGLE_API_KEY=your_google_api_key

# 地圖和搜索服務
GOOGLE_MAPS_API_KEY=your_google_maps_api_key
SERPER_API_KEY=your_serper_api_key
TAVILY_API_KEY=your_tavily_api_key

# 可選：模型版本配置
OPENAI_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002
```

### Django 設置
```bash
SECRET_KEY=your_secret_key
DEBUG=True
```

## 核心架構特點

### 多代理 AI 系統
- **LangGraph 編排**: 使用 LangGraph 實現多代理工作流程
- **雙 LLM 策略**: OpenAI GPT-4.1 + Google Gemini 2.5-flash 互補
- **CheckPoint 持久化**: SQLite 儲存代理狀態，支援長對話記憶
- **專門化代理**: GraphRAG 醫療查詢、事實查核、地圖搜索等

### 知識圖譜整合
- **Neo4j GraphRAG**: 結構化醫療知識查詢
- **領域專精**: 慢性病和心血管疾病專門資料庫
- **向量搜索**: 結合語義搜索和圖形查詢

### 前端模組化設計
- **命名空間模式**: `window.MedApp` 避免全域污染
- **動態載入**: `loader.js` 管理模組依賴
- **功能模組化**: 聊天、地圖、工具分離設計

### 安全性和本地化
- **自定義 CSP**: 支援外部 API 同時維持安全性
- **台灣特化**: Cofacts 整合、繁體中文、台北時區
- **開發/生產分離**: 環境變數控制安全設置

## 開發注意事項

### AI 系統開發
- **代理狀態管理**: 使用 `agent_checkpoint.sqlite` 追蹤代理執行狀態
- **記憶體摘要**: LangMem 自動管理長對話摘要 (1500 tokens 限制)
- **工具調用**: 支援並行工具調用，注意 `parallel_tool_calls=True` 設定
- **錯誤處理**: 所有 LLM 調用包含重試邏輯和備援模型

### 前端開發
- **模組載入順序**: 依賴 `loader.js` 管理，修改需更新依賴關係
- **命名空間使用**: 所有功能掛載在 `MedApp` 下，避免直接全域變數
- **API 整合**: CSRF token 和 API root 透過模板注入到 `window.appConfig`

### 資料庫管理
- **多重 SQLite**: Django 主庫 + 代理檢查點庫分離
- **Neo4j 連接**: 支援多資料庫實例，透過環境變數切換
- **會話管理**: Django 會話存於資料庫，2週過期

### 監控和調試
- **自定義監控**: `python manage.py monitor_agents` 追蹤代理活動
- **詳細日誌**: 檔案和控制台雙輸出，支援不同層級
- **測試腳本**: `test_chat_monitoring.py` 模擬聊天請求

## 部署考量

- 設置 `DEBUG=False` 啟用 HTTPS 安全設置
- 配置正確的 `ALLOWED_HOSTS`
- 確保 Neo4j 數據庫可訪問性
- 驗證所有外部 API 金鑰有效性