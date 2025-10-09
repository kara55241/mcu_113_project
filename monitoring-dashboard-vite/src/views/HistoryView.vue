<template>
  <div class="min-h-screen bg-gray-100">
    <header class="bg-white shadow">
      <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        <h1 class="text-3xl font-bold text-gray-900">執行歷史</h1>
        <router-link to="/" class="text-indigo-600 hover:text-indigo-900">← 返回首頁</router-link>
      </div>
    </header>

    <main class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
      <div class="card">
        <div class="flex justify-between items-center mb-6">
          <h2 class="text-lg font-semibold">Thread 執行歷史</h2>
          <button
            @click="refreshHistory"
            :disabled="loading"
            class="btn-secondary"
          >
            {{ loading ? '載入中...' : '刷新' }}
          </button>
        </div>

        <div v-if="loading" class="text-center py-8">
          <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <p class="text-gray-600 mt-2">載入歷史記錄中...</p>
        </div>

        <div v-else-if="error" class="error-message">
          {{ error }}
        </div>

        <div v-else-if="threads.length === 0" class="info-message">
          <p>目前沒有執行歷史記錄</p>
        </div>

        <div v-else>
          <!-- 統計摘要 -->
          <div class="stats-panel mb-6">
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div class="stat-item">
                <div class="stat-label">總 Thread 數</div>
                <div class="stat-value">{{ threads.length }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">總 Checkpoint 數</div>
                <div class="stat-value">{{ totalCheckpoints }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">總數據大小</div>
                <div class="stat-value">{{ formatBytes(totalSize) }}</div>
              </div>
              <div class="stat-item">
                <div class="stat-label">數據來源</div>
                <div class="stat-value text-sm">SQLite</div>
              </div>
            </div>
          </div>

          <!-- Thread 列表 -->
          <div class="thread-list">
            <div
              v-for="thread in threads"
              :key="thread.thread_id"
              class="thread-item"
              @click="viewThreadDetails(thread.thread_id)"
            >
              <div class="thread-header">
                <div class="flex-1">
                  <div class="thread-id">
                    <span class="font-mono text-sm">{{ thread.thread_id }}</span>
                  </div>
                  <div class="thread-meta">
                    <span class="meta-item">
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"></path>
                      </svg>
                      {{ thread.checkpoint_count }} Checkpoints
                    </span>
                    <span class="meta-item">
                      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                      </svg>
                      {{ formatBytes(thread.total_size) }}
                    </span>
                  </div>
                </div>
                <div class="thread-actions">
                  <button
                    @click.stop="viewWorkflow(thread.thread_id)"
                    class="action-btn"
                    title="查看工作流"
                  >
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path>
                    </svg>
                  </button>
                </div>
              </div>

              <div class="thread-timeline">
                <div class="timeline-point">
                  <span class="text-xs text-gray-500">首次:</span>
                  <span class="text-xs">ID {{ thread.first_checkpoint }}</span>
                </div>
                <div class="timeline-line"></div>
                <div class="timeline-point">
                  <span class="text-xs text-gray-500">最新:</span>
                  <span class="text-xs">ID {{ thread.last_checkpoint }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- 分頁（可選） -->
          <div v-if="threads.length >= 100" class="pagination-info mt-4 text-center text-sm text-gray-600">
            顯示最近 100 條記錄
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api } from '../api/client'

const router = useRouter()

const threads = ref<any[]>([])
const loading = ref(false)
const error = ref<string | null>(null)

const totalCheckpoints = computed(() => {
  return threads.value.reduce((sum, thread) => sum + thread.checkpoint_count, 0)
})

const totalSize = computed(() => {
  return threads.value.reduce((sum, thread) => sum + thread.total_size, 0)
})

const fetchHistory = async () => {
  loading.value = true
  error.value = null

  try {
    const response = await api.getAgentHistory()
    threads.value = response.data.threads || []
  } catch (err: any) {
    error.value = err.response?.data?.error || '載入歷史記錄失敗'
    console.error('Failed to fetch history:', err)
  } finally {
    loading.value = false
  }
}

const refreshHistory = () => {
  fetchHistory()
}

const viewThreadDetails = (threadId: string) => {
  console.log('View details for thread:', threadId)
  // 可以跳轉到詳情頁或展開詳情面板
}

const viewWorkflow = (threadId: string) => {
  router.push({ name: 'workflow', query: { thread_id: threadId } })
}

const formatBytes = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

onMounted(() => {
  fetchHistory()
})
</script>

<style scoped>
@import "tailwindcss" reference;

.card {
  @apply bg-white rounded-lg shadow p-6;
}

.stats-panel {
  @apply bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4;
}

.stat-item {
  @apply text-center;
}

.stat-label {
  @apply text-xs text-gray-600 mb-1;
}

.stat-value {
  @apply text-2xl font-bold text-gray-900;
}

.thread-list {
  @apply space-y-3;
}

.thread-item {
  @apply border border-gray-300 rounded-lg p-4 cursor-pointer transition-all hover:border-blue-400 hover:shadow-md bg-white;
}

.thread-header {
  @apply flex justify-between items-start;
}

.thread-id {
  @apply text-gray-900 font-medium mb-2;
}

.thread-meta {
  @apply flex gap-4 text-gray-600;
}

.meta-item {
  @apply flex items-center gap-1 text-sm;
}

.thread-actions {
  @apply flex gap-2;
}

.action-btn {
  @apply p-2 text-blue-600 hover:bg-blue-100 rounded transition-colors;
}

.thread-timeline {
  @apply flex items-center gap-2 mt-3 pt-3 border-t border-gray-200;
}

.timeline-point {
  @apply flex items-center gap-1;
}

.timeline-line {
  @apply flex-1 h-px bg-gray-300;
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

.pagination-info {
  @apply bg-yellow-50 border border-yellow-200 rounded p-2;
}
</style>
