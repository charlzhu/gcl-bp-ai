<template>
  <div class="page-card">
    <div class="page-header">
      <div>
        <h2 class="page-title">查询历史</h2>
        <p class="page-subtitle">
          查看已落库的查询记录，便于回溯问题、模板命中、执行模式和原始载荷。
        </p>
      </div>
      <el-space>
        <el-select v-model="filters.query_type" clearable placeholder="查询类型" style="width: 180px">
          <el-option label="NL_QUERY_PLAN" value="NL_QUERY_PLAN" />
          <el-option label="AGGREGATE" value="AGGREGATE" />
          <el-option label="DETAIL" value="DETAIL" />
          <el-option label="COMPARE" value="COMPARE" />
        </el-select>
        <el-input
          v-model="filters.trace_id"
          clearable
          placeholder="按 Trace ID 过滤"
          style="width: 220px"
        />
        <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      </el-space>
    </div>

    <el-alert v-if="warningText" :title="warningText" type="warning" :closable="false" show-icon style="margin-bottom: 16px" />

    <el-table :data="list" border stripe>
      <el-table-column prop="question" label="问题/标题" min-width="260" />
      <el-table-column prop="query_type" label="类型" width="140" />
      <el-table-column prop="execution_mode" label="执行模式" width="120" />
      <el-table-column prop="metric_type" label="指标" width="140" />
      <el-table-column prop="result_count" label="条数" width="90" />
      <el-table-column prop="status" label="状态" width="120" />
      <el-table-column prop="created_at" label="时间" min-width="180" />
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="scope">
          <el-button size="small" @click="view(scope.row)">查看</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="visible" title="查询详情" width="65%">
      <div class="mono-block">{{ formatJson(current) }}</div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchQueryHistory, type QueryHistoryItem, type QueryHistoryResponse } from '@/api/logistics'

const payload = ref<QueryHistoryResponse | null>(null)
const visible = ref(false)
const current = ref<QueryHistoryItem | null>(null)
const loading = ref(false)
const loadError = ref('')
const filters = reactive({
  query_type: '',
  trace_id: '',
})

/**
 * 当前表格数据。
 */
const list = computed(() => payload.value?.items ?? [])

/**
 * 页面提示文案。
 */
const warningText = computed(() => payload.value?.load_warning || loadError.value)

/**
 * 加载查询历史。
 * 说明：
 * 如果当前后端还没有开放该接口，这里会显示友好提示，不影响页面其它功能。
 */
async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const resp = await fetchQueryHistory({
      limit: 100,
      query_type: filters.query_type || undefined,
      trace_id: filters.trace_id || undefined,
    })
    payload.value = (resp.data ?? resp ?? null) as QueryHistoryResponse | null
  } catch (_error) {
    loadError.value = '当前后端未开放查询历史接口，或接口路径与前端默认配置不一致。'
    payload.value = {
      total: 0,
      items: [],
      load_warning: null,
    }
  } finally {
    loading.value = false
  }
}

/**
 * 查看单条历史记录。
 */
function view(row: Record<string, any>) {
  current.value = row as QueryHistoryItem
  visible.value = true
}

/**
 * JSON 格式化。
 */
function formatJson(value: unknown) {
  if (!value) return '-'
  return JSON.stringify(value, null, 2)
}

onMounted(() => {
  load()
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
</style>
