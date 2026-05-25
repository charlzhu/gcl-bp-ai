<template>
  <div class="nqe-chat-page">
    <el-header class="nqe-header">
      <h2>NQE 统一 SQL Agent</h2>
      <el-tag type="info" size="small">开发环境</el-tag>
    </el-header>

    <!-- messages -->
    <div class="messages" ref="msgList">
      <div v-if="messages.length===0" class="empty-state">输入问题开始查询</div>
      <div v-for="(m,i) in messages" :key="i" :class="['msg-bubble',m.role]">
        <div class="msg-role">{{ m.role==='user'?'你':'NQE' }}</div>
        <div class="msg-content">
          <div v-if="m.role==='user'">{{ m.text }}</div>
          <div v-else>
            <!-- progress timeline -->
            <div v-if="m.progress?.length" class="progress-timeline">
              <div v-for="(p,j) in m.progress" :key="j" :class="['timeline-step', p.status]">
                <span class="step-dot" :class="p.status"></span>
                <span class="step-label">{{ p.label }}</span>
                <span v-if="p.detail" class="step-detail">{{ p.detail }}</span>
              </div>
            </div>
            <div v-if="m.answer" class="msg-answer">{{ m.answer }}</div>
            <div v-if="m.error" class="msg-error">{{ m.error }}</div>
            <div v-if="m.row_count!=null" class="msg-meta">返回 {{ m.row_count }} 行</div>
          </div>
        </div>
      </div>
      <div v-if="loading" class="msg-bubble assistant"><div class="msg-role">NQE</div><div class="msg-content"><el-icon class="is-loading"><Loading /></el-icon> 处理中...</div></div>
    </div>

    <!-- input -->
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

interface Step { label: string; status: string; detail?: string }
interface Message { role:'user'|'assistant'; text?:string; answer?:string; progress?:Step[]; error?:string; row_count?:number }

const question = ref('')
const loading = ref(false)
const messages = ref<Message[]>([])
const msgList = ref<HTMLElement|null>(null)
let es: EventSource|null = null

// NQE-FE-3: progress step definitions (order is significant)
const STEP_ORDER = ['domain_routed','metadata_loaded','sql_generated','safety_checked','explain_checked','sql_executed','result']
const STEP_LABELS: Record<string,string> = {
  domain_routed:'领域识别', metadata_loaded:'加载元数据', sql_generated:'生成SQL',
  safety_checked:'安全校验', explain_checked:'EXPLAIN校验', sql_corrected:'修正SQL', sql_executed:'执行查询', result:'完成'
}

const scrollToBottom = () => nextTick(() => { const el=msgList.value; if(el) el.scrollTop=el.scrollHeight })
const addMsg = (m:Message) => { messages.value.push(m); scrollToBottom() }

