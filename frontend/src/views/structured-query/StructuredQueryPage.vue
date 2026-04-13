<template>
  <div>
    <div class="page-card" style="margin-bottom: 20px">
      <h2 class="page-title">条件查询</h2>
      <p class="page-subtitle">
        面向后端 <code>/api/v1/logistics/query-service/aggregate</code> 的结构化查询页。
        当前第二版在第一版基础上增强了结果表格与明细跳转能力。
      </p>

      <el-form :model="form" label-width="120px">
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item label="指标">
              <el-select v-model="form.metric_type" style="width: 100%">
                <el-option label="运量（瓦数）" value="shipment_watt" />
                <el-option label="总费用" value="total_fee" />
                <el-option label="车次" value="shipment_trip_count" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="来源范围">
              <el-select v-model="form.source_scope" style="width: 100%">
                <el-option label="历史" value="hist" />
                <el-option label="系统" value="sys" />
                <el-option label="全部" value="all" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="月份">
              <el-input v-model="monthInput" placeholder="例如：2025-03，多个用英文逗号分隔" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="客户">
              <el-input v-model="form.customer_name" placeholder="例如：华阳集团" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="物流公司">
              <el-input v-model="form.logistics_company_name" placeholder="选填" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="区域">
              <el-input v-model="form.region_name" placeholder="例如：华东" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="运输方式">
              <el-input v-model="form.transport_mode" placeholder="例如：公路 / 铁路" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="始发地">
              <el-input v-model="form.origin_place" placeholder="例如：合肥 / 阜宁" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="分组维度">
              <el-select v-model="form.group_by" style="width: 100%">
                <el-option label="按月份" value="biz_month" />
                <el-option label="按客户" value="customer_name" />
                <el-option label="按物流公司" value="logistics_company_name" />
                <el-option label="按区域" value="region_name" />
                <el-option label="按始发地" value="origin_place" />
                <el-option label="按运输方式" value="transport_mode" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-space>
          <el-button type="primary" :loading="loading" @click="handleQuery">开始查询</el-button>
          <el-button @click="fillExample">填充示例</el-button>
        </el-space>
      </el-form>
    </div>

    <QueryResultCard
      :query-result="resultData"
      :response-meta="resultData?.response_meta ?? null"
      :question="buildResultQuestion()"
      :request-payload="buildPayload()"
      @open-detail="openDetail"
      @row-detail="openRowDetail"
    />
    <div class="page-card" style="margin-top: 20px">
      <el-collapse>
        <el-collapse-item title="查看本次请求参数（调试）" name="request-payload">
          <div class="mono-block">{{ JSON.stringify(buildPayload(), null, 2) }}</div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchAggregateQuery, type LogisticsAggregatePayload } from '@/api/logistics'
import QueryResultCard from '@/components/QueryResultCard.vue'
import { formatMetricTypeLabel } from '@/utils/queryResultPresentation'
import {
  getLastQueryContext,
  getQueryPageDraft,
  saveLastQueryContext,
  saveQueryPageDraft,
} from '@/utils/queryStorage'

const router = useRouter()
const loading = ref(false)
const monthInput = ref('2025-03')
const resultData = ref<Record<string, any> | null>(null)

/**
 * 结构化查询表单。
 * 说明：
 * 这里优先覆盖附件里明确要求的一期关键筛选维度，
 * 包括客户、物流公司、区域、始发地、运输方式和时间。
 */
const form = reactive({
  metric_type: 'shipment_watt',
  source_scope: 'hist',
  customer_name: '',
  logistics_company_name: '',
  region_name: '',
  origin_place: '',
  transport_mode: '',
  group_by: 'biz_month',
})

/** 构建发给后端的聚合查询参数。 */
function buildPayload(): LogisticsAggregatePayload {
  const yearMonthList = monthInput.value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  return {
    metric_type: form.metric_type,
    source_scope: form.source_scope,
    year_month_list: yearMonthList,
    customer_name: form.customer_name || null,
    logistics_company_name: form.logistics_company_name || null,
    region_name: form.region_name || null,
    origin_place: form.origin_place || null,
    transport_mode: form.transport_mode || null,
    group_by: [form.group_by],
    order_direction: 'desc',
    limit: 100,
  }
}

/**
 * 构建当前结构化查询的摘要问题。
 * 说明：
 * 条件查询页没有自然语言原问题，这里用筛选条件拼出一个摘要，
 * 便于结果解释和空结果分析展示当前查询上下文。
 */
