<template>
  <div class="nl-page" :class="{ 'nl-page--conversation': hasResult }">
    <section v-if="!hasResult" class="nl-landing">
      <div class="nl-landing__badge">自然语言查询</div>
      <h2 class="nl-landing__title">准备好了，随时开始</h2>
      <p class="nl-landing__desc">
        直接输入业务问题，系统会自动完成条件识别、结果查询和说明展示。
      </p>
      <p class="nl-landing__note">当前已开通物流业务问答，BOM 自然语言问答后续接入。</p>
      <div class="nl-landing__tips">
        <span>支持月度统计</span>
        <span>支持合同明细</span>
        <span>支持历史与系统统一查询</span>
      </div>
    </section>

    <section v-if="hasResult" class="nl-chat-shell">
      <div ref="conversationRef" class="nl-conversation">
        <div class="nl-thread">
          <template v-for="item in chatItems" :key="item.id">
            <div class="nl-thread__question">
              <div class="nl-thread-card nl-thread-card--question">
                <div class="nl-thread-card__label">提问时间 {{ formatDisplayTime(item.askedAt) }}</div>
                <div class="nl-thread-card__content">{{ item.question }}</div>
              </div>
            </div>

            <div class="nl-thread__answer">
              <div class="nl-thread-card nl-thread-card--answer">
                <div class="nl-thread-card__label">回答时间 {{ formatDisplayTime(item.answeredAt) }}</div>
                <div class="nl-direct-answer">
                  <div class="nl-direct-answer__status" :class="`nl-direct-answer__status--${buildAnswerView(item).tone}`">
                    {{ buildAnswerView(item).statusLabel }}
                  </div>
                  <div class="nl-direct-answer__title">{{ buildAnswerView(item).title }}</div>
                  <div class="nl-direct-answer__body">{{ buildAnswerView(item).body }}</div>
                  <div v-if="buildAnswerView(item).tip" class="nl-direct-answer__tip">{{ buildAnswerView(item).tip }}</div>
                </div>
                <div class="nl-direct-answer__actions">
                  <el-button
                    v-if="buildPresentation(item).hasItems"
                    text
                    type="primary"
                    @click="expandDetail(item)"
                  >
                    查看详细结果
                  </el-button>
                  <el-button
                    v-if="buildPresentation(item).noResultAnalysis || hasDisplayPayload(item)"
                    text
                    @click="toggleAdvancedInfo(item)"
                  >
                    {{ item.showAdvancedInfo ? '收起补充信息' : '查看补充信息' }}
                  </el-button>
                </div>
              </div>

              <div v-if="item.showAdvancedInfo" class="page-card nl-thread-card nl-thread-card--analysis">
                <QueryResultCard
                  v-if="hasDisplayPayload(item)"
                  :query-result="item.response.query_result ?? null"
                  :parsed="item.response.parsed ?? null"
                  :question="item.question"
                  :request-payload="{ question: item.question }"
                  :response-meta="item.response.response_meta ?? null"
                  :show-template-info="false"
                  @open-detail="openDetail(item)"
                  @row-detail="openRowDetail(item, $event)"
                />
              </div>
            </div>
          </template>
        </div>
      </div>
    </section>

    <section class="page-card nl-composer" :class="{ 'nl-composer--conversation': hasResult }">
      <el-form class="nl-query-form" @submit.prevent>
        <el-form-item label="">
          <el-input
            v-model="question"
            class="nl-query-input"
            :class="{ 'nl-query-input--conversation': hasResult }"
            type="textarea"
            :rows="hasResult ? 1 : 3"
            resize="none"
            placeholder="有问题，尽管问。例如：2025年3月运量是多少；25年3月和26年3月发货量对比；合同编号 GCL5010ZJ202503015 的明细"
            @keydown.enter.exact.prevent="handleQuery"
          />
        </el-form-item>

        <div class="nl-query-actions" :class="{ 'nl-query-actions--conversation': hasResult }">
          <div v-if="!hasResult" class="nl-example-list">
            <button
              type="button"
              class="nl-example-chip"
              @click="fillExample('2025年3月运量是多少')"
            >
              2025 年 3 月运量是多少
            </button>
            <button
              type="button"
              class="nl-example-chip"
              @click="fillExample('25年3月和26年3月发货量对比')"
            >
              25 年 3 月和 26 年 3 月发货量对比
            </button>
            <button
              type="button"
              class="nl-example-chip"
              @click="fillExample('合同编号GCL5010ZJ202503015的明细')"
            >
              合同编号 GCL5010ZJ202503015 的明细
            </button>
          </div>

          <div class="nl-query-actions__submit">
            <span class="nl-query-actions__hint">
              {{ hasResult ? '修改问题后可继续提问。' : '如不确定输入方式，可直接点击示例问题。' }}
            </span>
            <el-button type="primary" size="large" :loading="loading" @click="handleQuery">
              开始查询
            </el-button>
          </div>
        </div>
      </el-form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchNLQuery } from '@/api/logistics'
