<template>
  <section class="chat-page" data-testid="business-chat-page">
    <div class="chat-toolbar" data-testid="business-chat-toolbar">
      <el-radio-group v-model="domainMode" size="small" class="domain-switch" data-testid="domain-switch">
        <el-radio-button value="auto" data-testid="domain-auto">自动识别</el-radio-button>
        <el-radio-button value="logistics" data-testid="domain-logistics">物流数据</el-radio-button>
        <el-radio-button value="plan_bom" data-testid="domain-plan-bom">计划 BOM</el-radio-button>
      </el-radio-group>
    </div>

    <div ref="conversationRef" :class="['conversation', { 'conversation--empty': messages.length === 0 }]" data-testid="conversation">
      <!-- 欢迎状态 -->
      <div v-if="messages.length === 0" class="empty-panel" data-testid="empty-panel">
        <div class="empty-glow" />
        <h1>协鑫集成 经营计划智能助手</h1>
        <p class="empty-subtitle">支持物流运量、费用、发运车次等结构化数据查询，以及计划 BOM 材料明细与差异对比。请直接输入业务问题。</p>
        <div class="quick-chips">
          <button v-for="item in examples" :key="item.text" type="button" class="quick-chip" @click="useExample(item)">
            <span class="chip-icon">{{ item.domain === '物流' ? '物流' : 'BOM' }}</span>
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
          <div v-if="message.role === 'assistant' && !message.loading && resolveStatusBadge(message.status)" class="message-status-row">
            <span :class="['status-badge', `status-badge--${resolveStatusBadge(message.status)?.type}`]">
              {{ resolveStatusBadge(message.status)?.label }}
            </span>
          </div>

          <div class="bubble">
            <p v-if="message.content" data-testid="message-content">{{ message.content }}</p>

            <!-- 加载动画：三点跳动 -->
            <div v-if="message.loading" class="loading-row" data-testid="message-loading">
              <span class="typing-indicator">
                <span /><span /><span />
              </span>
              <span class="loading-text">正在查询</span>
            </div>

            <div v-if="message.error" class="error" data-testid="message-error">{{ message.error }}</div>

            <div v-if="message.presentation" class="result" data-testid="assistant-result">
              <div v-if="message.presentation.title" class="result-title" data-testid="result-title">{{ message.presentation.title }}</div>
              <p v-if="message.presentation.answer" class="result-answer" data-testid="result-answer">{{ message.presentation.answer }}</p>

              <div v-if="message.presentation.highlights.length" class="highlight-list" data-testid="result-highlights">
                <span v-for="text in message.presentation.highlights" :key="text">{{ text }}</span>
              </div>

              <div v-if="message.presentation.chart" class="presentation-chart" data-testid="result-chart">
                <div class="presentation-chart__title">
                  {{ buildChartTitle(message.presentation.chart) }}
                </div>
                <svg
                  v-if="message.presentation.chart.chart_type === 'line'"
                  class="presentation-chart__svg"
                  viewBox="0 0 640 220"
                  role="img"
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
                <svg
                  v-else
                  class="presentation-chart__svg"
                  viewBox="0 0 640 220"
                  role="img"
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

              <div v-if="message.presentation.cards.length" class="metric-grid" data-testid="result-cards">
                <div v-for="card in message.presentation.cards" :key="card.label" class="metric-card">
                  <div class="metric-accent" />
                  <div class="metric-body">
                    <div class="metric-label">{{ card.label }}</div>
                    <div class="metric-value">{{ formatDisplayValue(card.value) }}<small v-if="card.unit">{{ card.unit }}</small></div>
                    <div v-if="card.description" class="metric-desc">{{ card.description }}</div>
                  </div>
                </div>
              </div>

              <el-table
                v-if="message.presentation.table"
                :data="message.presentation.table.rows"
                size="small"
                border
                class="result-table"
                data-testid="result-table"
              >
                <el-table-column
                  v-for="column in message.presentation.table.columns"
                  :key="column"
                  :prop="column"
                  :label="column"
                  min-width="130"
                  show-overflow-tooltip
                />
              </el-table>

              <div v-if="message.presentation.followUps.length" class="follow-up" data-testid="result-follow-ups">
                <div class="section-label">需要补充的信息</div>
                <button
                  v-for="followUp in message.presentation.followUps"
                  :key="followUp"
                  type="button"
                  class="follow-up-chip"
                  @click="appendFollowUp(followUp)"
                >
                  {{ followUp }}
                </button>
              </div>

              <div v-if="message.presentation.suggestions.length" class="suggestions" data-testid="result-suggestions">
                <div class="section-label">可改问方向</div>
                <span v-for="item in message.presentation.suggestions" :key="item">{{ item }}</span>
              </div>
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
        @keydown.enter.exact.prevent="submitQuestion()"
      />
      <el-button type="primary" native-type="submit" :loading="currentSessionLoading" data-testid="send-button">发送</el-button>
    </form>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { fetchLogisticsDataQaQuery, type LogisticsDataQaResult } from '@/api/logistics'
