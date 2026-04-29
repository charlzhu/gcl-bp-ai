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
      <div v-if="messages.length === 0" class="empty-panel" data-testid="empty-panel">
        <h1>协鑫集成 经营计划智能助手</h1>
        <p>可以直接输入物流或计划 BOM 业务问题。</p>
        <div class="quick-chips">
          <button v-for="item in examples" :key="item.text" type="button" @click="useExample(item)">
            <strong>{{ item.domain }}</strong>
            <span>{{ item.text }}</span>
          </button>
        </div>
      </div>

      <article
        v-for="message in messages"
        :key="message.id"
        :class="['message', `message--${message.role}`]"
        :data-testid="`chat-message-${message.role}`"
        :data-status="message.status"
        :data-domain="message.domain"
      >
        <div class="message-meta">
          <span>{{ message.role === 'user' ? '我' : '经营计划智能助手' }}</span>
          <em v-if="message.domain !== 'auto'">{{ domainLabelMap[message.domain] }}</em>
        </div>
        <div class="bubble">
          <p v-if="message.content" data-testid="message-content">{{ message.content }}</p>
          <div v-if="message.loading" class="loading" data-testid="message-loading">查询中...</div>
          <div v-if="message.error" class="error" data-testid="message-error">{{ message.error }}</div>

          <div v-if="message.presentation" class="result" data-testid="assistant-result">
            <div v-if="message.presentation.title" class="result-title" data-testid="result-title">{{ message.presentation.title }}</div>
            <p v-if="message.presentation.answer" class="result-answer" data-testid="result-answer">{{ message.presentation.answer }}</p>

            <div v-if="message.presentation.highlights.length" class="highlight-list" data-testid="result-highlights">
              <span v-for="text in message.presentation.highlights" :key="text">{{ text }}</span>
            </div>

            <div v-if="message.presentation.cards.length" class="metric-grid" data-testid="result-cards">
              <div v-for="card in message.presentation.cards" :key="card.label" class="metric-card">
                <div class="metric-label">{{ card.label }}</div>
                <div class="metric-value">{{ card.value }}<small v-if="card.unit">{{ card.unit }}</small></div>
                <div v-if="card.description" class="metric-desc">{{ card.description }}</div>
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
              <div class="section-label">需要补充</div>
              <button
                v-for="followUp in message.presentation.followUps"
                :key="followUp"
                type="button"
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
    </div>

    <form class="composer" data-testid="question-composer" @submit.prevent="submitQuestion()">
      <el-input
        v-model="question"
        type="textarea"
        :rows="2"
        resize="none"
        placeholder="输入业务问题"
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
  table: UnifiedTable | null
  followUps: string[]
  suggestions: string[]
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
  return normalizeResult({
    title: presentation?.title || '物流数据问答结果',
    answer: presentation?.answer || data.answer_summary || data.status?.message || '',
    highlights: filterBusinessTexts(presentation?.highlights || []),
    cards: localizeCards(presentation?.cards || []),
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
  return normalizeResult({
    title: presentation?.title || `计划 BOM 问答结果（${data.classification || '未知'}）`,
    answer: presentation?.answer || data.answer_summary || data.status?.message || '',
    highlights: filterBusinessTexts(presentation?.highlights || []),
    cards: [],
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
    table: normalizeTable(value.table || null),
    followUps: value.followUps || [],
    suggestions: value.suggestions || [],
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

/** 过滤技术口径说明，避免业务主界面出现表名、字段名、SQL 等内部信息。 */
function filterBusinessTexts(items: string[]) {
  const technicalPattern = /[_]|dwd|sql|query|table|字段|口径按|历史明细表|province|city|total_fee/i
  return items.filter((item) => item && !technicalPattern.test(item))
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

onMounted(() => {
  loadActiveSession()
  window.addEventListener(getBusinessChatSessionEventName(), loadActiveSession)
})

onBeforeUnmount(() => {
  window.removeEventListener(getBusinessChatSessionEventName(), loadActiveSession)
})
</script>

<style scoped>
.chat-page {
  height: calc(100vh - 64px);
  display: flex;
  flex-direction: column;
  font-size: 14px;
  background: #ffffff;
  overflow: hidden;
}

.chat-toolbar {
  display: flex;
  justify-content: center;
  padding: 12px 20px 0;
  flex-shrink: 0;
}

.domain-switch {
  --el-border-radius-base: 999px;
}

:deep(.domain-switch .el-radio-button__inner) {
  border-color: #e5e7eb;
  background: #ffffff;
  color: #4b5563;
  font-size: 13px;
  box-shadow: none;
}

:deep(.domain-switch .el-radio-button__original-radio:checked + .el-radio-button__inner) {
  border-color: #dbeafe;
  background: #eff6ff;
  color: #2563eb;
  box-shadow: none;
}

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
  width: 8px;
}

.conversation::-webkit-scrollbar-track {
  background: transparent;
}

.conversation::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: transparent;
}

.conversation:hover::-webkit-scrollbar-thumb {
  background: #d6d9de;
}

.conversation--empty {
  display: flex;
  align-items: center;
  justify-content: center;
  padding-bottom: 180px;
}

.empty-panel {
  width: min(760px, 100%);
  text-align: center;
}

.empty-panel h1 {
  margin: 0 0 8px;
  color: #111827;
  font-size: 28px;
  font-weight: 600;
  letter-spacing: 0;
}

.empty-panel p {
  margin: 0 0 22px;
  color: #6b7280;
  font-size: 14px;
}

.quick-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
}

.quick-chips button {
  max-width: 280px;
  border: 1px solid #e5e7eb;
  border-radius: 999px;
  background: #ffffff;
  color: #4b5563;
  padding: 8px 12px;
  font-size: 13px;
  line-height: 1.4;
  cursor: pointer;
}

.quick-chips button:hover {
  background: #f8fafc;
}

.quick-chips strong {
  margin-right: 6px;
  color: #2f6e42;
  font-weight: 600;
}

.message {
  display: grid;
  gap: 6px;
  margin-bottom: 24px;
}

.message--user {
  justify-items: end;
}

.message-meta {
  display: flex;
  gap: 8px;
  color: #8a919b;
  font-size: 12px;
}

.message-meta em {
  font-style: normal;
  color: #4b8a60;
}

.bubble {
  max-width: min(820px, 92%);
  border-radius: 18px;
  background: transparent;
  padding: 0;
  color: #1f2937;
  line-height: 1.7;
}

.message--user .bubble {
  max-width: min(660px, 88%);
  background: #f3f4f6;
  padding: 10px 14px;
}

.bubble p {
  margin: 0;
}

.loading,
.error {
  font-size: 13px;
}

.error {
  color: #b94a48;
}

.result {
  display: grid;
  gap: 12px;
}

.result-title {
  color: #111827;
  font-weight: 600;
}

.result-answer {
  color: #2d3f4d;
  font-size: 14px;
}

.highlight-list,
.suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.highlight-list span,
.suggestions span {
  border-radius: 999px;
  background: #f0f7f4;
  color: #3f7b50;
  padding: 4px 8px;
  font-size: 12px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}

.metric-card {
  border: 1px solid #eef0f3;
  border-radius: 12px;
  background: #fbfcfd;
  padding: 10px;
}

.metric-label,
.metric-desc,
.section-label {
  color: #6b7b86;
  font-size: 12px;
}

.metric-value {
  margin-top: 4px;
  color: #173653;
  font-size: 20px;
  font-weight: 800;
}

.metric-value small {
  margin-left: 4px;
  font-size: 12px;
}

.result-table {
  font-size: 13px;
  border-radius: 12px;
  overflow: hidden;
}

.follow-up {
  display: grid;
  gap: 8px;
}

.follow-up button {
  width: fit-content;
  border: 1px solid #e0ece5;
  border-radius: 999px;
  background: #ffffff;
  color: #2f6e42;
  padding: 5px 10px;
  font-size: 12px;
  cursor: pointer;
}

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
  box-shadow: 0 12px 34px rgba(31, 41, 55, 0.08);
  flex-shrink: 0;
}

:deep(.composer .el-textarea__inner) {
  border: none;
  box-shadow: none;
  padding: 8px 0;
  font-size: 14px;
  line-height: 1.6;
  background: transparent;
}

:deep(.composer .el-button) {
  border-radius: 999px;
  padding: 0 18px;
}

@media (max-width: 720px) {
  .conversation,
  .composer {
    width: calc(100vw - 32px);
  }
}

@media (max-width: 1100px) {
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