function buildResultQuestion() {
  const yearMonthList = monthInput.value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)

  const conditions: string[] = []
  if (yearMonthList.length > 0) {
    conditions.push(`月份 ${yearMonthList.join('、')}`)
  }
  if (form.customer_name) conditions.push(`客户 ${form.customer_name}`)
  if (form.logistics_company_name) conditions.push(`物流公司 ${form.logistics_company_name}`)
  if (form.region_name) conditions.push(`区域 ${form.region_name}`)
  if (form.origin_place) conditions.push(`始发地 ${form.origin_place}`)
  if (form.transport_mode) conditions.push(`运输方式 ${form.transport_mode}`)

  const summary = conditions.length > 0 ? conditions.join('，') : '当前筛选条件'
  return `${summary} 的 ${formatMetricTypeLabel(form.metric_type) || '指标'} 统计`
}

/**
 * 保存最近一次结构化查询上下文。
 */
function persistContext(selectedRow: Record<string, any> | null = null) {
  saveLastQueryContext({
    sourcePage: 'structured-query',
    requestPayload: buildPayload(),
    rawResponse: resultData.value,
    queryResult: resultData.value,
    selectedRow,
  })
}

/**
 * 恢复条件查询页草稿和最近一次查询结果。
 * 说明：
 * 1. 先恢复页面草稿，尽量保住未提交的表单；
 * 2. 若最近一次查询来自条件查询页，再恢复其结果和请求参数；
 * 3. 这样从明细页返回时，表单和结果都不会丢。
 */
function restorePageState() {
  const draft = getQueryPageDraft('structured-query')
  if (draft?.formData) {
    applyRequestPayload(draft.formData)
  }

  const context = getLastQueryContext()
  if (context?.sourcePage !== 'structured-query') return

  if (context.requestPayload) {
    applyRequestPayload(context.requestPayload)
  }

  if (context.rawResponse && typeof context.rawResponse === 'object') {
    resultData.value = context.rawResponse
    return
  }

  if (context.queryResult && typeof context.queryResult === 'object') {
    resultData.value = context.queryResult
  }
}

/**
 * 把请求参数回填到结构化查询表单。
 * 说明：
 * 这里优先复用后端字段名，避免维护两套映射。
 */
function applyRequestPayload(payload: Record<string, any>) {
  form.metric_type = String(payload.metric_type || form.metric_type)
  form.source_scope = String(payload.source_scope || form.source_scope)
  form.customer_name = String(payload.customer_name || '')
  form.logistics_company_name = String(payload.logistics_company_name || '')
  form.region_name = String(payload.region_name || '')
  form.origin_place = String(payload.origin_place || '')
  form.transport_mode = String(payload.transport_mode || '')

  const groupBy = Array.isArray(payload.group_by) ? payload.group_by[0] : payload.group_by
  form.group_by = String(groupBy || form.group_by)

  const yearMonthList = Array.isArray(payload.year_month_list) ? payload.year_month_list : []
  monthInput.value = yearMonthList.join(', ') || monthInput.value
}

/**
 * 打开完整明细页。
 */
function openDetail() {
  persistContext()
  router.push('/detail-view')
}

/**
 * 打开带有选中行的明细页。
 */
function openRowDetail(row: Record<string, any>) {
  persistContext(row)
  router.push('/detail-view')
}

/** 调用后端 aggregate 接口。 */
async function handleQuery() {
  loading.value = true
  try {
    const resp = await fetchAggregateQuery(buildPayload())
    resultData.value = resp.data ?? resp
    persistContext()
    ElMessage.success('查询成功')
  } finally {
    loading.value = false
  }
}

/** 填充一组默认示例。 */
function fillExample() {
  form.metric_type = 'shipment_watt'
  form.source_scope = 'hist'
  form.customer_name = ''
  form.region_name = '华东'
  form.origin_place = '合肥'
  form.transport_mode = ''
  form.logistics_company_name = ''
  form.group_by = 'biz_month'
  monthInput.value = '2025-03'
}

/**
 * 持续缓存结构化查询草稿。
 * 说明：
 * 用户在筛选条件中途切页时，回来后仍应看到最近一次输入。
 */
watch(
  () => ({
    metric_type: form.metric_type,
    source_scope: form.source_scope,
    customer_name: form.customer_name,
    logistics_company_name: form.logistics_company_name,
    region_name: form.region_name,
    origin_place: form.origin_place,
    transport_mode: form.transport_mode,
    group_by: form.group_by,
    year_month_list: monthInput.value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean),
  }),
  (value) => {
    saveQueryPageDraft({
      sourcePage: 'structured-query',
      formData: value,
    })
  },
  { deep: true, immediate: true },
)

onMounted(() => {
  restorePageState()
})
</script>
