<template>
  <div>
    <div class="page-card" style="margin-bottom: 20px">
      <h2 class="page-title">自然语言查询</h2>
      <p class="page-subtitle">
        面向业务人员的自然语言入口。当前优先联调后端的
        <code>/api/v1/logistics/nl2query/parse-and-query</code> 接口，
        用于查看问题解析、模板命中、执行绑定、结果解释和空结果分析。
      </p>

      <el-form @submit.prevent>
        <el-form-item label="问题">
          <el-input
            v-model="question"
            type="textarea"
            :rows="4"
            placeholder="例如：2025年3月运量是多少；合同编号GCL5010ZJ202503015的明细"
          />
        </el-form-item>

        <el-space>
          <el-button type="primary" :loading="loading" @click="handleQuery">开始查询</el-button>
          <el-button @click="fillExample('2025年3月运量是多少')">示例1</el-button>
          <el-button @click="fillExample('25年3月和26年3月发货量对比')">示例2</el-button>
          <el-button @click="fillExample('合同编号GCL5010ZJ202503015的明细')">示例3</el-button>
        </el-space>
      </el-form>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <ParsedResultCard :parsed="resultData?.parsed ?? null" />
      </el-col>
      <el-col :span="12">
        <QueryResultCard
          :query-result="resultData?.query_result ?? null"
          :parsed="resultData?.parsed ?? null"
          :question="resultData?.question ?? question"
          :request-payload="{ question: question.trim() }"
          :response-meta="resultData?.response_meta ?? null"
          @open-detail="openDetail"
          @row-detail="openRowDetail"
        />
      </el-col>
    </el-row>
    <div class="page-card" style="margin-top: 20px" v-if="resultData">
      <el-collapse>
        <el-collapse-item title="查看完整响应（调试）" name="raw-response">
          <div class="mono-block">{{ JSON.stringify(resultData, null, 2) }}</div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchNLQuery } from '@/api/logistics'
import ParsedResultCard from '@/components/ParsedResultCard.vue'
import QueryResultCard from '@/components/QueryResultCard.vue'
import {
  getLastQueryContext,
  getQueryPageDraft,
  saveLastQueryContext,
  saveQueryPageDraft,
} from '@/utils/queryStorage'

const router = useRouter()
const question = ref('2025年3月运量是多少')
const loading = ref(false)
const resultData = ref<Record<string, any> | null>(null)

/** 填充示例问题，便于快速联调。 */
function fillExample(value: string) {
  question.value = value
}

/**
 * 保存最近一次查询上下文。
 */
function persistContext(selectedRow: Record<string, any> | null = null) {
  if (!resultData.value) return
  saveLastQueryContext({
    sourcePage: 'nl-query',
    question: question.value.trim(),
    requestPayload: { question: question.value.trim() },
    rawResponse: resultData.value,
    parsed: resultData.value.parsed ?? null,
    queryResult: resultData.value.query_result ?? null,
    selectedRow,
  })
}

/**
 * 恢复自然语言查询页草稿和最近一次结果。
 * 说明：
 * 1. 先恢复未提交的输入草稿；
 * 2. 再恢复最近一次已执行查询的结果，保证从明细页返回时不丢上下文；
 * 3. 只恢复当前页面自己的缓存，避免误把条件查询页的结果带进来。
 */
function restorePageState() {
  const draft = getQueryPageDraft('nl-query')
  if (draft?.formData?.question) {
    question.value = String(draft.formData.question)
  }

  const context = getLastQueryContext()
  if (context?.sourcePage !== 'nl-query') return

  if (context.question) {
    question.value = context.question
  }

  if (context.rawResponse && typeof context.rawResponse === 'object') {
    resultData.value = context.rawResponse
    return
  }

  if (context.parsed || context.queryResult) {
    resultData.value = {
      question: context.question,
      parsed: context.parsed ?? null,
      query_result: context.queryResult ?? null,
    }
  }
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

/** 调用后端自然语言查询接口，并将完整结果挂到页面。 */
async function handleQuery() {
  if (!question.value.trim()) {
    ElMessage.warning('请输入查询问题')
    return
  }

  loading.value = true
  try {
    const resp = await fetchNLQuery({ question: question.value.trim() })
    resultData.value = resp.data ?? resp
    persistContext()
    ElMessage.success('查询成功')
  } catch (error) {
    ElMessage.error('查询失败，请检查后端接口或请求参数')
    throw error
  } finally {
    loading.value = false
  }
}

/**
 * 持续缓存输入草稿。
 * 说明：
 * 即使用户还没有点击查询，也尽量保住当前问题文本。
 */
watch(
  question,
  (value) => {
    saveQueryPageDraft({
      sourcePage: 'nl-query',
      formData: {
        question: value,
      },
    })
  },
  { immediate: true },
)

onMounted(() => {
  restorePageState()
})
</script>
