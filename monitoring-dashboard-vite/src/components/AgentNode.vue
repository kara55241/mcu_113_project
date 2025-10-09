<template>
  <div
    class="agent-node"
    :class="{
      running: data.status === 'running',
      completed: data.status === 'completed',
    }"
  >
    <div class="node-header">
      <div class="node-icon">
        <svg
          v-if="data.status === 'running'"
          class="animate-spin h-5 w-5"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            class="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            stroke-width="4"
          ></circle>
          <path
            class="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          ></path>
        </svg>
        <svg
          v-else
          class="h-5 w-5"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
        >
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
            clip-rule="evenodd"
          />
        </svg>
      </div>
      <div class="node-title">{{ data.name }}</div>
    </div>

    <div v-if="data.tools && data.tools.length > 0" class="node-tools">
      <div class="tools-label">工具:</div>
      <div class="tools-badges">
        <span
          v-for="(tool, index) in data.tools.slice(0, 3)"
          :key="index"
          class="tool-badge"
          :class="tool.status"
          :title="tool.tool"
        >
          {{ truncateTool(tool.tool) }}
        </span>
        <span v-if="data.tools.length > 3" class="tool-badge more">
          +{{ data.tools.length - 3 }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Props {
  data: {
    name: string
    status: 'running' | 'completed'
    tools?: Array<{
      tool: string
      status: 'success' | 'error'
    }>
  }
}

defineProps<Props>()

const truncateTool = (toolName: string): string => {
  if (toolName.length <= 15) return toolName
  return toolName.substring(0, 12) + '...'
}
</script>

<style scoped>
@import "tailwindcss" reference;

.agent-node {
  @apply bg-white border-2 rounded-lg shadow-lg p-4 min-w-[200px] transition-all;
}

.agent-node.running {
  @apply border-blue-500 bg-blue-50 shadow-blue-200 animate-pulse;
}

.agent-node.completed {
  @apply border-green-500;
}

.node-header {
  @apply flex items-center gap-2 mb-2;
}

.node-icon {
  @apply flex-shrink-0;
}

.agent-node.running .node-icon {
  @apply text-blue-600;
}

.agent-node.completed .node-icon {
  @apply text-green-600;
}

.node-title {
  @apply font-semibold text-sm;
}

.node-tools {
  @apply mt-2 pt-2 border-t border-gray-200;
}

.tools-label {
  @apply text-xs text-gray-500 mb-1;
}

.tools-badges {
  @apply flex flex-wrap gap-1;
}

.tool-badge {
  @apply text-xs px-2 py-0.5 rounded bg-gray-200 text-gray-700;
}

.tool-badge.success {
  @apply bg-green-100 text-green-700;
}

.tool-badge.error {
  @apply bg-red-100 text-red-700;
}

.tool-badge.more {
  @apply bg-gray-300 font-semibold;
}
</style>
