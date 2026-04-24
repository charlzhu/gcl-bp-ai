<template>
  <div>
    <div class="page-card" style="margin-bottom: 20px">
      <div class="page-header">
        <div>
          <h2 class="page-title">明细视图</h2>
          <p class="page-subtitle">
            用于查看最近一次查询的完整结果、单行详情以及原始响应。
          </p>
        </div>
        <el-space>
          <el-button @click="goBack">返回</el-button>
          <el-button type="danger" plain @click="clearContext">清空上下文</el-button>
        </el-space>
      </div>
    </div>

    <el-alert
      v-if="!context"
      title="当前没有可展示的查询上下文，请先在自然语言查询页或物流条件查询页执行一次查询。"
      type="warning"
      :closable="false"
      show-icon
      class="page-card"
    />

    <template v-else>
      <div class="page-card" style="margin-bottom: 20px">
        <h3 style="margin-top: 0">查询概览</h3>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="来源页面">{{ resolveSourcePageLabel(context.sourcePage) }}</el-descriptions-item>
          <el-descriptions-item label="问题">{{ context.question || '-' }}</el-descriptions-item>
          <el-descriptions-item label="查询类型">{{ context.queryResult?.query_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源范围">{{ context.queryResult?.source_scope || '-' }}</el-descriptions-item>
          <el-descriptions-item label="执行模式">{{ context.queryResult?.execution_mode || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态码">{{ context.rawResponse?.response_meta?.status?.code || context.queryResult?.status?.code || '-' }}</el-descriptions-item>
          <el-descriptions-item label="模板ID">{{ context.parsed?.template_id || '-' }}</el-descriptions-item>
          <el-descriptions-item label="返回条数">{{ resolveResultCount() }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="page-card" style="margin-bottom: 20px" v-if="activeRow">
        <div class="section-header">
          <h3 style="margin: 0">当前明细记录</h3>
          <el-tag size="small" type="info">{{ resolveSourceTypeLabel(activeRow.source_type) }}</el-tag>
        </div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="业务日期">{{ formatValue(activeRow.biz_date) }}</el-descriptions-item>
          <el-descriptions-item label="业务月份">{{ formatValue(activeRow.biz_month) }}</el-descriptions-item>
          <el-descriptions-item label="合同编号">{{ formatValue(activeRow.contract_no) }}</el-descriptions-item>
          <el-descriptions-item label="任务编号">{{ formatValue(activeRow.task_id) }}</el-descriptions-item>
          <el-descriptions-item label="客户">{{ formatValue(activeRow.customer_name) }}</el-descriptions-item>
          <el-descriptions-item label="物流公司">{{ formatValue(activeRow.logistics_company_name) }}</el-descriptions-item>
          <el-descriptions-item label="区域">{{ formatValue(activeRow.region_name) }}</el-descriptions-item>
          <el-descriptions-item label="始发地">{{ formatValue(activeRow.origin_place) }}</el-descriptions-item>
          <el-descriptions-item label="运输方式">{{ formatValue(activeRow.transport_mode) }}</el-descriptions-item>
          <el-descriptions-item label="车牌号">{{ formatValue(activeRow.plate_number) }}</el-descriptions-item>
          <el-descriptions-item label="来源引用">{{ formatValue(activeRow.source_ref) }}</el-descriptions-item>
          <el-descriptions-item label="运量">{{ formatValue(activeRow.shipment_watt) }}</el-descriptions-item>
        </el-descriptions>

        <el-collapse style="margin-top: 16px">
          <el-collapse-item title="查看当前记录完整 JSON" name="selected-row-json">
            <div class="mono-block">{{ formatJson(activeRow) }}</div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div class="page-card" style="margin-bottom: 20px">
        <h3 style="margin-top: 0">结果明细</h3>
        <ResultTable
          :items="context.queryResult?.items || []"
          title="明细结果"
          @row-detail="showRowDetail"
        />
      </div>

      <div class="page-card" style="margin-bottom: 20px">
        <h3 style="margin-top: 0">解析与执行上下文</h3>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="查询模式">{{ context.parsed?.mode || '-' }}</el-descriptions-item>
          <el-descriptions-item label="指标">{{ context.parsed?.metric_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源范围">{{ context.parsed?.source_scope || '-' }}</el-descriptions-item>
          <el-descriptions-item label="模板命中">{{ context.parsed?.template_hit ? '是' : '否' }}</el-descriptions-item>
          <el-descriptions-item label="执行模式">{{ context.queryResult?.execution_mode || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态说明">
            {{ context.rawResponse?.response_meta?.status?.message || context.queryResult?.status?.message || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <el-collapse style="margin-top: 16px">
          <el-collapse-item title="查看 parsed 关键上下文" name="parsed-json">
            <div class="mono-block">{{ formatJson(context.parsed || {}) }}</div>
          </el-collapse-item>
          <el-collapse-item title="查看汇总结果" name="summary-json">
            <div class="mono-block">{{ formatJson(context.queryResult?.summary || {}) }}</div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div class="page-card">
        <h3 style="margin-top: 0">完整原始响应</h3>
        <el-collapse>
          <el-collapse-item title="查看完整原始响应 JSON" name="raw-response-json">
            <div class="mono-block">{{ formatJson(context.rawResponse || {}) }}</div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <el-dialog v-model="visible" title="单行详情" width="60%">
        <div class="mono-block">{{ formatJson(selectedRow) }}</div>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import ResultTable from '@/components/ResultTable.vue'
import { clearLastQueryContext, getLastQueryContext } from '@/utils/queryStorage'

const router = useRouter()
const context = ref(getLastQueryContext())
const selectedRow = ref<Record<string, any> | null>(null)
const visible = ref(false)

/**
 * 来源类型中文映射。
 * 说明：
 * 明细页优先展示业务能理解的来源标签，而不是直接暴露底层枚举值。
 */
const SOURCE_TYPE_LABEL_MAP: Record<string, string> = {
  HIST: '历史 Excel',
  SYS: '正式系统',
  history: '历史 Excel',
  system_formal: '正式系统',
  mixed: '混合来源',
}

/**
 * 当前激活记录。
 * 说明：
 * 1. 优先使用上一个页面点击的那一行；
 * 2. 如果没有选中行，则默认取当前结果的第一条，避免明细页空白。
 */
const activeRow = computed(() => {
  if (selectedRow.value) return selectedRow.value
  if (context.value?.selectedRow) return context.value.selectedRow
  const items = context.value?.queryResult?.items
  if (Array.isArray(items) && items.length > 0) return items[0]
  return null
})

/**
 * 返回上一页。
 */
function goBack() {
  if (context.value?.sourcePage === 'structured-query') {
    router.push('/structured-query')
    return
  }
  router.push('/nl-query')
}

/**
 * 清理上下文后刷新当前视图。
 */
function clearContext() {
  clearLastQueryContext()
  context.value = null
}

/**
 * 展示单行详情。
 */
function showRowDetail(row: Record<string, any>) {
  selectedRow.value = row
  visible.value = true
}

/**
 * 返回来源页面中文名。
 */
function resolveSourcePageLabel(value: string | undefined) {
  if (value === 'structured-query') return '物流条件查询'
  if (value === 'nl-query') return '自然语言查询'
  return value || '-'
}

/**
 * 返回来源类型中文名。
 */
function resolveSourceTypeLabel(value: unknown) {
  const key = typeof value === 'string' ? value : ''
  return SOURCE_TYPE_LABEL_MAP[key] || key || '-'
}

/**
 * 计算当前结果条数。
 */
function resolveResultCount() {
  const queryResult = context.value?.queryResult
  if (!queryResult) return '-'
  if (queryResult.total !== undefined && queryResult.total !== null) {
    return formatValue(queryResult.total)
  }
  const items = queryResult.items
  if (Array.isArray(items)) return formatValue(items.length)
  return '-'
}

/**
 * 界面值格式化。
 * 说明：
 * 和结果表保持一致，空值统一显示为短横线。
 */
function formatValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') {
    return value.toLocaleString('zh-CN', {
      maximumFractionDigits: 2,
    })
  }
  return String(value)
}

/**
 * JSON 格式化。
 */
function formatJson(value: unknown) {
  if (!value) return '-'
  return JSON.stringify(value, null, 2)
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
</style>
