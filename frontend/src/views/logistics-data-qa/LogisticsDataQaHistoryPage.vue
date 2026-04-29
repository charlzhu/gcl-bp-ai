<template>
  <div class="data-qa-history-page">
    <div class="page-layout">
      <div class="page-main">
        <section class="page-card history-header-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">查询历史记录</h3>
              <p class="section-subtitle">
                查看已经问过的问题和当时保存下来的结果快照，方便回看、核对和继续导出。
              </p>
            </div>
            <el-space wrap>
              <el-button round @click="goDataQaPage">返回智能问答</el-button>
            </el-space>
          </div>

          <div class="history-toolbar">
            <el-input
              v-model="keyword"
              clearable
              placeholder="按问题关键词检索"
              @keyup.enter="searchHistory"
            />
            <el-space>
              <el-button type="primary" :loading="loading" @click="searchHistory">查询</el-button>
              <el-button :disabled="loading" @click="resetFilters">重置</el-button>
            </el-space>
          </div>

          <div class="summary-grid">
            <article class="summary-tile">
              <div class="summary-tile__label">历史记录数</div>
              <div class="summary-tile__value">{{ historyTotal }} 条</div>
            </article>
            <article class="summary-tile">
              <div class="summary-tile__label">本页展示</div>
              <div class="summary-tile__value">{{ historyItems.length }} 条</div>
            </article>
            <article class="summary-tile">
              <div class="summary-tile__label">当前筛选</div>
              <div class="summary-tile__value">{{ currentFilterSummary }}</div>
            </article>
          </div>
        </section>

        <section class="page-card history-list-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">历史记录</h3>
              <p class="section-subtitle">先看问了什么、结果状态和大概查到了什么，再决定是否回看结果。</p>
            </div>
          </div>

          <el-alert
            v-if="warningText"
            :title="warningText"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 16px"
          />

          <div v-loading="loading">
            <div v-if="historyItems.length" class="history-list">
              <article v-for="item in historyItems" :key="item.id" class="history-item">
                <div class="history-item__header">
                  <el-tag :type="resolveLogisticsDataQaHistoryTagType(item)" effect="plain">
                    {{ resolveLogisticsDataQaHistoryStatusLabel(item) }}
                  </el-tag>
                  <span class="history-item__time">{{ formatLogisticsDataQaDateTime(item.created_at) }}</span>
                </div>

                <div class="history-item__question">{{ item.question || '-' }}</div>
                <div class="history-item__summary">{{ resolveLogisticsDataQaHistorySummary(item) }}</div>

                <div class="history-item__footer">
                  <div class="history-item__meta">
                    <span v-if="item.result_count !== undefined">结果 {{ item.result_count }} 条</span>
                    <span v-if="item.id">历史编号 #{{ item.id }}</span>
                  </div>
                  <el-space wrap>
                    <el-button size="small" type="primary" plain @click="replayHistory(item)">回看结果</el-button>
                  </el-space>
                </div>
              </article>
            </div>

            <el-empty
              v-else-if="!loading"
              description="当前还没有物流数据问答历史记录"
            />
          </div>

          <div class="history-pager">
            <el-pagination
              background
              layout="total, prev, pager, next"
              :total="historyTotal"
              :current-page="pager.page"
              :page-size="pager.page_size"
              @current-change="handlePageChange"
            />
          </div>
        </section>
      </div>

      <aside class="page-side">
        <section class="page-card side-card">
          <div class="side-card__title">使用说明</div>
          <ul class="side-list">
            <li>这里展示的是已经留痕的物流数据问答查询记录，适合回看和复核。</li>
            <li>点击“回看结果”后，会回到正式查询页查看当时保存下来的结果快照。</li>
            <li>回看状态下仍可继续导出 Excel 和 CSV，不需要重新发起查询。</li>
          </ul>
        </section>

        <section class="page-card side-card">
          <div class="side-card__title">当前页说明</div>
          <div class="side-card__status">这是历史记录页</div>
          <div class="side-card__message">
            当前页用于查看过去查过的内容；如果你要继续提问，请返回“智能问答”正式页。
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { QueryHistoryItem, QueryHistoryResponse } from '@/api/logistics'
import { fetchLogisticsDataQaHistory } from '@/api/logistics'
import {
  formatLogisticsDataQaDateTime,
  resolveLogisticsDataQaHistoryStatusLabel,
  resolveLogisticsDataQaHistorySummary,
  resolveLogisticsDataQaHistoryTagType,
} from '@/utils/logisticsDataQaHistory'

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const loadError = ref('')
const payload = ref<QueryHistoryResponse | null>(null)
const keyword = ref('')
const pager = reactive({
  page: 1,
  page_size: 12,
})

/**
 * 当前历史列表。
 */
const historyItems = computed(() => payload.value?.items ?? [])

