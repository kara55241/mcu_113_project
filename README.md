# 台灣長者健康諮詢 AI 聊天助手

一個專為台灣長者設計的智能健康諮詢系統，整合多代理 AI、知識圖譜、事實查核和醫療設施查詢功能。

## 🌟 核心功能

### AI 多代理系統
- **專科代理架構**：慢性疾病專家、心血管疾病專家、資訊搜尋專家
- **智能路由**：基於語義相似度的自動代理分派
- **長對話記憶**：使用 LangMem 和 SQLite CheckPoint 管理對話上下文
- **雙 LLM 策略**：OpenAI GPT-4o-mini + Google Gemini 2.5-flash 互補

### 醫療知識圖譜 (Neo4j GraphRAG)
- 慢性疾病知識圖譜查詢
- 心血管疾病專門知識庫
- 結合語義搜索和圖形查詢的 RAG 系統

### 事實查核整合
- **Tavily Search**：即時網頁資訊檢索
- **Cofacts API**：台灣本地事實查核資料庫整合
- 自動識別並標記需要查證的資訊

### 醫療設施查詢
- **Google Maps API**：診所、醫院、藥局即時搜索
- **路線規劃**：提供前往醫療設施的導航
- **地點資訊**：營業時間、聯絡方式、評價等詳細資訊

### 監控儀表板
- **即時監控**：代理系統執行狀態、工具調用統計
- **歷史分析**：對話歷程、代理使用模式分析
- **健康檢查**：系統組件狀態監控
- **Vue 3 + Vite**：現代化響應式前端

## 🛠️ 技術棧

### 後端
- **框架**：Django 5.2
- **AI 編排**：LangGraph 0.6.3 + LangChain 0.3.27
- **LLM 服務**：
  - OpenAI GPT-4o-mini (主要對話)
  - Google Gemini 2.5-flash (備援和增強)
- **知識圖譜**：Neo4j 5.28.1 + neo4j-graphrag 1.6.1
- **向量搜索**：OpenAI text-embedding-ada-002
- **檢查點存儲**：SQLite (langgraph-checkpoint-sqlite)
- **記憶管理**：LangMem 0.0.29
- **API 整合**：
  - Tavily Search (網頁搜索)
  - Google Maps API (地圖和地點)
  - Cofacts API (台灣事實查核)

### 前端
- **主應用**：模組化 JavaScript (命名空間架構)
- **監控儀表板**：Vue 3 + Vite + TypeScript + Tailwind CSS 4
- **地圖顯示**：Google Maps JavaScript API
- **圖形可視化**：Vue Flow, Chart.js

### 資料庫
- **主資料庫**：SQLite (Django ORM)
- **代理檢查點**：SQLite (agent_checkpoint_new.sqlite)
- **知識圖譜**：Neo4j Graph Database

## 🚀 快速開始

### 環境需求
- Python 3.10+
- Node.js 18+ (監控儀表板)
- Neo4j 5.x (本地或遠端)
- Git

### 安裝步驟

#### 1. 克隆專案
```bash
git clone <repository-url>
cd myproject
```

#### 2. 設置 Python 虛擬環境
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

#### 3. 安裝 Python 依賴
```bash
pip install -r requirements.txt
```

#### 4. 配置環境變數
創建 `.env` 文件於專案根目錄：

```env
# Django 設置
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=*

# Neo4j 配置
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_neo4j_password
NEO4J_DATABASE=diseases-tw
NEO4J_CHRONIC=diseases-tw
NEO4J_CARDIOVASCULAR=diseases-tw

# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key
OPENAI_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002

# Google API
GOOGLE_API_KEY=your-google-api-key
GOOGLE_MAPS_API_KEY=your-google-maps-api-key

# 搜索服務
TAVILY_API_KEY=tvly-your-tavily-api-key
SERPER_API_KEY=your-serper-api-key  # 可選
```

#### 5. 初始化資料庫
```bash
python manage.py migrate
python manage.py createsuperuser  # 可選：創建管理員帳號
```

#### 6. 收集靜態文件
```bash
python manage.py collectstatic --noinput
```

#### 7. 啟動 Django 開發服務器
```bash
python manage.py runserver
```

主應用將運行於 `http://127.0.0.1:8000/`

#### 8. 啟動監控儀表板（可選）
```bash
cd monitoring-dashboard-vite
npm install
npm run dev
```

監控儀表板將運行於 `http://localhost:5173/`

## 📁 專案結構