import { askPlanBomQuestion, type PlanBomQaResponse } from '@/api/planBom'
import {
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

interface UnifiedResult {
  title: string
  answer: string
  highlights: string[]
  cards: Array<{ label: string; value: any; unit?: string | null; description?: string | null }>
  chart: UnifiedChart | null
  table: UnifiedTable | null
  followUps: string[]
  suggestions: string[]
}

interface UnifiedChart {
  chart_type: 'line' | 'bar'
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

interface ChartValue {
  label: unknown
  value: number
}

const question = ref('')
const activeSession = ref<BusinessChatSession | null>(null)
const conversationRef = ref<HTMLElement | null>(null)

const examples = [
  { domain: '物流', mode: 'logistics' as BusinessChatDomain, text: '2024年江苏省各城市总费用排名前五？' },
  { domain: '物流', mode: 'logistics' as BusinessChatDomain, text: '查询下个月物流费用预测需要哪些条件？' },
  { domain: 'BOM', mode: 'plan_bom' as BusinessChatDomain, text: '订单00104的玻璃、间隙贴膜、焊带、汇流条、接线盒规格描述？' },
  { domain: 'BOM', mode: 'plan_bom' as BusinessChatDomain, text: '哪些订单的接线盒规格不一样，按订单列出来。' },
]

const domainLabelMap: Record<BusinessChatDomain, string> = {
  auto: '自动识别',
  logistics: '物流数据',
  plan_bom: '计划 BOM',
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
  const bomKeywords = ['bom', '订单', '物料', '玻璃', '焊带', '汇流条', '接线盒', '线盒', '间隙贴膜', '版本', '电池片']
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
  const bomScore = bomKeywords.filter((item) => normalized.includes(item.toLowerCase())).length
  const logisticsScore = logisticsKeywords.filter((item) => normalized.includes(item.toLowerCase())).length
  // “规格”在物流产品规格和 BOM 规格中都会出现，不能单独作为 BOM 路由依据。
  if (logisticsScore > 0 && logisticsScore >= bomScore) return 'logistics'
  if (bomScore > 0) return 'plan_bom'
  return null
}

/** 推荐问题只填入输入框，不写死业务结果。 */
function useExample(item: (typeof examples)[number]) {
  domainMode.value = item.mode
  question.value = item.text
}

/** 点击追问建议后填入输入框，由用户确认发送。 */
function appendFollowUp(text: string) {
  question.value = text
}

/** 统一提交入口：物流和 BOM 都继续调用真实后端接口。 */
async function submitQuestion(input?: string) {
  const text = (input || question.value).trim()
  if (!text || !activeSession.value || currentSessionLoading.value) return

  const sessionId = activeSession.value.id
  const selectedDomain = activeSession.value.domain
  const resolvedDomain = selectedDomain === 'auto' ? inferDomain(text) : selectedDomain
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
      content: '请先选择“物流数据”或“计划 BOM”，也可以在问题中补充业务域关键词。',
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
    if (resolvedDomain === 'logistics') {
      const response = await fetchLogisticsDataQaQuery({ question: text })
      const data = (response as any).data || response
      completeAssistantMessage(sessionId, assistantId, {
        content: '',
        domain: resolvedDomain,
        status: data?.status?.code || 'OK',
        presentation: adaptLogisticsResult(data),
        rawResponse: data,
      })
    } else {
      const response = await askPlanBomQuestion({ question: text })
      const data = (response as any).data || response
      completeAssistantMessage(sessionId, assistantId, {
        content: '',
        domain: resolvedDomain,
        status: data?.status?.code || data?.classification || 'OK',
        presentation: adaptPlanBomResult(data),
        rawResponse: data,
      })
    }
  } catch (error) {
    failAssistantMessage(
      sessionId,
      assistantId,
      error instanceof Error ? error.message : '接口请求失败，请稍后重试。',
    )
  }
}

/** 构造标准消息。 */
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
    id: crypto.randomUUID(),
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
    target.content = input.content
    target.domain = input.domain
    target.status = input.status
    target.presentation = input.presentation as Record<string, any>
    target.rawResponse = input.rawResponse
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

/** 将物流结果适配为统一展示结构，前端不反推或修改业务事实。 */
function adaptLogisticsResult(data: LogisticsDataQaResult): UnifiedResult {
  const presentation = data.presentation
  const unsupported = presentation?.unsupported_explanation
  const answer = presentation?.answer || data.answer_summary || data.status?.message || ''
  return normalizeResult({
    title: presentation?.title || '物流数据问答结果',
    answer,
    highlights: filterBusinessTexts(dedupeBusinessTexts(presentation?.highlights || [], [answer])),
    cards: localizeCards(presentation?.cards || []),
    chart: normalizeChart(presentation?.chart_spec || null),
    table: presentation?.table_spec || data.result_table || null,
    followUps: localizeFollowUps(presentation?.follow_up?.questions || data.clarification_questions || []),
    suggestions: filterBusinessTexts(unsupported?.suggestions || data.query_plan?.unsupported_suggestions || []),
  })
}

/** 将计划 BOM 结果适配为统一展示结构，前端只展示后端确定性返回。 */
function adaptPlanBomResult(data: PlanBomQaResponse): UnifiedResult {
  const presentation = data.presentation
  const followUp = presentation?.follow_up as { questions?: string[]; examples?: string[] } | null | undefined
  const unsupported = presentation?.unsupported_explanation as { reason?: string; suggestions?: string[] } | null | undefined
  const answer = presentation?.answer || data.answer_summary || data.status?.message || ''
  return normalizeResult({
    title: presentation?.title || `计划 BOM 问答结果（${data.classification || '未知'}）`,
    answer,
    highlights: filterBusinessTexts(dedupeBusinessTexts(presentation?.highlights || [], [answer])),
    cards: [],
    chart: null,
    table: presentation?.table_spec || data.result_table || null,
    followUps: localizeFollowUps(followUp?.questions || []),
    suggestions: filterBusinessTexts(unsupported?.suggestions || []),
  })
}

/** 补齐展示默认值，避免字段缺失导致页面异常。 */
function normalizeResult(value: Partial<UnifiedResult>): UnifiedResult {
  return {
    title: value.title || '',
    answer: value.answer || '',
    highlights: value.highlights || [],
    cards: value.cards || [],
    chart: value.chart || null,
    table: normalizeTable(value.table || null),
    followUps: value.followUps || [],
    suggestions: value.suggestions || [],
  }
}

/** 归一化后端图表配置，缺少必要字段时不渲染图表。 */
function normalizeChart(chart: NonNullable<LogisticsDataQaResult['presentation']>['chart_spec'] | null | undefined): UnifiedChart | null {
  if (!chart || typeof chart !== 'object') return null
  if (chart.chart_type !== 'line' && chart.chart_type !== 'bar') return null
  const values = extractChartValues(chart as UnifiedChart)
  if (!values.length) return null
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
  const sourceColumns = table.columns?.length ? table.columns : Object.keys(table.rows[0] || {})
  const columns = sourceColumns.map((column, index) => localizeColumnName(column, index))
  const rows = table.rows.map((row) => {
    const next: Record<string, any> = {}
    sourceColumns.forEach((column, index) => {
      next[columns[index]] = row[column]
    })
    return next
  })
  return { columns, rows }
}

/** 构造图表标题。 */
function buildChartTitle(chart: UnifiedChart) {
  if (chart.title) return chart.title
  return chart.chart_type === 'line' ? '趋势图' : '对比图'
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
        value: Number(item.y),
      }))
      .filter((item: ChartValue) => Number.isFinite(item.value))
  }
  const xAxis = chart.x_axis || ''
  const yAxis = chart.y_axis?.[0] || ''
  return (chart.data || [])
    .map((row: Record<string, unknown>) => ({
      label: row[xAxis],
      value: Number(row[yAxis]),
    }))
    .filter((item: ChartValue) => Number.isFinite(item.value))
}