import QueryResultCard from '@/components/QueryResultCard.vue'
import { buildQueryResultPresentation } from '@/utils/queryResultPresentation'
import {
  buildNLQuerySessionId,
  buildNLQuerySessionTitle,
  getNLQuerySession,
  type NLConversationItem,
  saveNLQuerySession,
} from '@/utils/nlQuerySessions'
import {
  clearLastQueryContext,
  clearQueryPageDraft,
  getQueryPageDraft,
  saveLastQueryContext,
  saveQueryPageDraft,
} from '@/utils/queryStorage'

const router = useRouter()
const route = useRoute()
const question = ref('')
const loading = ref(false)
const chatItems = ref<NLConversationItem[]>([])
const conversationRef = ref<HTMLElement | null>(null)

/** 当前路由下激活的自然语言会话 ID。 */
const activeSessionId = computed(() => {
  return typeof route.query.session === 'string' ? route.query.session : ''
})

/** 当前是否已经拿到可展示的自然语言查询结果。 */
const hasResult = computed(() => chatItems.value.length > 0)

/** 填充示例问题，便于快速联调。 */
function fillExample(value: string) {
  question.value = value
}

/**
 * 恢复空白页输入草稿。
 * 说明：
 * 1. 只在“新聊天”空白页中恢复未发送的问题；
 * 2. 已进入会话页签后，不再用草稿覆盖真实会话内容。
 */
function restoreDraftQuestion() {
  const draft = getQueryPageDraft('nl-query')
  if (draft?.formData?.question) {
    question.value = String(draft.formData.question)
  }
}

/**
 * 根据当前路由中的会话 ID，同步自然语言页的数据来源。
 * 说明：
 * 1. 没有 session 参数时，视为“新聊天”空白页；
 * 2. 有 session 参数时，只从对应会话里恢复历史问答；
 * 3. 如果会话不存在，自动退回空白页，避免页面卡死在失效链接。
 */
async function syncSessionFromRoute() {
  if (!activeSessionId.value) {
    chatItems.value = []
    restoreDraftQuestion()
    await nextTick()
    return
  }

  const session = getNLQuerySession(activeSessionId.value)
  if (!session) {
    ElMessage.warning('当前会话不存在，已返回新聊天页面')
    await router.replace({ path: '/nl-query' })
    return
  }

  chatItems.value = session.items.map((item) => ({ ...item }))
  question.value = ''
  await nextTick()
  scrollConversationToBottom()
}

/**
 * 将当前会话滚动到底部。
 * 说明：
 * 一旦进入多轮会话模式，只滚动聊天区，不滚动整个页面。
 */
function scrollConversationToBottom() {
  if (!conversationRef.value) return
  conversationRef.value.scrollTop = conversationRef.value.scrollHeight
}

/**
 * 保存指定问答的最近一次查询上下文，便于从详情页返回时仍能回到自然语言页。
 */
function persistContext(item: NLConversationItem, selectedRow: Record<string, any> | null = null) {
  saveLastQueryContext({
    sourcePage: 'nl-query',
    question: item.question,
    requestPayload: { question: item.question },
    rawResponse: item.response,
    parsed: item.response.parsed ?? null,
    queryResult: item.response.query_result ?? null,
    selectedRow,
  })
}

/**
 * 以当前会话为单位持久化自然语言页签数据。
 * 说明：
 * 1. 只有已经形成真实会话 ID 的页面才会写入会话存储；
 * 2. 标题固定取首问，避免每轮提问导致左侧页签不断跳变。
 */
function persistCurrentSession(sessionId: string, items: NLConversationItem[]) {
  if (!items.length) return

  saveNLQuerySession({
    id: sessionId,
    title: buildNLQuerySessionTitle(items[0].question),
    items,
    updatedAt: items[items.length - 1].answeredAt,
  })
}

/**
 * 打开完整明细页。
 */
