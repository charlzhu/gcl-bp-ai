<template>
  <div class="nqe-chat-page">
    <el-header class="nqe-header">
      <h2>NQE 统一 SQL Agent</h2>
      <el-tag type="info" size="small">开发环境</el-tag>
    </el-header>

    <!-- message area -->
    <div class="messages" ref="msgList">
      <div v-if="messages.length === 0" class="empty-state">输入问题开始查询</div>
      <div v-for="(m,i) in messages" :key="i" :class="['msg-bubble', m.role]">
        <div class="msg-role">{{ m.role==='user'?'你':'NQE' }}</div>
        <div class="msg-content">
          <div v-if="m.role==='user'">{{ m.text }}</div>
          <div v-else>
            <div v-if="m.steps?.length" class="msg-progress">
              <span v-for="(s,j) in m.steps" :key="j" class="step-tag">{{ s.step || s.message }}</span>
            </div>
            <div v-if="m.answer" class="msg-answer">{{ m.answer }}</div>
            <div v-if="m.error" class="msg-error">{{ m.error }}</div>
            <div v-if="m.row_count != null" class="msg-meta">返回 {{ m.row_count }} 行</div>
          </div>
        </div>
      </div>
      <div v-if="loading" class="msg-bubble assistant">
        <div class="msg-role">NQE</div>
        <div class="msg-content"><el-icon class="is-loading"><Loading /></el-icon> 处理中...</div>
      </div>
    </div>

    <!-- input area -->
    <div class="input-area">
      <el-input v-model="question" type="textarea" :rows="2" placeholder="输入经营计划相关问题..." @keyup.enter.ctrl="send" :disabled="loading" />
      <div class="input-actions">
        <el-button type="primary" @click="send" :loading="loading" :disabled="loading">发送</el-button>
        <el-button v-if="loading" type="danger" @click="stop">停止</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onUnmounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'

interface Message { role: 'user'|'assistant'; text?: string; answer?: string; steps?: any[]; error?: string; row_count?: number }

const question = ref('')
const loading = ref(false)
const result = ref<any>(null)
const messages = ref<Message[]>([])
const msgList = ref<HTMLElement|null>(null)
let es: EventSource | null = null

const scrollToBottom = () => nextTick(() => { const el=msgList.value; if(el) el.scrollTop=el.scrollHeight })

const addMsg = (m: Message) => { messages.value.push(m); scrollToBottom() }

const send = () => {
  if (!question.value.trim() || loading.value) return
  const q = question.value.trim()
  question.value = ''
  addMsg({ role: 'user', text: q })
  
  loading.value = true
  const steps: any[] = []
  const tid = `nqe-${Date.now()}`
  
  // Clean up any existing connection
  if (es) { es.close(); es = null }
  
  const url = `/api/v1/nqe/query/stream?question=${encodeURIComponent(q)}&trace_id=${tid}`
  es = new EventSource(url)

  es.addEventListener('progress', (e: any) => {
    const d = JSON.parse(e.data)
    steps.push({ step: d.step || d.message, status: 'process' })
  })
  es.addEventListener('result', (e: any) => {
    const d = JSON.parse(e.data)
    addMsg({ role: 'assistant', steps: [...steps], answer: d.answer || d.status, row_count: d.row_count })
    loading.value = false
    es?.close(); es = null
  })
  es.addEventListener('error', (e: any) => {
    const d = e.data ? JSON.parse(e.data) : {}
    addMsg({ role: 'assistant', error: d.error || '查询失败' })
    loading.value = false
    es?.close(); es = null
  })
  es.addEventListener('done', () => {
    if (loading.value) {
      addMsg({ role: 'assistant', steps: [...steps], answer: '查询完成' })
      loading.value = false
    }
    es?.close(); es = null
  })
  es.onerror = () => {
    if (loading.value) { addMsg({ role: 'assistant', error: '连接中断' }); loading.value = false }
    es?.close(); es = null
  }
}

const stop = () => {
  if (es) { es.close(); es = null }
  loading.value = false
}
onUnmounted(() => { if (es) { es.close(); es = null } })
</script>

<style scoped>
.nqe-chat-page { display:flex; flex-direction:column; height:100vh; max-width:900px; margin:0 auto; }
.nqe-header { display:flex; align-items:center; gap:12px; padding:16px 0; border-bottom:1px solid #e4e7ed; }
.messages { flex:1; overflow-y:auto; padding:16px 0; }
.empty-state { text-align:center; color:#909399; padding:60px 0; }
.msg-bubble { margin-bottom:16px; }
.msg-role { font-size:12px; color:#909399; margin-bottom:4px; }
.msg-bubble.user .msg-role { text-align:right; }
.msg-content { background:#f5f7fa; border-radius:8px; padding:12px; }
.msg-bubble.user .msg-content { background:#ecf5ff; }
.msg-answer { white-space:pre-wrap; margin-top:4px; }
.msg-error { color:#f56c6c; margin-top:4px; }
.msg-meta { font-size:12px; color:#909399; margin-top:4px; }
.msg-progress { display:flex; flex-wrap:wrap; gap:4px; margin-bottom:4px; }
.step-tag { font-size:11px; background:#e6f7ff; padding:2px 6px; border-radius:3px; }
.input-area { padding:12px 0; border-top:1px solid #e4e7ed; }
.input-actions { display:flex; gap:8px; margin-top:8px; }
</style>
