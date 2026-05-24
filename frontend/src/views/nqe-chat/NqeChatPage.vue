<template>
  <div class="nqe-chat-page">
    <el-container>
      <el-header class="nqe-header">
        <h2>NQE 统一 SQL Agent</h2>
        <el-tag type="info" size="small">实验入口</el-tag>
      </el-header>
      <el-main class="nqe-main">
        <el-input
          v-model="question"
          type="textarea"
          :rows="2"
          placeholder="请输入经营计划相关问题..."
          @keyup.enter.ctrl="send"
        />
        <el-button type="primary" @click="send" :loading="loading" style="margin-top:12px">
          查询
        </el-button>
        <div v-if="result" class="nqe-result">
          <el-divider />
          <el-descriptions :column="2" border size="small">
            <el-descriptions-item label="业务域">{{ result.domain || '-' }}</el-descriptions-item>
            <el-descriptions-item label="模式">{{ result.mode || '-' }}</el-descriptions-item>
          </el-descriptions>
          <div v-if="result.answer" class="answer-text">{{ result.answer }}</div>
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

async function send() {
  if (!question.value.trim() || loading.value) return
  loading.value = true
  result.value = null
  try {
    const resp = await fetch('/api/v1/business-qa', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question: question.value }),
    })
    const data = await resp.json()
    result.value = {
      domain: data.domain || data._nqe_shadow?.domain || '-',
      mode: data._nqe_shadow?.mode || 'off',
      answer: data.answer || data.final_answer || '-',
      error: data.error,
    }
  } catch (e: any) {
    result.value = { error: e.message || '请求失败' }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.nqe-chat-page { padding: 20px; }
.nqe-header { display: flex; align-items: center; gap: 12px; }
.nqe-result { margin-top: 16px; }
.answer-text { margin-top: 12px; white-space: pre-wrap; }
.error-text { color: #f56c6c; margin-top: 12px; }
</style>