function openDetail(item: NLConversationItem) {
  persistContext(item)
  router.push('/detail-view')
}

/**
 * 打开带有选中行的明细页。
 */
function openRowDetail(item: NLConversationItem, row: Record<string, any>) {
  persistContext(item, row)
  router.push('/detail-view')
}

/** 主答案区点击“查看详细结果”时，直接展开补充信息区。 */
function expandDetail(item: NLConversationItem) {
  item.showAdvancedInfo = true
  if (activeSessionId.value) {
    persistCurrentSession(activeSessionId.value, chatItems.value)
  }
}

/** 切换单条问答的补充信息展示状态。 */
function toggleAdvancedInfo(item: NLConversationItem) {
  item.showAdvancedInfo = !item.showAdvancedInfo
  if (activeSessionId.value) {
    persistCurrentSession(activeSessionId.value, chatItems.value)
  }
}

/**
 * 调用后端自然语言查询接口，并把本轮问答追加到当前会话。
 * 说明：
 * 1. 如果当前还没有会话 ID，首轮成功后再创建会话页签；
 * 2. 后续提问只追加，不覆盖前面的问答；
 * 3. 提问模块始终保留在页面底部，只有聊天区域滚动。
 */
async function handleQuery() {
  const questionText = question.value.trim()
  if (!questionText) {
    ElMessage.warning('请输入查询问题')
    return
  }

  const askedAt = new Date().toISOString()
  loading.value = true

  try {
    const resp = await fetchNLQuery({ question: questionText })
    const response = (resp.data ?? resp) as Record<string, any>
    const answeredAt = new Date().toISOString()
    const item = buildConversationItem(questionText, response, askedAt, answeredAt)
    const nextItems = [...chatItems.value, item]
    const nextSessionId = activeSessionId.value || buildNLQuerySessionId()

    chatItems.value = nextItems
    persistCurrentSession(nextSessionId, nextItems)
    persistContext(item)
    question.value = ''
    clearQueryPageDraft('nl-query')

    if (!activeSessionId.value) {
      await router.replace({ path: '/nl-query', query: { session: nextSessionId } })
    }

    await nextTick()
    scrollConversationToBottom()
    ElMessage.success('查询成功')
  } catch (error) {
    ElMessage.error('查询失败，请稍后重试；如持续失败请联系技术支持')
    throw error
  } finally {
    loading.value = false
  }
}

/**
 * 持续缓存空白页输入草稿。
 * 说明：
 * 只有在“新聊天”空白页里才缓存草稿，避免覆盖已存在会话。
 */
watch(
  question,
  (value) => {
    if (activeSessionId.value) return
    saveQueryPageDraft({
      sourcePage: 'nl-query',
      formData: {
        question: value,
      },
    })
  },
  { immediate: true },
)

watch(
  () => route.query.session,
  async () => {
    await syncSessionFromRoute()
  },
  { immediate: true },
)

onMounted(() => {
  restoreDraftQuestion()
})

/**
 * 将直接回答里出现的数值做最小格式化，避免主答案区直接展示太长原始数字串。
 */
function formatAnswerValue(value: unknown) {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value.toLocaleString()
  }
  if (typeof value === 'string' && value.trim()) {
    const numeric = Number(value)
    if (Number.isFinite(numeric)) {
      return numeric.toLocaleString()
    }
    return value
  }
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}

/** 将 ISO 时间格式化成 hh:mm:ss，便于自然语言问答区按真实时间展示。 */
function formatDisplayTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '--:--:--'
  return date.toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

