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
  - `management/commands/monitor_agents.py`: 自定義 Django 命令，監控代理系統

- **監控 API**: `monitoring_api/` - 代理系統監控 API
  - REST API 端點於 `/api/monitoring/` 提供系統健康檢查和代理狀態查詢

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
- **`static/js/chat/`**: 聊天功能模組
  - `chat-core.js`: 核心聊天邏輯和 API 通訊
  - `chat-history.js`: 對話歷史管理
  - `chat-input.js`: 使用者輸入處理
  - `chat-display.js`: 訊息顯示和渲染（如存在）
- **`static/js/maps/`**: 地圖功能模組
  - `maps-core.js`: Google Maps 核心初始化
  - `maps-search.js`: 地點搜索功能
  - `maps-hospital.js`: 醫療設施顯示
  - `maps-direction.js`: 路線規劃
- **`static/js/utils/`**: 工具模組（accessibility, notifications, speech）

### 數據庫和外部服務
- **SQLite**: Django 主數據庫 (`db.sqlite3`)，會話管理
- **SQLite Checkpoint**: AI 代理狀態存儲 (`agent_checkpoint_new.sqlite`)
- **Neo4j**: 醫療知識圖譜，支援慢性病和心血管疾病查詢
- **外部 APIs**:
  - OpenAI GPT-4o-mini & text-embedding-ada-002
  - Google Gemini 2.5-flash
  - Google Maps API (地圖和地點搜索)
  - Tavily Search (網頁搜索)
  - Cofacts API (台灣事實查核)

### 監控儀表板
- **`monitoring-dashboard-vite/`**: Vite + Vue 3 監控前端
  - 使用 Vue 3 Composition API 和 Vite 建置工具
  - 連接到 `/api/monitoring/` 端點，提供代理系統即時可視化監控
  - 支援系統健康檢查、代理狀態追蹤、工具調用統計等功能

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
python manage.py monitor_agents --status              # 顯示系統狀態概覽
python manage.py monitor_agents --live                # 即時監控模式
python manage.py monitor_agents --session <chat_id>   # 監控特定對話
python manage.py monitor_agents --history --hours 24  # 顯示歷史分析
python manage.py monitor_agents --live --refresh 5    # 自訂刷新間隔（秒）
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

### 監控儀表板開發命令
```bash
# 進入監控儀表板目錄
cd monitoring-dashboard-vite

# 安裝依賴
npm install

# 啟動開發服務器（預設 http://localhost:5173）
npm run dev

# 建置生產版本
npm run build

# 預覽生產建置
npm run preview

# 程式碼檢查
npm run lint
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

# 可選：模型版本配置（預設值已在 llm.py 中設定）
OPENAI_MODEL=gpt-4o-mini
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
- **雙 LLM 策略**: OpenAI GPT-4o-mini + Google Gemini 2.5-flash 互補
- **CheckPoint 持久化**: SQLite (`agent_checkpoint_new.sqlite`) 儲存代理狀態，支援長對話記憶
- **專門化代理**:
  - `chronic_agent`: 慢性疾病專家（透過 GraphRAG 查詢 Neo4j）
  - `cardiovascular_agent`: 心血管疾病專家（透過 GraphRAG 查詢 Neo4j）
  - `fact_check_agent`: 資訊搜尋專家（整合 Tavily Search 和 Cofacts）
  - `supervisor`: 主控代理，負責路由和協調
- **語義路由**: 使用 OpenAI embeddings 計算查詢相似度，智慧分派代理

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
- **代理狀態管理**: 使用 `agent_checkpoint_new.sqlite` 追蹤代理執行狀態
- **記憶體摘要**: LangMem 自動管理長對話摘要 (5000 tokens 對話限制, 1000 tokens 摘要限制)
- **工具調用**: 支援並行工具調用，注意 `parallel_tool_calls=True` 設定
- **錯誤處理**: 所有 LLM 調用包含重試邏輯（max_retries=2）和備援模型
- **語義搜索**: 搜索計數追蹤（MAX_SEARCH_COUNT=2）避免循環，信心度閾值 0.6
- **代理追蹤**: `agent_tracker.py` 提供執行時間和狀態監控

### 前端開發
- **模組載入順序**: 依賴 `loader.js` 管理，修改需更新依賴關係
- **命名空間使用**: 所有功能掛載在 `MedApp` 下，避免直接全域變數
- **API 整合**: CSRF token 和 API root 透過模板注入到 `window.appConfig`

### 資料庫管理
- **多重 SQLite**: Django 主庫 + 代理檢查點庫分離
- **Neo4j 連接**: 支援多資料庫實例，透過環境變數切換
- **會話管理**: Django 會話存於資料庫，2週過期

### 監控和調試
- **自定義監控命令**: `python manage.py monitor_agents` 提供多種監控模式
  - `--status`: 系統狀態概覽（檢查點數據庫、Django 會話、模組健康檢查）
  - `--live`: 即時監控代理活動和工具調用
  - `--session <id>`: 追蹤特定對話的代理執行
  - `--history --hours N`: 歷史分析（線程活動、代理使用、工具調用統計）
- **監控 API**: `/api/monitoring/` 端點提供系統健康和代理狀態 JSON
- **視覺化儀表板**: Vite + Vue 3 前端 (`monitoring-dashboard-vite/`)
  - 連接監控 API，即時顯示系統狀態
  - 支援自動刷新和歷史數據查詢
  - 預設運行於 `http://localhost:5173`（開發模式）
- **詳細日誌**:
  - 多代理系統日誌：`agent_debug.log`
  - Django 應用日誌：`logs/django.log`
  - 檔案和控制台雙輸出，支援不同層級
- **測試腳本**: `test_chat_monitoring.py` 模擬聊天請求

## 部署考量

- 設置 `DEBUG=False` 啟用 HTTPS 安全設置
- 配置正確的 `ALLOWED_HOSTS`
- 確保 Neo4j 數據庫可訪問性
- 驗證所有外部 API 金鑰有效性
- 確保 `logs/` 目錄存在且有寫入權限
- 生產環境建議配置 CORS_ALLOWED_ORIGINS 限制監控儀表板來源
- REST Framework 需改為 `IsAuthenticated` 權限類別

## 關鍵文件路徑參考

### 配置文件
- Django 主配置：`myproject/settings.py`
- URL 路由：`myproject/urls.py`
- 中間件：`myproject/middleware.py`
- 環境變數：`.env`（不在版本控制中）

### AI 代理核心
- 多代理編排：`graph_rag_agent/multi_agent.py`
- GraphRAG 查詢：`graph_rag_agent/graph_rag.py`
- LLM 配置：`graph_rag_agent/llm.py`
- 代理追蹤：`graph_rag_agent/agent_tracker.py`

### 前端入口
- 聊天界面模板：`myapp/templates/myapp/index.html`
- 應用核心：`static/js/app-core.js`（定義 window.MedApp）
- 模組載入器：`static/js/loader.js`

### 數據庫
- Django 主庫：`db.sqlite3`
- 代理檢查點：`agent_checkpoint_new.sqlite`
- Neo4j：遠端連接（配置於 .env）

### 日誌
- 代理系統：`agent_debug.log`
- Django 應用：`logs/django.log`