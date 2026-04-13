<template>
  <div class="page-card">
    <div class="page-header">
      <div>
        <h2 class="page-title">查询历史</h2>
        <p class="page-subtitle">
          查看已落库的查询记录，便于回溯问题、执行模式、模板命中和历史快照。
        </p>
      </div>
      <el-space wrap>
        <el-select v-model="filters.query_type" clearable placeholder="查询类型" style="width: 180px">
          <el-option label="NL_QUERY_PLAN" value="NL_QUERY_PLAN" />
          <el-option label="AGGREGATE" value="AGGREGATE" />
          <el-option label="DETAIL" value="DETAIL" />
          <el-option label="COMPARE" value="COMPARE" />
        </el-select>
        <el-input
          v-model="filters.keyword"
          clearable
          placeholder="按问题关键词检索"
          style="width: 220px"
          @keyup.enter="handleSearch"
        />
        <el-input
          v-model="filters.trace_id"
          clearable
          placeholder="按 Trace ID 过滤"
          style="width: 220px"
          @keyup.enter="handleSearch"
        />
        <el-button type="primary" :loading="loading" @click="handleSearch">查询</el-button>
        <el-button :disabled="loading" @click="resetFilters">重置</el-button>
      </el-space>
    </div>

    <el-alert
      v-if="warningText"
      :title="warningText"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    />

    <el-table :data="list" border stripe row-key="id">
      <el-table-column prop="question" label="历史问题" min-width="320" show-overflow-tooltip />
      <el-table-column label="类型" width="140">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ formatQueryType(row.query_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="执行模式" width="130">
        <template #default="{ row }">
          <el-tag size="small" :type="resolveExecutionModeTagType(row.execution_mode)">
            {{ formatExecutionMode(row.execution_mode) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="模板命中" width="180">
        <template #default="{ row }">
          <div class="tag-cell">
            <el-tag size="small" :type="row.template_hit ? 'success' : 'info'">
              {{ row.template_hit ? '已命中' : '未命中' }}
            </el-tag>
            <span class="minor-text">{{ row.template_id || '-' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="220">
        <template #default="{ row }">
          <div class="tag-cell">
            <el-tag size="small" :type="resolveStatusTagType(row.status_code || row.status)">
              {{ row.status_code || row.status || '-' }}
            </el-tag>
            <span class="minor-text">{{ row.status_message || row.message || '-' }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="result_count" label="结果数" width="90" />
      <el-table-column prop="created_at" label="时间" min-width="180">
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <el-space>
            <el-button size="small" @click="view(row)">查看详情</el-button>
            <el-button size="small" type="primary" plain @click="requery(row)">重新查询</el-button>
          </el-space>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && list.length === 0" description="暂无查询历史记录" style="margin-top: 16px" />

    <div class="pager-wrap">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next"
        :total="payload?.total ?? 0"
        :current-page="pager.page"
        :page-size="pager.page_size"
        :page-sizes="[10, 20, 50, 100]"
        @current-change="handlePageChange"
        @size-change="handlePageSizeChange"
      />
    </div>

    <el-drawer
      v-model="detailVisible"
      title="查询历史详情"
      size="48%"
      destroy-on-close
    >
      <div v-loading="detailLoading">
        <el-alert
          v-if="detailError"
          :title="detailError"
          type="error"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        />

        <template v-if="detailData">
          <div class="detail-toolbar">
            <el-space wrap>
              <el-tag effect="dark" :type="resolveStatusTagType(detailData.status_code || detailData.status)">
                {{ detailData.status_code || detailData.status || '-' }}
              </el-tag>
              <el-tag :type="resolveExecutionModeTagType(detailData.execution_mode)">
                {{ formatExecutionMode(detailData.execution_mode) }}
              </el-tag>
              <el-tag :type="detailData.template_hit ? 'success' : 'info'">
                {{ detailData.template_hit ? '模板已命中' : '模板未命中' }}
              </el-tag>
            </el-space>
            <el-button size="small" type="primary" plain @click="requery(detailData)">重新查询</el-button>
          </div>

          <el-descriptions :column="1" border style="margin-bottom: 16px">
            <el-descriptions-item label="历史问题">
              {{ detailData.question || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="查询类型">
              {{ formatQueryType(detailData.query_type) }}
            </el-descriptions-item>
            <el-descriptions-item label="执行模式">
              {{ formatExecutionMode(detailData.execution_mode) }}
            </el-descriptions-item>
            <el-descriptions-item label="模板 ID">
              {{ detailData.template_id || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="状态说明">
              {{ detailData.status_message || detailData.message || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="Trace ID">
              {{ detailData.trace_id || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="时间">
              {{ formatDateTime(detailData.created_at) }}
            </el-descriptions-item>
          </el-descriptions>

          <el-collapse>
            <el-collapse-item name="parsed" title="问题解析（parsed）">
              <div class="mono-block">{{ formatJson(detailData.parsed) }}</div>
            </el-collapse-item>
            <el-collapse-item name="query-result" title="查询结果快照（query_result）">
              <div class="mono-block">{{ formatJson(detailData.query_result) }}</div>
            </el-collapse-item>
            <el-collapse-item name="response-meta" title="响应元信息（response_meta）">
              <div class="mono-block">{{ formatJson(detailData.response_meta) }}</div>
            </el-collapse-item>
            <el-collapse-item name="execution-binding" title="执行绑定（execution_binding）">
              <div class="mono-block">{{ formatJson(detailData.execution_binding) }}</div>
            </el-collapse-item>
            <el-collapse-item name="execution-summary" title="执行摘要（execution_summary）">
              <div class="mono-block">{{ formatJson(detailData.execution_summary) }}</div>
            </el-collapse-item>
            <el-collapse-item name="request-payload" title="原始请求载荷（request_payload_json）">
              <div class="mono-block">{{ formatJson(detailData.request_payload_json) }}</div>
            </el-collapse-item>
          </el-collapse>
        </template>

        <el-empty
          v-else-if="!detailLoading && !detailError"
          description="请选择一条历史记录查看详情"
        />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  fetchQueryHistory,
  fetchQueryHistoryDetail,
  type QueryHistoryDetailResponse,
  type QueryHistoryItem,
  type QueryHistoryResponse,
} from '@/api/logistics'
import { saveLastQueryContext, saveQueryPageDraft } from '@/utils/queryStorage'

const router = useRouter()
const payload = ref<QueryHistoryResponse | null>(null)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<QueryHistoryDetailResponse | null>(null)
const loading = ref(false)
const loadError = ref('')
const detailError = ref('')
const filters = reactive({
  query_type: '',
  keyword: '',
  trace_id: '',
})
const pager = reactive({
  page: 1,
  page_size: 20,
})

/**
 * 当前表格数据。
 */
const list = computed(() => payload.value?.items ?? [])

/**
 * 页面级提示文案。
 */
const warningText = computed(() => payload.value?.load_warning || loadError.value)

/**
 * 加载查询历史列表。
 * 说明：
 * 这里仍沿用列表接口，只在查看详情时再按需拉单条详情，避免页面初始请求过重。
 */
async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const resp = await fetchQueryHistory({
      page: pager.page,
      page_size: pager.page_size,
      query_type: filters.query_type || undefined,
      keyword: filters.keyword.trim() || undefined,
      trace_id: filters.trace_id || undefined,
    })
    payload.value = (resp.data ?? resp ?? null) as QueryHistoryResponse | null
    pager.page = payload.value?.page || pager.page
    pager.page_size = payload.value?.page_size || pager.page_size
  } catch (_error) {
    loadError.value = '当前后端未开放查询历史接口，或接口路径与前端默认配置不一致。'
    payload.value = {
      total: 0,
      page: pager.page,
      page_size: pager.page_size,
      items: [],
      load_warning: null,
    }
  } finally {
    loading.value = false
  }
}

/**
 * 以当前筛选条件重新查询历史列表。
 * 说明：
 * 关键词、类型和 Trace ID 变更后，统一回到第一页，避免仍停留在旧页码导致“查不到数据”的错觉。
 */
function handleSearch() {
  pager.page = 1
  load()
}

/**
 * 重置筛选条件并回到第一页。
 */
function resetFilters() {
  filters.query_type = ''
  filters.keyword = ''
  filters.trace_id = ''
  pager.page = 1
  pager.page_size = 20
  load()
}

/**
 * 切换页码。
 */
function handlePageChange(page: number) {
  pager.page = page
  load()
}

/**
 * 切换每页条数。
 * 说明：
 * 调整分页大小后也回到第一页，避免请求越界页码。
 */
function handlePageSizeChange(pageSize: number) {
  pager.page_size = pageSize
  pager.page = 1
  load()
}

/**
 * 查看单条历史详情。
 * 说明：
 * 详情统一走后端单条接口，避免列表页反复拼装结构化快照。
 */
async function view(row: QueryHistoryItem) {
  detailVisible.value = true
  detailLoading.value = true
  detailError.value = ''
  detailData.value = null
  try {
    const resp = await fetchQueryHistoryDetail(row.id)
    detailData.value = (resp.data ?? resp ?? null) as QueryHistoryDetailResponse | null
  } catch (_error) {
    detailError.value = '查询历史详情加载失败，请稍后重试。'
  } finally {
    detailLoading.value = false
  }
}

/**
 * 重新发起查询。
 * 说明：
 * 1. 这里只负责把历史问题或结构化条件带回对应查询页；
 * 2. 不在历史页自动重跑，避免用户离开历史页后立即触发新请求；
 * 3. 优先复用已有的 queryStorage，减少新增全局状态。
 */
function requery(row: QueryHistoryItem | QueryHistoryDetailResponse) {
  if (row.query_type === 'AGGREGATE') {
    const aggregatePayload = extractAggregatePayload(row.request_payload_json)
    if (!aggregatePayload) {
      ElMessage.warning('当前结构化历史记录缺少可回填的请求参数。')
      return
    }

    saveQueryPageDraft({
      sourcePage: 'structured-query',
      formData: aggregatePayload,
    })
    saveLastQueryContext({
      sourcePage: 'structured-query',
      requestPayload: aggregatePayload,
      rawResponse: null,
      queryResult: null,
      selectedRow: null,
    })
    router.push('/structured-query')
    return
  }

  if (!row.question || row.question === '-') {
    ElMessage.warning('当前历史记录缺少可回填的问题文本。')
    return
  }

  saveQueryPageDraft({
    sourcePage: 'nl-query',
    formData: {
      question: row.question,
    },
  })
  saveLastQueryContext({
    sourcePage: 'nl-query',
    question: row.question,
    requestPayload: { question: row.question },
    rawResponse: null,
    parsed: null,
    queryResult: null,
    selectedRow: null,
  })
  router.push('/nl-query')
}

/**
 * 提取结构化查询的原始请求参数。
 * 说明：
 * 历史日志的 request_payload_json 在不同来源下可能层级略有差异，
 * 这里只提取前端条件查询页已经支持的最小字段集合。
 */
function extractAggregatePayload(payloadJson: Record<string, any> | null | undefined) {
  if (!payloadJson || typeof payloadJson !== 'object') return null

  let candidate: Record<string, any> | null = null
  if (payloadJson.metric_type || payloadJson.source_scope || payloadJson.year_month_list) {
    candidate = payloadJson
  } else {
    const nestedPayload = payloadJson.request_payload
    if (isAggregatePayload(nestedPayload)) {
      candidate = nestedPayload
    }
  }

  if (!candidate) return null

  return {
    metric_type: candidate.metric_type,
    source_scope: candidate.source_scope,
    year_month_list: Array.isArray(candidate.year_month_list) ? candidate.year_month_list : [],
    customer_name: candidate.customer_name ?? null,
    logistics_company_name: candidate.logistics_company_name ?? null,
    region_name: candidate.region_name ?? null,
    origin_place: candidate.origin_place ?? null,
    transport_mode: candidate.transport_mode ?? null,
    group_by: Array.isArray(candidate.group_by) ? candidate.group_by : [],
    order_direction: candidate.order_direction ?? 'desc',
    limit: candidate.limit ?? 100,
  }
}

/**
 * 判断对象是否可视为结构化查询请求。
 */
function isAggregatePayload(value: unknown): value is Record<string, any> {
  if (!value || typeof value !== 'object') return false
  const payload = value as Record<string, any>
  return Boolean(payload.metric_type || payload.source_scope || payload.year_month_list)
}

/**
 * 格式化查询类型名称。
 */
function formatQueryType(value: string | null | undefined) {
  if (value === 'NL_QUERY_PLAN') return '自然语言'
  if (value === 'AGGREGATE') return '结构化统计'
  if (value === 'DETAIL') return '明细查询'
  if (value === 'COMPARE') return '对比查询'
  return value || '-'
}

/**
 * 格式化执行模式名称。
 */
function formatExecutionMode(value: string | null | undefined) {
  if (value === 'database') return '数据库'
  if (value === 'fallback') return '兼容模式'
  if (value === 'error_fallback') return '错误兜底'
  return value || '-'
}

/**
 * 统一映射执行模式标签颜色。
 */
function resolveExecutionModeTagType(value: string | null | undefined) {
  if (value === 'database') return 'success'
  if (value === 'fallback') return 'warning'
  if (value === 'error_fallback') return 'danger'
  return 'info'
}

/**
 * 统一映射状态标签颜色。
 */
function resolveStatusTagType(value: string | null | undefined) {
  if (value === 'OK') return 'success'
  if (value === 'EMPTY_RESULT' || value === 'FALLBACK_MODE' || value === 'DETAIL_NOT_FOUND') return 'warning'
  if (value === 'EXECUTION_ERROR') return 'danger'
  return 'info'
}

/**
 * 格式化时间。
 */
function formatDateTime(value: string | null | undefined) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
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
  gap: 16px;
  margin-bottom: 16px;
}

.tag-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.minor-text {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
  word-break: break-all;
}

.detail-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
