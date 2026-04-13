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
      @open-detail="openDetail"
      @row-detail="openRowDetail"
    />
    <div class="page-card" style="margin-top: 20px">
      <h3 style="margin-top: 0">本次请求参数</h3>
      <div class="mono-block">{{ JSON.stringify(buildPayload(), null, 2) }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchAggregateQuery, type LogisticsAggregatePayload } from '@/api/logistics'
import QueryResultCard from '@/components/QueryResultCard.vue'
import { saveLastQueryContext } from '@/utils/queryStorage'

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
</script>
