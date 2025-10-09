<template>
  <div class="min-h-screen bg-gray-100">
    <!-- Header -->
    <header class="bg-white shadow">
      <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 flex items-center justify-between">
        <h1 class="text-3xl font-bold text-gray-900">
          AI Agent 監控儀表板
        </h1>
        <div class="flex items-center gap-3">
          <button
            @click="refreshData"
            class="inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
          >
            <svg class="h-4 w-4 mr-1" :class="{ 'animate-spin': loading }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            刷新
          </button>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main>
      <div class="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <!-- Stats Cards -->
        <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 mb-8">
          <!-- Health Status -->
          <div class="card">
            <div class="flex items-center">
              <div class="flex-shrink-0">
                <svg class="h-6 w-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div class="ml-5 w-0 flex-1">
                <dl>
                  <dt class="text-sm font-medium text-gray-500 truncate">系統狀態</dt>
                  <dd class="text-lg font-semibold text-gray-900">{{ healthStatus }}</dd>
                </dl>
              </div>
            </div>
          </div>

          <!-- Checkpoint Count -->
          <div class="card">
            <div class="flex items-center">
              <div class="flex-shrink-0">
                <svg class="h-6 w-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" />
                </svg>
              </div>
              <div class="ml-5 w-0 flex-1">
                <dl>
                  <dt class="text-sm font-medium text-gray-500 truncate">Checkpoint 記錄</dt>
                  <dd class="text-lg font-semibold text-gray-900">{{ checkpointCount }}</dd>
                </dl>
              </div>
            </div>
          </div>

          <!-- API Version -->
          <div class="card">
            <div class="flex items-center">
              <div class="flex-shrink-0">
                <svg class="h-6 w-6 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
              <div class="ml-5 w-0 flex-1">
                <dl>
                  <dt class="text-sm font-medium text-gray-500 truncate">API 版本</dt>
                  <dd class="text-lg font-semibold text-gray-900">{{ apiVersion }}</dd>
                </dl>
              </div>
            </div>
          </div>
        </div>

        <!-- Quick Navigation -->
        <div class="card">
          <h3 class="text-lg leading-6 font-medium text-gray-900 mb-4">
            快速導航
          </h3>
          <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <router-link
              to="/workflow"
              class="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-gray-400 focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500 transition"
            >
              <div class="flex-shrink-0">
                <svg class="h-10 w-10 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900">Agent 工作流</p>
                <p class="text-sm text-gray-500">查看 AI Agent 執行流程</p>
              </div>
            </router-link>

            <router-link
              to="/graph"
              class="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-gray-400 focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500 transition"
            >
              <div class="flex-shrink-0">
                <svg class="h-10 w-10 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                </svg>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900">知識圖譜</p>
                <p class="text-sm text-gray-500">Neo4j 圖譜視覺化</p>
              </div>
            </router-link>

            <router-link
              to="/history"
              class="relative rounded-lg border border-gray-300 bg-white px-6 py-5 shadow-sm flex items-center space-x-3 hover:border-gray-400 focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500 transition"
            >
              <div class="flex-shrink-0">
                <svg class="h-10 w-10 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium text-gray-900">執行歷史</p>
                <p class="text-sm text-gray-500">查看所有 Thread 記錄</p>
              </div>
            </router-link>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../api/client'

const loading = ref(false)
const healthStatus = ref('檢查中...')
const apiVersion = ref('...')
const checkpointCount = ref(0)

const fetchHealth = async () => {
  try {
    const response = await api.health()
    healthStatus.value = response.data.status === 'healthy' ? '正常運行' : '異常'
    apiVersion.value = response.data.version || 'N/A'
  } catch (error) {
    healthStatus.value = '連接失敗'
    console.error('Health check failed:', error)
  }
}

const fetchAgentStatus = async () => {
  try {
    const response = await api.getAgentStatus()
    checkpointCount.value = response.data.checkpoint_count || 0
  } catch (error) {
    console.error('Failed to fetch agent status:', error)
  }
}

const refreshData = async () => {
  loading.value = true
  try {
    await Promise.all([fetchHealth(), fetchAgentStatus()])
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refreshData()
})
</script>
