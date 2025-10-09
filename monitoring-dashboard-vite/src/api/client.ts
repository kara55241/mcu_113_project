import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

// 創建 Axios 實例
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// API 端點
export const api = {
  // 健康檢查
  health: () => apiClient.get('/api/monitoring/health'),

  // Agent 狀態（支援可選的 thread_id 參數）
  getAgentStatus: (params?: { thread_id?: string }) =>
    apiClient.get('/api/monitoring/agents/status', { params }),
  getAgentFlow: (threadId: string) =>
    apiClient.get('/api/monitoring/agents/flow', { params: { thread_id: threadId } }),
  getAgentHistory: () => apiClient.get('/api/monitoring/agents/history'),

  // GraphRAG 追蹤
  getGraphRAGTrace: (threadId: string) =>
    apiClient.get('/api/monitoring/graphrag-trace', { params: { thread_id: threadId } }),

  // Neo4j 查詢
  queryNeo4j: (params: { cypher?: string; sample?: boolean }) =>
    apiClient.get('/api/monitoring/neo4j/query', { params }),

  // Neo4j Agent 追蹤（新增）
  getNeo4jAgentTrace: (threadId: string) =>
    apiClient.get('/api/monitoring/neo4j/agent-trace', { params: { thread_id: threadId } }),
}

export default api