const columnNameMap: Record<string, string> = {
  city: '城市',
  province: '省份',
  year: '年份',
  month: '月份',
  biz_month: '月份',
  customer: '客户',
  customer_name: '客户',
  total_fee: '总运费',
  task_count: '任务数',
  parse_fail_count: '未纳入运费统计任务数',
  price_missing_count: '缺少价格任务数',
  record_count: '记录数',
  total_record_count: '全部记录数',
  record_share_pct: '占比',
  shipment_watt: '发运量',
  shipment_mw: '发运量',
  shipment_share_pct: '占比',
  transport_mode: '运输方式',
  procurement_type: '采购方式',
  task_share_pct: '任务占比',
  delivery_city: '送达城市',
  driver_name: '司机',
  assign_task_count: '派车任务数',
  logistics_company: '物流公司',
  logistics_company_name: '物流公司',
  carrier_name: '承运商',
  company_name: '承运商',
  avg_fee_per_trip: '平均单价/车',
  shipment_trip_count: '车次',
  unit_price_per_vehicle: '单价/车',
  fee_per_watt: '元/瓦',
  avg_fee_per_watt: '平均元/瓦',
  unit_fee_per_watt: '平均元/瓦',
  extra_fee: '额外费用',
  extra_fee_amount: '额外费用',
  extra_fee_ratio: '额外费用占比',
  extra_fee_share_pct: '额外费用占比',
  total_fee_amount: '总费用',
  origin_place_count: '始发地数量',
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
}

