<template>
  <section class="chat-page" data-testid="business-chat-page">
    <div class="chat-toolbar" data-testid="business-chat-toolbar">
      <el-radio-group v-model="domainMode" size="small" class="domain-switch" data-testid="domain-switch">
        <el-radio-button value="auto" data-testid="domain-auto">自动识别</el-radio-button>
        <el-radio-button value="logistics" data-testid="domain-logistics">物流数据</el-radio-button>
        <el-radio-button value="plan_bom" data-testid="domain-plan-bom">计划 BOM</el-radio-button>
        <el-radio-button value="business_analysis" data-testid="domain-business-analysis">经营分析</el-radio-button>
      </el-radio-group>
    </div>

    <div ref="conversationRef" :class="['conversation', { 'conversation--empty': messages.length === 0 }]" data-testid="conversation">
      <!-- 欢迎状态 -->
      <div v-if="messages.length === 0" class="empty-panel" data-testid="empty-panel">
        <div class="empty-glow" />
        <h1>协鑫集成 经营计划智能助手</h1>
        <p class="empty-subtitle">支持物流运量、费用、发运车次等结构化数据查询，以及计划 BOM 材料明细与差异对比。请直接输入业务问题。</p>
        <div class="quick-chips">
          <button
            v-for="item in examples"
            :key="item.text"
            type="button"
            class="quick-chip"
            :title="`使用示例问题：${item.text}`"
            :aria-label="`使用示例问题：${item.text}`"
            @click="useExample(item)"
          >
            <span class="chip-icon">{{ resolveExampleDomainLabel(item.domain) }}</span>
            <span class="chip-text">{{ item.text }}</span>
          </button>
        </div>
      </div>

      <!-- 消息列表（带入场动画） -->
      <TransitionGroup v-else name="message" tag="div" class="message-list">
        <article
          v-for="message in messages"
          :key="message.id"
          :class="['message', `message--${message.role}`]"
          :data-testid="`chat-message-${message.role}`"
          :data-status="message.status"
          :data-domain="message.domain"
        >
          <div class="message-meta">
            <span class="message-sender">{{ message.role === 'user' ? '我' : '经营计划智能助手' }}</span>
            <em v-if="message.domain !== 'auto'" class="message-domain">{{ domainLabelMap[message.domain] }}</em>
            <time v-if="message.createdAt" class="message-time">{{ formatRelativeTime(message.createdAt) }}</time>
          </div>

          <!-- 助手消息状态标签 -->
          <div v-if="message.role === 'assistant' && !message.loading && !message.presentation && resolveStatusBadge(message.status)" class="message-status-row">
            <span :class="['status-badge', `status-badge--${resolveStatusBadge(message.status)?.type}`]">
              {{ resolveStatusBadge(message.status)?.label }}
            </span>
          </div>

          <div class="bubble">
            <div
              v-if="message.content && !message.presentation"
              :class="['message-content', { 'streaming-answer': message.role === 'assistant' && message.loading }]"
              data-testid="message-content"
            >
              <div
                v-if="message.role === 'assistant'"
                class="assistant-markdown"
                v-html="renderBusinessMarkdown(message.content)"
              />
              <p v-else>{{ message.content }}</p>
            </div>

            <!-- 加载动画：三点跳动 -->
            <div v-if="message.loading" class="loading-row" data-testid="message-loading" aria-live="polite">
              <span class="typing-indicator">
                <span /><span /><span />
              </span>
              <span class="loading-text" aria-label="AI 正在生成回答">{{ resolveLoadingText(message) }}</span>
            </div>

            <div v-if="message.error" class="error" data-testid="message-error">{{ message.error }}</div>

            <div
              v-if="message.presentation"
              :class="['result', `result--${resolveResultTone(message.status)}`, resolveAssistantResultLayout(message)]"
              data-testid="assistant-result"
            >
              <div class="result-hero">
                <div class="result-hero__meta">
                  <span
                    v-if="resolveStatusBadge(message.status)"
                    :class="['status-badge', `status-badge--${resolveStatusBadge(message.status)?.type}`]"
                  >
                    {{ resolveStatusBadge(message.status)?.label }}
                  </span>
                  <span v-if="message.presentation.displayType" class="display-badge">
                    {{ formatDisplayTypeLabel(message.presentation.displayType) }}
                  </span>
                  <span class="display-badge display-badge--layout">
                    {{ resolveAssistantReplyKicker(message) }}
                  </span>
                </div>
                <div v-if="message.presentation.title" class="result-title" data-testid="result-title">{{ message.presentation.title }}</div>
                <div
                  v-if="message.presentation.answer"
                  class="result-answer assistant-prose assistant-markdown"
                  data-testid="result-answer"
                  v-html="renderBusinessMarkdown(message.presentation.answer)"
                />
                <div v-if="shouldShowSecondaryActions(message)" class="answer-secondary-actions" data-testid="answer-secondary-actions">
                  <el-button
                    v-if="hasAssistantBasis(message)"
                    size="small"
                    round
                    plain
                    @click="toggleAssistantBasisDetails(message)"
                  >
                    查看数据依据
                  </el-button>
                  <el-button
                    v-if="hasAssistantAuditRows(message)"
                    size="small"
                    round
                    plain
                    @click="toggleAssistantTable(message)"
                  >
                    {{ isAssistantTableExpanded(message) ? '收起明细' : '展开明细' }}
                  </el-button>
                  <el-button
                    v-if="hasAssistantAuditRows(message)"
                    size="small"
                    round
                    plain
                    @click="exportAssistantTableToExcel(message)"
                  >
                    导出 Excel
                  </el-button>
                </div>
                <div v-if="buildResultSummaryItems(message).length" class="result-summary-strip">
                  <span
                    v-for="item in buildResultSummaryItems(message)"
                    :key="`${message.id}-${item.label}`"
                    class="result-summary-strip__item"
                  >
                    <strong>{{ item.value }}</strong>{{ item.label }}
                  </span>
                </div>
              </div>

              <div v-if="message.presentation.highlights.length" class="highlight-list" data-testid="result-highlights">
                <div class="section-label">关键结论</div>
                <span v-for="text in message.presentation.highlights" :key="text">{{ text }}</span>
              </div>

              <div v-if="shouldShowPresentationChart(message)" class="presentation-chart" data-testid="result-chart">
                <div class="presentation-chart__title">
                  {{ buildChartTitle(message.presentation.chart) }}
                </div>
                <div class="presentation-chart__meta">{{ buildChartMeta(message.presentation.chart) }}</div>
                <svg
                  v-if="message.presentation.chart.chart_type === 'line'"
                  class="presentation-chart__svg"
                  viewBox="0 0 640 220"
                  role="img"
                  :aria-label="buildChartAriaLabel(message.presentation.chart)"
                >
                  <polyline
                    class="presentation-chart__line"
                    :points="buildLineChartPoints(message.presentation.chart)"
                    fill="none"
                  />
                  <circle
                    v-for="point in buildLineChartCircles(message.presentation.chart)"
                    :key="`${message.id}-line-${point.x}-${point.y}`"
                    class="presentation-chart__point"
                    :cx="point.x"
                    :cy="point.y"
                    r="4"
                  />
                  <text
                    v-for="label in buildChartLabels(message.presentation.chart)"
                    :key="`${message.id}-line-label-${label.x}-${label.text}`"
                    class="presentation-chart__label"
                    :x="label.x"
                    y="210"
                    text-anchor="middle"
                  >
                    {{ label.text }}
                  </text>
                </svg>
                <div
                  v-else-if="message.presentation.chart.chart_type === 'pie'"
                  class="presentation-chart__pie-layout"
                >
                  <svg
                    class="presentation-chart__pie"
                    viewBox="0 0 260 220"
                    role="img"
                    :aria-label="buildChartAriaLabel(message.presentation.chart)"
                  >
                    <path
                      v-for="slice in buildPieChartSlices(message.presentation.chart)"
                      :key="`${message.id}-pie-${slice.label}`"
                      class="presentation-chart__pie-slice"
                      :d="slice.path"
                      :fill="slice.color"
                    >
                      <title>{{ slice.tooltip }}</title>
                    </path>
                    <circle class="presentation-chart__pie-hole" cx="110" cy="110" r="42" />
                    <text class="presentation-chart__pie-center" x="110" y="106" text-anchor="middle">占比</text>
                    <text class="presentation-chart__pie-center presentation-chart__pie-center--sub" x="110" y="126" text-anchor="middle">
                      {{ buildPieChartSlices(message.presentation.chart).length }} 项
                    </text>
                  </svg>
                  <div class="presentation-chart__legend">
                    <div
                      v-for="item in buildPieChartLegend(message.presentation.chart)"
                      :key="`${message.id}-pie-legend-${item.label}`"
                      class="presentation-chart__legend-item"
                    >
                      <span class="presentation-chart__legend-color" :style="{ background: item.color }" />
                      <span class="presentation-chart__legend-label">{{ item.label }}</span>
                      <span class="presentation-chart__legend-value">{{ item.valueText }}</span>
                    </div>
                  </div>
                </div>
                <svg
                  v-else
                  class="presentation-chart__svg"
                  viewBox="0 0 640 220"
                  role="img"
                  :aria-label="buildChartAriaLabel(message.presentation.chart)"
                >
                  <rect
                    v-for="bar in buildBarChartRects(message.presentation.chart)"
                    :key="`${message.id}-bar-${bar.x}-${bar.height}`"
                    class="presentation-chart__bar"
                    :x="bar.x"
                    :y="bar.y"
                    :width="bar.width"
                    :height="bar.height"
                    rx="6"
                  />
                  <text
                    v-for="label in buildChartLabels(message.presentation.chart)"
                    :key="`${message.id}-bar-label-${label.x}-${label.text}`"
                    class="presentation-chart__label"
                    :x="label.x"
                    y="210"
                    text-anchor="middle"
                  >
                    {{ label.text }}
                  </text>
                </svg>
              </div>

              <div v-if="shouldShowMetricCards(message)" class="metric-grid" data-testid="result-cards">
                <div v-for="card in message.presentation.cards" :key="card.label" class="metric-card">
                  <div class="metric-accent" />
                  <div class="metric-body">
                    <div class="metric-label">{{ card.label }}</div>
                    <div class="metric-value">{{ formatDisplayValue(card.value) }}<small v-if="card.unit">{{ card.unit }}</small></div>
                    <div v-if="card.description" class="metric-desc">{{ card.description }}</div>
                  </div>
                </div>
              </div>

              <div v-if="shouldShowResultTable(message)" class="result-table-card">
                <div class="result-table-card__head">
                  <div class="result-table-card__title">
                    <span>明细数据</span>
                    <em>{{ getAssistantResultTable(message)?.rows.length || 0 }} 行</em>
                  </div>
                  <el-button
                    type="primary"
                    plain
                    size="small"
                    class="result-table-card__export"
                    data-testid="export-result-table-excel"
                    :disabled="!getAssistantResultTable(message)?.rows.length"
                    @click="exportAssistantTableToExcel(message)"
                  >
                    导出 Excel
                  </el-button>
                </div>
                <div
                  v-if="shouldUseIrregularResultTable(message)"
                  class="result-table-scroll"
                  data-testid="result-table-scroll"
                >
                  <table class="result-table result-table--irregular" data-testid="result-table">
                    <thead>
                      <tr>
                        <th
                          v-for="column in getAssistantResultTable(message)?.columns || []"
                          :key="column"
                          :style="getResultTableColumnStyle(column)"
                        >
                          {{ column }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr
                        v-for="(row, rowIndex) in getAssistantResultTable(message)?.rows || []"
                        :key="buildIrregularResultTableRowKey(row, rowIndex)"
                      >
                        <template
                          v-for="column in getAssistantResultTable(message)?.columns || []"
                          :key="`${rowIndex}-${column}`"
                        >
                          <td
                            v-if="shouldRenderIrregularResultTableCell(row, column)"
                            :rowspan="getIrregularResultTableCellRowSpan(row, column)"
                            :class="getIrregularResultTableCellClassName(column)"
                            :style="getResultTableColumnStyle(column)"
                          >
                            <span
                              :class="[
                                'result-table__cell',
                                {
                                  'result-table__cell--multi-line': isMultiLineTableColumn(column),
                                  'result-table__cell--fall-ratio': isFallRatioEstimateColumn(column),
                                },
                              ]"
                            >
                              {{ formatTableCell(row[column]) }}
                            </span>
                          </td>
                        </template>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <el-table
                  v-else
                  :data="getAssistantResultTable(message)?.rows || []"
                  size="small"
                  border
                  class="result-table"
                  data-testid="result-table"
                  max-height="360"
                  empty-text="暂无明细数据"
                >
                  <el-table-column
                    v-for="column in getAssistantResultTable(message)?.columns || []"
                    :key="column"
                    :prop="column"
                    :label="column"
                    :min-width="getResultTableColumnMinWidth(column)"
                    :class-name="getResultTableColumnClassName(column)"
                    :show-overflow-tooltip="!isMultiLineTableColumn(column)"
                  >
                    <template #default="scope">
                      <span
                        :class="[
                          'result-table__cell',
                          {
                            'result-table__cell--multi-line': isMultiLineTableColumn(column),
                            'result-table__cell--fall-ratio': isFallRatioEstimateColumn(column),
                          },
                        ]"
                      >
                        {{ formatTableCell(scope.row[column]) }}
                      </span>
                    </template>
                  </el-table-column>
                </el-table>
              </div>

              <div v-if="message.presentation.followUps.length" class="follow-up" data-testid="result-follow-ups">
                <div class="section-label">需要补充的信息</div>
                <button
                  v-for="followUp in message.presentation.followUps"
                  :key="followUp"
                  type="button"
                  class="follow-up-chip"
                  :title="`使用补充问题：${followUp}`"
                  :aria-label="`使用补充问题：${followUp}`"
                  @click="appendFollowUp(followUp)"
                >
                  {{ followUp }}
                </button>
              </div>

              <div v-if="message.presentation.suggestions.length" class="suggestions" data-testid="result-suggestions">
                <div class="section-label">可改问方向</div>
                <span v-for="item in message.presentation.suggestions" :key="item">{{ item }}</span>
              </div>

              <div v-if="getCaveatItemsByLevel(message, 'danger').length" class="result-caveats result-caveats--danger">
                <div class="section-label">重要风险</div>
                <div v-for="item in getCaveatItemsByLevel(message, 'danger')" :key="item.text" class="result-caveats__item">
                  {{ item.text }}
                </div>
              </div>

              <div v-if="getCaveatItemsByLevel(message, 'warning').length" class="result-caveats result-caveats--warning">
                <div class="section-label">数据提醒</div>
                <div v-for="item in getCaveatItemsByLevel(message, 'warning')" :key="item.text" class="result-caveats__item">
                  {{ item.text }}
                </div>
              </div>

              <details
                v-if="getCaveatItemsByLevel(message, 'info').length"
                class="result-caveats result-caveats--info"
                :open="isAssistantBasisExpanded(message)"
              >
                <summary>数据口径</summary>
                <div v-for="item in getCaveatItemsByLevel(message, 'info')" :key="item.text" class="result-caveats__item">
                  {{ item.text }}
                </div>
              </details>
            </div>
          </div>
        </article>
      </TransitionGroup>
    </div>

    <form class="composer" data-testid="question-composer" @submit.prevent="submitQuestion()">
      <el-input
        v-model="question"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="输入业务问题，例如：2024年江苏省各城市总费用排名"
        data-testid="question-input"
        :disabled="currentSessionLoading"
        @keydown="handleComposerKeydown"
      />
      <el-button
        type="primary"
        native-type="submit"
        :loading="currentSessionLoading"
        :disabled="currentSessionLoading || !question.trim()"
        data-testid="send-button"
        title="发送业务问题"
        aria-label="发送业务问题"
      >
        发送
      </el-button>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx-js-style'
