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
          @open-detail="openDetail"
          @row-detail="openRowDetail"
        />
      </el-col>
    </el-row>
    <div class="page-card" style="margin-top: 20px" v-if="resultData">
      <h3 style="margin-top: 0">完整响应</h3>
      <div class="mono-block">{{ JSON.stringify(resultData, null, 2) }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchNLQuery } from '@/api/logistics'
import ParsedResultCard from '@/components/ParsedResultCard.vue'
import QueryResultCard from '@/components/QueryResultCard.vue'
import { saveLastQueryContext } from '@/utils/queryStorage'

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
</script>
