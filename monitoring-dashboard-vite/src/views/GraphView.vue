<template>
  <div class="min-h-screen bg-gray-100">
    <header class="bg-white shadow">
      <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        <h1 class="text-3xl font-bold text-gray-900">Neo4j 知識圖譜</h1>
        <router-link to="/" class="text-indigo-600 hover:text-indigo-900">← 返回首頁</router-link>
      </div>
    </header>

    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <!-- 控制面板 -->
      <div class="card mb-6">
        <h2 class="text-lg font-semibold mb-4">查詢控制</h2>

        <div class="flex gap-4 mb-4">
          <button
            @click="setMode('sample')"
            :disabled="loading"
            :class="mode === 'sample' ? 'btn-primary' : 'btn-secondary'"
          >
            載入範例圖譜
          </button>
          <button
            @click="setMode('custom')"
            :disabled="loading"
            :class="mode === 'custom' ? 'btn-primary' : 'btn-secondary'"
          >
            自定義查詢
          </button>
          <button
            @click="setMode('agent')"
            :disabled="loading"
            :class="mode === 'agent' ? 'btn-primary' : 'btn-secondary'"
          >
            Agent 查詢記錄
          </button>
        </div>

        <!-- 自定義 Cypher 查詢面板 -->
        <div v-if="mode === 'custom'" class="custom-query-panel">
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Cypher 查詢語句
          </label>
          <textarea
            v-model="customCypher"
            class="w-full border border-gray-300 rounded p-2 font-mono text-sm"
            rows="4"
            placeholder="MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50"
          ></textarea>
          <button
            @click="executeCustomQuery"
            :disabled="loading"
            class="btn-primary mt-2"
          >
            執行查詢
          </button>
        </div>

        <!-- Agent 追蹤查詢面板 -->
        <div v-if="mode === 'agent'" class="custom-query-panel">
          <label class="block text-sm font-medium text-gray-700 mb-2">
            Thread ID（對話識別碼）
          </label>
          <div class="flex gap-2">
            <input
              v-model="agentThreadId"
              type="text"
              class="flex-1 border border-gray-300 rounded p-2 font-mono text-sm"
              placeholder="輸入 Thread ID，例如：1234567890"
            />
            <button
              @click="loadAgentTrace"
              :disabled="loading || !agentThreadId"
              class="btn-primary"
            >
              載入 Agent 圖譜
            </button>
          </div>
          <p class="text-xs text-gray-500 mt-2">
            提示：從監控儀表板的對話歷史中獲取 Thread ID
          </p>
        </div>

        <div v-if="loading" class="text-center py-4">
          <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p class="text-gray-600 mt-2">載入中...</p>
        </div>

        <div v-if="error" class="error-message mt-4">
          {{ error }}
        </div>

        <!-- 統計信息面板 -->
        <div v-if="graphData" class="info-panel mt-4">
          <div class="grid grid-cols-3 gap-4 text-sm">
            <div>
              <span class="text-gray-600">節點數:</span>
              <span class="font-semibold ml-2">{{ graphData.count?.nodes || 0 }}</span>
            </div>
            <div>
              <span class="text-gray-600">關係數:</span>
              <span class="font-semibold ml-2">{{ graphData.count?.relationships || 0 }}</span>
            </div>
            <div>
              <span class="text-gray-600">資料來源:</span>
              <span class="font-semibold ml-2">{{ dataSource }}</span>
            </div>
          </div>
        </div>

        <!-- Agent 追蹤詳細信息 -->
        <div v-if="mode === 'agent' && agentTraceData" class="info-panel mt-4">
          <h3 class="font-semibold mb-2">Agent 查詢詳情</h3>
          <div class="grid grid-cols-2 gap-4 text-sm">
            <div>
              <span class="text-gray-600">查詢問題:</span>
              <span class="ml-2">{{ agentTraceData.query }}</span>
            </div>
            <div>
              <span class="text-gray-600">追蹤記錄數:</span>
              <span class="ml-2 font-semibold">{{ agentTraceData.trace_count }}</span>
            </div>
          </div>
          <div v-if="selectedTrace" class="mt-3 pt-3 border-t border-gray-200">
            <div class="text-sm">
              <div><span class="text-gray-600">使用 Agent:</span> {{ selectedTrace.agent_display_name }}</div>
              <div><span class="text-gray-600">工具:</span> {{ selectedTrace.tool_name }}</div>
              <div><span class="text-gray-600">資料庫:</span> {{ selectedTrace.graph_data?.database }}</div>
              <div class="mt-2">
                <span class="text-gray-600">答案摘要:</span>
                <p class="text-xs text-gray-700 mt-1">{{ selectedTrace.answer_summary }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 圖譜視覺化 -->
      <div class="card">
        <h2 class="text-lg font-semibold mb-4">圖譜視覺化</h2>

        <div v-if="!graphData" class="info-message">
          <p>請點擊「載入範例圖譜」開始查看知識圖譜</p>
        </div>

        <div v-else>
          <div ref="graphContainer" class="graph-canvas"></div>

          <!-- 圖例 -->
          <div class="legend mt-4">
            <h3 class="text-sm font-semibold mb-2">圖例</h3>
            <div class="flex flex-wrap gap-2">
              <div v-for="(color, label) in nodeLegend" :key="label" class="legend-item">
                <span class="legend-color" :style="{ backgroundColor: color }"></span>
                <span class="text-xs">{{ label }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { api } from '../api/client'
import { Network } from 'vis-network'
import { DataSet } from 'vis-data'

const route = useRoute()

const graphContainer = ref<HTMLElement | null>(null)
const graphData = ref<any>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const mode = ref<'sample' | 'custom' | 'agent'>('sample')
const customCypher = ref('MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50')
const agentThreadId = ref('')
const agentTraceData = ref<any>(null)
const selectedTrace = ref<any>(null)
const dataSource = ref('Neo4j')

let network: Network | null = null

const nodeLegend = ref<Record<string, string>>({
  '疾病': '#e74c3c',
  '症狀': '#f39c12',
  '藥物': '#3498db',
  '治療': '#2ecc71',
  '風險因素': '#9b59b6',
  '檢查': '#1abc9c',
})

const setMode = (newMode: 'sample' | 'custom' | 'agent') => {
  mode.value = newMode
  error.value = null

  // 自動載入範例圖譜
  if (newMode === 'sample') {
    loadSampleGraph()
  }
}

const loadSampleGraph = async () => {
  loading.value = true
  error.value = null
  dataSource.value = 'Neo4j (範例)'

  try {
    const response = await api.queryNeo4j({ sample: true })
    graphData.value = response.data
    agentTraceData.value = null
    selectedTrace.value = null
    renderGraph()
  } catch (err: any) {
    error.value = err.response?.data?.error || '載入圖譜失敗'
    console.error('Failed to load graph:', err)
  } finally {
    loading.value = false
  }
}

const loadAgentTrace = async () => {
  if (!agentThreadId.value) {
    error.value = '請輸入 Thread ID'
    return
  }

  loading.value = true
  error.value = null
  dataSource.value = 'Agent 追蹤記錄'

  try {
    const response = await api.getNeo4jAgentTrace(agentThreadId.value)
    agentTraceData.value = response.data

    if (!response.data.traces || response.data.traces.length === 0) {
      error.value = '此對話沒有使用 Neo4j 知識圖譜'
      graphData.value = null
      return
    }

    // 默認選擇第一個追蹤記錄
    selectedTrace.value = response.data.traces[0]

    // 轉換 Agent 追蹤數據為圖譜格式
    const traceGraphData = selectedTrace.value.graph_data
    graphData.value = {
      nodes: traceGraphData.nodes || [],
      relationships: traceGraphData.relationships || [],
      count: {
        nodes: traceGraphData.statistics?.node_count || 0,
        relationships: traceGraphData.statistics?.relationship_count || 0
      }
    }

    renderGraph()
  } catch (err: any) {
    error.value = err.response?.data?.error || '載入 Agent 追蹤記錄失敗'
    console.error('Failed to load agent trace:', err)
  } finally {
    loading.value = false
  }
}

const executeCustomQuery = async () => {
  if (!customCypher.value.trim()) {
    error.value = '請輸入 Cypher 查詢語句'
    return
  }

  loading.value = true
  error.value = null
  dataSource.value = 'Neo4j (自定義查詢)'

  try {
    const response = await api.queryNeo4j({ cypher: customCypher.value })
    graphData.value = response.data
    agentTraceData.value = null
    selectedTrace.value = null
    renderGraph()
  } catch (err: any) {
    error.value = err.response?.data?.error || '查詢失敗'
    console.error('Failed to execute query:', err)
  } finally {
    loading.value = false
  }
}

const renderGraph = () => {
  if (!graphContainer.value || !graphData.value) return

  // Debug logging
  console.log('[GraphView] Rendering graph:', {
    totalNodes: graphData.value.nodes?.length || 0,
    totalRels: graphData.value.relationships?.length || 0,
    sampleNode: graphData.value.nodes?.[0],
    sampleRel: graphData.value.relationships?.[0]
  })

  // Create ID mapping: original node ID -> simple numeric ID
  // This ensures vis.js receives consistent primitive IDs
  const nodeIdMap = new Map()

  // 準備節點數據
  const nodesData = graphData.value.nodes.map((node: any, index: number) => {
    // Ensure ID is a primitive (number or string)
    const simpleId = typeof node.id === 'number' || typeof node.id === 'string'
      ? node.id
      : index + 1000

    // Store mapping from original ID to simple ID
    nodeIdMap.set(node.id, simpleId)

    return {
      id: simpleId,
      label: node.properties?.name || node.properties?.title || `Node ${simpleId}`,
      title: JSON.stringify(node.properties || {}, null, 2),
      color: getNodeColor(node.labels),
      shape: 'dot' as const,
      size: 20,
    }
  })

  const nodes = new DataSet(nodesData)

  console.log('[GraphView] Prepared nodes:', nodes.length)

  // 準備邊數據
  const edgesData = graphData.value.relationships.map((rel: any, index: number) => {
    // Map relationship node references to simple IDs
    const fromId = nodeIdMap.get(rel.startNode) || rel.startNode
    const toId = nodeIdMap.get(rel.endNode) || rel.endNode

    return {
      id: index,
      from: fromId,
      to: toId,
      label: rel.type,
      title: JSON.stringify(rel.properties || {}, null, 2),
      arrows: 'to' as const,
      color: { color: '#95a5a6' },
    }
  })

  const edges = new DataSet(edgesData)

  console.log('[GraphView] Prepared edges:', edges.length)

  // 配置選項
  const options = {
    nodes: {
      font: {
        size: 14,
        color: '#333',
      },
      borderWidth: 2,
      borderWidthSelected: 4,
    },
    edges: {
      font: {
        size: 12,
        color: '#666',
        background: '#fff',
      },
      width: 2,
      smooth: {
        enabled: true,
        type: 'continuous',
        roundness: 0.5,
      },
    },
    physics: {
      enabled: true,
      barnesHut: {
        gravitationalConstant: -8000,
        springLength: 150,
        springConstant: 0.04,
      },
      stabilization: {
        iterations: 200,
      },
    },
    interaction: {
      hover: true,
      tooltipDelay: 100,
      zoomView: true,
    },
  }

  // 創建網絡
  if (network) {
    network.destroy()
  }

  network = new Network(graphContainer.value, { nodes: nodes as any, edges: edges as any }, options)

  // 添加事件監聽
  network.on('click', (params) => {
    if (params.nodes.length > 0) {
      const nodeId = params.nodes[0]
      console.log('Clicked node:', nodeId)
    }
  })
}

const getNodeColor = (labels: string[]): string => {
  if (!labels || labels.length === 0) return '#95a5a6'

  const labelColorMap: Record<string, string> = {
    '疾病': '#e74c3c',
    'Disease': '#e74c3c',
    '症狀': '#f39c12',
    'Symptom': '#f39c12',
    '藥物': '#3498db',
    'Drug': '#3498db',
    '治療': '#2ecc71',
    'Treatment': '#2ecc71',
    '風險因素': '#9b59b6',
    'RiskFactor': '#9b59b6',
    '檢查': '#1abc9c',
    'Examination': '#1abc9c',
  }

  for (const label of labels) {
    if (labelColorMap[label]) {
      return labelColorMap[label]
    }
  }

  return '#95a5a6'
}

onMounted(() => {
  // Check for thread_id in route query params
  const routeThreadId = route.query.thread_id as string

  if (routeThreadId) {
    // Auto-load agent trace if thread_id is provided
    mode.value = 'agent'
    agentThreadId.value = routeThreadId
    console.log('[GraphView] Auto-loading agent trace for thread:', routeThreadId)
    loadAgentTrace()
  }
  // Otherwise, don't auto-load anything, wait for user action
})

onUnmounted(() => {
  if (network) {
    network.destroy()
  }
})
</script>

<style scoped>
@import "tailwindcss" reference;

.card {
  @apply bg-white rounded-lg shadow p-6;
}

.graph-canvas {
  @apply h-[600px] border border-gray-300 rounded bg-white;
}

.custom-query-panel {
  @apply border border-gray-200 rounded p-4 bg-gray-50;
}

.info-panel {
  @apply bg-blue-50 border border-blue-200 rounded p-4;
}

.legend {
  @apply border-t border-gray-200 pt-4;
}

.legend-item {
  @apply flex items-center gap-2 px-3 py-1 bg-gray-100 rounded;
}

.legend-color {
  @apply w-4 h-4 rounded-full border border-gray-300;
}

.btn-primary {
  @apply px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50;
}

.btn-secondary {
  @apply px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400 disabled:opacity-50;
}

.error-message {
  @apply bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded;
}

.info-message {
  @apply bg-blue-100 border border-blue-400 text-blue-700 px-4 py-3 rounded text-center;
}
</style>
