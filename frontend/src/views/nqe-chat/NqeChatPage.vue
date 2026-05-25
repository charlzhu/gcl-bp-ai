<template>
  <div class="nqe-chat-page">
    <el-container>
      <el-header class="nqe-header">
        <h2>NQE 统一 SQL Agent</h2>
        <el-tag type="info" size="small">实验入口</el-tag>
      </el-header>
      <el-main>
        <!-- quick chips (NQE-39) -->
        <div class="chips">
          <el-tag v-for="chip in chips" :key="chip" class="chip" @click="question = chip; send()" effect="plain">{{ chip }}</el-tag>
        </div>
        <el-input v-model="question" type="textarea" :rows="2" placeholder="请输入经营计划相关问题..." @keyup.enter.ctrl="send" />
        <el-button type="primary" @click="send" :loading="loading" style="margin-top:12px">查询</el-button>

        <!-- progress timeline (NQE-36) -->
        <el-timeline v-if="steps.length" class="progress">
          <el-timeline-item v-for="s in steps" :key="s.step" :type="s.status === 'done' ? 'success' : 'primary'" :timestamp="s.ts">{{ s.step }}</el-timeline-item>
        </el-timeline>

        <!-- disambiguation (NQE-38) -->
        <div v-if="disambiguation.length" class="disambig">
          <p>请选择：</p>
          <el-radio-group v-model="selectedCandidate">
            <el-radio v-for="c in disambiguation" :key="c.value" :value="c.value">{{ c.label }}</el-radio>
          </el-radio-group>
        </div>

        <!-- result table (NQE-37) -->
        <div v-if="result" class="nqe-result">
          <el-divider />
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="业务域">{{ result.domain || '-' }}</el-descriptions-item>
            <el-descriptions-item label="模式">{{ result.mode || '-' }}</el-descriptions-item>
            <el-descriptions-item label="耗时">{{ result.elapsed || '-' }}</el-descriptions-item>
          </el-descriptions>
          <div v-if="result.answer" class="answer-text">{{ result.answer }}</div>
          <el-table v-if="result.rows" :data="result.rows" border stripe size="small" style="margin-top:12px">
            <el-table-column v-for="col in result.columns" :key="col" :prop="col" :label="col" />
          </el-table>
          <div v-if="result.error" class="error-text">{{ result.error }}</div>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const question = ref('')
const result = ref<Record<string, any> | null>(null)
const loading = ref(false)
const steps = ref<Array<{step:string;status:string;ts:string}>>([])
const disambiguation = ref<Array<{value:string;label:string}>>([])
const selectedCandidate = ref('')
const chips = ['2024年总发运量', 'BOM评审号查询', '供应商效率对比', '库存周转率']

const send = () => {
  if (!question.value.trim() || loading.value) return
  loading.value = true; result.value = null; steps.value = []
  const tid = `nqe-${Date.now()}`
  
  // NQE-FE-1: real SSE via EventSource
  const url = `/api/v1/nqe/query/stream?question=${encodeURIComponent(question.value)}&trace_id=${tid}`
  const es = new EventSource(url)
  
  es.addEventListener('progress', (e: any) => {
    const d = JSON.parse(e.data)
    steps.value.push({step: d.step||d.message, status: 'process', ts: new Date().toLocaleTimeString()})
  })
  es.addEventListener('sql_generated', (e: any) => {
    const d = JSON.parse(e.data)
    steps.value.push({step: `SQL: ${(d.sql||'').slice(0,100)}`, status: 'process', ts: new Date().toLocaleTimeString()})
  })
  es.addEventListener('result', (e: any) => {
    const d = JSON.parse(e.data)
    result.value = { domain: '-', mode: 'on', answer: d.answer || d.status, columns: d.columns || [], rows: d.rows || [], elapsed: '-' }
  })
  es.addEventListener('error', (e: any) => {
    const err = JSON.parse(e.data||'{}')
    result.value = { error: err.error || 'NQE error' }
    es.close()
    loading.value = false
  })
  es.addEventListener('done', () => {
    steps.value.push({step: '查询完成', status: 'done', ts: new Date().toLocaleTimeString()})
    es.close()
    loading.value = false
  })
  es.onerror = () => { es.close(); loading.value = false }
}
</script>

<style scoped>
.nqe-chat-page { padding: 20px; }
.nqe-header { display:flex; align-items:center; gap:12px; }
.chips { margin-bottom: 12px; }
.chip { margin-right: 8px; cursor: pointer; }
.progress { margin: 16px 0; }
.disambig { margin: 12px 0; padding: 12px; background: #f5f7fa; border-radius: 4px; }
.nqe-result { margin-top: 16px; }
.answer-text { margin-top: 12px; white-space: pre-wrap; }
.error-text { color: #f56c6c; margin-top: 12px; }
</style>