/**
 * 当前历史总数。
 */
const historyTotal = computed(() => payload.value?.total ?? 0)

/**
 * 页面提示文案。
 * 说明：
 * 历史页继续使用业务化提示，不直接暴露接口异常结构。
 */
const warningText = computed(() => payload.value?.load_warning || loadError.value)

/**
 * 当前筛选摘要。
 */
const currentFilterSummary = computed(() => {
  return keyword.value.trim() ? `关键词：${keyword.value.trim()}` : '全部历史'
})

/**
 * 加载物流数据问答历史列表。
 * 说明：
 * 当前继续复用统一查询历史接口，只固定筛选 DATA_QA，不新造平行历史系统。
 */
async function loadHistory() {
  loading.value = true
  loadError.value = ''
  try {
    const resp = await fetchLogisticsDataQaHistory({
      page: pager.page,
      page_size: pager.page_size,
      keyword: keyword.value.trim() || undefined,
    })
    payload.value = (resp.data ?? resp ?? null) as QueryHistoryResponse | null
  } catch (_error) {
    loadError.value = '历史记录加载失败，请稍后重试。'
    payload.value = {
      total: 0,
      page: pager.page,
      page_size: pager.page_size,
      items: [],
      load_warning: null,
    }
  } finally {
    loading.value = false
  }
}

/**
 * 按当前关键词查询历史。
 */
async function searchHistory() {
  pager.page = 1
  await loadHistory()
}

/**
 * 重置历史检索条件。
 */
async function resetFilters() {
  keyword.value = ''
  pager.page = 1
  await loadHistory()
}

/**
 * 切换页码。
 */
async function handlePageChange(page: number) {
  pager.page = page
  await loadHistory()
}

/**
 * 进入正式查询页并触发历史回放。
 * 说明：
 * 历史页不自己重算结果，只把 historyLogId 带回正式查询页，让结果区按历史快照展示。
 */
function replayHistory(item: QueryHistoryItem) {
  router.push({
    path: '/logistics/data-qa',
    query: {
      session: currentSessionId.value || undefined,
      historyLogId: String(item.id),
    },
  })
}

/**
 * 返回正式查询页。
 */
function goDataQaPage() {
  router.push({
    path: '/logistics/data-qa',
    query: currentSessionId.value ? { session: currentSessionId.value } : undefined,
  })
}

/**
 * 从历史页返回时保留当前查询页的会话上下文。
 * 说明：
 * 当前历史页只负责查看历史记录，不额外接管会话切换逻辑。
 */
const currentSessionId = computed(() => {
  return typeof route.query.session === 'string' ? route.query.session : ''
})

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.data-qa-history-page {
  width: 100%;
}

.page-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 280px;
  gap: 20px;
  align-items: start;
}

.page-main {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-side {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.history-header-card,
.history-list-card,
.side-card {
  border-radius: 24px;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.section-title {
  margin: 0;
  color: #18314b;
  font-size: 20px;
  font-weight: 800;
}

.section-subtitle {
  margin: 8px 0 0;
  color: #687887;
  line-height: 1.7;
  font-size: 14px;
}

.history-toolbar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.summary-tile {
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, #fbfdff 0%, #f4f8fb 100%);
  border: 1px solid #e2ebf1;
}

.summary-tile__label {
  color: #708190;
  font-size: 13px;
  margin-bottom: 10px;
}

.summary-tile__value {
  color: #18314b;
  font-size: 17px;
  line-height: 1.5;
  font-weight: 800;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.history-item {
  border-radius: 20px;
  border: 1px solid #dfe8ef;
  padding: 18px 20px;
  background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.history-item:hover {
  border-color: #c8dbea;
  box-shadow: 0 12px 28px rgba(32, 66, 102, 0.08);
  transform: translateY(-1px);
}

.history-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.history-item__time {
  color: #7a8896;
  font-size: 13px;
}

.history-item__question {
  margin-top: 14px;
  color: #18314b;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.7;
}

.history-item__summary {
  margin-top: 10px;
  color: #5d7083;
  font-size: 13px;
  line-height: 1.8;
}

.history-item__footer {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.history-item__meta {
  color: #7a8896;
  font-size: 12px;
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.history-pager {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.side-card__title {
  color: #18314b;
  font-size: 16px;
  font-weight: 800;
  margin-bottom: 14px;
}

.side-list {
  margin: 0;
  padding-left: 18px;
  color: #536476;
  line-height: 1.9;
}

.side-card__status {
  color: #18314b;
  font-size: 15px;
  line-height: 1.8;
  font-weight: 700;
}

.side-card__message {
  margin-top: 10px;
  color: #667889;
  line-height: 1.8;
}

@media (max-width: 1200px) {
  .page-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .section-heading {
    flex-direction: column;
  }

  .history-toolbar {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .history-item__header,
  .history-item__footer {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