import {
  streamInventorySalesProductionQuestion,
  type InventorySalesProductionQaResponse,
} from '@/api/inventorySalesProduction'
import { streamLogisticsDataQaQuery, type LogisticsDataQaResult } from '@/api/logistics'
import * as planBomApi from '@/api/planBom'
import type { PlanBomQaResponse } from '@/api/planBom'
/* LQG-8：统一业务问数流式入口 */
import { streamBusinessQa } from '@/api/businessQa'
import { renderBusinessMarkdown } from '@/utils/businessMarkdown'
import {
  buildBusinessChatMessageId,
  buildBusinessChatSessionTitle,
  ensureBusinessChatSession,
  getActiveBusinessChatSessionId,
  getBusinessChatSession,
  getBusinessChatSessionEventName,
  saveBusinessChatSession,
  type BusinessChatDomain,
  type BusinessChatMessage,
  type BusinessChatSession,
} from '@/utils/businessChatSessions'

interface UnifiedTable {
  columns: string[]
  rows: Array<Record<string, any>>
}

const resultTableRowSpanKey = '__resultTableRowSpan'
const resultTableSubRowIndexKey = '__resultTableSubRowIndex'
const resultTableSourceRowIndexKey = '__resultTableSourceRowIndex'

interface UnifiedResult {
  displayType: string
  title: string
  answer: string
  highlights: string[]
  cards: Array<{ label: string; value: any; unit?: string | null; description?: string | null }>
  chart: UnifiedChart | null
  table: UnifiedTable | null
  followUps: string[]
  suggestions: string[]
  caveats: string[]
  caveatItems: CaveatItem[]
}

interface CaveatItem {
  level: 'info' | 'warning' | 'danger'
  text: string
}

interface UnifiedChart {
  chart_type: 'line' | 'bar' | 'pie'
  title?: string | null
  x_axis?: string | null
  y_axis?: string[]
  series?: Array<Record<string, any>>
  unit?: string | null
  data?: Array<Record<string, any>>
}

interface ChartRenderPoint {
  x: number
  y: number
}

interface ChartRenderLabel {
  x: number
  text: string
}

interface ChartRenderBar {
  x: number
  y: number
  width: number
  height: number
}

interface ChartRenderSlice {
  path: string
  color: string
  label: string
  value: number
  percent: number
  tooltip: string
}

interface ChartLegendItem {
  color: string
  label: string
  valueText: string
}

interface ChartValue {
  label: unknown
  value: number
}

interface ResultSummaryItem {
  label: string
  value: string
}

type AssistantResultLayoutClass = 'ai-response-card--narrative' | 'ai-response-card--data' | 'ai-response-card--chart'

const pieChartColors = ['#2f7a4a', '#60a5fa', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#f97316', '#64748b']
const chartDisplayTypes = new Set(['line_chart', 'bar_chart', 'pie_chart', 'mixed'])
const tableDisplayTypes = new Set(['table', 'comparison_table', 'mixed'])
const cardDisplayTypes = new Set(['summary_cards', 'mixed'])

const question = ref('')
const activeSession = ref<BusinessChatSession | null>(null)
const conversationRef = ref<HTMLElement | null>(null)
const expandedBasisMessageIds = ref<Set<string>>(new Set())
const expandedTableMessageIds = ref<Set<string>>(new Set())
const collapsedTableMessageIds = ref<Set<string>>(new Set())

const examples = [
  { domain: '物流', mode: 'logistics' as BusinessChatDomain, text: '2024年江苏省各城市总费用排名前五？' },
  { domain: '物流', mode: 'logistics' as BusinessChatDomain, text: '查询下个月物流费用预测需要哪些条件？' },
  { domain: 'BOM', mode: 'plan_bom' as BusinessChatDomain, text: '订单00104的玻璃、间隙贴膜、焊带、汇流条、接线盒规格描述？' },
  { domain: 'BOM', mode: 'plan_bom' as BusinessChatDomain, text: '订单00104做功率预测，给出功率档分布。' },
  { domain: 'BOM', mode: 'plan_bom' as BusinessChatDomain, text: '订单00104目标620W 50%，625W 50%，推荐供应商。' },
  { domain: 'BOM', mode: 'plan_bom' as BusinessChatDomain, text: '哪些订单的接线盒规格不一样，按订单列出来。' },
  { domain: '经营分析', mode: 'business_analysis' as BusinessChatDomain, text: '2024年组件事业部销量和预算达成率如何？' },
  { domain: '经营分析', mode: 'business_analysis' as BusinessChatDomain, text: '今年产销存库存和销售量趋势怎么样？' },
]

const domainLabelMap: Record<BusinessChatDomain, string> = {
  auto: '自动识别',
  logistics: '物流数据',
  plan_bom: '计划 BOM',
  business_analysis: '产销存经营分析',
}

/** 当前窗口消息列表，切换窗口时自动隔离。 */
const messages = computed(() => activeSession.value?.messages || [])

/** 当前窗口是否存在未完成请求，只影响当前输入区按钮。 */
const currentSessionLoading = computed(() => messages.value.some((message) => message.loading))

/** 当前窗口业务域选择，变更后立即保存到本地会话。 */
const domainMode = computed<BusinessChatDomain>({
  get() {
    return activeSession.value?.domain || 'auto'
  },
  set(value) {
    if (!activeSession.value) return
    mutateSession(activeSession.value.id, (session) => {
      session.domain = value
    })
  },
})

/** 读取当前激活窗口；不存在时创建一个空白窗口。 */
function loadActiveSession() {
  const session = ensureBusinessChatSession()
  const activeId = getActiveBusinessChatSessionId() || session.id
  activeSession.value = getBusinessChatSession(activeId) || session
  nextTick(scrollToBottom)
}

/** 根据关键词选择真实业务接口，只决定路由，不生成业务答案。 */
function inferDomain(text: string): Exclude<BusinessChatDomain, 'auto'> | null {
  const normalized = text.toLowerCase()
  const businessAnalysisKeywords = [
    '产销存',
    '经营分析',
    '预算',
    '达成率',
    '销售量',
    '销量',
    '产量',
    '库存',
    '存货',
    'sap数据',
    '寄存仓',
    '寄存合计',
    '周转率',
  ]
  const bomKeywords = [
    'bom',
    'bill of materials',
    'billofmaterials',
    '订单',
    '物料',
    '物料描述',
    '材料规格',
    '核心材料',
    '玻璃',
    '焊带',
    '汇流条',
    '接线盒',
    '线盒',
    '间隙贴膜',
    '功率预测',
    '功率档',
    '功率分布',
    '目标功率',
    '目标比例',
    '供应商推荐',
    '推荐供应商',
    '电池效率',
    '标板',
    '北德',
    '计量院',
    '莱茵',
    '版本',
    '电池片',
    'nt10',
    'nt12',
    'gdf',
  ]
  const logisticsKeywords = [
    '物流',
    '运费',
    '运价',
    '报价',
    '发运',
    '发货',
    '发运量',
    '运输',
    '承运商',
    '车次',
    '省份',
    '区域',
    '签收',
    '费用',
    '历史',
    '瓦数',
    '元/瓦',
    '始发',
    '基地',
    '运量',
    '发货量',
    '装载',
    '托数',
    '每车',
    '车次',
    '车型',
    '单价/车',
    '平均单价',
    '均价',
    '单瓦价',
    '目的地',
    '采购方式',
    '经营计划',
    '辅料送样',
    '场景',
    '单瓦成本',
    '客户名',
    '项目名',
    '项目名称',
    '查询结果',
    '任务量',
    '送达城市',
    '送达距离',
    '身份证',
    '手机号',
    '司机',
    '水路',
    '铁路',
    '公路',
    '招标',
    '询比价',
    '华东',
    '西北',
  ]
  const businessAnalysisScore = businessAnalysisKeywords.filter((item) => normalized.includes(item.toLowerCase())).length
  const bomScore = bomKeywords.filter((item) => normalized.includes(item.toLowerCase())).length
  const logisticsScore = logisticsKeywords.filter((item) => normalized.includes(item.toLowerCase())).length
  // 经营分析关键词命中时优先进入产销存链路，避免“库存/销量”被物流或 BOM 规则误收。
  if (businessAnalysisScore > 0 && businessAnalysisScore >= logisticsScore && businessAnalysisScore >= bomScore) return 'business_analysis'
  // “规格”在物流产品规格和 BOM 规格中都会出现，不能单独作为 BOM 路由依据。
  if (logisticsScore > 0 && logisticsScore >= bomScore) return 'logistics'
  if (bomScore > 0) return 'plan_bom'
  return null
}

/**
 * 合并用户手动选择和问题文本识别结果。
 *
 * 参数：
 *   selectedDomain: 当前会话选择的业务域；
 *   text: 用户输入的问题文本。
 *
 * 返回：
 *   实际调用的业务域；当手动选择和明显业务关键词冲突时按文本纠偏。
 */
function resolveQuestionDomain(selectedDomain: BusinessChatDomain, text: string): Exclude<BusinessChatDomain, 'auto'> | null {
  const inferredDomain = inferDomain(text)
  if (selectedDomain === 'auto') return inferredDomain
  if (inferredDomain && inferredDomain !== selectedDomain) return inferredDomain
  return selectedDomain
}

/** 推荐问题只填入输入框，不写死业务结果。 */
function useExample(item: (typeof examples)[number]) {
  domainMode.value = item.mode
  question.value = item.text
}

/** 根据示例所属业务域展示短标签，避免新增经营分析示例仍显示为 BOM。 */
function resolveExampleDomainLabel(domain: string) {
  if (domain === '物流') return '物流'
  if (domain === '经营分析') return '产销存'
  return 'BOM'
}

/** 点击追问建议后填入输入框，由用户确认发送。 */
function appendFollowUp(text: string) {
  question.value = text
}

/** 统一提交入口：物流、经营分析和 BOM 都继续调用真实后端接口。 */
async function submitQuestion(input?: string) {
  const text = (input || question.value).trim()
  if (!text || !activeSession.value || currentSessionLoading.value) return

  const sessionId = activeSession.value.id
  const selectedDomain = activeSession.value.domain
  const resolvedDomain = resolveQuestionDomain(selectedDomain, text)
  const userMessage = buildMessage({
    role: 'user',
    content: text,
    domain: resolvedDomain || selectedDomain,
  })
  question.value = ''

  mutateSession(sessionId, (session) => {
    session.messages.push(userMessage)
    session.lastQuestion = text
    session.isNew = false
    if (!session.title || session.title === '新对话') {
      session.title = buildBusinessChatSessionTitle(text, resolvedDomain || selectedDomain)
    }
    if (resolvedDomain) session.domain = resolvedDomain
  })

  if (!resolvedDomain) {
    appendAssistantMessage(sessionId, {
      content: '请先选择“物流数据”“计划 BOM”或“经营分析/产销存”，也可以在问题中补充业务域关键词。',
      domain: 'auto',
      status: 'needs_domain',
    })
    return
  }

  const assistantId = appendAssistantMessage(sessionId, {
    content: '',
    domain: resolvedDomain,
    status: 'loading',
    loading: true,
  })

  try {
    /* LQG-8：物流与计划 BOM 统一走 business-qa/stream 入口；
       经营分析/产销存继续使用原有独立流式接口。 */
    if (resolvedDomain === 'logistics' || resolvedDomain === 'plan_bom') {
      let completed = false
      await streamBusinessQa(
        { question: text, domain_hint: resolvedDomain as 'logistics' | 'plan_bom' },
        {
          onMeta: (meta) => updateAssistantStreamMeta(sessionId, assistantId, meta),
          onDelta: (chunk) => updateAssistantStreamingContent(sessionId, assistantId, chunk),
          onDone: (streamData) => {
            const data = ((streamData as any)?.data || streamData) as Record<string, any>
            completed = true
            if (resolvedDomain === 'logistics') {
              completeAssistantMessage(sessionId, assistantId, {
                content: '',
                domain: resolvedDomain,
                status: data?.status?.code || 'OK',
                presentation: adaptLogisticsResult(data as any),
                rawResponse: data as unknown as Record<string, any>,
              })
            } else {
              completeAssistantMessage(sessionId, assistantId, {
                content: '',
                domain: resolvedDomain,
                status: data?.status?.code || data?.classification || 'OK',
                presentation: adaptPlanBomResult(data as any),
                rawResponse: data as unknown as Record<string, any>,
              })
            }
          },
        },
      )
      if (!completed) throw new Error('流式回答未正常结束，请稍后重试。')
    } else if (resolvedDomain === 'business_analysis') {
      let completed = false
      await streamInventorySalesProductionQuestion(
        { question: text },
        {
          onMeta: (meta) => updateAssistantStreamMeta(sessionId, assistantId, meta),
          onDelta: (chunk) => updateAssistantStreamingContent(sessionId, assistantId, chunk),
          onDone: (streamData) => {
            const data = ((streamData as any)?.data || streamData) as InventorySalesProductionQaResponse
            completed = true
            completeAssistantMessage(sessionId, assistantId, {
              content: '',
              domain: resolvedDomain,
              status: data?.status?.code || data?.classification || 'OK',
              presentation: adaptInventorySalesProductionResult(data),
              rawResponse: data as unknown as Record<string, any>,
            })
          },
        },
      )
      if (!completed) throw new Error('流式回答未正常结束，请稍后重试。')
    }
  } catch (error) {
    failAssistantMessage(
      sessionId,
      assistantId,
      error instanceof Error ? error.message : '接口请求失败，请稍后重试。',
    )
  }
}

/** 输入区键盘发送，兼容中文输入法组合态，避免按 Enter 选字时误提交。 */
function handleComposerKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return
  event.preventDefault()
  submitQuestion()
}

