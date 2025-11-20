<template>
  <div class="workflow-container">
    <div class="flex justify-between items-center mb-4">
      <h2 class="text-lg font-semibold">Agent 執行流程</h2>
      <div class="flex gap-2">
        <button
          @click="toggleViewMode"
          class="btn-secondary"
          :title="viewMode === 'logical' ? '切換到時間序視圖' : '切換到邏輯層視圖'"
        >
          {{ viewMode === 'logical' ? '📊 邏輯層' : '⏱️ 時間序' }}
        </button>
        <button
          @click="refreshData"
          :disabled="loading"
          class="btn-secondary"
        >
          {{ loading ? '載入中...' : '刷新' }}
        </button>
        <button
          @click="toggleAutoRefresh"
          :class="autoRefresh ? 'btn-primary' : 'btn-secondary'"
        >
          {{ autoRefresh ? '自動刷新 (開)' : '自動刷新 (關)' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <div v-if="!execution && !loading" class="info-message">
      <p>請選擇一個 Thread ID 或等待新的對話</p>
    </div>

    <div v-if="execution" class="execution-info mb-4">
      <div class="grid grid-cols-3 gap-4 text-sm">
        <div>
          <span class="text-gray-600">Thread ID:</span>
          <span class="font-mono ml-2">{{ execution.thread_id }}</span>
        </div>
        <div>
          <span class="text-gray-600">狀態:</span>
          <span class="ml-2" :class="statusClass">{{ execution.status }}</span>
        </div>
        <div>
          <span class="text-gray-600">開始時間:</span>
          <span class="ml-2">{{ formatTime(execution.started_at) }}</span>
        </div>
      </div>
      <div class="mt-2" v-if="execution.query">
        <span class="text-gray-600">查詢:</span>
        <span class="ml-2 text-sm">{{ execution.query }}</span>
      </div>
    </div>

    <div class="flow-canvas">
      <VueFlow
        v-if="nodes.length > 0"
        v-model:nodes="nodes"
        v-model:edges="edges"
        :fit-view-on-init="true"
        :zoom-on-scroll="true"
        :pan-on-drag="true"
        :min-zoom="0.5"
        :max-zoom="2"
      >
        <Background />
        <Controls />

        <template #node-agent="{ data }">
          <AgentNode :data="data" />
        </template>
      </VueFlow>

      <!-- Loading 狀態 -->
      <div v-else-if="loading" class="empty-state">
        <div class="animate-spin h-12 w-12 border-4 border-blue-500 border-t-transparent rounded-full"></div>
        <p class="mt-2 text-sm text-gray-500">載入工作流中...</p>
      </div>

      <!-- 無數據狀態 -->
      <div v-else class="empty-state">
        <svg class="h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <p class="mt-2 text-sm text-gray-500">尚無執行數據</p>
      </div>
    </div>

    <div v-if="execution && execution.agents.length > 0" class="agent-timeline mt-4">
      <h3 class="text-md font-semibold mb-2">執行時間線</h3>
      <div class="space-y-2">
        <div
          v-for="(agent, index) in execution.agents"
          :key="index"
          class="timeline-item"
          :class="agent.status"
        >
          <div class="flex justify-between items-center">
            <div>
              <span class="font-semibold">{{ agent.display_name }}</span>
              <span class="text-sm text-gray-600 ml-2">({{ agent.name }})</span>
            </div>
            <span class="status-badge" :class="agent.status">
              {{ agent.status === 'running' ? '執行中' : '已完成' }}
            </span>
          </div>
          <div class="text-sm text-gray-600 mt-1">
            開始: {{ formatTime(agent.started_at) }}
            <span v-if="agent.completed_at"> | 完成: {{ formatTime(agent.completed_at) }}</span>
          </div>
          <div v-if="agent.tools_used && agent.tools_used.length > 0" class="tools-list mt-2">
            <div class="text-xs text-gray-500 font-semibold mb-1">
              使用的工具 ({{ agent.tools_used.length }}):
            </div>
            <div class="space-y-1">
              <div
                v-for="(tool, tIndex) in agent.tools_used"
                :key="tIndex"
                class="tool-item flex items-center gap-2 text-sm"
              >
                <span
                  class="tool-tag"
                  :class="tool.status"
                  :title="tool.result_summary || tool.args || ''"
                >
                  {{ tool.tool }}
                </span>
                <span class="text-xs text-gray-500">
                  {{ formatTime(tool.timestamp) }}
                </span>
                <span v-if="tool.error" class="text-xs text-red-600">
                  錯誤: {{ tool.error }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import AgentNode from './AgentNode.vue'
import { api } from '../api/client'

// VueFlow 官方樣式文件
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import '@vue-flow/controls/dist/style.css'
// 注意：@vue-flow/background 沒有獨立的 CSS 文件，樣式已包含在 core 中

interface Props {
  threadId?: string
}

const props = defineProps<Props>()

const execution = ref<any>(null)
const nodes = ref<any[]>([])
const edges = ref<any[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const autoRefresh = ref(true)
const refreshInterval = ref<number | null>(null)
const lastUpdateTime = ref<number>(Date.now())
const noChangeCount = ref<number>(0)
const viewMode = ref<'timeline' | 'logical'>('logical') // 新增：視圖模式（時間序 vs 邏輯層）

const statusClass = computed(() => ({
  'text-green-600 font-semibold': execution.value?.status === 'completed',
  'text-blue-600 font-semibold animate-pulse': execution.value?.status === 'running',
}))

const fetchExecutionData = async () => {
  if (!props.threadId) {
    console.warn('[AgentFlowChart] No threadId provided')
    return
  }

  loading.value = true
  error.value = null

  try {
    // 傳遞 thread_id 參數獲取特定執行數據
    const response = await api.getAgentStatus({ thread_id: props.threadId })

    console.log('[AgentFlowChart] API response:', response.data)

    // 處理回應
    if (response.data.execution) {
      const prevAgentCount = execution.value?.agents?.length || 0
      execution.value = response.data.execution
      const currentAgentCount = execution.value.agents?.length || 0

      console.log(`[AgentFlowChart] Loaded execution for thread: ${props.threadId}`)
      console.log(`  - Status: ${execution.value.status}`)
      console.log(`  - Agents: ${currentAgentCount}`)

      // 檢測數據是否有變化
      if (currentAgentCount === prevAgentCount && execution.value.status === 'running') {
        noChangeCount.value++
        if (noChangeCount.value >= 5) {
          console.warn('[AgentFlowChart] Thread appears stuck, disabling auto-refresh')
          autoRefresh.value = false
        }
      } else {
        noChangeCount.value = 0
      }

      // 如果狀態已完成，停止自動刷新
      if (execution.value.status === 'completed') {
        autoRefresh.value = false
      }

      // 構建流程圖節點和邊
      buildFlowGraph()
    } else {
      // 如果 API 回應格式不符，記錄警告
      console.warn('[AgentFlowChart] Unexpected API response format:', response.data)
      error.value = '資料格式不符，請檢查 API 回應'
      execution.value = null
    }
  } catch (err: any) {
    error.value = err.response?.data?.error || '載入執行數據失敗'
    console.error('[AgentFlowChart] Failed to fetch execution data:', err)
    execution.value = null
  } finally {
    loading.value = false
  }
}

const buildFlowGraph = () => {
  if (!execution.value || !execution.value.agents) {
    nodes.value = []
    edges.value = []
    return
  }

  console.log('[buildFlowGraph] Building graph with', execution.value.agents.length, 'agents')

  if (viewMode.value === 'logical') {
    buildLogicalFlowGraph()
  } else {
    buildTimelineFlowGraph()
  }
}

const buildLogicalFlowGraph = () => {
  // 邏輯層視圖：層次化佈局
  const newNodes: any[] = []
  const newEdges: any[] = []

  const centerX = 400
  const layerSpacing = 200
  const expertSpacing = 350  // 專家代理之間的水平間距

  let currentY = 0

  // 第一層：起始節點
  newNodes.push({
    id: 'start',
    type: 'input',
    position: { x: centerX, y: currentY },
    data: { label: '用戶查詢' },
  })
  currentY += layerSpacing

  const grouped = execution.value.grouped_agents || {}

  // 第二層：Supervisor 決策（合併所有 supervisor 節點）
  if (grouped.supervisor && grouped.supervisor.length > 0) {
    const supervisorId = 'supervisor-layer'
    const supervisorTools = grouped.supervisor.flatMap((a: any) => a.tools_used || [])
    const supervisorStatus = grouped.supervisor.some((a: any) => a.status === 'running') ? 'running' : 'completed'

    newNodes.push({
      id: supervisorId,
      type: 'agent',
      position: { x: centerX, y: currentY },
      data: {
        name: 'SUPERVISOR 決策中心',
        status: supervisorStatus,
        tools: supervisorTools,
      },
    })

    newEdges.push({
      id: 'start-supervisor',
      source: 'start',
      target: supervisorId,
      animated: supervisorStatus === 'running',
      style: { stroke: supervisorStatus === 'running' ? '#3b82f6' : '#10b981', strokeWidth: 2 },
    })

    currentY += layerSpacing
  }

  // 第三層：專家代理（並行顯示）
  if (grouped.expert && grouped.expert.length > 0) {
    const expertCount = grouped.expert.length
    const startX = centerX - ((expertCount - 1) * expertSpacing) / 2

    grouped.expert.forEach((agent: any, index: number) => {
      const expertId = `expert-${agent.name}`
      const expertX = startX + index * expertSpacing

      newNodes.push({
        id: expertId,
        type: 'agent',
        position: { x: expertX, y: currentY },
        data: {
          name: agent.display_name,
          status: agent.status,
          tools: agent.tools_used || [],
        },
      })

      // 從 supervisor 連接到專家
      newEdges.push({
        id: `supervisor-${expertId}`,
        source: 'supervisor-layer',
        target: expertId,
        animated: agent.status === 'running',
        style: { stroke: agent.status === 'running' ? '#3b82f6' : '#10b981', strokeWidth: 2 },
        label: '轉交'
      })
    })

    currentY += layerSpacing
  }

  // 第四層：整合節點
  if (grouped.integration && grouped.integration.length > 0) {
    const integrationAgent = grouped.integration[0]
    const integrationId = 'integration-layer'

    newNodes.push({
      id: integrationId,
      type: 'agent',
      position: { x: centerX, y: currentY },
      data: {
        name: integrationAgent.display_name,
        status: integrationAgent.status,
        tools: integrationAgent.tools_used || [],
      },
    })

    // 從所有專家連接到整合節點
    if (grouped.expert && grouped.expert.length > 0) {
      grouped.expert.forEach((agent: any) => {
        const expertId = `expert-${agent.name}`
        newEdges.push({
          id: `${expertId}-integration`,
          source: expertId,
          target: integrationId,
          style: { stroke: '#10b981', strokeWidth: 2 },
          label: '回報'
        })
      })
    } else {
      // 如果沒有專家代理，從 supervisor 連接
      newEdges.push({
        id: 'supervisor-integration',
        source: 'supervisor-layer',
        target: integrationId,
        style: { stroke: '#10b981', strokeWidth: 2 },
      })
    }

    currentY += layerSpacing
  }

  // 第五層：結束節點
  if (execution.value.status === 'completed') {
    newNodes.push({
      id: 'end',
      type: 'output',
      position: { x: centerX, y: currentY },
      data: { label: '完成' },
    })

    // 從整合節點或最後一個代理連接到結束
    const lastNodeId = grouped.integration && grouped.integration.length > 0
      ? 'integration-layer'
      : (grouped.expert && grouped.expert.length > 0
        ? `expert-${grouped.expert[grouped.expert.length - 1].name}`
        : 'supervisor-layer')

    newEdges.push({
      id: `${lastNodeId}-end`,
      source: lastNodeId,
      target: 'end',
      style: { stroke: '#10b981', strokeWidth: 2 },
    })
  }

  nodes.value = newNodes
  edges.value = newEdges

  console.log('[buildLogicalFlowGraph] Created', newNodes.length, 'nodes and', newEdges.length, 'edges')
}

const buildTimelineFlowGraph = () => {
  // 時間序視圖：線性佈局（原有邏輯）
  const newNodes: any[] = []
  const newEdges: any[] = []

  const nodeWidth = 250
  const verticalSpacing = 180

  newNodes.push({
    id: 'start',
    type: 'input',
    position: { x: nodeWidth, y: 0 },
    data: { label: '開始' },
  })

  execution.value.agents.forEach((agent: any, index: number) => {
    const nodeId = `agent-${index}`

    newNodes.push({
      id: nodeId,
      type: 'agent',
      position: { x: nodeWidth, y: 100 + index * verticalSpacing },
      data: {
        name: agent.display_name,
        status: agent.status,
        tools: agent.tools_used || [],
      },
    })

    const edgeStyle = agent.status === 'running'
      ? { stroke: '#3b82f6', strokeWidth: 2 }
      : { stroke: '#10b981', strokeWidth: 2 }

    if (index === 0) {
      newEdges.push({
        id: `start-${nodeId}`,
        source: 'start',
        target: nodeId,
        animated: agent.status === 'running',
        style: edgeStyle,
      })
    } else {
      newEdges.push({
        id: `agent-${index - 1}-${nodeId}`,
        source: `agent-${index - 1}`,
        target: nodeId,
        animated: agent.status === 'running',
        style: edgeStyle,
      })
    }
  })

  if (execution.value.status === 'completed') {
    newNodes.push({
      id: 'end',
      type: 'output',
      position: { x: nodeWidth, y: 100 + execution.value.agents.length * verticalSpacing },
      data: { label: '完成' },
    })

    newEdges.push({
      id: `agent-${execution.value.agents.length - 1}-end`,
      source: `agent-${execution.value.agents.length - 1}`,
      target: 'end',
      style: { stroke: '#10b981', strokeWidth: 2 },
    })
  }

  nodes.value = newNodes
  edges.value = newEdges

  console.log('[buildTimelineFlowGraph] Created', newNodes.length, 'nodes and', newEdges.length, 'edges')
}

const formatTime = (isoString: string) => {
  if (!isoString) return '-'
  return new Date(isoString).toLocaleTimeString('zh-TW')
}

const refreshData = () => {
  fetchExecutionData()
}

const toggleAutoRefresh = () => {
  autoRefresh.value = !autoRefresh.value
}

const toggleViewMode = () => {
  viewMode.value = viewMode.value === 'logical' ? 'timeline' : 'logical'
  buildFlowGraph()  // 重新建構流程圖
}

const startAutoRefresh = () => {
  if (refreshInterval.value) clearInterval(refreshInterval.value)

  refreshInterval.value = setInterval(() => {
    if (autoRefresh.value && props.threadId) {
      fetchExecutionData()
    }
  }, 10000) // 每 10 秒刷新（降低頻率）
}

watch(() => props.threadId, (newThreadId) => {
  if (newThreadId) {
    fetchExecutionData()
  }
})

// 監控節點和邊的變化，用於調試
watch([nodes, edges], ([newNodes, newEdges]) => {
  console.log('[AgentFlowChart] Graph updated:', {
    nodes: newNodes.length,
    edges: newEdges.length,
    nodeIds: newNodes.map((n: any) => n.id),
  })
}, { deep: true })

onMounted(() => {
  console.log('[AgentFlowChart] Component mounted')
  if (props.threadId) {
    fetchExecutionData()
  }
  startAutoRefresh()
})

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})
</script>

<style scoped>
@import "tailwindcss" reference;

.workflow-container {
  @apply bg-white rounded-lg shadow p-6;
  max-height: calc(100vh - 200px);
  overflow-y: auto;
}

.flow-canvas {
  @apply border border-gray-300 rounded bg-gray-50;
  height: 500px;
  overflow: auto;
  position: relative;
}

.execution-info {
  @apply bg-blue-50 border border-blue-200 rounded p-4;
}

.agent-timeline {
  @apply bg-gray-50 border border-gray-200 rounded p-4;
  max-height: 400px;
  overflow-y: auto;
}

/* 自訂捲動條樣式（Webkit 瀏覽器）*/
.workflow-container::-webkit-scrollbar,
.agent-timeline::-webkit-scrollbar {
  width: 8px;
}

.workflow-container::-webkit-scrollbar-track,
.agent-timeline::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.workflow-container::-webkit-scrollbar-thumb,
.agent-timeline::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.workflow-container::-webkit-scrollbar-thumb:hover,
.agent-timeline::-webkit-scrollbar-thumb:hover {
  background: #555;
}

.timeline-item {
  @apply bg-white border rounded p-3;
}

.timeline-item.running {
  @apply border-blue-400 bg-blue-50;
}

.timeline-item.completed {
  @apply border-green-400;
}

.status-badge {
  @apply text-xs px-2 py-1 rounded;
}

.status-badge.running {
  @apply bg-blue-500 text-white;
}

.status-badge.completed {
  @apply bg-green-500 text-white;
}

.tools-list {
  @apply pl-4 border-l-2 border-gray-300;
}

.tool-item {
  @apply text-sm;
}

.tool-tag {
  @apply text-xs px-2 py-1 rounded font-medium cursor-help;
  transition: all 0.2s ease;
}

.tool-tag.success {
  @apply bg-green-100 text-green-800 border border-green-300;
}

.tool-tag.error {
  @apply bg-red-100 text-red-800 border border-red-300;
}

.tool-tag:hover {
  @apply shadow-md transform scale-105;
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

/* flow-canvas 自訂捲動條樣式 */
.flow-canvas::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

.flow-canvas::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 5px;
}

.flow-canvas::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 5px;
}

.flow-canvas::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* 空白狀態樣式 */
.empty-state {
  @apply flex flex-col items-center justify-center h-full text-center;
  min-height: 500px;
}
</style>