const send = () => {
  if (!question.value.trim() || loading.value) return
  const q = question.value.trim(); question.value = ''
  addMsg({ role:'user', text:q })
  loading.value = true
  if (es) { es.close(); es=null }

  // Initialize progress with all steps as pending
  const progress = STEP_ORDER.map(s => ({ label: STEP_LABELS[s]||s, status:'pending' as const, detail:'' }))
  let curIdx = 0

  const url = `/api/v1/nqe/query/stream?question=${encodeURIComponent(q)}&trace_id=nqe-${Date.now()}`
  es = new EventSource(url)

  es.addEventListener('progress', (e:any) => {
    const d = JSON.parse(e.data)
    const stepName = d.step || d.message || ''
    const idx = STEP_ORDER.indexOf(stepName)
    if (idx >= 0) {
      for (let i = curIdx; i < idx; i++) progress[i].status = 'success'
      progress[idx].status = 'running'; curIdx = idx
    }
  })
  es.addEventListener('sql_generated', (e:any) => {
    const d = JSON.parse(e.data)
    const si = STEP_ORDER.indexOf('sql_generated')
    if (si>=0) { progress[si].status='success'; progress[si].detail=(d.sql||'').slice(0,80); curIdx=si+1 }
  })
  es.addEventListener('safety_checked', () => {
    const si = STEP_ORDER.indexOf('safety_checked')
    if (si>=0) { progress[si].status='success'; curIdx=si+1 }
  })
  es.addEventListener('explain_checked', (e:any) => {
    const d = JSON.parse(e.data)
    const si = STEP_ORDER.indexOf('explain_checked')
    if (si>=0) { progress[si].status=d.passed?'success':'error'; progress[si].detail=d.passed?'':'EXPLAIN失败'; curIdx=si+1 }
  })
  es.addEventListener('sql_executed', (e:any) => {
    const d = JSON.parse(e.data)
    const si = STEP_ORDER.indexOf('sql_executed')
    if (si>=0) { progress[si].status='success'; progress[si].detail=`${d.row_count}行`; curIdx=si+1 }
  })
  es.addEventListener('result', (e:any) => {
    const d = JSON.parse(e.data)
    progress.forEach(p => { if (p.status==='pending'||p.status==='running') p.status='success' })
    const ri = STEP_ORDER.indexOf('result')
    if (ri>=0) progress[ri].status='success'
    addMsg({ role:'assistant', progress:[...progress], answer:d.answer||d.status, row_count:d.row_count })
    loading.value = false; es?.close(); es=null
  })
  es.addEventListener('error', (e:any) => {
    const d = e.data ? JSON.parse(e.data) : {}
    const si = STEP_ORDER.indexOf('sql_executed')
    if (si>=0 && progress[si].status==='pending') { progress[si].status='error'; progress[si].detail=d.error||'执行失败' }
    addMsg({ role:'assistant', progress:[...progress], error:d.error||'查询失败' })
    loading.value = false; es?.close(); es=null
  })
  es.addEventListener('done', () => {
    if (loading.value) {
      progress.forEach(p => { if (p.status==='pending'||p.status==='running') p.status='success' })
      addMsg({ role:'assistant', progress:[...progress], answer:'完成' })
      loading.value = false
    }
    es?.close(); es=null
  })
  es.onerror = () => {
    if (loading.value) { addMsg({ role:'assistant', error:'连接中断' }); loading.value = false }
    es?.close(); es=null
  }
}

const stop = () => { if(es){es.close();es=null}; loading.value = false }
onUnmounted(() => { if(es){es.close();es=null} })
</script>

<style scoped>
.nqe-chat-page{display:flex;flex-direction:column;height:100vh;max-width:900px;margin:0 auto}
.nqe-header{display:flex;align-items:center;gap:12px;padding:16px 0;border-bottom:1px solid #e4e7ed}
.messages{flex:1;overflow-y:auto;padding:16px 0}
.empty-state{text-align:center;color:#909399;padding:60px 0}
.msg-bubble{margin-bottom:16px}
.msg-role{font-size:12px;color:#909399;margin-bottom:4px}
.msg-bubble.user .msg-role{text-align:right}
.msg-content{background:#f5f7fa;border-radius:8px;padding:12px}
.msg-bubble.user .msg-content{background:#ecf5ff}
.msg-answer{white-space:pre-wrap;margin-top:8px}
.msg-error{color:#f56c6c;margin-top:8px}
.msg-meta{font-size:12px;color:#909399;margin-top:4px}
/* progress timeline */
.progress-timeline{padding:4px 0}
.timeline-step{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px}
.step-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.step-dot.pending{background:#dcdfe6}
.step-dot.running{background:#409eff;animation:pulse 1s infinite}
.step-dot.success{background:#67c23a}
.step-dot.error{background:#f56c6c}
.step-label{color:#606266;min-width:80px}
.step-detail{color:#909399;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:300px}
.timeline-step.running .step-label{color:#409eff;font-weight:600}
.timeline-step.error .step-label{color:#f56c6c}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.input-area{padding:12px 0;border-top:1px solid #e4e7ed}
.input-actions{display:flex;gap:8px;margin-top:8px}
</style>