/**
 * 构造标准消息。
 *
 * 参数：
 *   input: 消息角色、内容、业务域、状态、展示数据和错误信息。
 *
 * 返回：
 *   可写入当前会话窗口的标准消息对象。
 */
function buildMessage(input: {
  role: BusinessChatMessage['role']
  content: string
  domain: BusinessChatDomain
  status?: string
  presentation?: UnifiedResult | null
  rawResponse?: Record<string, any> | null
  loading?: boolean
  error?: string
}): BusinessChatMessage {
  return {
    id: buildBusinessChatMessageId(),
    role: input.role,
    content: input.content,
    domain: input.domain,
    status: input.status,
    presentation: input.presentation as Record<string, any> | null | undefined,
    rawResponse: input.rawResponse,
    loading: input.loading,
    error: input.error,
    createdAt: new Date().toISOString(),
  }
}

/** 在指定窗口追加助手消息，并返回消息 ID。 */
function appendAssistantMessage(
  sessionId: string,
  input: {
    content: string
    domain: BusinessChatDomain
    status?: string
    loading?: boolean
  },
) {
  const message = buildMessage({
    role: 'assistant',
    content: input.content,
    domain: input.domain,
    status: input.status,
    loading: input.loading,
  })
  mutateSession(sessionId, (session) => {
    session.messages.push(message)
  })
  return message.id
}

/**
 * 追加流式回答片段。
 *
 * 参数：
 *   sessionId: 当前会话窗口 ID。
 *   messageId: 正在生成的助手消息 ID。
 *   chunk: 后端 LLM 流式输出的文本片段。
 *
 * 返回值：无。仅更新当前助手气泡中的临时文本，done 后再渲染结构化结果。
 */
function updateAssistantStreamingContent(sessionId: string, messageId: string, chunk: string) {
  if (!chunk) return
  mutateSession(sessionId, (session) => {
    const target = session.messages.find((message) => message.id === messageId)
    if (!target || !target.loading) return
    target.content = `${target.content || ''}${chunk}`
    target.status = 'streaming'
    ;(target as any).streamStage = 'streaming'
  })
}

/** 根据后端 meta 事件推进“理解问题 / 查询数据 / 组织回答”的阶段感。 */
function updateAssistantStreamMeta(sessionId: string, messageId: string, meta: Record<string, any>) {
  mutateSession(sessionId, (session) => {
    const target = session.messages.find((message) => message.id === messageId)
    if (!target || !target.loading) return
    const stage = String(meta?.stage || '')
    ;(target as any).streamStage = stage === 'received' ? 'querying' : stage === 'deterministic_result_ready' ? 'organizing' : stage
  })
}

/** 根据当前流式阶段展示更有过程感的加载文案。 */
function resolveLoadingText(message: BusinessChatMessage) {
  const stage = String((message as any).streamStage || '')
  if (stage === 'querying') return '正在查询数据'
  if (stage === 'organizing') return '正在组织回答'
  if (stage === 'streaming' || message.content) return '正在生成回答'
  return '正在理解问题'
}

/** 完成指定窗口内的助手消息，保证切换窗口后结果仍写回原窗口。 */
function completeAssistantMessage(
  sessionId: string,
  messageId: string,
  input: {
    content: string
    domain: BusinessChatDomain
    status: string
    presentation: UnifiedResult
    rawResponse: Record<string, any>
  },
) {
  mutateSession(sessionId, (session) => {
    const target = session.messages.find((message) => message.id === messageId)
    if (!target) return
    target.loading = false
    target.content = input.content || target.content || input.presentation.answer || ''
    target.domain = input.domain
    target.status = input.status
    target.presentation = input.presentation as Record<string, any>
    target.rawResponse = input.rawResponse
    ;(target as any).streamStage = 'done'
  })
}

/** 请求失败时只更新对应窗口，不影响当前正在查看的其他窗口。 */
function failAssistantMessage(sessionId: string, messageId: string, error: string) {
  mutateSession(sessionId, (session) => {
    const target = session.messages.find((message) => message.id === messageId)
    if (!target) return
    target.loading = false
    target.status = 'error'
    target.error = error
  })
}

/** 修改指定窗口并持久化。 */
function mutateSession(sessionId: string, mutator: (session: BusinessChatSession) => void) {
  const session = getBusinessChatSession(sessionId)
  if (!session) return
  mutator(session)
  session.updatedAt = new Date().toISOString()
  const saved = saveBusinessChatSession(session)
  if (saved && activeSession.value?.id === sessionId) {
    activeSession.value = saved
    nextTick(scrollToBottom)
  }
}

/** 将经营分析产销存结果适配为统一展示结构，前端不补算业务指标。 */
function adaptInventorySalesProductionResult(data: InventorySalesProductionQaResponse): UnifiedResult {
  const presentation = data.presentation
  const unsupported = presentation?.unsupported_explanation
  const answer = presentation?.answer || data.answer_summary || data.status?.message || ''
  return normalizeResult({
    displayType: presentation?.display_type || '',
    title: presentation?.title || '经营分析产销存问答结果',
    answer,
    highlights: filterBusinessTexts(dedupeBusinessTexts(presentation?.highlights || [], [answer])),
    cards: localizeCards(presentation?.cards || []),
    chart: normalizeChart((presentation?.chart_spec || null) as NonNullable<LogisticsDataQaResult['presentation']>['chart_spec'] | null),
    table: resolvePresentationTable(presentation),
    followUps: localizeFollowUps(presentation?.follow_up?.questions || []),
    suggestions: filterBusinessTexts(unsupported?.suggestions || []),
    caveats: filterBusinessTexts(presentation?.caveats || []),
    caveatItems: normalizeCaveatItems(presentation?.caveat_items as CaveatItem[] | null | undefined, presentation?.caveats || []),
  })
}

/** 将物流结果适配为统一展示结构，前端不反推或修改业务事实。 */
function adaptLogisticsResult(data: LogisticsDataQaResult): UnifiedResult {
  const presentation = data.presentation
  const unsupported = presentation?.unsupported_explanation
  const answer = presentation?.answer || data.answer_summary || data.status?.message || ''
  return normalizeResult({
    displayType: presentation?.display_type || '',
    title: presentation?.title || '物流数据问答结果',
    answer,
    highlights: filterBusinessTexts(dedupeBusinessTexts(presentation?.highlights || [], [answer])),
    cards: localizeCards(presentation?.cards || []),
    chart: normalizeChart(presentation?.chart_spec || null),
    table: resolvePresentationTable(presentation),
    followUps: localizeFollowUps(presentation?.follow_up?.questions || data.clarification_questions || []),
    suggestions: filterBusinessTexts(unsupported?.suggestions || data.query_plan?.unsupported_suggestions || []),
    caveats: filterBusinessTexts(presentation?.caveats || []),
    caveatItems: normalizeCaveatItems((presentation as Record<string, any> | null | undefined)?.caveat_items, presentation?.caveats || []),
  })
}

/** 将计划 BOM 结果适配为统一展示结构，前端只展示后端确定性返回。 */
function adaptPlanBomResult(data: PlanBomQaResponse): UnifiedResult {
  const presentation = data.presentation
  const followUp = presentation?.follow_up as { questions?: string[]; examples?: string[] } | null | undefined
  const unsupported = presentation?.unsupported_explanation as { reason?: string; suggestions?: string[] } | null | undefined
  const answer = presentation?.answer || data.answer_summary || data.status?.message || ''
  return normalizeResult({
    displayType: (presentation as Record<string, any> | null | undefined)?.display_type || '',
    title: presentation?.title || `计划 BOM 问答结果（${data.classification || '未知'}）`,
    answer,
    highlights: filterBusinessTexts(dedupeBusinessTexts(presentation?.highlights || [], [answer])),
    cards: [],
    chart: null,
    table: resolvePresentationTable(presentation),
    followUps: localizeFollowUps(followUp?.questions || []),
    suggestions: filterBusinessTexts(unsupported?.suggestions || []),
    caveats: filterBusinessTexts((presentation as Record<string, any> | null | undefined)?.caveats || []),
    caveatItems: normalizeCaveatItems((presentation as Record<string, any> | null | undefined)?.caveat_items, (presentation as Record<string, any> | null | undefined)?.caveats || []),
  })
}