/** 构建单条会话项，确保后续多轮提问不会覆盖前面的结果。 */
function buildConversationItem(
  questionText: string,
  response: Record<string, any>,
  askedAt: string,
  answeredAt: string,
): NLConversationItem {
  return {
    id: `nl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    question: questionText,
    response,
    askedAt,
    answeredAt,
    showAdvancedInfo: false,
  }
}

/** 为指定问答构建统一展示视图，避免多轮问答共享同一份计算结果。 */
function buildPresentation(item: NLConversationItem) {
  return buildQueryResultPresentation({
    queryResult: item.response.query_result ?? null,
    parsed: item.response.parsed ?? null,
    question: item.question,
    requestPayload: { question: item.question },
    responseMeta: item.response.response_meta ?? null,
  })
}

/** 判断某条问答是否已有可展示的完整查询载荷。 */
function hasDisplayPayload(item: NLConversationItem) {
  return Boolean(item.response.query_result || item.response.response_meta || item.response.parsed)
}

/** 为指定问答提炼自然语言页主视觉里的直接回答，避免多轮问答互相覆盖。 */
function buildAnswerView(item: NLConversationItem) {
  const view = buildPresentation(item)
  const summaryEntries = view.summaryEntries

  if (view.noResultAnalysis) {
    return {
      tone: 'warning',
      statusLabel: '未找到结果',
      title: '当前没有查到符合条件的结果',
      body: view.noResultAnalysis.possible_reasons[0] || '当前条件下没有命中数据。',
      tip: view.noResultAnalysis.suggestions[0] || '建议换一个问题表达或放宽筛选条件后重试。',
    }
  }

  if (view.showCompareSummary) {
    const leftLabel = item.response.query_result?.left_label || '左侧结果'
    const rightLabel = item.response.query_result?.right_label || '右侧结果'
    const leftValue = formatAnswerValue(item.response.query_result?.left_value)
    const rightValue = formatAnswerValue(item.response.query_result?.right_value)
    const diffValue = formatAnswerValue(item.response.query_result?.diff_value)
    return {
      tone: 'success',
      statusLabel: '已完成对比',
      title: `${leftLabel} 与 ${rightLabel} 已完成对比`,
      body: `左侧为 ${leftValue}，右侧为 ${rightValue}，差值为 ${diffValue}。`,
      tip: null,
    }
  }

  if (summaryEntries.length > 0) {
    const primaryEntry = summaryEntries[0]
    const secondaryEntry = summaryEntries[1]
    return {
      tone: 'success',
      statusLabel: '已找到结果',
      title: `${primaryEntry.label}：${formatAnswerValue(primaryEntry.value)}`,
      body: secondaryEntry
        ? `${secondaryEntry.label}：${formatAnswerValue(secondaryEntry.value)}`
        : view.resultExplanation?.summary || '查询已完成。',
      tip: null,
    }
  }

  return {
    tone: view.status.severity === 'warning' ? 'warning' : 'success',
    statusLabel: view.status.success ? '查询完成' : '查询失败',
    title: view.resultExplanation?.summary || view.status.message || '查询已完成',
    body: view.resultExplanation?.highlights[0] || '如需进一步核对，可展开查看详细结果。',
    tip: view.status.success ? null : '请稍后重试；如持续失败，请联系管理员或技术支持。',
  }
}
</script>

<style scoped>
.nl-page {
  width: 100%;
  max-width: 1180px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 28px;
  min-height: calc(100vh - 210px);
}

.nl-page:not(.nl-page--conversation) {
  justify-content: center;
  padding: 32px 0 40px;
}

.nl-page--conversation {
  height: calc(100vh - 150px);
  max-height: calc(100vh - 150px);
  min-height: calc(100vh - 150px);
  gap: 18px;
}

.nl-landing {
  max-width: 780px;
  margin: 0 auto;
  text-align: center;
}

.nl-landing__badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 7px 14px;
  background: #eef6fb;
  color: #1f5f95;
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 18px;
}

.nl-landing__title {
  margin: 0;
  font-size: 44px;
  line-height: 1.18;
  color: #172f49;
  letter-spacing: -0.04em;
}

.nl-landing__desc {
  margin: 18px auto 0;
  max-width: 720px;
  color: #667784;
  font-size: 16px;
  line-height: 1.9;
}

.nl-landing__note {
  margin: 14px auto 0;
  color: #7a8894;
  font-size: 13px;
  line-height: 1.8;
}

.nl-landing__tips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
  margin-top: 24px;
}

.nl-landing__tips span {
  display: inline-flex;
  align-items: center;
  padding: 9px 15px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid #dde8ef;
  color: #496173;
  font-size: 13px;
}

.nl-chat-shell {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.nl-conversation {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 6px;
}

.nl-conversation::-webkit-scrollbar {
  width: 8px;
}

.nl-conversation::-webkit-scrollbar-thumb {
  background: #d7e3ea;
  border-radius: 999px;
}

.nl-thread {
  max-width: 920px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding-bottom: 12px;
}

.nl-thread__question {
  display: flex;
  justify-content: flex-end;
}

.nl-thread__answer {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.nl-thread-card {
  max-width: 920px;
  border-radius: 22px;
}

.nl-thread-card--question {
  width: min(720px, 100%);
  padding: 22px 24px;
  background: #f1f7fb;
  border: 1px solid #dce7ef;
}

.nl-thread-card--answer {
  width: min(920px, 100%);
  padding: 24px 26px;
  background: #ffffff;
  border: 1px solid #dde6ec;
  box-shadow: 0 14px 34px rgba(28, 56, 84, 0.08);
}

.nl-thread-card--analysis {
  width: min(920px, 100%);
  margin-left: 0;
}

.nl-thread-card__label {
  color: #6f8190;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  margin-bottom: 10px;
}

.nl-thread-card__content {
  color: #18314b;
  font-size: 16px;
  line-height: 1.8;
  white-space: pre-wrap;
}

.nl-direct-answer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.nl-direct-answer__status {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.nl-direct-answer__status--success {
  background: #eef7f0;
  color: #3b7c2a;
}

.nl-direct-answer__status--warning {
  background: #fff6e6;
  color: #b57707;
}

.nl-direct-answer__title {
  color: #17324f;
  font-size: 24px;
  line-height: 1.45;
  font-weight: 700;
}

.nl-direct-answer__body {
  color: #4c6172;
  font-size: 15px;
  line-height: 1.9;
}

.nl-direct-answer__tip {
  color: #7a8894;
  font-size: 13px;
  line-height: 1.7;
}

.nl-direct-answer__actions {
  margin-top: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.nl-composer {
  max-width: 980px;
  width: 100%;
  margin: 0 auto;
  padding: 22px 24px 20px;
  border-radius: 28px;
  border: 1px solid #dbe6ec;
  box-shadow: 0 18px 40px rgba(28, 56, 84, 0.08);
  background: rgba(255, 255, 255, 0.96);
}

.nl-composer--conversation {
  flex-shrink: 0;
  margin-top: auto;
  margin-bottom: 10px;
  padding: 14px 18px 14px;
  //border-radius: 22px;
}

.nl-query-form :deep(.el-form-item) {
  margin-bottom: 0;
}

.nl-query-input :deep(.el-textarea__inner) {
  min-height: 120px !important;
  border-radius: 24px;
  padding: 20px 22px;
  border: 1px solid #d8e4eb;
  background: #ffffff;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92);
  font-size: 15px;
  line-height: 1.9;
}

.nl-query-input--conversation :deep(.el-textarea__inner) {
  min-height: 68px !important;
  padding: 14px 18px;
  border-radius: 20px;
  line-height: 1.65;
}

.nl-query-input :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 3px rgba(48, 113, 185, 0.08);
  border-color: #9dc0dd;
}

.nl-query-actions {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-top: 16px;
}

.nl-query-actions--conversation {
  align-items: center;
  margin-top: 12px;
}

.nl-query-actions__submit {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 14px;
  flex-shrink: 0;
}

.nl-query-actions :deep(.el-button--primary) {
  --el-button-bg-color: #3071b9;
  --el-button-border-color: #3071b9;
  --el-button-hover-bg-color: #225d9d;
  --el-button-hover-border-color: #225d9d;
  --el-button-active-bg-color: #1d4f87;
  --el-button-active-border-color: #1d4f87;
  min-width: 132px;
  border-radius: 999px;
  font-weight: 700;
}

.nl-query-actions__hint {
  color: #71818d;
  font-size: 13px;
}

.nl-example-list {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.nl-example-chip {
  border: 1px solid #d8e5ec;
  background: #f9fbfd;
  color: #365269;
  border-radius: 18px;
  padding: 12px 16px;
  font-size: 13px;
  line-height: 1.6;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nl-example-chip:hover {
  border-color: #aac8dc;
  background: #ffffff;
  transform: translateY(-1px);
}

.page-card {
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid #dde7ed;
  border-radius: 24px;
  box-shadow: 0 16px 38px rgba(34, 60, 86, 0.08);
  //padding: 22px 24px;
}

@media (max-width: 960px) {
  .nl-page--conversation {
    height: auto;
    max-height: none;
    min-height: calc(100vh - 180px);
  }

  .nl-conversation {
    overflow: visible;
  }

  .nl-query-actions {
    flex-direction: column;
    align-items: stretch;
  }

  .nl-query-actions__submit {
    justify-content: space-between;
  }

  .nl-thread-card--question,
  .nl-thread-card--answer,
  .nl-thread-card--analysis,
  .nl-composer,
  .nl-thread {
    width: 100%;
    max-width: 100%;
  }
}
</style>