function localizeColumnName(column: string, index = 0) {
  if (columnNameMap[column]) return columnNameMap[column]
  if (/^[\u4e00-\u9fa5A-Za-z0-9/（）() -]+$/.test(column) && !/[a-zA-Z_]/.test(column)) return column
  return `列${index + 1}`
}

function localizeCards(cards: UnifiedResult['cards']) {
  return cards.map((card) => ({
    ...card,
    label: localizeColumnName(card.label),
  }))
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
  if (lower === 'clarification' || lower === 'needs_clarification' || lower === 'b' || lower === 'missing_slots') {
    return { type: 'warning', label: '需补充信息' }
  }
  // C类 / 暂不支持
  if (
    lower === 'unsupported' ||
    lower === 'not_supported' ||
    lower === 'c' ||
    lower === 'needs_domain'
  ) {
    return { type: 'info', label: '暂不支持' }
  }
  // 错误
  if (lower === 'error' || lower === 'fail') {
    return { type: 'danger', label: '请求出错' }
  }
  return null
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
  padding: 34px 0 24px;
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

.result-title {
  color: #111827;
  font-weight: 600;
  font-size: 15px;
}

.result-answer {
  color: #374151;
  font-size: 14px;
  line-height: 1.8;
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

.presentation-chart__svg {
  display: block;
  width: 100%;
  height: 220px;
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

/* ======== 表格（优化版） ======== */
.result-table {
  font-size: 13px;
  border-radius: var(--radius-md);
  overflow: hidden;
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
}
</style>