/** 只尊重后端 presentation 明确编排的表格，不再因原始 result_table 存在而固定展示“明细数据”。 */
function resolvePresentationTable(presentation: { table_spec?: UnifiedTable | null } | null | undefined): UnifiedTable | null {
  return presentation?.table_spec || null
}

/** 补齐展示默认值，避免字段缺失导致页面异常。 */
function normalizeResult(value: Partial<UnifiedResult>): UnifiedResult {
  return {
    displayType: value.displayType || '',
    title: value.title || '',
    answer: value.answer || '',
    highlights: value.highlights || [],
    cards: value.cards || [],
    chart: value.chart || null,
    table: normalizeTable(value.table || null),
    followUps: value.followUps || [],
    suggestions: value.suggestions || [],
    caveats: value.caveats || [],
    caveatItems: normalizeCaveatItems(value.caveatItems, value.caveats || []),
  }
}

/**
 * 归一化后端分级口径提醒。
 *
 * 参数：
 *   caveatItems: 后端新协议返回的分级口径提醒；
 *   caveats: 旧协议普通口径提醒，用作 info 级兜底。
 *
 * 返回：
 *   去重后的 CaveatItem 数组。前端只展示业务可读文本，不暴露技术字段。
 */
function normalizeCaveatItems(caveatItems?: CaveatItem[] | null, caveats: string[] = []): CaveatItem[] {
  const candidates: CaveatItem[] = []
  if (Array.isArray(caveatItems)) {
    caveatItems.forEach((item) => {
      const text = String((item as CaveatItem)?.text || '').trim()
      if (!text || !filterBusinessTexts([text]).length) return
      candidates.push({
        level: normalizeCaveatLevel((item as CaveatItem)?.level),
        text,
      })
    })
  }
  filterBusinessTexts(caveats).forEach((text) => candidates.push({ level: 'info', text }))

  const seen = new Set<string>()
  return candidates.filter((item) => {
    const key = `${item.level}:${normalizeBusinessText(item.text)}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
}

/** 将异常或历史等级兜底到 info，避免前端渲染未知风险等级。 */
function normalizeCaveatLevel(level: unknown): CaveatItem['level'] {
  return level === 'warning' || level === 'danger' ? level : 'info'
}

/** 归一化后端图表配置，缺少必要字段时不渲染图表。 */
function normalizeChart(chart: NonNullable<LogisticsDataQaResult['presentation']>['chart_spec'] | null | undefined): UnifiedChart | null {
  if (!chart || typeof chart !== 'object') return null
  if (chart.chart_type !== 'line' && chart.chart_type !== 'bar' && chart.chart_type !== 'pie') return null
  const values = extractChartValues(chart as UnifiedChart)
  if (!values.length) return null
  if (chart.chart_type === 'pie' && (values.some((item) => item.value < 0) || !values.some((item) => item.value > 0))) return null
  return {
    chart_type: chart.chart_type,
    title: typeof chart.title === 'string' ? chart.title : '',
    x_axis: typeof chart.x_axis === 'string' ? chart.x_axis : '',
    y_axis: Array.isArray(chart.y_axis) ? chart.y_axis.filter((item: unknown) => typeof item === 'string') : [],
    series: Array.isArray(chart.series) ? chart.series.filter((item: unknown) => item && typeof item === 'object') as Array<Record<string, any>> : [],
    unit: typeof chart.unit === 'string' ? chart.unit : null,
    data: Array.isArray(chart.data) ? chart.data.filter((item: unknown) => item && typeof item === 'object') as Array<Record<string, any>> : [],
  }
}

/** 统一表格列名，避免业务界面直接暴露英文技术字段。 */
function normalizeTable(table: UnifiedTable | null): UnifiedTable | null {
  if (!table?.rows?.length) return null
  if (table.rows.some((row) => row && typeof row === 'object' && resultTableRowSpanKey in row && resultTableSubRowIndexKey in row)) {
    return table
  }
  const sourceColumns = table.columns?.length ? table.columns : Object.keys(table.rows[0] || {})
  const columns = sourceColumns.map((column, index) => localizeColumnName(column, index))
  const normalizedRows = table.rows.map((row) => {
    const next: Record<string, any> = {}
    sourceColumns.forEach((column, index) => {
      next[columns[index]] = row[column]
    })
    return next
  })
  return { columns, rows: expandFallRatioEstimateRows(normalizedRows, columns) }
}

/**
 * 把“落档比例预估”由单元格内多行拆成真实表格子行。
 * 参数：rows 已完成列名归一化的表格行；columns 当前可见列名。
 * 返回值：展开后的表格行，并携带 rowspan 元信息供 Element Plus 合并其它列。
 */
function expandFallRatioEstimateRows(rows: Array<Record<string, any>>, columns: string[]) {
  const fallRatioColumn = columns.find((column) => isFallRatioEstimateColumn(column))
  if (!fallRatioColumn) {
    return rows.map((row, sourceRowIndex) => ({
      ...row,
      [resultTableRowSpanKey]: 1,
      [resultTableSubRowIndexKey]: 0,
      [resultTableSourceRowIndexKey]: sourceRowIndex,
    }))
  }

  return rows.flatMap((row, sourceRowIndex) => {
    const lines = splitFallRatioEstimateLines(row[fallRatioColumn])
    const rowSpan = Math.max(lines.length, 1)
    return lines.map((line, subRowIndex) => ({
      ...row,
      [fallRatioColumn]: line,
      [resultTableRowSpanKey]: rowSpan,
      [resultTableSubRowIndexKey]: subRowIndex,
      [resultTableSourceRowIndexKey]: sourceRowIndex,
    }))
  })
}

/**
 * 判断明细表列是否是“落档比例预估”。
 * 参数：column 当前可见列名。
 * 返回值：该列需要按“每个效率段一行”的异形表格结构展示时返回 true。
 */
function isFallRatioEstimateColumn(column: string) {
  return localizeColumnName(column) === '落档比例预估'
}

/**
 * 判断明细表列是否需要按多行文本展示。
 * 参数：column 当前可见列名。
 * 返回值：需要保留换行时返回 true。
 */
function isMultiLineTableColumn(column: string) {
  return isFallRatioEstimateColumn(column)
}

/**
 * 根据列类型给表格列设置最小宽度。
 * 参数：column 当前可见列名。
 * 返回值：Element Plus 表格列 min-width，落档比例列加宽以避免效率段被拆散。
 */
function getResultTableColumnMinWidth(column: string) {
  return isFallRatioEstimateColumn(column) ? 420 : 130
}

/**
 * 构造原生异形表格列样式。
 * 参数：column 当前可见列名。
 * 返回值：列最小宽度，确保附件中的“落档比例预估”有足够书写空间。
 */
function getResultTableColumnStyle(column: string) {
  return { minWidth: `${getResultTableColumnMinWidth(column)}px` }
}

/**
 * 判断是否使用附件式原生异形表格。
 * 参数：message 当前助手消息。
 * 返回值：存在落档比例列时返回 true，使该列可以像供应商行一样另起真实行。
 */
function shouldUseIrregularResultTable(message: BusinessChatMessage) {
  const table = getAssistantResultTable(message)
  return Boolean(table?.columns.some((column) => isFallRatioEstimateColumn(column)) && table.rows.length)
}

/**
 * 判断异形表格当前单元格是否需要渲染。
 * 参数：row 展示行；column 当前可见列名。
 * 返回值：落档比例列每个子行都渲染，其它列只在原业务行首个子行渲染并 rowspan 合并。
 */
function shouldRenderIrregularResultTableCell(row: Record<string, any>, column: string) {
  return isFallRatioEstimateColumn(column) || getResultTableSubRowIndex(row) === 0
}

/**
 * 计算异形表格当前单元格 rowspan。
 * 参数：row 展示行；column 当前可见列名。
 * 返回值：落档比例列始终 1，其它列按原业务行子行数纵向合并。
 */
function getIrregularResultTableCellRowSpan(row: Record<string, any>, column: string) {
  return isFallRatioEstimateColumn(column) ? 1 : getResultTableRowSpan(row)
}

/**
 * 生成异形表格单元格 class。
 * 参数：column 当前可见列名。
 * 返回值：落档比例列附加专用 class，便于单独控制横向滚动和不折行。
 */
function getIrregularResultTableCellClassName(column: string) {
  return isFallRatioEstimateColumn(column) ? 'result-table__td--fall-ratio' : ''
}

/**
 * 构造异形表格展示行 key。
 * 参数：row 展示行；rowIndex 当前展开后的行号。
 * 返回值：稳定区分同一业务行下多个落档比例子行。
 */
function buildIrregularResultTableRowKey(row: Record<string, any>, rowIndex: number) {
  return `${row[resultTableSourceRowIndexKey] ?? rowIndex}-${row[resultTableSubRowIndexKey] ?? 0}`
}

/**
 * 给特殊列添加单元格 class，便于只针对“落档比例预估”列开启横向滚动。
 * 参数：column 当前可见列名。
 * 返回值：Element Plus 表格列 class-name。
 */
function getResultTableColumnClassName(column: string) {
  return isFallRatioEstimateColumn(column) ? 'result-table-column--fall-ratio' : ''
}

/**
 * 读取展开行的合并行数。
 * 参数：row 展示表格行。
 * 返回值：大于等于 1 的 rowspan。
 */
function getResultTableRowSpan(row: Record<string, any>) {
  const value = Number(row?.[resultTableRowSpanKey])
  return Number.isFinite(value) && value > 1 ? Math.floor(value) : 1
}

/**
 * 读取展开行在原业务行中的子行序号。
 * 参数：row 展示表格行。
 * 返回值：从 0 开始的子行序号。
 */
function getResultTableSubRowIndex(row: Record<string, any>) {
  const value = Number(row?.[resultTableSubRowIndexKey])
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : 0
}

/**
 * Element Plus 表格合并策略：落档比例每段一行，其它列按原业务行纵向合并。
 * 参数：row/column 为 Element Plus span-method 入参。
 * 返回值：当前单元格的 rowspan/colspan。
 */
function getResultTableSpanMethod({ row, column }: { row: Record<string, any>; column: { property?: string } }) {
  const property = String(column?.property || '')
  if (isFallRatioEstimateColumn(property)) return { rowspan: 1, colspan: 1 }

  const rowSpan = getResultTableRowSpan(row)
  if (rowSpan <= 1) return { rowspan: 1, colspan: 1 }
  return getResultTableSubRowIndex(row) === 0 ? { rowspan: rowSpan, colspan: 1 } : { rowspan: 0, colspan: 0 }
}

/**
 * 构造导出 Excel 的合并单元格配置，使导出的异形表格与页面展示一致。
 * 参数：table 已归一化且已展开的表格。
 * 返回值：xlsx `!merges` 可识别的合并区域数组。
 */
function buildAssistantTableExportMerges(table: UnifiedTable) {
  const merges: Array<{ s: { r: number; c: number }; e: { r: number; c: number } }> = []
  table.rows.forEach((row, rowIndex) => {
    const rowSpan = getResultTableRowSpan(row)
    if (rowSpan <= 1 || getResultTableSubRowIndex(row) !== 0) return
    table.columns.forEach((column, columnIndex) => {
      if (isFallRatioEstimateColumn(column)) return
      merges.push({
        s: { r: rowIndex + 1, c: columnIndex },
        e: { r: rowIndex + rowSpan, c: columnIndex },
      })
    })
  })
  return merges
}

/**
 * 将“落档比例预估”拆成一个效率段一行的展示数组。
 * 参数：value 后端返回的单元格原值，可能是换行分隔的新格式，也可能是历史分号分隔格式。
 * 返回值：每个元素对应截图红框中的一个独立效率段。
 */
function splitFallRatioEstimateLines(value: unknown) {
  const text = String(formatTableCell(value) || '')
  if (!text.trim()) return ['']
  const lines = text
    .split(/(?:\r?\n|[；;])+/)
    .map((line) => line.trim())
    .filter(Boolean)
  return lines.length ? lines : [text.trim()]
}

/**
 * 格式化明细表单元格展示值，只做显示层归一化，不改变后端业务事实。
 * 参数：value 后端返回的单元格原值。
 * 返回值：可直接展示的字符串或数值。
 */
function formatTableCell(value: unknown): string | number | boolean {
  if (value === null || value === undefined) return ''
  if (typeof value === 'number' || typeof value === 'boolean') return value
  if (Array.isArray(value)) return value.map((item) => formatTableCell(item)).join('、')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/** 构造图表标题。 */
function buildChartTitle(chart: UnifiedChart) {
  if (chart.title) return chart.title
  if (chart.chart_type === 'pie') return '占比图'
  return chart.chart_type === 'line' ? '趋势图' : '对比图'
}

/** 构造图表辅助说明，帮助业务用户快速理解当前图表口径。 */
function buildChartMeta(chart: UnifiedChart) {
  const values = extractChartValues(chart)
  const typeLabel = chart.chart_type === 'line' ? '趋势' : chart.chart_type === 'pie' ? '占比' : '对比'
  const unitText = chart.unit ? `，单位：${chart.unit}` : ''
  return `${typeLabel}展示，共 ${values.length} 个数据点${unitText}`
}

/** 构造图表无障碍说明，只描述后端已返回的数据结构，不补算业务结论。 */
function buildChartAriaLabel(chart: UnifiedChart) {
  return `${buildChartTitle(chart)}，${buildChartMeta(chart)}`
}

/** 生成折线图 polyline points。 */
function buildLineChartPoints(chart: UnifiedChart) {
  return buildChartRenderPoints(chart)
    .map((point) => `${point.x},${point.y}`)
    .join(' ')
}

/** 生成折线图圆点。 */
function buildLineChartCircles(chart: UnifiedChart) {
  return buildChartRenderPoints(chart)
}

/** 生成条形图矩形。 */
function buildBarChartRects(chart: UnifiedChart) {
  const values = extractChartValues(chart)
  const max = Math.max(...values.map((item) => item.value), 1)
  const chartLeft = 28
  const chartTop = 18
  const chartHeight = 168
  const slotWidth = values.length ? 584 / values.length : 584
  const barWidth = Math.max(14, Math.min(42, slotWidth * 0.54))
  return values.map((item, index): ChartRenderBar => {
    const height = Math.max(4, (item.value / max) * chartHeight)
    const x = chartLeft + slotWidth * index + (slotWidth - barWidth) / 2
    return {
      x,
      y: chartTop + chartHeight - height,
      width: barWidth,
      height,
    }
  })
}

/** 生成饼图扇区路径。 */
function buildPieChartSlices(chart: UnifiedChart): ChartRenderSlice[] {
  const values = extractPieChartValues(chart)
  const total = values.reduce((sum, item) => sum + item.value, 0)
  if (total <= 0) return []
  let cursor = 0
  return values
    .filter((item) => item.value > 0)
    .map((item, index) => {
      const start = cursor
      const percent = item.value / total
      cursor += percent
      const color = pieChartColors[index % pieChartColors.length]
      const label = String(item.label ?? `项目${index + 1}`)
      const valueText = formatPieValue(item.value, chart.unit)
      return {
        path: buildPieSlicePath(110, 110, 84, start, cursor),
        color,
        label,
        value: item.value,
        percent,
        tooltip: `${label}：${valueText}，占比 ${(percent * 100).toFixed(1)}%`,
      }
    })
}

/** 生成饼图图例。 */
function buildPieChartLegend(chart: UnifiedChart): ChartLegendItem[] {
  return buildPieChartSlices(chart).map((slice) => ({
    color: slice.color,
    label: slice.label,
    valueText: `${formatPieValue(slice.value, chart.unit)} · ${(slice.percent * 100).toFixed(1)}%`,
  }))
}

/** 构造单个饼图扇区 SVG 路径。 */
function buildPieSlicePath(cx: number, cy: number, radius: number, startRatio: number, endRatio: number) {
  // 单一切片会出现起止点重合，必须拆成两段圆弧，否则 SVG 可能渲染为空。
  if (endRatio - startRatio >= 0.999999) {
    return [
      `M ${formatSvgNumber(cx)} ${formatSvgNumber(cy - radius)}`,
      `A ${radius} ${radius} 0 1 1 ${formatSvgNumber(cx)} ${formatSvgNumber(cy + radius)}`,
      `A ${radius} ${radius} 0 1 1 ${formatSvgNumber(cx)} ${formatSvgNumber(cy - radius)}`,
      'Z',
    ].join(' ')
  }
  const startAngle = -Math.PI / 2 + startRatio * Math.PI * 2
  const endAngle = -Math.PI / 2 + endRatio * Math.PI * 2
  const start = {
    x: cx + radius * Math.cos(startAngle),
    y: cy + radius * Math.sin(startAngle),
  }
  const end = {
    x: cx + radius * Math.cos(endAngle),
    y: cy + radius * Math.sin(endAngle),
  }
  const largeArc = endRatio - startRatio > 0.5 ? 1 : 0
  return [
    `M ${formatSvgNumber(cx)} ${formatSvgNumber(cy)}`,
    `L ${formatSvgNumber(start.x)} ${formatSvgNumber(start.y)}`,
    `A ${radius} ${radius} 0 ${largeArc} 1 ${formatSvgNumber(end.x)} ${formatSvgNumber(end.y)}`,
    'Z',
  ].join(' ')
}

/** 格式化 SVG 坐标，减少 DOM 中无意义长小数。 */
function formatSvgNumber(value: number) {
  return Number(value.toFixed(3))
}

/** 格式化饼图图例数值，保留业务单位。 */
function formatPieValue(value: number, unit?: string | null) {
  const formatted = formatDisplayValue(value)
  return unit ? `${formatted}${unit}` : formatted
}

/** 生成图表 X 轴标签。 */
function buildChartLabels(chart: UnifiedChart) {
  const values = extractChartValues(chart)
  const lineSlotWidth = values.length > 1 ? 584 / (values.length - 1) : 0
  const barSlotWidth = values.length ? 584 / values.length : 584
  const maxLabels = 8
  const step = Math.max(1, Math.ceil(values.length / maxLabels))
  return values
    .map((item, index): ChartRenderLabel => ({
      x: chart.chart_type === 'bar'
        ? 28 + barSlotWidth * index + barSlotWidth / 2
        : values.length > 1 ? 28 + lineSlotWidth * index : 320,
      text: String(item.label ?? '').slice(0, 8),
    }))
    .filter((_, index) => index % step === 0)
}

/** 根据图表数据生成 SVG 坐标点。 */
function buildChartRenderPoints(chart: UnifiedChart) {
  const values = extractChartValues(chart)
  const numbers = values.map((item) => item.value)
  const min = Math.min(...numbers, 0)
  const max = Math.max(...numbers, 1)
  const range = max - min || 1
  const chartLeft = 28
  const chartTop = 18
  const chartHeight = 168
  const step = values.length > 1 ? 584 / (values.length - 1) : 0
  return values.map((item, index): ChartRenderPoint => ({
    x: values.length > 1 ? chartLeft + step * index : 320,
    y: chartTop + chartHeight - ((item.value - min) / range) * chartHeight,
  }))
}

/** 从 chart_spec 中提取第一组可展示数据。 */
function extractChartValues(chart: UnifiedChart): ChartValue[] {
  const firstSeries = chart.series?.[0]
  if (Array.isArray(firstSeries?.data) && firstSeries.data.length) {
    return firstSeries.data
      .map((item: Record<string, unknown>) => ({
        label: item.x,
        value: parseChartNumber(item.y),
      }))
      .filter((item: ChartValue) => Number.isFinite(item.value))
  }
  const xAxis = chart.x_axis || ''
  const yAxis = chart.y_axis?.[0] || ''
  return (chart.data || [])
    .map((row: Record<string, unknown>) => ({
      label: row[xAxis],
      value: parseChartNumber(row[yAxis]),
    }))
    .filter((item: ChartValue) => Number.isFinite(item.value))
}

/** 解析图表数值，兼容后端或历史快照中可能出现的千分位字符串。 */
function parseChartNumber(value: unknown) {
  if (typeof value === 'number') return value
  if (typeof value === 'string') return Number(value.replace(/,/g, '').trim())
  return Number(value)
}

/** 饼图只展示非负切片，全零时由 normalizeChart 阻止渲染。 */
function extractPieChartValues(chart: UnifiedChart): ChartValue[] {
  return extractChartValues(chart).filter((item) => item.value >= 0)
}

const columnNameMap: Record<string, string> = {
  dimension_value: '维度',
  metric: '指标',
  city: '城市',
  province: '省份',
  address: '地址',
  year: '年份',
  biz_year: '年份',
  month: '月份',
  biz_month: '月份',
  scope_label: '统计范围',
  customer: '客户',
  customer_name: '客户',
  total_fee: '总运费',
  task_count: '任务数',
  parse_fail_count: '未纳入运费统计任务数',
  price_missing_count: '缺少价格任务数',
  record_count: '记录数',
  total_record_count: '全部记录数',
  record_share_pct: '占比',
  category: '类别',
  item: '项目',
  shipment_count: '发运件数',
  shipment_watt: '发运量',
  shipment_mw: '发运量',
  shipment_share_pct: '占比',
  region_name: '区域',
  transport_mode: '运输方式',
  procurement_type: '采购方式',
  task_share_pct: '任务占比',
  delivery_city: '送达城市',
  driver_name: '司机',
  driver_phone: '司机手机号',
  driver_names: '司机姓名列表',
  driver_id_number: '司机身份证号',
  driver_phones: '手机号列表',
  driver_name_count: '司机姓名数',
  driver_phone_count: '手机号数',
  assign_task_count: '派车任务数',
  distinct_task_count: '去重任务数',
  logistics_company: '物流公司',
  logistics_company_name: '物流公司',
  carrier_name: '承运商',
  company_name: '承运商',
  avg_fee_per_trip: '平均单价/车',
  avg_fee: '平均运费',
  max_fee: '最高运费',
  min_fee: '最低运费',
  shipment_trip_count: '车次',
  avg_pallet_per_vehicle: '平均每车装载托数',
  valid_record_count: '有效记录数',
  missing_record_count: '缺失记录数',
  unit_price_per_vehicle: '单价/车',
  fee_per_watt: '元/瓦',
  avg_fee_per_watt: '平均元/瓦',
  unit_fee_per_watt: '平均元/瓦',
  extra_fee: '额外费用',
  extra_fee_amount: '额外费用',
  extra_fee_ratio: '额外费用占比',
  extra_fee_share_pct: '额外费用占比',
  total_fee_amount: '总费用',
  total_fee_share_pct: '运费占比',
  denominator_total_fee: '口径总运费',
  origin_place_count: '始发地数量',
  matched_spec_count: '命中规格数',
  plan_qty_total: '计划发运件数',
  actual_qty_total: '实际发运件数',
  deviation_rate: '偏差率',
  detail_count: '明细条数',
  pickup_date_available_count: '有提货日期记录数',
  pickup_date_missing_count: '缺少提货日期记录数',
  power_missing_count: '缺少功率记录数',
  strict_scope_task_count: '严格口径任务数',
  year_task_count: '年度任务数',
  order_no: '订单号',
  order_name: '订单名称',
  material_category: '材料类别',
  material_category_label: '材料类别',
  material_name: '物料名称',
  description: '规格描述',
  version_no: '版本',
  sap_code: '物料编码',
  line_no: '行号',
  remark: '备注',
  unit: '单位',
  standard_usage: '用量',
  source_file: '来源文件',
  diff_type: '差异类型',
  left_order: '左侧订单',
  left_description: '左侧规格',
  right_order: '右侧订单',
  right_description: '右侧规格',
  changed_fields: '变化字段',
  status: '状态',
  row_count: '记录数',
  ctm值: 'CTM 值',
  ctm_值: 'CTM 值',
  ctm_value: 'CTM 值',
  落档比例预估: '落档比例预估',
}

function localizeColumnName(column: string, index = 0) {
  const normalizedColumn = normalizeColumnKey(column)
  if (columnNameMap[normalizedColumn]) return columnNameMap[normalizedColumn]
  if (columnNameMap[column]) return columnNameMap[column]
  const syntheticCountLabel = localizeSyntheticCountLabel(normalizedColumn)
  if (syntheticCountLabel) return syntheticCountLabel
  if (/^[\u4e00-\u9fa5A-Za-z0-9/（）() -]+$/.test(column) && !/[a-zA-Z_]/.test(column)) return column
  return `指标${index + 1}`
}

/** 统一技术字段写法，兼容后端 card label 中的空格形式。 */
function normalizeColumnKey(column: string) {
  return String(column || '')
    .trim()
    .replace(/[\s-]+/g, '_')
    .replace(/_+/g, '_')
    .toLowerCase()
}

/** 处理后端表达层自动生成的“维度字段 + 数”指标卡标签。 */
function localizeSyntheticCountLabel(column: string) {
  const matched = column.match(/^(.+)数$/)
  if (!matched) return ''
  const baseLabel = columnNameMap[matched[1]]
  return baseLabel ? `${baseLabel}数量` : ''
}

function localizeCards(cards: UnifiedResult['cards']) {
  return cards.map((card) => {
    const normalizedLabel = normalizeColumnKey(card.label)
    // 发运件数与车次是两个不同业务口径：shipment_count 用“件”，shipment_trip_count 才用“次”。
    // 后端 presentation 历史兼容字段可能把 count 类指标统一带成“次”，这里在展示层做最小纠偏。
    const correctedUnit =
      normalizedLabel === 'shipment_count' ? '件' : normalizedLabel === 'avg_pallet_per_vehicle' ? '托' : card.unit
    return {
      ...card,
      unit: correctedUnit,
      label: localizeColumnName(card.label),
    }
  })
}

/** 格式化指标卡数值，只做展示格式化，不改变业务计算结果。 */
function formatDisplayValue(value: unknown) {
  if (typeof value === 'number') {
    return value.toLocaleString('zh-CN', {
      minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
      maximumFractionDigits: 2,
    })
  }
  if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) {
    const numberValue = Number(value)
    return numberValue.toLocaleString('zh-CN', {
      minimumFractionDigits: Number.isInteger(numberValue) ? 0 : 2,
      maximumFractionDigits: 2,
    })
  }
  return value ?? '-'
}

/** 过滤技术口径说明，避免业务主界面出现表名、字段名、SQL 等内部信息。 */
function filterBusinessTexts(items: string[]) {
  const technicalPattern = /[_]|dwd|sql|query|table|字段|口径按|历史明细表|province|city|total_fee/i
  return items.filter((item) => item && !technicalPattern.test(item))
}

/** 对主回答和标签做相似去重，避免同一结论在多个位置重复出现。 */
function dedupeBusinessTexts(items: string[], baseTexts: string[] = []) {
  const result: string[] = []
  const anchors = baseTexts.filter(Boolean)
  items.forEach((item) => {
    if (!item) return
    if (anchors.some((anchor) => isSimilarBusinessText(item, anchor))) return
    if (result.some((existing) => isSimilarBusinessText(item, existing))) return
    result.push(item)
  })
  return result
}

/** 判断两段业务展示文本是否重复或高度相似。 */
function isSimilarBusinessText(left: string, right: string) {
  const leftText = normalizeBusinessText(left)
  const rightText = normalizeBusinessText(right)
  if (!leftText || !rightText) return false
  if (leftText === rightText) return true
  const [shorter, longer] = [leftText, rightText].sort((a, b) => a.length - b.length)
  return shorter.length >= 12 && longer.includes(shorter)
}

/** 归一化业务展示文本，供相似去重使用。 */
function normalizeBusinessText(text: string) {
  return String(text || '').replace(/[\s，。,.；;：:、（）()]+/g, '').toLowerCase()
}

const followUpTextMap: Record<string, string> = {
  material_category: '请补充要查询或对比的材料类别，例如玻璃、焊带、汇流条、接线盒。',
  target_power_ratio: '请补充目标功率档比例，例如：620W 50%，625W 50%。',
  power_configuration: 'BOM 中有功率预测配置未确认，请补充玻璃、线缆、标板或供应商等配置。',
  candidate: '当前条件命中多个 BOM 候选，请补充更完整订单号或确认文件实例。',
  order_id: '请补充订单号或订单尾号。',
  order_tail_no: '请补充订单尾号。',
  compare_orders: '请补充需要对比的订单。',
  bom_version: '请补充需要对比的 BOM 版本。',
  business_domain: '请先选择物流数据或计划 BOM 业务域。',
  year: '请补充统计年份。',
  month: '请补充统计月份。',
  date_range: '请补充统计时间范围。',
  province: '请补充省份范围。',
  city: '请补充城市范围。',
  customer: '请补充客户范围。',
}

/** 追问内容业务化展示，避免把 slot 字段名直接暴露给业务用户。 */
function localizeFollowUps(items: string[]) {
  return items
    .map((item) => {
      const normalized = String(item || '').trim()
      return followUpTextMap[normalized] || normalized
    })
    .filter((item) => item && !/[a-z]+_[a-z_]+/.test(item))
}

/** 新消息到达后滚动到当前窗口底部。 */
function scrollToBottom() {
  const el = conversationRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

/** 将 ISO 时间转为相对时间文案（刚刚 / N分钟前 / N小时前）。 */
function formatRelativeTime(iso?: string | null): string {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 0) return ''
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return '刚刚'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  return `${days}天前`
}

/** 根据消息状态返回状态标签信息（类型和文案）。 */
function resolveStatusBadge(status?: string): { type: string; label: string } | null {
  if (!status) return null
  const lower = status.toLowerCase()
  // A类 / success 态
  if (lower === 'ok' || lower === 'success' || lower === 'answered' || lower === 'a') {
    return { type: 'success', label: '已解答' }
  }
  // B类 / 需澄清
  if (
    lower === 'clarification' ||
    lower === 'clarification_required' ||
    lower === 'needs_clarification' ||
    lower === 'b' ||
    lower === 'missing_slots'
  ) {
    return { type: 'warning', label: '需补充信息' }
  }
  // C类 / 暂不支持
  if (
    lower === 'unsupported' ||
    lower === 'not_supported' ||
    lower === 'unsupported_question' ||
    lower === 'c' ||
    lower === 'needs_domain'
  ) {
    return { type: 'info', label: '暂不支持' }
  }
  if (lower === 'empty_result') {
    return { type: 'empty', label: '未查到结果' }
  }
  // 错误
  if (lower === 'error' || lower === 'fail' || lower === 'execution_error') {
    return { type: 'danger', label: '请求出错' }
  }
  return null
}

/** 根据后端状态生成结果面板语气，只影响视觉层级，不改变业务裁决。 */
function resolveResultTone(status?: string) {
  const badge = resolveStatusBadge(status)
  if (!badge) return 'neutral'
  if (badge.type === 'success') return 'success'
  if (badge.type === 'warning') return 'clarify'
  if (badge.type === 'empty') return 'empty'
  if (badge.type === 'danger') return 'error'
  return 'unsupported'
}

/** 生成结果摘要条，优先展示行数、图表类型和指标卡数量等展示事实。 */
function buildResultSummaryItems(message: BusinessChatMessage): ResultSummaryItem[] {
  const presentation = message.presentation as UnifiedResult | null | undefined
  if (!presentation) return []
  const items: ResultSummaryItem[] = []
  const table = getAssistantResultTable(message)
  if (shouldShowResultTable(message) && table?.rows.length) {
    items.push({ label: '行明细', value: String(table.rows.length) })
  }
  if (shouldShowMetricCards(message)) {
    items.push({ label: '项指标', value: String(presentation.cards.length) })
  }
  if (shouldShowPresentationChart(message) && presentation.chart) {
    items.push({ label: '图表', value: formatChartTypeLabel(presentation.chart.chart_type) })
  }
  return items
}

/** 判断助手回复应采用叙事、数据还是图表布局；只控制 UI 层，不改变后端业务结果。 */
function resolveAssistantResultLayout(message: BusinessChatMessage): AssistantResultLayoutClass {
  if (shouldShowPresentationChart(message)) return 'ai-response-card--chart'
  if (shouldShowResultTable(message) || shouldShowMetricCards(message)) return 'ai-response-card--data'
  return 'ai-response-card--narrative'
}

/** 指标卡只在后端返回卡片且当前布局需要数据摘要时展示。 */
function shouldShowMetricCards(message: BusinessChatMessage): boolean {
  const presentation = message.presentation as UnifiedResult | null | undefined
  return Boolean(presentation && cardDisplayTypes.has(presentation.displayType) && presentation.cards.length)
}

/** 图表只在后端按用户显式图表意图返回 chart display_type 时展示。 */
function shouldShowPresentationChart(message: BusinessChatMessage): boolean {
  const presentation = message.presentation as UnifiedResult | null | undefined
  return Boolean(presentation?.chart && chartDisplayTypes.has(presentation.displayType))
}

/**
 * 判断是否展示二级操作。
 *
 * 参数：message 当前助手消息。
 * 返回：存在数据口径或审计明细时返回 true，把结构化结果放到主回答下方的次级入口。
 */
function shouldShowSecondaryActions(message: BusinessChatMessage): boolean {
  return Boolean(message.presentation && (hasAssistantBasis(message) || hasAssistantAuditRows(message)))
}

/** 判断当前回答是否有可展开的数据口径。 */
function hasAssistantBasis(message: BusinessChatMessage): boolean {
  return getCaveatItemsByLevel(message, 'info').length > 0
}

/** 判断当前回答是否有可展开/可导出的明细行；没有行时隐藏对应按钮，避免展示点不开的操作。 */
function hasAssistantAuditRows(message: BusinessChatMessage): boolean {
  return Boolean(getAssistantAuditTable(message)?.rows.length)
}

/** 判断“数据口径”折叠区是否由二级按钮展开。 */
function isAssistantBasisExpanded(message: BusinessChatMessage): boolean {
  return expandedBasisMessageIds.value.has(message.id)
}

/** 切换“查看数据依据”折叠区，只影响 UI 展开状态，不改变后端事实。 */
function toggleAssistantBasisDetails(message: BusinessChatMessage) {
  expandedBasisMessageIds.value = toggleMessageIdSet(expandedBasisMessageIds.value, message.id)
}

/** 按等级读取口径提醒；没有新协议 caveatItems 时兼容旧 caveats。 */
function getCaveatItemsByLevel(message: BusinessChatMessage, level: CaveatItem['level']): CaveatItem[] {
  const presentation = message.presentation as UnifiedResult | null | undefined
  if (!presentation) return []
  const safeCaveatItems = Array.isArray(presentation.caveatItems) ? presentation.caveatItems : []
  const items = safeCaveatItems.length ? safeCaveatItems : normalizeCaveatItems([], Array.isArray(presentation.caveats) ? presentation.caveats : [])
  return items.filter((item) => item.level === level)
}

/** 获取审计/导出可用的明细表；叙事回答默认不展示，但仍保留给用户手动展开和导出。 */
function getAssistantAuditTable(message: BusinessChatMessage): UnifiedTable | null {
  const presentation = message.presentation as UnifiedResult | null | undefined
  const presentationTable = normalizeTable(presentation?.table || null)
  if (presentationTable) return presentationTable
  const rawResponse = message.rawResponse as Record<string, any> | null | undefined
  return normalizeTable((rawResponse?.result_table || rawResponse?.data?.result_table || null) as UnifiedTable | null)
}

/** 判断明细表当前是否应展开；显式表格问题默认展开，普通叙事问题需用户点击“展开明细”。 */
function isAssistantTableExpanded(message: BusinessChatMessage): boolean {
  if (collapsedTableMessageIds.value.has(message.id)) return false
  const presentation = message.presentation as UnifiedResult | null | undefined
  const hasRows = Boolean(getAssistantAuditTable(message)?.rows.length)
  if (presentation && tableDisplayTypes.has(presentation.displayType) && hasRows) return true
  return expandedTableMessageIds.value.has(message.id)
}

/** 切换明细展开状态，支持显式表格回答收起、叙事回答手动展开。 */
function toggleAssistantTable(message: BusinessChatMessage) {
  if (!getAssistantAuditTable(message)?.rows.length) return
  if (isAssistantTableExpanded(message)) {
    const nextExpanded = new Set(expandedTableMessageIds.value)
    nextExpanded.delete(message.id)
    expandedTableMessageIds.value = nextExpanded
    collapsedTableMessageIds.value = addMessageIdToSet(collapsedTableMessageIds.value, message.id)
    return
  }
  expandedTableMessageIds.value = addMessageIdToSet(expandedTableMessageIds.value, message.id)
  collapsedTableMessageIds.value = removeMessageIdFromSet(collapsedTableMessageIds.value, message.id)
}

/** 获取当前助手消息的可见明细表；默认只在显式表格或用户手动展开时返回。 */
function getAssistantResultTable(message: BusinessChatMessage): UnifiedTable | null {
  const presentation = message.presentation as UnifiedResult | null | undefined
  if (!presentation || !isAssistantTableExpanded(message)) return null
  if (tableDisplayTypes.has(presentation.displayType)) return getAssistantAuditTable(message)
  return expandedTableMessageIds.value.has(message.id) ? getAssistantAuditTable(message) : null
}

/** 表格只在后端返回有效列和行且当前允许展开时展示，避免空表占据叙事型回答空间。 */
function shouldShowResultTable(message: BusinessChatMessage): boolean {
  const table = getAssistantResultTable(message)
  return Boolean(table?.columns.length && table.rows.length)
}

/** 切换 Set 中的消息 ID，返回新 Set 以触发 Vue 响应式更新。 */
function toggleMessageIdSet(source: Set<string>, messageId: string): Set<string> {
  const next = new Set(source)
  if (next.has(messageId)) next.delete(messageId)
  else next.add(messageId)
  return next
}

/** 向消息 ID Set 添加一项，返回新 Set 以触发 Vue 响应式更新。 */
function addMessageIdToSet(source: Set<string>, messageId: string): Set<string> {
  const next = new Set(source)
  next.add(messageId)
  return next
}

/** 从消息 ID Set 移除一项，返回新 Set 以触发 Vue 响应式更新。 */
function removeMessageIdFromSet(source: Set<string>, messageId: string): Set<string> {
  const next = new Set(source)
  next.delete(messageId)
  return next
}

/**
 * 将当前助手回复中的明细表导出为 Excel。
 *
 * 参数：
 *   message: 当前助手消息，导出其中 presentation.table 的已展示明细。
 *
 * 返回：
 *   无返回值；浏览器侧触发 xlsx 文件下载。
 */
function exportAssistantTableToExcel(message: BusinessChatMessage) {
  const table = getAssistantAuditTable(message)
  if (!table?.columns.length || !table.rows.length) {
    ElMessage.warning('当前回答没有可导出的明细数据')
    return
  }

  const exportRows = buildAssistantTableExportRows(table)
  const worksheet = XLSX.utils.json_to_sheet(exportRows, { header: table.columns })
  const exportMerges = buildAssistantTableExportMerges(table)
  if (exportMerges.length) worksheet['!merges'] = exportMerges
  applyAssistantTableExportAlignment(worksheet)
  // 按中文列名和单元格内容给出保守列宽，避免导出后业务用户第一眼只能看到截断内容。
  worksheet['!cols'] = table.columns.map((column) => ({
    wch: Math.max(12, Math.min(36, String(column).length + 8)),
  }))
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, '明细数据')
  XLSX.writeFile(workbook, buildAssistantTableExportFileName(message))
  ElMessage.success(`已导出 ${table.rows.length} 行明细数据`)
}

/**
 * 构造 Excel 导出行，保持列顺序与页面表格一致。
 *
 * 参数：
 *   table: 已归一化的页面展示表格。
 *
 * 返回：
 *   适合 XLSX.utils.json_to_sheet 的对象数组。
 */
function buildAssistantTableExportRows(table: UnifiedTable): Array<Record<string, string | number | boolean>> {
  return table.rows.map((row) => {
    const next: Record<string, string | number | boolean> = {}
    const mergedSubRow = getResultTableSubRowIndex(row) > 0
    table.columns.forEach((column) => {
      next[column] = mergedSubRow && !isFallRatioEstimateColumn(column) ? '' : normalizeAssistantTableExportCell(row[column])
    })
    return next
  })
}

/**
 * 给导出的 Excel 可见内容单元格统一设置垂直居中、左对齐。
 *
 * 参数：
 *   worksheet: SheetJS 工作表对象，函数会直接修改其中已有单元格样式。
 *
 * 返回：
 *   无返回值；保留既有样式并补充 alignment 配置。
 */
function applyAssistantTableExportAlignment(worksheet: XLSX.WorkSheet) {
  const rangeRef = worksheet['!ref']
  if (!rangeRef) return
  const range = XLSX.utils.decode_range(rangeRef)
  for (let rowIndex = range.s.r; rowIndex <= range.e.r; rowIndex += 1) {
    for (let columnIndex = range.s.c; columnIndex <= range.e.c; columnIndex += 1) {
      const cellRef = XLSX.utils.encode_cell({ r: rowIndex, c: columnIndex })
      const cell = worksheet[cellRef]
      if (!cell) continue
      cell.s = {
        ...(cell.s || {}),
        alignment: {
          ...(cell.s?.alignment || {}),
          vertical: 'center',
          horizontal: 'left',
        },
      }
    }
  }
}

/** 归一化 Excel 单元格值，避免对象/数组导出成 [object Object]。 */
function normalizeAssistantTableExportCell(value: unknown): string | number | boolean {
  if (value === null || value === undefined) return ''
  if (typeof value === 'number' || typeof value === 'boolean') return value
  if (value instanceof Date) return value.toISOString()
  if (Array.isArray(value)) return value.map((item) => normalizeAssistantTableExportCell(item)).join('、')
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch (_error) {
      return String(value)
    }
  }
  return String(value)
}

/** 根据回答标题和时间生成安全 Excel 文件名。 */
function buildAssistantTableExportFileName(message: BusinessChatMessage) {
  const presentation = message.presentation as UnifiedResult | null | undefined
  const fallbackTitle = domainLabelMap[message.domain] || '智能助手明细数据'
  const safeTitle = sanitizeAssistantTableExportFileName(presentation?.title || fallbackTitle) || '智能助手明细数据'
  return `${safeTitle.slice(0, 36)}_${formatAssistantTableExportTimestamp(new Date())}.xlsx`
}

/** 清理文件名中的系统保留字符。 */
function sanitizeAssistantTableExportFileName(value: string) {
  return String(value || '')
    .replace(/[\\/:*?"<>|\r\n\t]+/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
}

/** 构造导出时间戳，便于同一回答多次导出时区分文件。 */
function formatAssistantTableExportTimestamp(date: Date) {
  const pad = (value: number) => String(value).padStart(2, '0')
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
    '_',
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds()),
  ].join('')
}

/** 根据回答布局生成轻量提示词，不参与业务判断。 */
function resolveAssistantReplyKicker(message: BusinessChatMessage): string {
  const layout = resolveAssistantResultLayout(message)
  if (layout === 'ai-response-card--chart') return '图表视图'
  if (layout === 'ai-response-card--data') return '数据视图'
  return '文字说明'
}

/** 展示类型中文化，便于把后端 display_type 作为轻量徽标呈现。 */
function formatDisplayTypeLabel(displayType?: string) {
  const mapping: Record<string, string> = {
    narrative: '文字说明',
    summary_cards: '指标卡',
    table: '表格',
    line_chart: '折线图',
    bar_chart: '柱状图',
    pie_chart: '饼图',
    mixed: '组合展示',
    clarification: '澄清',
    unsupported: '拒答',
    empty_result: '空结果',
    error: '错误',
  }
  return displayType ? mapping[displayType] || displayType : ''
}

/** 图表类型中文化，只用于 UI 标识。 */
function formatChartTypeLabel(chartType: UnifiedChart['chart_type']) {
  if (chartType === 'line') return '折线'
  if (chartType === 'pie') return '饼图'
  return '柱状'
}

onMounted(() => {
  loadActiveSession()
  window.addEventListener(getBusinessChatSessionEventName(), loadActiveSession)
})

onBeforeUnmount(() => {
  window.removeEventListener(getBusinessChatSessionEventName(), loadActiveSession)
})
</script>

<style scoped>
/* ======== 页面布局 ======== */
.chat-page {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  font-size: 14px;
  background: #ffffff;
  overflow: hidden;
}

/* ======== 工具栏 ======== */
.chat-toolbar {
  display: flex;
  justify-content: center;
  padding: 12px 20px 0;
  flex-shrink: 0;
}

.domain-switch {
  --el-border-radius-base: var(--radius-pill);
}

:deep(.domain-switch .el-radio-button__inner) {
  border-color: #e5e7eb;
  background: #ffffff;
  color: #4b5563;
  font-size: 13px;
  box-shadow: none;
  transition: all 0.2s ease;
}

:deep(.domain-switch .el-radio-button__original-radio:checked + .el-radio-button__inner) {
  border-color: var(--brand-green-border);
  background: var(--brand-green-bg);
  color: var(--brand-green);
  box-shadow: none;
}

/* ======== 对话滚动区 ======== */
.conversation {
  flex: 1;
  min-height: 0;
  width: min(920px, calc(100vw - 360px));
  margin: 0 auto;
  /* 底部留出输入区缓冲，避免滚动到底时最后一段表格被输入框视觉遮挡。 */
  padding: 34px 0 120px;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-gutter: stable;
}

.conversation::-webkit-scrollbar {
  width: 6px;
}

.conversation::-webkit-scrollbar-track {
  background: transparent;
}

.conversation::-webkit-scrollbar-thumb {
  border-radius: var(--radius-pill);
  background: transparent;
}

.conversation:hover::-webkit-scrollbar-thumb {
  background: #d1d5db;
}

.conversation--empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-bottom: 180px;
}

/* ======== 消息列表 TransitionGroup 容器 ======== */
.message-list {
  display: contents;
}

/* 消息入场 / 离场动画 */
.message-enter-active {
  animation: fadeInUp 0.35s cubic-bezier(0.22, 0.61, 0.36, 1) both;
}

.message-leave-active {
  animation: fadeIn 0.2s ease-in reverse both;
}

/* ======== 欢迎空状态 ======== */
.empty-panel {
  position: relative;
  width: min(760px, 100%);
  text-align: center;
  animation: fadeInUp 0.5s ease-out;
}

.empty-glow {
  position: absolute;
  top: -60px;
  left: 50%;
  transform: translateX(-50%);
  width: 320px;
  height: 120px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--brand-green-soft) 0%, transparent 70%);
  pointer-events: none;
}

.empty-panel h1 {
  position: relative;
  margin: 0 0 12px;
  color: #111827;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 0;
}

.empty-subtitle {
  position: relative;
  margin: 0 auto 28px;
  max-width: 540px;
  color: #6b7280;
  font-size: 14px;
  line-height: 1.7;
}

/* 快速问题卡片网格 */
.quick-chips {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  max-width: 600px;
  margin: 0 auto;
}

.quick-chip {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  border: 1px solid #e5e7eb;
  border-radius: var(--radius-md);
  background: #ffffff;
  color: #4b5563;
  padding: 12px 14px;
  font-size: 13px;
  line-height: 1.5;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}

.quick-chip:hover {
  border-color: var(--brand-green-border);
  background: var(--brand-green-bg);
  box-shadow: 0 2px 8px rgba(47, 110, 66, 0.08);
  transform: translateY(-1px);
}

.chip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  width: 36px;
  height: 24px;
  border-radius: var(--radius-sm);
  background: var(--brand-green-bg);
  color: var(--brand-green);
  font-size: 11px;
  font-weight: 700;
}

.chip-text {
  min-width: 0;
}

/* ======== 单条消息 ======== */
.message {
  display: grid;
  gap: 6px;
  margin-bottom: 24px;
}

.message--user {
  justify-items: end;
}

/* 消息元信息行 */
.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #9ca3af;
  font-size: 12px;
}

.message-sender {
  font-weight: 600;
  color: #6b7280;
}

.message-domain {
  font-style: normal;
  color: var(--brand-green);
  background: var(--brand-green-bg);
  padding: 1px 7px;
  border-radius: var(--radius-pill);
  font-size: 11px;
  font-weight: 500;
}

.message-time {
  color: #9ca3af;
  font-size: 11px;
}

/* 状态标签行 */
.message-status-row {
  padding: 0 0 2px;
}

/* ======== 气泡 ======== */
.bubble {
  max-width: min(820px, 92%);
  border-radius: var(--radius-lg);
  background: transparent;
  padding: 0;
  color: #1f2937;
  line-height: 1.7;
}

.message--user .bubble {
  max-width: min(660px, 88%);
  background: #f3f4f6;
  padding: 12px 16px;
  border-radius: var(--radius-lg);
}

.bubble p {
  margin: 0;
}

.message-content {
  max-width: 760px;
  color: #111827;
  word-break: break-word;
}

.streaming-answer {
  color: #111827;
}

.streaming-answer .assistant-markdown :deep(p:last-child)::after,
.streaming-answer .assistant-markdown :deep(li:last-child)::after {
  content: '';
  display: inline-block;
  width: 7px;
  height: 1em;
  margin-left: 2px;
  vertical-align: -2px;
  border-right: 2px solid var(--brand-logo-blue, #3071b9);
  animation: cursorBlink 0.9s steps(1) infinite;
}

.assistant-markdown {
  color: inherit;
  font-size: inherit;
  line-height: inherit;
  word-break: break-word;
}

.assistant-markdown :deep(p) {
  margin: 0 0 12px;
}

.assistant-markdown :deep(p:last-child),
.assistant-markdown :deep(ul:last-child),
.assistant-markdown :deep(ol:last-child) {
  margin-bottom: 0;
}

.assistant-markdown :deep(strong) {
  color: #111827;
  font-weight: 700;
}

.assistant-markdown :deep(ul),
.assistant-markdown :deep(ol) {
  margin: 8px 0 14px;
  padding-left: 20px;
}

.assistant-markdown :deep(li) {
  margin: 4px 0;
  padding-left: 2px;
  line-height: 1.85;
}

.assistant-markdown :deep(h3),
.assistant-markdown :deep(h4) {
  margin: 12px 0 8px;
  color: #111827;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.6;
}

.assistant-markdown :deep(code) {
  border-radius: 6px;
  background: #eef6f2;
  color: #176b4d;
  padding: 1px 5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.92em;
}

/* ======== 加载动画 ======== */
.loading-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}

.loading-text {
  color: var(--brand-green-light);
  font-size: 13px;
  font-weight: 500;
  animation: fadeIn 0.6s ease-out;
}

/* ======== 错误提示 ======== */
.error {
  padding: 12px 16px;
  border-radius: var(--radius-md);
  background: var(--danger-bg);
  color: var(--danger);
  font-size: 13px;
  border: 1px solid var(--danger-border);
  line-height: 1.6;
}

/* ======== 对话结果区域 ======== */
.result {
  display: grid;
  gap: 14px;
  animation: fadeIn 0.3s ease-out;
}

.ai-response-card--narrative {
  max-width: 780px;
}

.ai-response-card--data,
.ai-response-card--chart {
  max-width: 100%;
}

.result-hero {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border: 1px solid #e7edf2;
  border-radius: var(--radius-md);
  background: linear-gradient(180deg, #ffffff 0%, #fbfcfd 100%);
}

.result--success .result-hero {
  border-color: #d9eadf;
  background: linear-gradient(180deg, #ffffff 0%, #f4fbf6 100%);
}

.result--clarify .result-hero,
.result--empty .result-hero {
  border-color: #f0dfbb;
  background: linear-gradient(180deg, #ffffff 0%, #fffaf0 100%);
}

.result--unsupported .result-hero {
  border-color: #dfe5eb;
  background: linear-gradient(180deg, #ffffff 0%, #f7f9fb 100%);
}

.result--error .result-hero {
  border-color: #f2c8c8;
  background: linear-gradient(180deg, #ffffff 0%, #fff5f5 100%);
}

.result-hero__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.display-badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  border-radius: var(--radius-pill);
  background: #f3f4f6;
  color: #4b5563;
  padding: 2px 9px;
  font-size: 12px;
  font-weight: 650;
}

.status-badge--empty {
  background: #fff7ed;
  color: #9a5b10;
  border: 1px solid #fed7aa;
}

.result-title {
  color: #111827;
  font-weight: 600;
  font-size: 15px;
  line-height: 1.55;
}

.result-answer {
  color: #374151;
  font-size: 14px;
  line-height: 1.8;
  word-break: break-word;
}

.answer-secondary-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 2px;
}

.answer-secondary-actions :deep(.el-button) {
  margin-left: 0;
  border-color: #d7e5ee;
  background: #ffffff;
  color: #475569;
  font-size: 12px;
}

.answer-secondary-actions :deep(.el-button:not(.is-disabled):hover) {
  border-color: var(--brand-logo-blue, #3071b9);
  color: var(--brand-logo-blue, #3071b9);
  background: #f1f7ff;
}

.assistant-prose {
  white-space: normal;
}

.result-summary-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.result-summary-strip__item {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  border-radius: var(--radius-pill);
  background: #ffffff;
  border: 1px solid #e5e7eb;
  color: #6b7280;
  padding: 5px 10px;
  font-size: 12px;
}

.result-summary-strip__item strong {
  color: #111827;
  font-weight: 800;
}

.highlight-list,
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.highlight-list span,
.suggestions span {
  border-radius: var(--radius-pill);
  background: var(--brand-green-bg);
  color: var(--brand-green);
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 500;
}

.highlight-list .section-label,
.suggestions .section-label {
  flex: 0 0 100%;
}

/* ======== 指标卡片（优化版） ======== */
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}

.metric-card {
  display: flex;
  gap: 10px;
  border: 1px solid #eef0f3;
  border-radius: var(--radius-md);
  background: #fbfcfd;
  padding: 0;
  overflow: hidden;
  transition: all 0.2s ease;
}

.metric-card:hover {
  border-color: var(--brand-green-border);
  box-shadow: 0 4px 12px rgba(47, 110, 66, 0.06);
  transform: translateY(-2px);
}

.metric-accent {
  width: 4px;
  flex-shrink: 0;
  background: var(--brand-green);
  border-radius: var(--radius-md) 0 0 var(--radius-md);
}

.metric-body {
  padding: 12px 14px 12px 6px;
  min-width: 0;
}

.metric-label,
.metric-desc,
.section-label {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.4;
}

.metric-value {
  margin-top: 6px;
  color: #111827;
  font-size: 22px;
  font-weight: 800;
  line-height: 1.2;
}

.metric-value small {
  margin-left: 4px;
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
}

.metric-desc {
  margin-top: 4px;
}

/* ======== 图表展示 ======== */
.presentation-chart {
  border: 1px solid #eef0f3;
  border-radius: var(--radius-md);
  background: #fbfcfd;
  padding: 12px 14px 10px;
}

.presentation-chart__title {
  margin-bottom: 8px;
  color: #1f2937;
  font-size: 13px;
  font-weight: 600;
}

.presentation-chart__meta {
  margin: -2px 0 8px;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.5;
}

.presentation-chart__svg {
  display: block;
  width: 100%;
  height: 220px;
}

.presentation-chart__pie-layout {
  display: grid;
  grid-template-columns: minmax(220px, 280px) minmax(180px, 1fr);
  gap: 18px;
  align-items: center;
}

.presentation-chart__pie {
  display: block;
  width: 100%;
  height: 220px;
}

.presentation-chart__pie-slice {
  stroke: #ffffff;
  stroke-width: 2;
}

.presentation-chart__pie-hole {
  fill: #fbfcfd;
}

.presentation-chart__pie-center {
  fill: #1f2937;
  font-size: 16px;
  font-weight: 700;
}

.presentation-chart__pie-center--sub {
  fill: #6b7280;
  font-size: 12px;
  font-weight: 500;
}

.presentation-chart__legend {
  display: grid;
  gap: 8px;
}

.presentation-chart__legend-item {
  display: grid;
  grid-template-columns: 10px minmax(72px, 1fr) auto;
  gap: 8px;
  align-items: center;
  color: #374151;
  font-size: 12px;
}

.presentation-chart__legend-color {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.presentation-chart__legend-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.presentation-chart__legend-value {
  color: #111827;
  font-weight: 600;
}

.presentation-chart__line {
  stroke: var(--brand-green);
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.presentation-chart__point,
.presentation-chart__bar {
  fill: var(--brand-green);
}

.presentation-chart__label {
  fill: #6b7280;
  font-size: 12px;
}

@keyframes cursorBlink {
  0%,
  45% {
    opacity: 1;
  }
  46%,
  100% {
    opacity: 0;
  }
}

@media (max-width: 720px) {
  .presentation-chart__pie-layout {
    grid-template-columns: 1fr;
  }
}

/* ======== 表格（优化版） ======== */
.result-table {
  font-size: 13px;
  border-radius: var(--radius-md);
  overflow: hidden;
}

.result-table-card {
  border: 1px solid #eef0f3;
  border-radius: var(--radius-md);
  background: #ffffff;
  overflow: hidden;
}

.result-table-scroll {
  max-height: 360px;
  overflow: auto;
}

.result-table--irregular {
  width: 100%;
  min-width: max-content;
  border-collapse: collapse;
  table-layout: auto;
  background: #ffffff;
}

.result-table--irregular th,
.result-table--irregular td {
  border: 1px solid #e5e7eb;
  padding: 8px 10px;
  color: #111827;
  font-size: 13px;
  line-height: 1.45;
  text-align: left;
  vertical-align: middle;
  background: #ffffff;
}

.result-table--irregular th {
  position: sticky;
  top: 0;
  z-index: 1;
  background: #f8fafc;
  font-weight: 700;
  white-space: nowrap;
}

.result-table--irregular td {
  min-height: 42px;
}

.result-table-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-bottom: 1px solid #eef0f3;
  color: #1f2937;
  font-size: 13px;
  font-weight: 700;
}

.result-table-card__title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.result-table-card__head em {
  flex: none;
  font-style: normal;
  color: #6b7280;
  font-size: 12px;
  font-weight: 500;
}

.result-table-card__export {
  flex: none;
  border-color: var(--brand-green-border);
}

.result-table-card__export:not(.is-disabled):hover {
  border-color: var(--brand-green);
  background: var(--brand-green-bg);
  color: var(--brand-green);
}

:deep(.result-table .el-table__header-wrapper th) {
  background: #f8fafb;
  color: #374151;
  font-weight: 600;
  font-size: 12px;
  border-bottom: 2px solid var(--brand-green-border);
}

:deep(.result-table .el-table__body-wrapper tr:nth-child(even)) {
  background: #fafbfc;
}

:deep(.result-table .el-table__body-wrapper tr:hover > td) {
  background: #ecfdf3;
}

:deep(.result-table .el-table__body-wrapper td) {
  transition: background 0.15s ease;
}

.result-table__cell {
  display: inline-block;
  max-width: 100%;
  line-height: 1.55;
  word-break: break-word;
}

.result-table__cell--multi-line {
  white-space: pre-line;
}

:deep(.result-table-column--fall-ratio .cell) {
  overflow-x: auto;
  white-space: nowrap;
}

.result-table__td--fall-ratio {
  overflow-x: auto;
  white-space: nowrap;
}

.result-table--irregular .result-table__cell {
  max-width: none;
}

.result-table__cell--fall-ratio {
  display: block;
  width: max-content;
  max-width: none;
  white-space: nowrap;
  word-break: keep-all;
  overflow-wrap: normal;
}

/* ======== 追问区域 ======== */
.follow-up {
  display: grid;
  gap: 8px;
}

.section-label {
  font-weight: 600;
  color: #6b7280;
}

.follow-up-chip {
  width: fit-content;
  border: 1px solid #e0ece5;
  border-radius: var(--radius-pill);
  background: #ffffff;
  color: var(--brand-green);
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.follow-up-chip:hover {
  background: var(--brand-green-bg);
  border-color: var(--brand-green);
  transform: translateY(-1px);
}

.result-caveats {
  display: grid;
  gap: 8px;
  border: 1px solid #f2e4c7;
  border-radius: var(--radius-md);
  background: #fffaf0;
  padding: 12px 14px;
}

.result-caveats--info {
  border-color: #e2e8f0;
  background: #f8fafc;
  color: #475569;
}

.result-caveats--info summary {
  cursor: pointer;
  color: #475569;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.5;
}

.result-caveats--info .result-caveats__item {
  margin-top: 6px;
  color: #64748b;
}

.result-caveats--warning {
  border-color: #fde68a;
  background: #fffbeb;
}

.result-caveats--danger {
  border-color: #fecaca;
  background: #fff1f2;
}

.result-caveats--danger .section-label,
.result-caveats--danger .result-caveats__item {
  color: #b91c1c;
}

.result-caveats__item {
  color: #785a20;
  font-size: 12px;
  line-height: 1.65;
  word-break: break-word;
}

/* ======== 输入区 ======== */
.composer {
  width: min(920px, calc(100vw - 360px));
  margin: 0 auto 18px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 10px 12px 10px 18px;
  border: 1px solid #dfe3e8;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 2px 16px rgba(31, 41, 55, 0.06);
  flex-shrink: 0;
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

.composer:focus-within {
  border-color: var(--brand-green);
  box-shadow: 0 2px 20px rgba(47, 110, 66, 0.1), 0 0 0 3px var(--brand-green-soft);
}

:deep(.composer .el-textarea__inner) {
  border: none;
  box-shadow: none;
  padding: 8px 0;
  font-size: 14px;
  line-height: 1.6;
  background: transparent;
  resize: none;
}

:deep(.composer .el-textarea__inner::placeholder) {
  color: #b0b8c1;
}

:deep(.composer .el-button) {
  border-radius: var(--radius-pill);
  padding: 0 18px;
  font-weight: 600;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

:deep(.composer .el-button:not(.is-loading):hover) {
  transform: scale(1.04);
  box-shadow: 0 2px 8px rgba(47, 110, 66, 0.2);
}

/* ======== 响应式 ======== */
@media (max-width: 720px) {
  .quick-chips {
    grid-template-columns: 1fr;
  }

  .conversation,
  .composer {
    width: calc(100vw - 32px);
  }
}

@media (max-width: 1100px) {
  .quick-chips {
    grid-template-columns: 1fr;
  }

  .conversation,
  .composer {
    width: calc(100vw - 32px);
  }

  .composer {
    grid-template-columns: 1fr;
  }

  .bubble {
    max-width: 100%;
  }

  .metric-value {
    font-size: 20px;
    overflow-wrap: anywhere;
  }

  .result-hero,
  .presentation-chart,
  .result-caveats {
    padding: 12px;
  }
}
</style>
