<template>
  <div class="page-card">
    <div class="header-row">
      <h3 style="margin: 0">查询结果</h3>
      <el-space>
        <el-button
          v-if="hasItems"
          size="small"
          @click="emitOpenDetail"
        >
          查看完整明细
        </el-button>
        <el-button
          v-if="hasItems"
          size="small"
          @click="exportCurrentItems"
        >
          导出当前结果
        </el-button>
      </el-space>
    </div>

    <el-alert
      v-if="props.queryResult?.status"
      :title="`${props.queryResult.status.code} - ${props.queryResult.status.message}`"
      :type="resolveAlertType(props.queryResult.status.severity)"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    />

    <el-descriptions v-if="props.queryResult?.result_explanation" :column="1" border style="margin-bottom: 16px">
      <el-descriptions-item label="结果说明">
        {{ props.queryResult.result_explanation.summary || '-' }}
      </el-descriptions-item>
      <el-descriptions-item label="执行模式">
        {{ props.queryResult.execution_mode || '-' }}
      </el-descriptions-item>
      <el-descriptions-item label="返回条数">
        {{ props.queryResult.result_explanation.result_count ?? '-' }}
      </el-descriptions-item>
    </el-descriptions>

    <el-alert
      v-if="compatibilityNotice"
      type="info"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    >
      <template #title>兼容提示</template>
      <div style="line-height: 1.8">{{ compatibilityNotice }}</div>
    </el-alert>

    <el-alert
      v-if="props.queryResult?.no_result_analysis"
      type="warning"
      show-icon
      :closable="false"
      style="margin-bottom: 16px"
    >
      <template #title>无结果分析</template>
      <div style="line-height: 1.8">
        <div><strong>可能原因：</strong>{{ (props.queryResult.no_result_analysis.possible_reasons || []).join('；') || '-' }}</div>
        <div><strong>建议：</strong>{{ (props.queryResult.no_result_analysis.suggestions || []).join('；') || '-' }}</div>
      </div>
    </el-alert>

    <div v-if="props.queryResult?.summary" style="margin-bottom: 16px">
      <h4>汇总结果</h4>
      <div class="mono-block">{{ formatJson(props.queryResult.summary) }}</div>
    </div>

    <el-descriptions
      v-if="showCompareSummary"
      :column="2"
      border
      style="margin-bottom: 16px"
    >
      <el-descriptions-item :label="props.queryResult?.left_label || '左值'">
        {{ formatCell(props.queryResult?.left_value) }}
      </el-descriptions-item>
      <el-descriptions-item :label="props.queryResult?.right_label || '右值'">
        {{ formatCell(props.queryResult?.right_value) }}
      </el-descriptions-item>
      <el-descriptions-item label="差值">
        {{ formatCell(props.queryResult?.diff_value) }}
      </el-descriptions-item>
      <el-descriptions-item label="差异率">
        {{ formatRate(props.queryResult?.diff_rate) }}
      </el-descriptions-item>
    </el-descriptions>

    <div v-if="hasItems">
      <ResultTable
        :items="tableItems"
        title="明细/统计列表"
        @row-detail="emitRowDetail"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import ResultTable from '@/components/ResultTable.vue'

interface Props {
  queryResult: Record<string, any> | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'open-detail'): void
  (e: 'row-detail', row: Record<string, any>): void
}>()

/**
 * 当前结果是否存在 items。
 */
const hasItems = computed(() => {
  const items = props.queryResult?.items
  return Array.isArray(items) && items.length > 0
})

/**
 * 表格数据兜底为数组，避免模板层重复做空值判断。
 */
const tableItems = computed<Record<string, any>[]>(() => {
  const items = props.queryResult?.items
  return Array.isArray(items) ? items : []
})

/**
 * compare 总量对比场景在没有 items 时，仍然需要把 left/right/diff 展示出来。
 */
const showCompareSummary = computed(() => {
  if (hasItems.value) return false
  return Boolean(
    props.queryResult &&
      (props.queryResult.left_value !== undefined ||
        props.queryResult.right_value !== undefined ||
        props.queryResult.diff_value !== undefined),
  )
})

/**
 * fallback / 兼容模式提示合并展示。
 */
const compatibilityNotice = computed(() => {
  const notices = props.queryResult?.compatibility_notice
  if (!Array.isArray(notices) || notices.length === 0) return ''
  return notices.join('；')
})

/**
 * 导出当前结果。
 * 说明：
 * 第二版先做 JSON 导出，确保联调阶段可用；
 * 如果后续要导出 Excel，可在第三版增强。
 */
function exportCurrentItems() {
  try {
    const payload = JSON.stringify(props.queryResult?.items ?? [], null, 2)
    const blob = new Blob([payload], { type: 'application/json;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'query-result.json'
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已导出当前结果 JSON')
  } catch (_error) {
    ElMessage.error('导出失败')
  }
}

/**
 * 打开完整明细页。
 */
function emitOpenDetail() {
  emit('open-detail')
}

/**
 * 查看单行明细。
 */
function emitRowDetail(row: Record<string, any>) {
  emit('row-detail', row)
}

/**
 * 将对象格式化为 JSON 字符串。
 */
function formatJson(value: unknown) {
  if (!value) return '-'
  return JSON.stringify(value, null, 2)
}

/**
 * 统一把状态严重级别映射为 Element Plus 的提示类型。
 */
function resolveAlertType(severity: string | undefined) {
  if (severity === 'error') return 'error'
  if (severity === 'warning') return 'warning'
  return 'success'
}

/**
 * 对比数值格式化。
 */
function formatCell(value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') return value.toLocaleString()
  return String(value)
}

/**
 * 对比比例格式化为百分比。
 */
function formatRate(value: unknown) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return `${(value * 100).toFixed(2)}%`
}
</script>

<style scoped>
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
</style>
