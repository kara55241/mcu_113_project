<template>
  <div class="min-h-screen bg-gray-100">
    <header class="bg-white shadow">
      <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        <h1 class="text-3xl font-bold text-gray-900">Agent 工作流</h1>
        <router-link to="/" class="text-indigo-600 hover:text-indigo-900">← 返回首頁</router-link>
      </div>
    </header>

    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <!-- Thread 選擇器 -->
      <div class="card mb-6">
        <h2 class="text-lg font-semibold mb-4">選擇對話 Thread</h2>

        <div v-if="loadingThreads" class="text-center py-4">
          <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p class="text-gray-600 mt-2">載入中...</p>
        </div>

        <div v-else-if="threadsError" class="error-message">
          {{ threadsError }}
        </div>

        <div v-else-if="threads.length === 0" class="info-message">
          <p>目前沒有活動的對話 Thread</p>
          <p class="text-sm text-gray-500 mt-1">請先在主系統進行對話</p>
        </div>

        <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div
            v-for="thread in threads"
            :key="thread.thread_id"
            @click="selectThread(thread.thread_id)"
            class="thread-card"
            :class="{ active: selectedThreadId === thread.thread_id }"
          >
            <div class="flex justify-between items-start">
              <div class="flex-1">
                <div class="font-mono text-sm text-gray-600 mb-1">
                  {{ truncateThreadId(thread.thread_id) }}
                </div>
                <div class="text-sm text-gray-700 mb-2" v-if="thread.query">
                  {{ truncateQuery(thread.query) }}
                </div>
                <div class="text-xs text-gray-500">
                  {{ formatTime(thread.started_at) }}
                </div>
              </div>
              <span
                class="status-badge"
                :class="thread.status"
              >
                {{ thread.status === 'running' ? '執行中' : '已完成' }}
              </span>
            </div>
          </div>
        </div>

        <div class="mt-4 text-center">
          <button
            @click="refreshThreads"
            :disabled="loadingThreads"
            class="btn-secondary"
          >
            刷新列表
          </button>
        </div>
      </div>

      <!-- 工作流視覺化 -->
      <div v-if="selectedThreadId" class="card">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-lg font-semibold">Agent 執行流程</h2>
          <button
            @click="viewGraphForThread"
            class="btn-primary"
            title="查看此對話使用的知識圖譜"
          >
            <svg class="w-4 h-4 inline mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
            </svg>
            查看知識圖譜
          </button>
        </div>
        <AgentFlowChart :thread-id="selectedThreadId" />
      </div>

      <div v-else class="card">
        <div class="info-message">
          <p>請從上方選擇一個 Thread 查看其工作流</p>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AgentFlowChart from '../components/AgentFlowChart.vue'
import { api } from '../api/client'

const router = useRouter()

const threads = ref<any[]>([])
const loadingThreads = ref(false)
const threadsError = ref<string | null>(null)
const selectedThreadId = ref<string | null>(null)
const refreshInterval = ref<number | null>(null)

const fetchThreads = async () => {
  loadingThreads.value = true
  threadsError.value = null

  try {
    // 不傳遞 thread_id，獲取所有 threads
    const response = await api.getAgentStatus()

    // 處理多種可能的回應格式
    if (response.data.threads && Array.isArray(response.data.threads)) {
      threads.value = response.data.threads
    } else if (Array.isArray(response.data)) {
      threads.value = response.data
    } else {
      console.warn('Unexpected API response format:', response.data)
      threads.value = []
      threadsError.value = '資料格式不符預期'
    }

    console.log(`[WorkflowView] Loaded ${threads.value.length} threads`)
  } catch (err: any) {
    threadsError.value = err.response?.data?.error || '載入 Thread 列表失敗'
    console.error('Failed to fetch threads:', err)
  } finally {
    loadingThreads.value = false
  }
}

const selectThread = (threadId: string) => {
  selectedThreadId.value = threadId
}

const refreshThreads = () => {
  fetchThreads()
}

const viewGraphForThread = () => {
  if (!selectedThreadId.value) return

  // Navigate to graph view with thread_id as query parameter
  router.push({
    name: 'graph',
    query: { thread_id: selectedThreadId.value }
  })
}

const truncateThreadId = (threadId: string): string => {
  if (threadId.length <= 16) return threadId
  return threadId.substring(0, 8) + '...' + threadId.substring(threadId.length - 8)
}

const truncateQuery = (query: string): string => {
  if (query.length <= 60) return query
  return query.substring(0, 60) + '...'
}

const formatTime = (isoString: string): string => {
  if (!isoString) return '-'
  const date = new Date(isoString)
  return date.toLocaleString('zh-TW', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const startAutoRefresh = () => {
  refreshInterval.value = setInterval(() => {
    fetchThreads()
  }, 5000) // 每 5 秒刷新 Thread 列表
}

onMounted(() => {
  fetchThreads()
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

.card {
  @apply bg-white rounded-lg shadow p-6;
}

.thread-card {
  @apply border border-gray-300 rounded-lg p-4 cursor-pointer transition-all hover:border-blue-400 hover:shadow-md;
}

.thread-card.active {
  @apply border-blue-600 bg-blue-50 shadow-lg;
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
