<template>
  <div class="page-card">
    <div class="header-row">
      <h3 style="margin: 0">查询结果</h3>
      <el-space>
        <el-button
          v-if="presentation.hasItems"
          size="small"
          @click="emitOpenDetail"
        >
          查看完整明细
        </el-button>
        <el-button
          v-if="presentation.hasItems"
          size="small"
          @click="exportCurrentItems"
        >
          导出当前结果
        </el-button>
      </el-space>
    </div>

    <template v-if="hasDisplayPayload">
      <div class="status-panel" :class="`status-panel--${resolvePanelTone(presentation.status.severity)}`">
        <div class="status-panel__top">
          <el-space wrap>
            <el-tag effect="dark" :type="resolveStatusTagType(presentation.status.severity)">
              {{ presentation.status.code }}
            </el-tag>
            <span class="status-message">{{ presentation.status.message }}</span>
          </el-space>
        </div>
        <div class="status-panel__meta">
          <el-tag size="small" :type="resolveExecutionModeTagType(presentation.executionMode)">
            {{ formatExecutionModeLabel(presentation.executionMode) }}
          </el-tag>
          <el-tag size="small" effect="plain">
            {{ formatQueryTypeLabel(presentation.queryType) }}
          </el-tag>
          <el-tag size="small" effect="plain">
            {{ formatMetricTypeLabel(presentation.metricType) }}
          </el-tag>
          <el-tag size="small" effect="plain">
            {{ formatSourceScopeLabel(presentation.sourceScope) }}
          </el-tag>
        </div>
      </div>

      <div class="overview-grid">
        <div class="overview-card">
          <div class="overview-card__label">结果条数</div>
          <div class="overview-card__value">{{ presentation.resultCount.toLocaleString() }}</div>
        </div>
        <div class="overview-card">
          <div class="overview-card__label">执行模式</div>
          <div class="overview-card__value">{{ formatExecutionModeLabel(presentation.executionMode) }}</div>
        </div>
        <div class="overview-card">
          <div class="overview-card__label">指标口径</div>
          <div class="overview-card__value">{{ formatMetricTypeLabel(presentation.metricType) }}</div>
        </div>
        <div class="overview-card">
          <div class="overview-card__label">来源范围</div>
          <div class="overview-card__value">{{ formatSourceScopeLabel(presentation.sourceScope) }}</div>
        </div>
      </div>

      <div v-if="presentation.resultExplanation" class="explanation-panel">
        <div class="section-title">结果摘要</div>
        <div class="summary-text">{{ presentation.resultExplanation.summary }}</div>
        <div v-if="presentation.resultExplanation.highlights.length" class="tag-group">
          <el-tag
            v-for="item in presentation.resultExplanation.highlights"
            :key="item"
            size="small"
            effect="plain"
          >
            {{ item }}
          </el-tag>
        </div>
        <ul v-if="presentation.resultExplanation.notes.length" class="note-list">
          <li v-for="item in presentation.resultExplanation.notes" :key="item">
            {{ item }}
          </li>
        </ul>
      </div>

      <el-alert
        v-if="presentation.compatibilityNotice.length > 0"
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 16px"
      >
        <template #title>兼容提示</template>
        <div class="alert-list">
          <div v-for="item in presentation.compatibilityNotice" :key="item">{{ item }}</div>
        </div>
      </el-alert>

      <div
        v-if="presentation.noResultAnalysis"
        class="analysis-panel"
        :class="`analysis-panel--${resolvePanelTone(presentation.status.severity)}`"
      >
        <div class="section-title">空结果分析</div>
        <div class="analysis-panel__question">{{ presentation.noResultAnalysis.question }}</div>
        <div class="analysis-columns">
          <div>
            <div class="analysis-subtitle">可能原因</div>
            <ul class="note-list">
              <li v-for="item in presentation.noResultAnalysis.possible_reasons" :key="item">
                {{ item }}
              </li>
            </ul>
          </div>
          <div>
            <div class="analysis-subtitle">建议动作</div>
            <ul class="note-list">
              <li v-for="item in presentation.noResultAnalysis.suggestions" :key="item">
                {{ item }}
              </li>
            </ul>
          </div>
        </div>
      </div>

      <div v-if="presentation.summaryEntries.length > 0" class="summary-panel">
        <div class="section-title">汇总指标</div>
        <div class="summary-grid">
          <div
            v-for="entry in presentation.summaryEntries"
            :key="entry.key"
            class="summary-card"
          >
            <div class="summary-card__label">{{ entry.label }}</div>
            <div class="summary-card__value">{{ formatSummaryValue(entry.key, entry.value) }}</div>
          </div>
        </div>
      </div>

      <div v-if="presentation.showCompareSummary" class="summary-panel">
        <div class="section-title">对比摘要</div>
        <div class="summary-grid">
          <div class="summary-card">
            <div class="summary-card__label">{{ props.queryResult?.left_label || '左值' }}</div>
            <div class="summary-card__value">{{ formatSummaryValue('left_value', props.queryResult?.left_value) }}</div>
          </div>
          <div class="summary-card">
            <div class="summary-card__label">{{ props.queryResult?.right_label || '右值' }}</div>
            <div class="summary-card__value">{{ formatSummaryValue('right_value', props.queryResult?.right_value) }}</div>
          </div>
          <div class="summary-card">
            <div class="summary-card__label">差值</div>
            <div class="summary-card__value">{{ formatSummaryValue('diff_value', props.queryResult?.diff_value) }}</div>
          </div>
          <div class="summary-card">
            <div class="summary-card__label">差异率</div>
            <div class="summary-card__value">{{ formatRate(props.queryResult?.diff_rate) }}</div>
          </div>
        </div>
      </div>

      <el-collapse v-if="presentation.templateInfo" style="margin-bottom: 16px">
        <el-collapse-item title="模板命中信息" name="template-info">
          <el-descriptions :column="1" border>
            <el-descriptions-item label="模板状态">
              {{ presentation.templateInfo.template_hit ? '已命中' : '未命中' }}
            </el-descriptions-item>
            <el-descriptions-item label="模板 ID">
              {{ presentation.templateInfo.template_id || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="模板名称">
              {{ presentation.templateInfo.template_name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="模板分数">
              {{ presentation.templateInfo.template_score ?? '-' }}
            </el-descriptions-item>
          </el-descriptions>
          <ul v-if="presentation.templateInfo.template_match_reasons.length" class="note-list" style="margin-top: 12px">
            <li v-for="item in presentation.templateInfo.template_match_reasons" :key="item">
              {{ item }}
            </li>
          </ul>
        </el-collapse-item>
      </el-collapse>

      <div v-if="presentation.hasItems">
        <ResultTable
          :items="tableItems"
          title="明细/统计列表"
          @row-detail="emitRowDetail"
        />
      </div>
    </template>

    <el-empty v-else description="当前暂无查询结果" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import ResultTable from '@/components/ResultTable.vue'
import {
  buildQueryResultPresentation,
  formatExecutionModeLabel,
  formatMetricTypeLabel,
  formatQueryTypeLabel,
  formatSourceScopeLabel,
} from '@/utils/queryResultPresentation'

interface Props {
  queryResult: Record<string, any> | null
  parsed?: Record<string, any> | null
  question?: string | null
  requestPayload?: Record<string, any> | null
  responseMeta?: Record<string, any> | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'open-detail'): void
  (e: 'row-detail', row: Record<string, any>): void
}>()

/**
 * 表格数据兜底为数组，避免模板层重复做空值判断。
 */
const tableItems = computed<Record<string, any>[]>(() => {
  const items = props.queryResult?.items
  return Array.isArray(items) ? items : []
})

/**
 * 构建统一的页面展示视图。
 */
const presentation = computed(() =>
  buildQueryResultPresentation({
    queryResult: props.queryResult,
    parsed: props.parsed,
    question: props.question,
    requestPayload: props.requestPayload,
    responseMeta: props.responseMeta,
  }),
)

/**
 * 当前是否已有可展示的查询载荷。
 * 说明：
 * 未执行查询前只展示空态，避免把“尚未查询”误渲染成“空结果”。
 */
const hasDisplayPayload = computed(() => {
  return Boolean(props.queryResult || props.responseMeta || props.parsed)
})

/**
 * 导出当前结果。
 * 说明：
 * 第二版先做 JSON 导出，确保联调阶段可用；
 * 如果后续要导出 Excel，可在后续版本增强。
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
 * 统一映射状态标签颜色。
 */
function resolveStatusTagType(severity: string | undefined) {
  if (severity === 'error') return 'danger'
  if (severity === 'warning') return 'warning'
  return 'success'
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
 * 将状态严重级别映射为展示面板色调。
 */
function resolvePanelTone(severity: string | undefined) {
  if (severity === 'error') return 'danger'
  if (severity === 'warning') return 'warning'
  return 'success'
}

/**
 * 汇总数值格式化。
 * 说明：
 * 1. 百分比字段单独转百分数；
 * 2. 可解析的数字统一千分位；
 * 3. 其它值原样兜底。
 */
function formatSummaryValue(key: string, value: unknown) {
  if (key === 'diff_rate') {
    return formatRate(value)
  }

  if (value === null || value === undefined || value === '') return '-'

  if (typeof value === 'number') {
    return value.toLocaleString()
  }

  if (typeof value === 'string') {
    const parsedNumber = Number(value)
    if (!Number.isNaN(parsedNumber)) {
      return parsedNumber.toLocaleString()
    }
    return value
  }

  return String(value)
}

/**
 * 比例格式化为百分比。
 */
function formatRate(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return `${(value * 100).toFixed(2)}%`
  }
  if (typeof value === 'string' && value.trim()) {
    const parsedNumber = Number(value)
    if (!Number.isNaN(parsedNumber)) {
      return `${(parsedNumber * 100).toFixed(2)}%`
    }
  }
  return '-'
}
</script>

<style scoped>
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.status-panel {
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

.status-panel--success {
  background: #f0f9eb;
  border: 1px solid #c2e7b0;
}

.status-panel--warning {
  background: #fdf6ec;
  border: 1px solid #f3d19e;
}

.status-panel--danger {
  background: #fef0f0;
  border: 1px solid #fab6b6;
}

.status-panel__top {
  margin-bottom: 12px;
}

.status-panel__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.status-message {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.overview-card,
.summary-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 14px 16px;
  background: #fff;
}

.overview-card__label,
.summary-card__label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  margin-bottom: 8px;
}

.overview-card__value,
.summary-card__value {
  color: var(--el-text-color-primary);
  font-size: 20px;
  font-weight: 600;
  word-break: break-word;
}

.explanation-panel,
.summary-panel,
.analysis-panel {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 16px;
  background: #fff;
  margin-bottom: 16px;
}

.analysis-panel--warning {
  background: #fff7e6;
  border-color: #f3d19e;
}

.analysis-panel--danger {
  background: #fff1f0;
  border-color: #fab6b6;
}

.section-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 12px;
}

.summary-text {
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
  margin-bottom: 12px;
}

.tag-group {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.note-list {
  margin: 0;
  padding-left: 18px;
  color: var(--el-text-color-regular);
  line-height: 1.8;
}

.alert-list {
  line-height: 1.8;
}

.analysis-panel__question {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 12px;
  color: var(--el-text-color-primary);
}

.analysis-columns {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 16px;
}

.analysis-subtitle {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}
</style>
