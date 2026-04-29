<template>
  <div class="data-qa-chat-page">
    <div class="data-qa-shell">
      <section class="chat-main">
        <header class="chat-toolbar">
          <div class="chat-toolbar__main">
            <el-button
              circle
              text
              class="chat-toolbar__menu"
              title="收起或展开主菜单"
              @click="toggleMainSidebar"
            >
              <el-icon><Fold /></el-icon>
            </el-button>

            <div class="chat-toolbar__title">物流数据问答</div>
          </div>

          <el-button text class="chat-toolbar__history" @click="goHistoryPage">历史记录</el-button>
        </header>

        <div ref="conversationRef" class="chat-thread">
        <div class="chat-thread__inner">
          <section v-if="showWelcome" class="chat-welcome">
            <h2 class="chat-welcome__title">想查什么物流数据？</h2>
          </section>

          <div v-for="turn in sessionTurns" :key="turn.id" class="chat-turn">
            <div class="chat-message chat-message--user">
              <div class="chat-bubble chat-bubble--user">
                <div class="chat-bubble__meta">{{ formatLogisticsDataQaDateTime(turn.askedAt) }}</div>
                <div class="chat-bubble__content">{{ turn.question }}</div>
              </div>
            </div>

            <div class="chat-message chat-message--assistant">
              <div class="chat-bubble chat-bubble--assistant" :class="resolveTurnToneClass(turn)">
                <div class="chat-bubble__header">
                  <div class="chat-bubble__role">助手</div>
                  <div class="chat-bubble__meta">{{ formatLogisticsDataQaDateTime(turn.answeredAt) }}</div>
                </div>

                <div class="chat-bubble__title-row">
                  <div class="chat-bubble__title">{{ buildTurnPresentationTitle(turn) }}</div>
                  <div v-if="isTurnSuccess(turn) && getTurnRows(turn).length" class="chat-bubble__mini-stat">
                    {{ getTurnRows(turn).length }} 行结果
                  </div>
                </div>
                <div v-if="buildTurnPresentationAnswer(turn)" class="chat-bubble__desc">
                  {{ buildTurnPresentationAnswer(turn) }}
                </div>

                <div v-if="getPresentationHighlights(turn).length" class="presentation-highlights">
                  <div
                    v-for="(item, index) in getPresentationHighlights(turn)"
                    :key="`${turn.id}-highlight-${index}`"
                    class="presentation-highlights__item"
                  >
                    {{ item }}
                  </div>
                </div>

                <div v-if="getPresentationCards(turn).length" class="presentation-cards">
                  <div
                    v-for="(card, index) in getPresentationCards(turn)"
                    :key="`${turn.id}-card-${index}`"
                    class="presentation-card"
                  >
                    <div class="presentation-card__label">{{ card.label }}</div>
                    <div class="presentation-card__value">
                      {{ formatPresentationValue(card.value) }}<span v-if="card.unit">{{ card.unit }}</span>
                    </div>
                    <div v-if="card.description" class="presentation-card__desc">{{ card.description }}</div>
                  </div>
                </div>

                <div v-if="getPresentationChart(turn)" class="presentation-chart">
                  <div class="presentation-chart__title">
                    {{ getPresentationChart(turn)?.title || (getPresentationChart(turn)?.chart_type === 'line' ? '趋势图' : '对比图') }}
                  </div>
                  <svg
                    v-if="getPresentationChart(turn)?.chart_type === 'line'"
                    class="presentation-chart__svg"
                    viewBox="0 0 640 220"
                    role="img"
                  >
                    <polyline
                      class="presentation-chart__line"
                      :points="buildTurnLineChartPoints(turn)"
                      fill="none"
                    />
                    <circle
                      v-for="point in buildTurnLineChartCircles(turn)"
                      :key="`${turn.id}-line-${point.x}-${point.y}`"
                      class="presentation-chart__point"
                      :cx="point.x"
                      :cy="point.y"
                      r="4"
                    />
                    <text
                      v-for="label in buildTurnChartLabels(turn)"
                      :key="`${turn.id}-label-${label.x}-${label.text}`"
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
                      v-for="bar in buildTurnBarChartRects(turn)"
                      :key="`${turn.id}-bar-${bar.x}-${bar.height}`"
                      class="presentation-chart__bar"
                      :x="bar.x"
                      :y="bar.y"
                      :width="bar.width"
                      :height="bar.height"
                      rx="6"
                    />
                    <text
                      v-for="label in buildTurnChartLabels(turn)"
                      :key="`${turn.id}-bar-label-${label.x}-${label.text}`"
                      class="presentation-chart__label"
                      :x="label.x"
                      y="210"
                      text-anchor="middle"
                    >
                      {{ label.text }}
                    </text>
                  </svg>
                </div>

                <div v-if="isTurnUnsupported(turn)" class="chat-unsupported-tips">
                  <div class="chat-unsupported-tips__item">
                    {{ getPresentationUnsupportedReason(turn) }}
                  </div>
                  <div
                    v-for="(item, index) in getPresentationUnsupportedSuggestions(turn)"
                    :key="`${turn.id}-unsupported-${index}`"
                    class="chat-unsupported-tips__item"
                  >
                    {{ item }}
                  </div>
                </div>

                <div v-if="isTurnClarification(turn)" class="chat-question-list">
                  <div
                    v-for="(item, index) in getPresentationFollowUpQuestions(turn)"
                    :key="`${turn.id}-clarify-${index}`"
                    class="chat-question-list__item"
                  >
                    <span class="chat-question-list__index">{{ index + 1 }}</span>
                    <span>{{ item }}</span>
                  </div>
                  <div class="chat-suggestion-row">
                    <button
                      v-for="item in getPresentationFollowUpExamples(turn)"
                      :key="`${turn.id}-quick-${item}`"
                      type="button"
                      class="chat-suggestion-chip"
                      @click="fillExample(item)"
                    >
                      {{ item }}
                    </button>
                  </div>
                </div>

                <div v-if="isTurnEmpty(turn)" class="chat-empty-tips">
                  <div class="chat-empty-tips__item">当前问题已识别成功，但在现有数据范围内没有查到符合条件的结果。</div>
                  <div class="chat-empty-tips__item">建议缩小范围，或把年份、区域、承运商、客户等条件写得更直接。</div>
                </div>

                <div v-if="shouldShowDisplayTable(turn)" class="chat-table-card">
                  <el-table :data="getDisplayTableRows(turn)" stripe size="small" class="chat-result-table">
                    <el-table-column
                      v-for="column in getDisplayTableColumns(turn)"
                      :key="column"
                      :prop="column"
                      :label="resolveColumnLabel(column)"
                      :min-width="resolveColumnMinWidth(column)"
                      :align="resolveColumnAlign(column)"
                      show-overflow-tooltip
                    >
                      <template #default="scope">
                        {{ formatCell(column, scope.row[column]) }}
                      </template>
                    </el-table-column>
                  </el-table>
                </div>

                <div v-if="getPresentationCaveats(turn).length" class="presentation-caveats">
                  <div
                    v-for="(item, index) in getPresentationCaveats(turn)"
                    :key="`${turn.id}-caveat-${index}`"
                    class="presentation-caveats__item"
                  >
                    {{ item }}
                  </div>
                </div>

                <div v-if="getTurnWarnings(turn).length" class="chat-warning-list">
                  <el-alert
                    v-for="(item, index) in getTurnWarnings(turn)"
                    :key="`${turn.id}-warning-${index}`"
                    type="warning"
                    show-icon
                    :closable="false"
                    :title="item"
                  />
                </div>

                <div class="chat-bubble__actions">
                  <el-space wrap>
                    <el-button
                      v-if="canExportTurn(turn)"
                      size="small"
                      type="primary"
                      plain
                      :loading="exportLoadingKey === `${turn.id}-xlsx`"
                      @click="exportTurnResult(turn, 'xlsx')"
                    >
                      {{ turn.source === 'history' ? '导出回看结果 Excel' : '导出 Excel' }}
                    </el-button>
                    <el-button
                      v-if="canExportTurn(turn)"
                      size="small"
                      plain
                      :loading="exportLoadingKey === `${turn.id}-csv`"
                      @click="exportTurnResult(turn, 'csv')"
                    >
                      {{ turn.source === 'history' ? '导出回看结果 CSV' : '导出 CSV' }}
                    </el-button>
                    <el-button
                      v-if="hasTurnAdvancedInfo(turn)"
                      size="small"
                      text
                      @click="toggleAdvancedInfo(turn.id)"
                    >
                    {{ turn.showAdvancedInfo ? '收起' : '详情' }}
                  </el-button>
                </el-space>
                </div>

                <el-collapse v-if="turn.showAdvancedInfo && hasTurnAdvancedInfo(turn)">
                  <el-collapse-item title="查看计算说明与高级信息" name="advanced-info">
                    <div class="chat-advanced-block" v-if="getTurnCalculationLogic(turn).length">
                      <div class="chat-advanced-block__title">计算说明</div>
                      <ul class="chat-advanced-list">
                        <li
                          v-for="(item, index) in getTurnCalculationLogic(turn)"
                          :key="`${turn.id}-logic-${index}`"
                        >
                          {{ item }}
                        </li>
                      </ul>
                    </div>

                    <div class="chat-advanced-block" v-if="getTurnScopeEntries(turn).length">
                      <div class="chat-advanced-block__title">数据范围</div>
                      <div class="chat-advanced-grid">
                        <div
                          v-for="item in getTurnScopeEntries(turn)"
                          :key="`${turn.id}-${item.label}`"
                          class="chat-advanced-item"
                        >
                          <div class="chat-advanced-item__label">{{ item.label }}</div>
                          <div class="chat-advanced-item__value">{{ item.value }}</div>
                        </div>
                      </div>
                    </div>

                    <div class="chat-advanced-block" v-if="turn.result?.query_plan">
                      <div class="chat-advanced-block__title">查询计划</div>
                      <div class="chat-mono-block">{{ JSON.stringify(turn.result?.query_plan, null, 2) }}</div>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </div>

          <div v-if="loading" class="chat-message chat-message--assistant">
            <div class="chat-bubble chat-bubble--assistant chat-bubble--loading">
              <div class="chat-bubble__header">
                <el-tag type="primary" effect="plain">正在查询</el-tag>
                <div class="chat-bubble__meta">{{ formatLogisticsDataQaDateTime(loadingStartedAt) }}</div>
              </div>
              <div class="chat-loading">
                <span class="chat-loading__dot" />
                <span class="chat-loading__dot" />
                <span class="chat-loading__dot" />
              </div>
              <div class="chat-bubble__desc">系统正在处理当前问题，请稍候。</div>
            </div>
          </div>
        </div>
      </div>

      <footer class="chat-composer">
        <div class="chat-composer__box">
          <div class="chat-composer__label">输入物流业务问题</div>
          <el-input
            v-model="question"
            class="chat-composer__input"
            type="textarea"
            resize="none"
            maxlength="200"
            show-word-limit
            :autosize="{ minRows: 1, maxRows: 5 }"
            placeholder="例如：2026年1月份总发运量是多少MW？总共发了多少车次？"
            @keydown="handleComposerKeydown"
          />

          <div class="chat-composer__footer">
            <div class="chat-composer__hint">
              {{ composerHint }}
            </div>
            <el-space wrap>
              <el-button round @click="resetQuestion">清空问题</el-button>
              <el-button
                type="primary"
                round
                :loading="loading || replayRestoring"
                :disabled="loading || replayRestoring"
                @click="submitQuery"
              >
                {{ loading || replayRestoring ? '处理中' : '发送问题' }}
              </el-button>
            </el-space>
          </div>
        </div>
      </footer>
      </section>

    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Fold } from '@element-plus/icons-vue'