```
myproject/
├── myproject/              # Django 主專案配置
│   ├── settings.py         # 配置文件（Neo4j、中文本地化、安全設置）
│   ├── urls.py             # 主路由配置
│   ├── views.py            # 聊天視圖和 API
│   ├── middleware.py       # 自定義安全中間件
│   └── wsgi.py
├── myapp/                  # Django 主應用
│   ├── templates/          # HTML 模板
│   │   └── myapp/
│   │       └── index.html  # 響應式聊天界面
│   ├── utils/
│   │   └── chatgpt.py      # OpenAI API 封裝
│   └── management/
│       └── commands/
│           └── monitor_agents.py  # 代理監控命令
├── monitoring_api/         # 監控 REST API
│   ├── views.py            # 健康檢查、代理狀態端點
│   └── urls.py
├── graph_rag_agent/        # AI 代理系統核心
│   ├── multi_agent.py      # LangGraph 多代理編排（主要入口）
│   ├── graph_rag.py        # Neo4j GraphRAG 查詢
│   ├── llm.py              # 統一 LLM 接口
│   ├── research.py         # 研究和搜索功能
│   ├── fact_check.py       # Tavily 事實查核
│   ├── cofacts_check.py    # Cofacts API 整合
│   ├── SearchTool.py       # Google Maps/Search 工具
│   └── agent_tracker.py    # 代理執行追蹤
├── monitoring-dashboard-vite/  # Vue 3 監控儀表板
│   ├── src/
│   │   ├── components/     # Vue 組件
│   │   ├── views/          # 頁面視圖
│   │   ├── App.vue
│   │   └── main.ts
│   ├── package.json
│   └── vite.config.ts
├── static/                 # 靜態資源
│   ├── js/
│   │   ├── app-core.js     # 全域命名空間 (window.MedApp)
│   │   ├── loader.js       # 動態模組載入器
│   │   ├── chat/           # 聊天功能模組
│   │   ├── maps/           # 地圖功能模組
│   │   └── utils/          # 工具模組
│   ├── css/
│   └── images/
├── logs/                   # 日誌目錄
│   └── django.log
├── db.sqlite3              # Django 主資料庫
├── agent_checkpoint_new.sqlite  # 代理檢查點資料庫
├── agent_debug.log         # 代理系統日誌
├── requirements.txt        # Python 依賴
├── CLAUDE.md              # Claude Code 專案指引
└── README.md              # 本文件
```

## 🔌 API 端點

### 聊天 API
- `POST /chat/` - 發送聊天訊息
  ```json
  {
    "message": "我想了解高血壓的症狀",
    "session_id": "optional-session-id"
  }
  ```

- `GET /history/` - 獲取聊天歷史
  - Query params: `session_id` (可選)

- `GET /history/<session_id>/` - 獲取特定會話歷史

- `POST /upload/` - 上傳文件
  - Form data: `file`, `session_id` (可選)

### 監控 API
- `GET /api/monitoring/health/` - 系統健康檢查
  ```json
  {
    "status": "healthy",
    "checkpoint_db": "connected",
    "sessions": 10,
    "timestamp": "2025-01-15T10:30:00Z"
  }
  ```

- `GET /api/monitoring/agents/status/` - 代理系統狀態
  - Query params: `session_id` (可選)

## 🧪 開發工具

### Django 管理命令

#### 代理系統監控
```bash
# 系統狀態概覽
python manage.py monitor_agents --status

# 即時監控模式
python manage.py monitor_agents --live

# 監控特定對話
python manage.py monitor_agents --session <chat_id>

# 歷史分析（最近 24 小時）
python manage.py monitor_agents --history --hours 24

# 自訂刷新間隔（即時監控）
python manage.py monitor_agents --live --refresh 5
```

#### 資料庫管理
```bash
# 數據遷移
python manage.py makemigrations
python manage.py migrate

# 清理過期會話
python manage.py clearsessions

# Django shell（調試）
python manage.py shell
```

### AI 系統測試
```bash
cd graph_rag_agent

# 測試 GraphRAG 功能
python graph_rag.py

# 測試研究功能
python research.py

# 測試多代理系統
python multi_agent.py

# 測試聊天監控系統
python test_chat_monitoring.py
```

### 監控儀表板開發
```bash
cd monitoring-dashboard-vite

# 啟動開發服務器
npm run dev

# 建置生產版本
npm run build

# 預覽生產建置
npm run preview

# 程式碼檢查
npm run lint
```

## 🏗️ 架構特點

### 多代理 AI 系統
- **LangGraph 編排**：StateGraph 管理代理工作流程
- **專門化代理**：
  - `supervisor`：主控代理，負責路由決策
  - `chronic_agent`：慢性疾病專家（查詢 Neo4j GraphRAG）
  - `cardiovascular_agent`：心血管疾病專家（查詢 Neo4j GraphRAG）
  - `fact_check_agent`：資訊搜尋專家（整合 Tavily + Cofacts）
