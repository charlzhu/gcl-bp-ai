<template>
  <div>
    <div class="page-card" style="margin-bottom: 20px">
      <div class="page-header">
        <div>
          <h2 class="page-title">明细视图</h2>
          <p class="page-subtitle">
            用于查看最近一次查询的完整结果、单行详情以及原始响应。
          </p>
        </div>
        <el-space>
          <el-button @click="goBack">返回</el-button>
          <el-button type="danger" plain @click="clearContext">清空上下文</el-button>
        </el-space>
      </div>
    </div>

    <el-alert
      v-if="!context"
      title="当前没有可展示的查询上下文，请先在自然语言查询页或条件查询页执行一次查询。"
      type="warning"
      :closable="false"
      show-icon
      class="page-card"
    />

    <template v-else>
      <div class="page-card" style="margin-bottom: 20px">
        <h3 style="margin-top: 0">查询概览</h3>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="来源页面">{{ context.sourcePage }}</el-descriptions-item>
          <el-descriptions-item label="问题">{{ context.question || '-' }}</el-descriptions-item>
          <el-descriptions-item label="查询类型">{{ context.queryResult?.query_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="来源范围">{{ context.queryResult?.source_scope || '-' }}</el-descriptions-item>
          <el-descriptions-item label="执行模式">{{ context.queryResult?.execution_mode || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态码">{{ context.rawResponse?.response_meta?.status?.code || context.queryResult?.status?.code || '-' }}</el-descriptions-item>
        </el-descriptions>
      </div>

      <div class="page-card" style="margin-bottom: 20px" v-if="context.selectedRow">
        <h3 style="margin-top: 0">上次选中行</h3>
        <div class="mono-block">{{ formatJson(context.selectedRow) }}</div>
      </div>

      <div class="page-card" style="margin-bottom: 20px">
        <h3 style="margin-top: 0">结果明细</h3>
        <ResultTable
          :items="context.queryResult?.items || []"
          title="明细结果"
          @row-detail="showRowDetail"
        />
      </div>

      <div class="page-card" style="margin-bottom: 20px">
        <h3 style="margin-top: 0">汇总结果</h3>
        <div class="mono-block">{{ formatJson(context.queryResult?.summary || {}) }}</div>
      </div>

      <div class="page-card">
        <h3 style="margin-top: 0">完整原始响应</h3>
        <div class="mono-block">{{ formatJson(context.rawResponse || {}) }}</div>
      </div>

      <el-dialog v-model="visible" title="单行详情" width="60%">
        <div class="mono-block">{{ formatJson(selectedRow) }}</div>
      </el-dialog>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ResultTable from '@/components/ResultTable.vue'
import { clearLastQueryContext, getLastQueryContext } from '@/utils/queryStorage'

const router = useRouter()
const context = ref(getLastQueryContext())
const selectedRow = ref<Record<string, any> | null>(null)
const visible = ref(false)

/**
 * 返回上一页。
 */
function goBack() {
  router.back()
}

/**
 * 清理上下文后刷新当前视图。
 */
function clearContext() {
  clearLastQueryContext()
  context.value = null
}

/**
 * 展示单行详情。
 */
function showRowDetail(row: Record<string, any>) {
  selectedRow.value = row
  visible.value = true
}

/**
 * JSON 格式化。
 */
function formatJson(value: unknown) {
  if (!value) return '-'
  return JSON.stringify(value, null, 2)
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}
</style>