import type { LogisticsDataQaPresentation, LogisticsDataQaResult } from '@/api/logistics'
import {
  fetchLogisticsDataQaHistoryDetail,
  fetchLogisticsDataQaQuery,
} from '@/api/logistics'
import {
  exportLogisticsDataQaResultAsCsv,
  exportLogisticsDataQaResultAsXlsx,
} from '@/utils/logisticsDataQaExport'
import {
  formatLogisticsDataQaDateTime,
  extractLogisticsDataQaReplaySnapshot,
} from '@/utils/logisticsDataQaHistory'
import {
  buildLogisticsDataQaSessionId,
  buildLogisticsDataQaSessionPreview,
  buildLogisticsDataQaSessionTitle,
  getActiveLogisticsDataQaSessionId,
  getLogisticsDataQaSession,
  getLogisticsDataQaSessionEventName,
  saveLogisticsDataQaSession,
  setActiveLogisticsDataQaSessionId,
  type LogisticsDataQaSessionRecord,
  type LogisticsDataQaSessionTurn,
} from '@/utils/logisticsDataQaSessions'

interface DisplayEntry {
  label: string
  value: string
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

type PresentationChartSpec = NonNullable<LogisticsDataQaPresentation['chart_spec']>

interface ChartValue {
  label: unknown
  value: number
}

const DEFAULT_SESSION_TITLE = '新建对话'
const APP_SHELL_SIDEBAR_TOGGLE_EVENT = 'app-shell:toggle-sidebar'

const exampleQuestions = [
  {
    label: 'A 直接查询',
    question: '2026年1月份总发运量是多少MW？总共发了多少车次？',
  },
  {
    label: 'A 多问法',
    question: '帮我看下 26 年 1 月物流总出货规模和总车数',
  },
  {
    label: 'B 需要追问',
    question: '最近物流成本是不是变高了？',
  },
  {
    label: 'B 补槽示例',
    question: '哪个承运商表现最差？',
  },
  {
    label: 'C 解释拒答',
    question: '预测下个月物流费用会是多少？',
  },
  {
    label: '空结果示例',
    question: '2026年1月不存在省份的总运费是多少？',
  },
]

const COLUMN_LABEL_MAP: Record<string, string> = {
  biz_month: '月份',
  city: '城市',
  total_fee: '总运费',
  avg_fee: '平均运费',
  extra_fee_amount: '额外费用',
  total_fee_amount: '总费用',
  extra_fee_ratio: '额外费用占比',
  shipment_trip_count: '车次',
  shipment_count: '发运件数',
  shipment_mw: '发运量(MW)',
  transport_mode: '运输方式',
  avg_fee_per_watt: '平均元/瓦',
  carrier_name: '承运商',
  company_name: '承运商',
  logistics_company_name: '承运商',
  signedfor_rate: '签收率',
  task_count: '任务数',
  customer_name: '客户',
  origin_place_count: '始发地数量',
  plan_qty_total: '计划件数',
  actual_qty_total: '实际件数',
  deviation_rate: '偏差率',
  bucket: '排名分组',
  power_missing_count: '功率缺失记录数',
  pickup_date_missing_count: '提货日期缺失记录数',
  strict_scope_task_count: '命中任务数',
  year_task_count: '年度任务数',
  pickup_date_available_count: '可用提货日期任务数',
}

const route = useRoute()
const router = useRouter()
const conversationRef = ref<HTMLElement | null>(null)
const question = ref('')
const loading = ref(false)
const replayRestoring = ref(false)
const currentSession = ref<LogisticsDataQaSessionRecord | null>(null)
const loadingStartedAt = ref('')
const exportLoadingKey = ref('')

/**
 * 当前激活的会话 ID。
 */
const activeSessionId = computed(() => {
  return typeof route.query.session === 'string' ? route.query.session : ''
})

/**
 * 当前会话里的全部问答轮次。
 */
const sessionTurns = computed(() => currentSession.value?.items ?? [])

/**
 * 当前会话标题。
 * 说明：
 * 正文区只保留当前会话信息，不再重复出现独立的会话列表模块。
 */
const currentSessionTitle = computed(() => {
  return currentSession.value?.title || '自然语言问答'
})

/**
 * 当前会话描述。
 */
const currentSessionDescription = computed(() => {
  if (!sessionTurns.value.length) {
    return '开始新的业务问题，或从历史页回看已经保存的结果。'
  }

  const latestTurn = sessionTurns.value[sessionTurns.value.length - 1]
  if (latestTurn.source === 'history') {
    return '当前会话中包含历史回看结果，页面展示的是当时保存下来的结果快照。'
  }
  return `当前已累计 ${sessionTurns.value.length} 轮问答，可继续提问。`
})

/**
 * 输入区提示。
 */
const composerHint = computed(() => {
  if (loading.value) return '系统正在处理当前问题，请稍候。'
  if (replayRestoring.value) return '正在打开历史结果，请稍候。'
  if (!sessionTurns.value.length) return 'Enter 发送，Shift + Enter 换行。'
  return '继续提问会追加到当前会话中；历史回看结果也会保留在会话流里。'
})

/**
 * 当前是否展示欢迎区。
 */
const showWelcome = computed(() => {
  return !sessionTurns.value.length && !loading.value && !replayRestoring.value
})

/**
 * 填充示例问题。
 */
function fillExample(value: string) {
  question.value = value
}

/**
 * 清空当前输入。
 */
function resetQuestion() {
  question.value = ''
}

/**
 * 进入独立历史页。
 * 说明：
 * 历史页继续作为正式业务入口保留，便于查看过去所有查询记录。
 */
function goHistoryPage() {
  router.push({
    path: '/logistics/data-qa/history',
    query: activeSessionId.value ? { session: activeSessionId.value } : undefined,
  })
}

/**
 * 触发主菜单缩进。
 * 说明：
 * 当前页内不再维护独立会话侧栏，这个按钮只作用于左侧主菜单。
 */
function toggleMainSidebar() {
  window.dispatchEvent(new CustomEvent(APP_SHELL_SIDEBAR_TOGGLE_EVENT))
}

/**
 * 确保当前路由上始终存在一个可用会话。
 */
async function ensureSessionRoute() {
  const routeSessionId = activeSessionId.value
  if (routeSessionId && getLogisticsDataQaSession(routeSessionId)) {
    return routeSessionId
  }

  const rememberedSessionId = getActiveLogisticsDataQaSessionId()
  if (rememberedSessionId && getLogisticsDataQaSession(rememberedSessionId)) {
    await router.replace({
      path: '/logistics/data-qa',
      query: {
        ...route.query,
        session: rememberedSessionId,
      },
    })
    return rememberedSessionId
  }

  const sessionId = buildLogisticsDataQaSessionId()
  saveLogisticsDataQaSession({
    id: sessionId,
    title: DEFAULT_SESSION_TITLE,
    preview: '等待开始新的业务问题',
    updatedAt: new Date().toISOString(),
    items: [],
  })

  await router.replace({
    path: '/logistics/data-qa',
    query: {
      ...route.query,
      session: sessionId,
    },
  })
  return sessionId
}

/**
 * 从存储同步当前会话。
 */
function syncCurrentSessionFromStorage() {
  if (!activeSessionId.value) {
    currentSession.value = null
    return
  }

  const session = getLogisticsDataQaSession(activeSessionId.value)
  currentSession.value = session
  if (session) {
    setActiveLogisticsDataQaSessionId(session.id)
  }
}

/**
 * 保存当前会话轮次。
 * 说明：
 * 1. 如果会话还是默认标题，则首轮成功后自动改成首问标题；
 * 2. 用户主动重命名后，不再自动覆盖标题。
 */
function persistSessionTurns(sessionId: string, items: LogisticsDataQaSessionTurn[]) {
  const existing = getLogisticsDataQaSession(sessionId)
  const latestTurn = items[items.length - 1] ?? null

  const nextTitle =
    !existing || existing.title === DEFAULT_SESSION_TITLE
      ? buildLogisticsDataQaSessionTitle(items[0]?.question)
      : existing.title

  saveLogisticsDataQaSession({
    id: sessionId,
    title: nextTitle,
    preview: buildLogisticsDataQaSessionPreview(latestTurn),
    updatedAt: latestTurn?.answeredAt || existing?.updatedAt || new Date().toISOString(),
    items,
  })

  syncCurrentSessionFromStorage()
}

/**
 * 向当前会话追加一轮问答。
 */
function appendTurn(turn: LogisticsDataQaSessionTurn) {
  if (!activeSessionId.value || !currentSession.value) return
  const nextItems = [...currentSession.value.items, turn]
  persistSessionTurns(activeSessionId.value, nextItems)
}

/**
 * 构造单轮问答。
 * 说明：
 * 当前页面把一次查询组织成“用户消息 + AI 回复”的一轮，便于持续追问和回看。
 */
function buildTurn(payload: {
  question: string
  askedAt: string
  answeredAt: string
  source: 'live' | 'history' | 'error'
  historyLogId?: number | null
  result?: LogisticsDataQaResult | null
  requestError?: string
}) {
  return {
    id: `${payload.source}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    question: payload.question,
    askedAt: payload.askedAt,
    answeredAt: payload.answeredAt,
    source: payload.source,
    historyLogId: payload.historyLogId ?? null,
    requestError: payload.requestError ?? '',
    result: payload.result ?? null,
    showAdvancedInfo: false,
  } satisfies LogisticsDataQaSessionTurn
}

/**
 * 提交当前业务问题。
 * 说明：
 * 1. 每次查询都会追加到当前会话，不覆盖前面的结果；
 * 2. 错误态也进入消息流，避免页面割裂；
 * 3. 成功后若当前来自历史回放入口，会清掉 historyLogId，避免重复恢复。
 */
async function submitQuery() {
  const questionText = question.value.trim()
  if (!questionText) {
    ElMessage.warning('请输入业务问题。')
    return
  }

  const sessionId = await ensureSessionRoute()
  if (!sessionId) return

  const askedAt = new Date().toISOString()
  loading.value = true
  loadingStartedAt.value = askedAt
  question.value = ''

  await nextTick()
  scrollConversationToBottom()

  try {
    const response = await fetchLogisticsDataQaQuery({ question: questionText })
    const answeredAt = new Date().toISOString()
    appendTurn(
      buildTurn({
        question: questionText,
        askedAt,
        answeredAt,
        source: 'live',
        historyLogId: response.data?.history_log_id ?? null,
        result: response.data ?? null,
      }),
    )

    if (route.query.historyLogId) {
      await router.replace({
        path: '/logistics/data-qa',
        query: { session: sessionId },
      })
    }
  } catch (error: any) {
    const answeredAt = new Date().toISOString()
    appendTurn(
      buildTurn({
        question: questionText,
        askedAt,
        answeredAt,
        source: 'error',
        requestError:
          error?.response?.data?.message ||
          error?.response?.data?.detail ||
          error?.message ||
          '查询失败，请稍后重试。',
      }),
    )
    ElMessage.error('查询失败，请稍后重试。')
  } finally {
    loading.value = false
    await nextTick()
    scrollConversationToBottom()
  }
}

/**
 * 恢复历史回放。
 * 说明：
 * 1. 回放优先展示历史快照，不重新执行后端查询；
 * 2. 同一条历史结果不会在同一会话里重复追加。
 */
async function restoreHistoryReplay(historyLogId: number) {
  if (!activeSessionId.value || replayRestoring.value) return
  if (currentSession.value?.items.some((item) => item.historyLogId === historyLogId && item.source === 'history')) {
    await router.replace({
      path: '/logistics/data-qa',
      query: { session: activeSessionId.value },
    })
    await nextTick()
    scrollConversationToBottom()
    return
  }

  replayRestoring.value = true
  try {
    const resp = await fetchLogisticsDataQaHistoryDetail(historyLogId)
    const detail = resp.data ?? resp ?? null
    const snapshot = extractLogisticsDataQaReplaySnapshot(detail)

    if (!detail || !snapshot) {
      ElMessage.error('当前历史记录缺少可回看的结果快照。')
      return
    }

    const replayTime = detail.created_at || new Date().toISOString()
    appendTurn(
      buildTurn({
        question: detail.question || '历史回看',
        askedAt: replayTime,
        answeredAt: replayTime,
        source: 'history',
        historyLogId: detail.id,
        result: snapshot,
      }),
    )

    ElMessage.success('已打开该次历史结果。')
    await router.replace({
      path: '/logistics/data-qa',
      query: { session: activeSessionId.value },
    })
  } catch (_error) {
    ElMessage.error('历史回放失败，请稍后重试。')
  } finally {
    replayRestoring.value = false
    await nextTick()
    scrollConversationToBottom()
  }
}

/**
 * 切换单轮问答的高级信息展开状态。
 */
function toggleAdvancedInfo(turnId: string) {
  if (!activeSessionId.value || !currentSession.value) return

  const nextItems = currentSession.value.items.map((item) => {
    if (item.id !== turnId) return item
    return {
      ...item,
      showAdvancedInfo: !item.showAdvancedInfo,
    }
  })

  persistSessionTurns(activeSessionId.value, nextItems)
}

/**
 * 导出指定轮次结果。
 * 说明：
 * 导出按钮继续放在结果消息附近，避免和当前历史/当前查询来源混淆。
 */
async function exportTurnResult(turn: LogisticsDataQaSessionTurn, format: 'csv' | 'xlsx') {
  if (!turn.result) {
    ElMessage.warning('当前没有可导出的结果。')
    return
  }

  const exportKey = `${turn.id}-${format}`
  if (exportLoadingKey.value === exportKey) return

  exportLoadingKey.value = exportKey
  ElMessage.info(format === 'xlsx' ? '正在导出 Excel，请稍候。' : '正在导出 CSV，请稍候。')

  try {
    const statusLabel = resolveTurnStatusLabel(turn)
    const queryTime = turn.answeredAt || turn.askedAt
    const payload = {
      question: turn.question,
      queryTime,
      statusLabel,
      answerSummary: turn.result.answer_summary,
      result: turn.result,
      columnLabelResolver: resolveColumnLabel,
    }

    if (format === 'xlsx') {
      exportLogisticsDataQaResultAsXlsx(payload)
      ElMessage.success('Excel 已导出，请在浏览器下载列表中查看。')
    } else {
      exportLogisticsDataQaResultAsCsv(payload)
      ElMessage.success('CSV 已导出，请在浏览器下载列表中查看。')
    }
  } catch (_error) {
    ElMessage.error(format === 'xlsx' ? '导出 Excel 失败，请稍后重试。' : '导出 CSV 失败，请稍后重试。')
  } finally {
    exportLoadingKey.value = ''
  }
}

/**
 * 键盘发送逻辑。
 * 说明：
 * 1. Enter 直接发送；
 * 2. Shift + Enter 换行；
 * 3. 继续保留 200 字限制。
 */
function handleComposerKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter') return
  if (event.shiftKey) return
  event.preventDefault()
  submitQuery()
}

/**
 * 当前轮次状态码。
 */
function resolveTurnStatusCode(turn: LogisticsDataQaSessionTurn) {
  if (turn.requestError) return 'EXECUTION_ERROR'
  if (turn.result?.status?.code) return turn.result.status.code
  if (turn.result?.needs_clarification) return 'CLARIFICATION_REQUIRED'
  if (turn.result && !turn.result.supported) return 'UNSUPPORTED_QUESTION'
  if (turn.result?.supported && getTurnRows(turn).length === 0) return 'EMPTY_RESULT'
  if (turn.result?.supported && getTurnRows(turn).length > 0) return 'OK'
  return ''
}

/**
 * 解析单轮状态标签。
 */
function resolveTurnStatusLabel(turn: LogisticsDataQaSessionTurn) {
  const code = resolveTurnStatusCode(turn)
  const mapping: Record<string, string> = {
    OK: '查询成功',
    CLARIFICATION_REQUIRED: '需要再确认',
    UNSUPPORTED_QUESTION: '当前暂不支持',
    EMPTY_RESULT: '未查到结果',
    EXECUTION_ERROR: '查询失败',
  }
  return mapping[code] || '结果状态'
}

/**
 * 解析单轮状态颜色。
 */
function resolveTurnTagType(turn: LogisticsDataQaSessionTurn) {
  const code = resolveTurnStatusCode(turn)
  if (code === 'OK') return 'success'
  if (code === 'CLARIFICATION_REQUIRED' || code === 'EMPTY_RESULT') return 'warning'
  if (code === 'UNSUPPORTED_QUESTION') return 'info'
  if (code === 'EXECUTION_ERROR') return 'danger'
  return 'info'
}

/**
 * 解析助手回复的视觉语气。
 * 说明：
 * 只影响 UI 展示，不参与 A/B/C 业务裁决。
 */
function resolveTurnToneClass(turn: LogisticsDataQaSessionTurn) {
  const code = resolveTurnStatusCode(turn)
  return {
    'chat-bubble--ok': code === 'OK',
    'chat-bubble--clarify': code === 'CLARIFICATION_REQUIRED',
    'chat-bubble--unsupported': code === 'UNSUPPORTED_QUESTION',
    'chat-bubble--empty': code === 'EMPTY_RESULT',
    'chat-bubble--error': code === 'EXECUTION_ERROR',
  }
}

/**
 * 构造单轮主标题。
 */
function buildTurnTitle(turn: LogisticsDataQaSessionTurn) {
  if (turn.requestError) return '当前请求未完成，请稍后重试。'
  if (turn.result?.answer_summary) return turn.result.answer_summary
  return '当前暂无可展示结果'
}

/**
 * 构造单轮补充描述。
 */
function buildTurnDescription(turn: LogisticsDataQaSessionTurn) {
  if (turn.source === 'history' && !turn.requestError) {
    return '当前展示的是当时保存下来的历史结果快照，不会自动重新实时计算。'
  }

  if (turn.requestError) {
    return turn.requestError
  }

  if (isTurnClarification(turn)) {
    return '请先根据系统提示补充时间范围、指标口径或对比维度，再继续查询。'
  }

  if (isTurnUnsupported(turn)) {
    return '当前问题已识别成功，但不在当前受控结构化查询能力范围内。'
  }

  if (isTurnEmpty(turn)) {
    return '当前问题已识别成功，但在现有数据范围内没有查到符合条件的结果。'
  }

  return ''
}

/**
 * 当前轮次不支持原因。
 * 说明：
 * 后端可能把业务化拒答原因放在 query_plan.unsupported_reason、status.message 或 answer_summary；
 * 前端只做展示兜底，不改变 unsupported 的最终裁决。
 */
function getTurnUnsupportedReason(turn: LogisticsDataQaSessionTurn) {
  return (
    turn.result?.query_plan?.unsupported_reason ||
    turn.result?.status?.message ||
    turn.result?.answer_summary ||
    '当前问题缺少可验证数据、已确认口径或可执行查询能力，暂不能直接回答。'
  )
}

/**
 * 生成澄清态的快捷补充建议。
 * 说明：
 * 这些建议仅帮助用户组织下一次提问，不会在前端拼接或执行查询逻辑。
 */
function buildClarificationQuickReplies(turn: LogisticsDataQaSessionTurn) {
  const text = `${turn.question} ${(turn.result?.clarification_questions || []).join(' ')}`
  const suggestions: string[] = []
  if (/时间|最近|范围|月份|年份|同比|环比/.test(text)) {
    suggestions.push('限定为2025年全年')
  }
  if (/指标|口径|成本|费用|运费/.test(text)) {
    suggestions.push('按总运费口径统计')
  }
  if (/承运商|物流公司|排名|最差|表现/.test(text)) {
    suggestions.push('按签收率从低到高排序')
  }
  if (/区域|省|城市/.test(text)) {
    suggestions.push('按省份维度输出')
  }
  if (/车型|运输方式|公路|铁路/.test(text)) {
    suggestions.push('限定运输方式为公路')
  }
  return Array.from(new Set(suggestions)).slice(0, 3)
}

/**
 * 获取答案表达层结果。
 * 说明：
 * 该字段来自后端确定性结果之后的展示编排层；如果不存在，页面必须继续使用旧字段降级展示。
 */
function getPresentation(turn: LogisticsDataQaSessionTurn): LogisticsDataQaPresentation | null {
  return turn.result?.presentation || null
}

/**
 * 构造主展示标题。
 */
function buildTurnPresentationTitle(turn: LogisticsDataQaSessionTurn) {
  return getPresentation(turn)?.title || buildTurnTitle(turn)
}

/**
 * 构造主展示回答。
 */
function buildTurnPresentationAnswer(turn: LogisticsDataQaSessionTurn) {
  const presentationAnswer = getPresentation(turn)?.answer
  if (presentationAnswer) return presentationAnswer
  return buildTurnDescription(turn)
}

/**
 * 获取表达层关键结论。
 */
function getPresentationHighlights(turn: LogisticsDataQaSessionTurn) {
  const answer = buildTurnPresentationAnswer(turn)
  return (getPresentation(turn)?.highlights || [])
    .filter((item) => item && item !== answer)
    .slice(0, 4)
}

/**
 * 获取表达层指标卡。
 */
function getPresentationCards(turn: LogisticsDataQaSessionTurn) {
  return getPresentation(turn)?.cards || []
}

/**
 * 获取表达层图表配置。
 */
function getPresentationChart(turn: LogisticsDataQaSessionTurn) {
  const chart = getPresentation(turn)?.chart_spec
  if (!chart || !chart.chart_type) return null
  return chart
}

/**
 * 获取表达层口径提醒。
 */
function getPresentationCaveats(turn: LogisticsDataQaSessionTurn) {
  return getPresentation(turn)?.caveats || []
}

/**
 * 获取表达层拒答原因。
 */
function getPresentationUnsupportedReason(turn: LogisticsDataQaSessionTurn) {
  return getPresentation(turn)?.unsupported_explanation?.reason || getTurnUnsupportedReason(turn)
}

/**
 * 获取表达层可改问方向。
 */
function getPresentationUnsupportedSuggestions(turn: LogisticsDataQaSessionTurn) {
  const suggestions = getPresentation(turn)?.unsupported_explanation?.suggestions || []
  if (suggestions.length) return suggestions
  return turn.result?.query_plan?.unsupported_suggestions?.length
    ? turn.result.query_plan.unsupported_suggestions
    : ['可以改问为已锁定口径的发运量、运费、车次、签收率、状态分布或排名统计。']
}

/**
 * 获取表达层追问。
 */
function getPresentationFollowUpQuestions(turn: LogisticsDataQaSessionTurn) {
  return getPresentation(turn)?.follow_up?.questions?.length
    ? getPresentation(turn)?.follow_up?.questions || []
    : turn.result?.clarification_questions || []
}

/**
 * 获取表达层补充示例。
 */
function getPresentationFollowUpExamples(turn: LogisticsDataQaSessionTurn) {
  return getPresentation(turn)?.follow_up?.examples?.length
    ? getPresentation(turn)?.follow_up?.examples || []
    : buildClarificationQuickReplies(turn)
}

/**
 * 判断是否展示表格。
 */
function shouldShowDisplayTable(turn: LogisticsDataQaSessionTurn) {
  const rows = getDisplayTableRows(turn)
  if (!rows.length) return false
  const displayType = getPresentation(turn)?.display_type
  if (displayType === 'line_chart' || displayType === 'bar_chart') {
    return !getPresentationChart(turn)
  }
  return isTurnSuccess(turn)
}

/**
 * 获取表达层表格列。
 */
function getDisplayTableColumns(turn: LogisticsDataQaSessionTurn) {
  return getPresentation(turn)?.table_spec?.columns?.length
    ? getPresentation(turn)?.table_spec?.columns || []
    : getTurnColumns(turn)
}

/**
 * 获取表达层表格行。
 */
function getDisplayTableRows(turn: LogisticsDataQaSessionTurn) {
  return getPresentation(turn)?.table_spec?.rows?.length
    ? getPresentation(turn)?.table_spec?.rows || []
    : getTurnRows(turn)
}

/**
 * 格式化指标卡值。
 */
function formatPresentationValue(value: unknown) {
  return formatCell('', value)
}

/**
 * 当前轮次折线图 points。
 */
function buildTurnLineChartPoints(turn: LogisticsDataQaSessionTurn) {
  const chart = getPresentationChart(turn)
  return chart ? buildLineChartPoints(chart) : ''
}

/**
 * 当前轮次折线图圆点。
 */
function buildTurnLineChartCircles(turn: LogisticsDataQaSessionTurn) {
  const chart = getPresentationChart(turn)
  return chart ? buildLineChartCircles(chart) : []
}

/**
 * 当前轮次柱状图矩形。
 */
function buildTurnBarChartRects(turn: LogisticsDataQaSessionTurn) {
  const chart = getPresentationChart(turn)
  return chart ? buildBarChartRects(chart) : []
}

/**
 * 当前轮次图表标签。
 */
function buildTurnChartLabels(turn: LogisticsDataQaSessionTurn) {
  const chart = getPresentationChart(turn)
  return chart ? buildChartLabels(chart) : []
}

/**
 * 生成折线图 polyline points。
 */
function buildLineChartPoints(chart: PresentationChartSpec) {
  return buildChartRenderPoints(chart)
    .map((point) => `${point.x},${point.y}`)
    .join(' ')
}

/**
 * 生成折线图圆点。
 */
function buildLineChartCircles(chart: PresentationChartSpec) {
  return buildChartRenderPoints(chart)
}

/**
 * 生成柱状图矩形。
 */
function buildBarChartRects(chart: PresentationChartSpec) {
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

/**
 * 生成图表 X 轴标签。
 */
function buildChartLabels(chart: PresentationChartSpec) {
  const values = extractChartValues(chart)
  const slotWidth = values.length > 1 ? 584 / (values.length - 1) : 0
  const maxLabels = 8
  const step = Math.max(1, Math.ceil(values.length / maxLabels))
  return values
    .map((item, index): ChartRenderLabel => ({
      x: values.length > 1 ? 28 + slotWidth * index : 320,
      text: String(item.label ?? '').slice(0, 8),
    }))
    .filter((_, index) => index % step === 0)
}

/**
 * 根据图表数据生成 SVG 坐标点。
 */
function buildChartRenderPoints(chart: PresentationChartSpec) {
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

/**
 * 从 chart_spec 中提取第一组可展示数据。
 */
function extractChartValues(chart: PresentationChartSpec): ChartValue[] {
  const firstSeries = chart.series?.[0]
  if (firstSeries?.data?.length) {
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

/**
 * 当前轮次是否成功。
 */
function isTurnSuccess(turn: LogisticsDataQaSessionTurn) {
  return resolveTurnStatusCode(turn) === 'OK' && getTurnRows(turn).length > 0
}

/**
 * 当前轮次是否为澄清态。
 */
function isTurnClarification(turn: LogisticsDataQaSessionTurn) {
  return resolveTurnStatusCode(turn) === 'CLARIFICATION_REQUIRED'
}

/**
 * 当前轮次是否为不支持态。
 */
function isTurnUnsupported(turn: LogisticsDataQaSessionTurn) {
  return resolveTurnStatusCode(turn) === 'UNSUPPORTED_QUESTION'
}

/**
 * 当前轮次是否为空结果。
 */
function isTurnEmpty(turn: LogisticsDataQaSessionTurn) {
  return resolveTurnStatusCode(turn) === 'EMPTY_RESULT'
}

/**
 * 当前轮次是否可导出。
 */
function canExportTurn(turn: LogisticsDataQaSessionTurn) {
  return Boolean(turn.result)
}

/**
 * 当前轮次表头。
 */
function getTurnColumns(turn: LogisticsDataQaSessionTurn) {
  return turn.result?.result_table?.columns || []
}

/**
 * 当前轮次表格行。
 */
function getTurnRows(turn: LogisticsDataQaSessionTurn) {
  return turn.result?.result_table?.rows || []
}

/**
 * 当前轮次提醒信息。
 */
function getTurnWarnings(turn: LogisticsDataQaSessionTurn) {
  return turn.result?.warnings || []
}

/**
 * 当前轮次计算说明。
 */
function getTurnCalculationLogic(turn: LogisticsDataQaSessionTurn) {
  return turn.result?.calculation_logic || []
}

/**
 * 当前轮次数据范围信息。
 */
function getTurnScopeEntries(turn: LogisticsDataQaSessionTurn): DisplayEntry[] {
  if (!turn.result?.data_scope) return []
  return Object.entries(turn.result.data_scope)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => ({
      label: resolveScopeLabel(key),
      value: formatScopeValue(value),
    }))
}

/**
 * 当前轮次是否有高级信息。
 */
function hasTurnAdvancedInfo(turn: LogisticsDataQaSessionTurn) {
  return Boolean(
    getTurnCalculationLogic(turn).length ||
      getTurnScopeEntries(turn).length ||
      turn.result?.query_plan,
  )
}

/**
 * 结果字段格式化。
 * 说明：
 * 前端只做展示层格式化，不在消息流里补算业务结果。
 */
function formatCell(column: string, value: unknown) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') {
    if (column.includes('rate') || column.includes('ratio')) {
      return `${value}%`
    }
    return value.toLocaleString('zh-CN', {
      minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
      maximumFractionDigits: 2,
    })
  }
  if (Array.isArray(value)) return value.join('，')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

/**
 * 解析列名。
 */
function resolveColumnLabel(column: string) {
  return COLUMN_LABEL_MAP[column] || column.replace(/_/g, ' ')
}

/**
 * 解析列宽。
 */
function resolveColumnMinWidth(column: string) {
  if (column.includes('name') || column.includes('summary')) return 180
  if (column.includes('logic') || column.includes('scope')) return 220
  return 140
}

/**
 * 解析列对齐方式。
 */
function resolveColumnAlign(column: string) {
  if (
    column.includes('rate') ||
    column.includes('ratio') ||
    column.includes('fee') ||
    column.includes('count') ||
    column.includes('mw')
  ) {
    return 'right'
  }
  return 'left'
}

/**
 * 解析数据范围字段名称。
 */
function resolveScopeLabel(key: string) {
  const labels: Record<string, string> = {
    table: '来源表',
    tables: '来源表',
    year: '年份',
    months: '月份',
    province: '省份',
    region_name: '区域',
    origin_place: '始发地',
    customer_name: '客户',
    vehicle_type: '车型',
    carrier_name: '承运商',
    special_scope: '特殊业务口径',
    question: '原始问题',
  }
  return labels[key] || key
}

/**
 * 格式化数据范围值。
 */
function formatScopeValue(value: unknown) {
  if (Array.isArray(value)) return value.join('，')
  if (typeof value === 'object' && value) return JSON.stringify(value)
  return String(value)
}

/**
 * 滚动到底部。
 */
function scrollConversationToBottom(behavior: ScrollBehavior = 'smooth') {
  if (!conversationRef.value) return
  conversationRef.value.scrollTo({
    top: conversationRef.value.scrollHeight,
    behavior,
  })
}

/**
 * 监听当前路由中的会话与历史回放参数。
 * 说明：
 * 1. 没有 session 时自动补一个可用会话；
 * 2. historyLogId 只负责触发一次历史回看；
 * 3. 切换会话时不重新执行后端查询。
 */
watch(
  () => [route.query.session, route.query.historyLogId] as const,
  async ([, historyQuery]) => {
    const ensuredSessionId = await ensureSessionRoute()
    if (!ensuredSessionId) return

    syncCurrentSessionFromStorage()

    if (typeof historyQuery === 'string' && historyQuery) {
      const historyLogId = Number(historyQuery)
      if (Number.isFinite(historyLogId)) {
        await restoreHistoryReplay(historyLogId)
      }
      return
    }

    await nextTick()
    scrollConversationToBottom('auto')
  },
  { immediate: true },
)

/**
 * 页面挂载时同步会话事件。
 */
onMounted(() => {
  window.addEventListener(getLogisticsDataQaSessionEventName(), syncCurrentSessionFromStorage)
})

/**
 * 页面卸载时清理事件监听。
 */
onBeforeUnmount(() => {
  window.removeEventListener(getLogisticsDataQaSessionEventName(), syncCurrentSessionFromStorage)
})
</script>

<style scoped>
.data-qa-chat-page {
  width: 100%;
  height: 100%;
  min-height: 0;
}

.chat-main {
  width: min(1040px, 100%);
  height: 100%;
  min-height: 0;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow: hidden;
}

.chat-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 2px 0;
}

.chat-toolbar__main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

.chat-toolbar__menu {
  color: #5b7186;
}

.chat-toolbar__copy {
  min-width: 0;
}

.chat-toolbar__eyebrow {
  color: #7a8a98;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.chat-toolbar__title {
  color: #18314b;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.4;
  margin-top: 4px;
}

.chat-toolbar__desc {
  margin-top: 4px;
  color: #697989;
  font-size: 12px;
  line-height: 1.6;
}

.chat-toolbar__actions {
  flex: none;
}

.chat-toolbar__actions :deep(.el-button) {
  min-width: 112px;
}

.chat-thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 6px 4px 0 0;
  display: flex;
}

.chat-thread__inner {
  width: min(960px, 100%);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding: 6px 6px 18px;
}

.chat-welcome {
  margin: auto 0 0;
  text-align: center;
  padding: 64px 18px 22px;
}

.chat-welcome__title {
  margin: 0 0 12px;
  color: #18314b;
  font-size: 38px;
  line-height: 1.25;
  font-weight: 800;
}

.chat-welcome__desc {
  color: #667889;
  line-height: 1.8;
  font-size: 15px;
  max-width: 680px;
  margin: 0 auto;
}

.chat-welcome__examples {
  margin-top: 28px;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
}

.chat-example-chip {
  border: 1px solid #d9e7f1;
  background: #ffffff;
  color: #335a7d;
  border-radius: 999px;
  padding: 10px 16px;
  font-size: 13px;
  line-height: 1.5;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.chat-example-chip:hover,
.chat-example-chip:focus-visible {
  border-color: #bcd5e6;
  background: #f7fbfe;
}

.chat-turn {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chat-message {
  display: flex;
}

.chat-message--user {
  justify-content: flex-end;
}

.chat-message--assistant {
  justify-content: flex-start;
}

.chat-bubble {
  max-width: min(860px, 88%);
  border-radius: 22px;
  padding: 18px 20px;
  box-shadow: 0 10px 24px rgba(32, 66, 102, 0.06);
}

.chat-bubble--user {
  background: linear-gradient(180deg, #dceeff 0%, #d4ecff 100%);
  color: #14344f;
}

.chat-bubble--assistant {
  background: #ffffff;
  border: 1px solid #e1eaf1;
}

.chat-bubble--loading {
  min-width: 280px;
}

.chat-bubble__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.chat-bubble__meta {
  color: #8693a1;
  font-size: 12px;
  flex: none;
}

.chat-bubble__content {
  margin-top: 10px;
  white-space: pre-wrap;
  line-height: 1.8;
}

.chat-bubble__title {
  margin-top: 12px;
  color: #18314b;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.7;
}

.chat-bubble__desc {
  margin-top: 8px;
  color: #607282;
  line-height: 1.8;
}

.chat-question-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-question-list__item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 12px 14px;
  border-radius: 16px;
  background: #f8fbfd;
  border: 1px solid #e5edf3;
}

.chat-question-list__index {
  width: 22px;
  height: 22px;
  flex: none;
  border-radius: 50%;
  background: #dff0ff;
  color: #1f5f95;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.chat-empty-tips {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-unsupported-tips {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-unsupported-tips__item {
  padding: 12px 14px;
  border-radius: 16px;
  background: #f6f8fb;
  border: 1px solid #dfe7ef;
  color: #526476;
  line-height: 1.7;
}

.chat-empty-tips__item {
  padding: 12px 14px;
  border-radius: 16px;
  background: #fff8ec;
  border: 1px solid #f6dfb8;
  color: #7b6134;
  line-height: 1.7;
}

.chat-table-card {
  margin-top: 16px;
  border: 1px solid #e5edf3;
  border-radius: 18px;
  overflow: hidden;
  background: #fbfdff;
}

.chat-result-table {
  width: 100%;
}

.chat-result-table :deep(.el-table__header th) {
  background: #f4f8fb;
  color: #55697c;
  font-weight: 700;
}

.chat-warning-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chat-bubble__actions {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-top: 12px;
  border-top: 1px solid #edf3f7;
}

.chat-bubble__action-hint {
  color: #758595;
  font-size: 12px;
  line-height: 1.7;
}

.chat-advanced-block {
  margin-bottom: 20px;
}

.chat-advanced-block__title {
  color: #18314b;
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 10px;
}

.chat-advanced-list {
  margin: 0;
  padding-left: 18px;
  color: #5f7282;
  line-height: 1.8;
}

.chat-advanced-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.chat-advanced-item {
  padding: 12px;
  border-radius: 14px;
  background: #f8fbfd;
  border: 1px solid #e7eef4;
}

.chat-advanced-item__label {
  color: #7a8a98;
  font-size: 12px;
  margin-bottom: 6px;
}

.chat-advanced-item__value {
  color: #1b334d;
  line-height: 1.7;
  word-break: break-word;
}

.chat-mono-block {
  margin: 0;
  padding: 14px;
  border-radius: 14px;
  background: #f7fafc;
  border: 1px solid #e5edf3;
  font-family: 'SFMono-Regular', 'Consolas', 'Liberation Mono', monospace;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-loading {
  margin-top: 14px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.chat-loading__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #7eb5e3;
  animation: chat-loading-dot 1.2s infinite ease-in-out;
}

.chat-loading__dot:nth-child(2) {
  animation-delay: 0.15s;
}

.chat-loading__dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes chat-loading-dot {
  0%,
  80%,
  100% {
    transform: scale(0.7);
    opacity: 0.5;
  }

  40% {
    transform: scale(1);
    opacity: 1;
  }
}

.chat-composer {
  flex: none;
  padding: 6px 0 10px;
  background: linear-gradient(180deg, rgba(245, 248, 251, 0) 0%, rgba(245, 248, 251, 0.9) 18%, #f5f8fb 100%);
}

.chat-composer__box {
  width: min(960px, 100%);
  margin: 0 auto;
  background: #ffffff;
  border: 1px solid #d9e6ef;
  border-radius: 24px;
  padding: 14px 16px 12px;
  box-shadow: 0 14px 30px rgba(32, 66, 102, 0.08);
}

.chat-composer__footer {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.chat-composer__hint {
  color: #738393;
  font-size: 12px;
  line-height: 1.6;
}

.chat-composer__input :deep(.el-textarea__inner) {
  border: none;
  box-shadow: none;
  resize: none;
  min-height: 72px !important;
  padding: 0 0 8px;
  font-size: 14px;
  line-height: 1.8;
  color: #18314b;
  background: transparent;
}

.chat-composer__input :deep(.el-input__count) {
  right: 0;
  bottom: 0;
  color: #8a98a6;
}

@media (max-width: 1279px) {
  .data-qa-chat-page {
    height: 100%;
  }
}

@media (max-width: 767px) {
  .data-qa-chat-page {
    height: 100%;
    min-height: 0;
  }

  .chat-main {
    min-height: 0;
  }

  .chat-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .chat-thread {
    padding-right: 0;
  }

  .chat-bubble {
    max-width: 100%;
  }

  .chat-composer__footer,
  .chat-bubble__header {
    flex-direction: column;
    align-items: flex-start;
  }

  .chat-welcome__title {
    font-size: 30px;
  }
}

/* 试运行 UI 升级：保持业务逻辑不变，只重塑物流问答的演示级对话体验。 */
.data-qa-chat-page {
  --logistics-text: #16283d;
  --logistics-muted: #64748b;
  --logistics-line: #dbe6ef;
  --logistics-blue: #1f6fb2;
  --logistics-blue-soft: #e9f4ff;
  --logistics-green: #0f8f62;
  --logistics-green-soft: #eaf8f0;
  --logistics-amber: #b46b08;
  --logistics-amber-soft: #fff7e8;
  --logistics-red: #b83a3a;
  --logistics-red-soft: #fff1f1;
  --logistics-shadow: 0 22px 52px rgba(28, 54, 85, 0.1);
  min-height: calc(100vh - 88px);
  height: calc(100vh - 88px);
  padding: 18px;
  overflow: hidden;
  color: var(--logistics-text);
  background:
    radial-gradient(circle at 12% 12%, rgba(31, 111, 178, 0.12), transparent 34%),
    radial-gradient(circle at 88% 0%, rgba(15, 143, 98, 0.1), transparent 32%),
    linear-gradient(135deg, #f7fafc 0%, #eef5fa 48%, #f8faf7 100%);
}

.data-qa-shell {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 18px;
  width: min(1440px, 100%);
  height: 100%;
  margin: 0 auto;
}

.chat-main {
  width: 100%;
  height: 100%;
  gap: 0;
  border: 1px solid rgba(219, 230, 239, 0.86);
  border-radius: 30px;
  background: rgba(255, 255, 255, 0.84);
  box-shadow: var(--logistics-shadow);
  backdrop-filter: blur(18px);
}

.chat-toolbar {
  align-items: center;
  padding: 18px 20px 14px;
  border-bottom: 1px solid rgba(219, 230, 239, 0.82);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(255, 255, 255, 0.78));
}

.chat-toolbar__main {
  flex: 1;
}

.chat-toolbar__menu {
  background: #f4f8fb;
  border: 1px solid #dbe6ef;
}

.brand-lockup {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 12px;
}

.brand-lockup__logo {
  width: 42px;
  height: 42px;
  flex: none;
  object-fit: contain;
  padding: 8px;
  border-radius: 14px;
  background: #ffffff;
  border: 1px solid #e4edf4;
  box-shadow: 0 10px 20px rgba(31, 111, 178, 0.08);
}

.brand-lockup__copy {
  min-width: 0;
}

.brand-lockup__eyebrow {
  font-size: 12px;
  font-weight: 800;
  color: var(--logistics-blue);
  letter-spacing: 0.08em;
}

.brand-lockup__title {
  margin-top: 2px;
  color: var(--logistics-text);
  font-size: 18px;
  font-weight: 850;
  line-height: 1.35;
}

.chat-toolbar__desc {
  color: #607086;
}

.chat-toolbar__center {
  flex: none;
}

.chat-toolbar__actions :deep(.el-button) {
  border-radius: 999px;
  background: #ffffff;
}

.chat-thread {
  padding: 0;
  background: linear-gradient(180deg, rgba(248, 251, 253, 0.62), rgba(255, 255, 255, 0.2));
}

.chat-thread__inner {
  width: min(940px, 100%);
  gap: 24px;
  padding: 26px 24px 28px;
}

.chat-welcome {
  margin: auto 0;
  padding: 48px 18px 34px;
}

.chat-welcome__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(31, 111, 178, 0.1);
  color: var(--logistics-blue);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.chat-welcome__title {
  margin-top: 18px;
  color: var(--logistics-text);
  font-size: clamp(30px, 5vw, 48px);
  letter-spacing: -0.04em;
}

.chat-welcome__desc {
  color: #5f7187;
}

.chat-welcome__examples {
  width: min(820px, 100%);
  margin: 30px auto 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.chat-example-chip {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  min-height: 78px;
  border-radius: 20px;
  padding: 14px 16px;
  text-align: left;
  background: rgba(255, 255, 255, 0.86);
  border: 1px solid rgba(219, 230, 239, 0.92);
  color: #233a52;
  box-shadow: 0 10px 24px rgba(28, 54, 85, 0.06);
}

.chat-example-chip__label {
  color: var(--logistics-blue);
  font-size: 12px;
  font-weight: 850;
}

.chat-example-chip__text {
  color: #31485f;
  font-size: 13px;
  line-height: 1.55;
}

.chat-example-chip:hover,
.chat-example-chip:focus-visible {
  border-color: rgba(31, 111, 178, 0.36);
  background: #ffffff;
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(31, 111, 178, 0.1);
}

.chat-message--user .chat-bubble {
  max-width: min(720px, 82%);
}

.chat-message--assistant .chat-bubble {
  max-width: min(900px, 92%);
}

.chat-bubble {
  border-radius: 24px;
  padding: 18px 20px;
}

.chat-bubble--user {
  background: linear-gradient(135deg, #1f6fb2 0%, #164f84 100%);
  color: #ffffff;
  box-shadow: 0 16px 34px rgba(31, 111, 178, 0.18);
}

.chat-bubble--user .chat-bubble__meta,
.chat-bubble--user .chat-bubble__content {
  color: #16181d;
}

.chat-bubble--assistant {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(219, 230, 239, 0.95);
  box-shadow: 0 18px 36px rgba(28, 54, 85, 0.08);
}

.chat-bubble--ok {
  border-left: 5px solid var(--logistics-green);
}

.chat-bubble--clarify {
  border-left: 5px solid #e19a1d;
  background: linear-gradient(180deg, #ffffff 0%, rgba(255, 247, 232, 0.8) 100%);
}

.chat-bubble--unsupported {
  border-left: 5px solid #6a7a8a;
  background: linear-gradient(180deg, #ffffff 0%, rgba(246, 248, 251, 0.95) 100%);
}

.chat-bubble--empty {
  border-left: 5px solid #d6982d;
  background: linear-gradient(180deg, #ffffff 0%, rgba(255, 248, 236, 0.95) 100%);
}

.chat-bubble--error {
  border-left: 5px solid var(--logistics-red);
  background: linear-gradient(180deg, #ffffff 0%, rgba(255, 241, 241, 0.9) 100%);
}

.chat-bubble__header {
  align-items: flex-start;
}

.chat-bubble__meta {
  color: #718096;
}

.chat-bubble__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 14px;
}

.chat-bubble__title {
  margin-top: 0;
  font-size: 18px;
}

.chat-bubble__mini-stat {
  flex: none;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--logistics-green-soft);
  color: #096143;
  font-size: 12px;
  font-weight: 800;
}

.chat-question-list__item,
.chat-empty-tips__item,
.chat-unsupported-tips__item,
.chat-advanced-item {
  border-radius: 18px;
}

.chat-question-list__item {
  background: #fffaf0;
  border-color: #f2dbad;
}

.chat-question-list__index {
  background: #fff0cf;
  color: #9c5f07;
}

.chat-suggestion-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
}

.chat-suggestion-chip {
  border: 1px solid #edd6a9;
  background: #fffaf1;
  color: #8a5a0a;
  border-radius: 999px;
  padding: 7px 11px;
  font-size: 12px;
  line-height: 1.4;
  cursor: pointer;
  transition: all 0.2s ease;
}

.chat-suggestion-chip:hover,
.chat-suggestion-chip:focus-visible {
  border-color: #d39a2e;
  background: #fff4d8;
}

.chat-table-card {
  border-radius: 20px;
  border-color: rgba(219, 230, 239, 0.95);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.chat-bubble__actions {
  border-top-color: #edf3f7;
}

.chat-bubble__action-hint {
  color: #70839a;
}

.chat-composer {
  padding: 12px 24px 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0), rgba(247, 250, 252, 0.92) 28%, #f7fafc 100%);
}

.chat-composer__box {
  border-radius: 26px;
  border-color: rgba(188, 211, 229, 0.95);
  box-shadow: 0 18px 38px rgba(28, 54, 85, 0.12);
}

.chat-composer__label {
  margin-bottom: 8px;
  color: var(--logistics-blue);
  font-size: 12px;
  font-weight: 850;
}

.chat-composer__hint {
  max-width: 680px;
}

.chat-composer__footer :deep(.el-button) {
  min-width: 118px;
  border-radius: 999px;
  font-weight: 800;
}

.trial-panel {
  height: 100%;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.trial-card {
  border: 1px solid rgba(219, 230, 239, 0.92);
  border-radius: 26px;
  padding: 18px;
  background: rgba(255, 255, 255, 0.78);
  box-shadow: 0 16px 34px rgba(28, 54, 85, 0.08);
  backdrop-filter: blur(14px);
}

.trial-card__label {
  display: inline-flex;
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(31, 111, 178, 0.1);
  color: var(--logistics-blue);
  font-size: 11px;
  font-weight: 850;
  letter-spacing: 0.04em;
}

.trial-card__title {
  margin-top: 12px;
  color: var(--logistics-text);
  font-size: 17px;
  font-weight: 850;
}

.trial-card__desc {
  margin-top: 8px;
  color: #65768a;
  font-size: 13px;
  line-height: 1.75;
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.capability-item {
  padding: 12px 10px;
  border-radius: 18px;
  background: #ffffff;
  border: 1px solid #e1eaf1;
  text-align: center;
}

.capability-item__num {
  font-size: 20px;
  line-height: 1.15;
  font-weight: 900;
  color: var(--logistics-blue);
}

.capability-item--clarify .capability-item__num {
  color: var(--logistics-amber);
}

.capability-item--unsupported .capability-item__num {
  color: #596b7d;
}

.capability-item__label {
  margin-top: 5px;
  color: #6b7d91;
  font-size: 12px;
}

.trial-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.trial-list li {
  position: relative;
  padding-left: 16px;
  color: #4e6075;
  font-size: 13px;
  line-height: 1.7;
}

.trial-list li::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0.75em;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--logistics-blue);
}

.trial-note {
  padding: 14px;
  border-radius: 18px;
  background: #f5f9fc;
  border: 1px solid #dfeaf2;
  color: #52677b;
  font-size: 13px;
  line-height: 1.75;
}

@media (max-width: 1180px) {
  .data-qa-chat-page {
    height: auto;
    min-height: calc(100vh - 88px);
    overflow: auto;
  }

  .data-qa-shell {
    grid-template-columns: 1fr;
    height: auto;
  }

  .chat-main {
    min-height: calc(100vh - 112px);
  }

  .trial-panel {
    height: auto;
    overflow: visible;
  }
}

@media (max-width: 767px) {
  .data-qa-chat-page {
    padding: 10px;
    min-height: calc(100vh - 72px);
  }

  .chat-main {
    border-radius: 22px;
  }

  .chat-toolbar {
    padding: 14px;
  }

  .chat-toolbar__actions,
  .chat-toolbar__actions :deep(.el-button) {
    width: 100%;
  }

  .chat-thread__inner {
    padding: 18px 12px 20px;
  }

  .chat-welcome {
    padding: 30px 4px 20px;
  }

  .chat-welcome__examples {
    grid-template-columns: 1fr;
  }

  .chat-bubble,
  .chat-message--user .chat-bubble,
  .chat-message--assistant .chat-bubble {
    max-width: 100%;
  }

  .chat-bubble__title-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .chat-composer {
    padding: 10px 12px 14px;
  }

  .chat-composer__footer {
    align-items: stretch;
  }

  .chat-composer__footer :deep(.el-button) {
    width: 100%;
  }

  .capability-grid {
    grid-template-columns: 1fr;
  }
}

/* 极简对话页：去掉介绍面板与装饰性布局，靠近 ChatGPT 的单列、留白和固定输入体验。 */
.data-qa-chat-page {
  --logistics-text: #111827;
  --logistics-muted: #6b7280;
  --logistics-line: #e5e7eb;
  --logistics-soft: #f7f7f8;
  --logistics-user: #f3f4f6;
  width: 100%;
  height: calc(100vh - 72px);
  min-height: 640px;
  padding: 0;
  overflow: hidden;
  background: #ffffff;
  color: var(--logistics-text);
}

.data-qa-shell {
  display: block;
  width: 100%;
  height: 100%;
  margin: 0;
}

.chat-main {
  width: 100%;
  max-width: none;
  height: 100%;
  margin: 0;
  border: 0;
  border-radius: 0;
  box-shadow: none;
  background: #ffffff;
}

.chat-toolbar {
  height: 56px;
  flex: none;
  align-items: center;
  padding: 0 24px;
  border-bottom: 1px solid var(--logistics-line);
  background: rgba(255, 255, 255, 0.96);
}

.chat-toolbar__main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.chat-toolbar__menu {
  width: 34px;
  height: 34px;
  color: #4b5563;
  border: 0;
  background: transparent;
}

.chat-toolbar__menu:hover {
  background: var(--logistics-soft);
}

.chat-toolbar__title {
  margin: 0;
  color: #111827;
  font-size: 15px;
  font-weight: 650;
  letter-spacing: 0;
}

.chat-toolbar__history {
  color: #4b5563;
  font-weight: 500;
}

.chat-thread {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0;
  background: #ffffff;
}

.chat-thread__inner {
  width: min(820px, calc(100% - 32px));
  min-height: 100%;
  margin: 0 auto;
  gap: 30px;
  padding: 44px 0 28px;
}

.chat-welcome {
  margin: auto 0;
  padding: 0 0 88px;
}

.chat-welcome__title {
  margin: 0;
  color: #111827;
  font-size: clamp(28px, 4vw, 36px);
  line-height: 1.2;
  font-weight: 600;
  letter-spacing: -0.03em;
}

.chat-turn {
  gap: 18px;
}

.chat-message--user {
  justify-content: flex-end;
}

.chat-message--assistant {
  justify-content: flex-start;
}

.chat-message--user .chat-bubble {
  max-width: min(660px, 78%);
}

.chat-message--assistant .chat-bubble {
  max-width: min(820px, 100%);
}

.chat-bubble {
  border-radius: 18px;
  padding: 14px 16px;
  box-shadow: none;
}

.chat-bubble--user {
  background: var(--logistics-user);
  color: #111827;
}

.chat-bubble--assistant {
  width: 100%;
  border: 0;
  background: transparent;
  padding-left: 0;
  padding-right: 0;
}

.chat-bubble--loading {
  width: auto;
  min-width: 220px;
  padding: 14px 16px;
  border: 1px solid var(--logistics-line);
  background: #ffffff;
}

.chat-bubble--ok,
.chat-bubble--clarify,
.chat-bubble--unsupported,
.chat-bubble--empty,
.chat-bubble--error {
  border-left: 0;
}

.chat-bubble__header {
  align-items: center;
  margin-bottom: 8px;
}

.chat-bubble__meta {
  color: #9ca3af;
  font-size: 12px;
}

.chat-bubble__content {
  margin-top: 4px;
  color: inherit;
  line-height: 1.7;
}

.chat-bubble__title-row {
  align-items: flex-start;
  margin-top: 0;
}

.chat-bubble__title {
  color: #111827;
  font-size: 17px;
  line-height: 1.75;
  font-weight: 650;
}

.chat-bubble__mini-stat {
  margin-top: 4px;
  padding: 4px 9px;
  border-radius: 999px;
  background: #eef2ff;
  color: #4f46e5;
  font-size: 12px;
  font-weight: 600;
}

.chat-bubble__desc {
  margin-top: 8px;
  color: var(--logistics-muted);
  line-height: 1.7;
}

.chat-question-list,
.chat-empty-tips,
.chat-unsupported-tips,
.chat-warning-list {
  margin-top: 14px;
}

.chat-question-list__item,
.chat-empty-tips__item,
.chat-unsupported-tips__item {
  border-radius: 14px;
  border: 1px solid var(--logistics-line);
  background: #ffffff;
  color: #374151;
}

.chat-question-list__index {
  background: var(--logistics-soft);
  color: #374151;
}

.chat-suggestion-row {
  margin-top: 12px;
}

.chat-suggestion-chip {
  border-color: var(--logistics-line);
  background: #ffffff;
  color: #374151;
}

.chat-suggestion-chip:hover,
.chat-suggestion-chip:focus-visible {
  border-color: #9ca3af;
  background: var(--logistics-soft);
}

.chat-table-card {
  margin-top: 14px;
  border-color: var(--logistics-line);
  border-radius: 14px;
  background: #ffffff;
}

.chat-result-table :deep(.el-table__header th) {
  background: #fafafa;
  color: #4b5563;
}

.chat-bubble__actions {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--logistics-line);
}

.chat-bubble__actions :deep(.el-button) {
  border-radius: 999px;
}

.chat-bubble__role {
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
}

.presentation-highlights {
  margin-top: 14px;
  display: grid;
  gap: 8px;
}

.presentation-highlights__item {
  padding: 10px 12px;
  border: 1px solid var(--logistics-line);
  border-radius: 12px;
  background: #fafafa;
  color: #374151;
  line-height: 1.65;
}

.presentation-cards {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
  gap: 10px;
}

.presentation-card {
  padding: 14px;
  border: 1px solid var(--logistics-line);
  border-radius: 14px;
  background: #ffffff;
}

.presentation-card__label {
  color: #6b7280;
  font-size: 12px;
}

.presentation-card__value {
  margin-top: 6px;
  color: #111827;
  font-size: 22px;
  line-height: 1.25;
  font-weight: 700;
}

.presentation-card__value span {
  margin-left: 3px;
  color: #6b7280;
  font-size: 13px;
  font-weight: 500;
}

.presentation-card__desc {
  margin-top: 6px;
  color: #6b7280;
  font-size: 12px;
  line-height: 1.55;
}

.presentation-chart {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid var(--logistics-line);
  border-radius: 16px;
  background: #ffffff;
}

.presentation-chart__title {
  margin-bottom: 8px;
  color: #374151;
  font-size: 13px;
  font-weight: 600;
}

.presentation-chart__svg {
  width: 100%;
  height: 220px;
  display: block;
  overflow: visible;
}

.presentation-chart__line {
  stroke: #2563eb;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.presentation-chart__point,
.presentation-chart__bar {
  fill: #2563eb;
}

.presentation-chart__bar {
  opacity: 0.82;
}

.presentation-chart__label {
  fill: #6b7280;
  font-size: 11px;
}

.presentation-caveats {
  margin-top: 12px;
  display: grid;
  gap: 6px;
}

.presentation-caveats__item {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.6;
}

.chat-advanced-item,
.chat-mono-block {
  border-color: var(--logistics-line);
  background: #fafafa;
}

.chat-loading__dot {
  background: #9ca3af;
}

.chat-composer {
  flex: none;
  padding: 14px 16px 18px;
  background: #ffffff;
  border-top: 1px solid rgba(229, 231, 235, 0.72);
}

.chat-composer__box {
  width: min(820px, 100%);
  margin: 0 auto;
  padding: 12px 14px 10px;
  border: 1px solid #d1d5db;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 8px 24px rgba(17, 24, 39, 0.08);
}

.chat-composer__label {
  display: none;
}

.chat-composer__input :deep(.el-textarea__inner) {
  min-height: 44px !important;
  padding: 2px 2px 8px;
  color: #111827;
  font-size: 15px;
  line-height: 1.7;
}

.chat-composer__footer {
  margin-top: 8px;
  align-items: center;
}

.chat-composer__hint {
  color: #9ca3af;
  font-size: 12px;
}

.chat-composer__footer :deep(.el-button) {
  min-width: auto;
  border-radius: 999px;
}

.trial-panel,
.chat-welcome__badge,
.chat-welcome__desc,
.chat-welcome__examples,
.brand-lockup,
.chat-toolbar__center,
.chat-bubble__action-hint {
  display: none;
}

@media (max-width: 767px) {
  .data-qa-chat-page {
    height: calc(100vh - 56px);
    min-height: 560px;
    padding: 0;
  }

  .chat-toolbar {
    height: 52px;
    padding: 0 12px;
    flex-direction: row;
  }

  .chat-toolbar__history {
    padding-left: 8px;
    padding-right: 8px;
  }

  .chat-thread__inner {
    width: calc(100% - 24px);
    padding-top: 28px;
  }

  .chat-message--user .chat-bubble,
  .chat-message--assistant .chat-bubble {
    max-width: 100%;
  }

  .chat-composer {
    padding: 10px 10px 12px;
  }

  .chat-composer__footer {
    gap: 8px;
  }
}
</style>