- **語義路由**：使用 OpenAI embeddings 計算查詢相似度（閾值 0.6）
- **CheckPoint 持久化**：SQLite 存儲代理狀態，支援中斷恢復
- **記憶體摘要**：
  - 對話歷史限制：5000 tokens
  - 摘要長度限制：1000 tokens
  - 自動觸發摘要機制

### 前端模組化架構
- **命名空間模式**：`window.MedApp` 避免全域變數污染
- **動態載入**：`loader.js` 管理模組依賴關係
- **功能分離**：
  - `chat/`：聊天核心、歷史、輸入處理
  - `maps/`：地圖初始化、搜索、醫院顯示、路線規劃
  - `utils/`：無障礙、通知、語音功能

### 安全性設計
- **自定義 CSP**：`CustomSecurityMiddleware` 支援外部 API
- **CORS 配置**：限制監控儀表板來源
- **環境分離**：開發/生產環境不同的安全策略
- **CSRF 保護**：Django 內建保護機制

### 本地化特性
- **語言**：繁體中文 (zh-hant)
- **時區**：Asia/Taipei
- **事實查核**：整合台灣 Cofacts 資料庫
- **醫療資訊**：台灣本地醫療設施查詢

## 📊 監控和調試

### 日誌系統
- **Django 應用日誌**：`logs/django.log`
- **代理系統日誌**：`agent_debug.log`
- **控制台輸出**：即時開發調試資訊

### 監控工具
1. **自定義 Django 命令**：`python manage.py monitor_agents`
   - 檢查點資料庫狀態
   - Django 會話統計
   - 代理活動追蹤
   - 工具調用分析

2. **REST API**：`/api/monitoring/`
   - JSON 格式系統狀態
   - 適合自動化監控

3. **視覺化儀表板**：`http://localhost:5173`
   - 即時圖表和統計
   - 代理執行流程可視化
   - 歷史數據查詢

### 資料庫檢查
```bash
# 查看檢查點資料庫內容
sqlite3 agent_checkpoint_new.sqlite
.tables
.schema checkpoints
SELECT * FROM checkpoints LIMIT 5;

# 查看 Django 資料庫
python manage.py dbshell
```

## 🚢 部署建議

### 生產環境配置清單
- [ ] 設置 `DEBUG=False` 於 `.env`
- [ ] 配置正確的 `ALLOWED_HOSTS`
- [ ] 使用強密碼的 `SECRET_KEY`
- [ ] 驗證所有 API 金鑰有效性
- [ ] 確保 Neo4j 資料庫可訪問
- [ ] 配置 PostgreSQL 或 MySQL（替代 SQLite）
- [ ] 設置 Gunicorn + Nginx
- [ ] 配置 HTTPS（Let's Encrypt）
- [ ] 啟用 CORS_ALLOWED_ORIGINS 白名單
- [ ] 設置 REST_FRAMEWORK 為 `IsAuthenticated`
- [ ] 確保 `logs/` 目錄有寫入權限
- [ ] 配置靜態文件服務（CDN 或 Nginx）
- [ ] 設置備份策略（資料庫 + 檢查點）

### 環境變數範例（生產）
```env
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SECRET_KEY=your-very-secure-random-secret-key

# 資料庫配置（建議使用 PostgreSQL）
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# HTTPS 設置
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

## 🤝 開發注意事項

### AI 代理開發
- **代理狀態追蹤**：使用 `agent_tracker.py` 監控執行時間
- **錯誤處理**：所有 LLM 調用包含重試邏輯（max_retries=2）
- **並行工具調用**：注意 `parallel_tool_calls=True` 設定
- **搜索限制**：MAX_SEARCH_COUNT=2 避免無限循環
- **信心度閾值**：語義搜索閾值 0.6（可調整）

### 前端開發
- **模組載入順序**：依賴 `loader.js` 管理
- **命名空間使用**：所有功能掛載在 `MedApp` 下
- **API 整合**：CSRF token 透過 `window.appConfig` 注入
- **響應式設計**：支援桌面和移動設備

### 資料庫管理
- **多重 SQLite**：主資料庫 + 檢查點資料庫分離
- **會話過期**：Django 會話 2 週自動過期
- **定期清理**：使用 `clearsessions` 命令清理過期資料

## 📝 授權

本專案為私有專案，僅供內部使用。

## 📧 聯絡方式

如有問題或建議，請聯繫專案維護者。

---

**最後更新**：2025-01-15
**版本**：1.0.0
**Django**：5.2
**Python**：3.10+
