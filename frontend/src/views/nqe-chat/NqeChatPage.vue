<template>
  <div class="nqe-chat-page">
    <el-header class="nqe-header"><h2>NQE 统一 SQL Agent</h2><el-tag type="info" size="small">开发环境</el-tag></el-header>

    <div class="messages" ref="msgList">
      <div v-if="messages.length===0" class="empty-state">输入问题开始查询</div>
      <div v-for="(m,i) in messages" :key="i" :class="['msg-bubble',m.role]">
        <div class="msg-role">{{ m.role==='user'?'你':'NQE' }}</div>
        <div class="msg-content">
          <div v-if="m.role==='user'">{{ m.text }}</div>
          <div v-else>
            <!-- progress timeline -->
            <div v-if="m.progress?.length" class="progress-timeline">
              <div v-for="(p,j) in m.progress" :key="j" :class="['timeline-step',p.status]">
                <span class="step-dot" :class="p.status"></span><span class="step-label">{{p.label}}</span>
                <span v-if="p.detail" class="step-detail">{{p.detail}}</span>
              </div>
            </div>
            <!-- answer -->
            <div v-if="m.answer" class="msg-answer">{{ m.answer }}</div>
            <!-- metric cards -->
            <div v-if="m.metrics?.length" class="metric-cards">
              <div v-for="(c,j) in m.metrics" :key="j" class="metric-card">
                <div class="metric-label">{{ c.label||c.name }}</div>
                <div class="metric-value">{{ c.value }}</div>
              </div>
            </div>
            <!-- result table -->
            <div v-if="m.columns?.length" class="result-table-wrap">
              <el-table :data="m.rows||[]" border stripe size="small" max-height="400">
                <el-table-column v-for="col in m.columns" :key="col" :prop="col" :label="col" min-width="120" show-overflow-tooltip />
              </el-table>
              <template #empty>无匹配数据</template>
            </el-table>
              <div class="table-meta" v-if="m.row_count!=null">共 {{ m.row_count }} 行{{ m.row_count>=(m.rows?.length||0)&&m.row_count>0?`（显示前${m.rows?.length||0}行）`:'' }}</div>
            </div>
            <!-- NQE-FE-5: disambiguation panel -->
            <div v-if="m.disambiguation?.candidates?.length" class="disambig-panel">
              <div class="disambig-header">{{ m.disambiguation.message||'请选择' }}</div>
              <div class="disambig-candidates">
                <el-button v-for="(c,k) in m.disambiguation.candidates" :key="k" size="small" type="primary" plain @click="selectCandidate(m,c)" class="candidate-btn">{{ c.display_name||c.candidate_key||c.name }}</el-button>
              </div>
              <div v-if="m.disambiguation.selected" class="selected-info">已选择: {{ m.disambiguation.selected.display_name||m.disambiguation.selected }}</div>
            </div>

            <!-- chart placeholder -->
            <div v-if="m.chart" class="chart-area">[图表]</div>
            <!-- fallback -->
            <div v-if="m.fallback_used" class="msg-fallback">⚠ fallback: {{ m.fallback_reason||'已回退旧链路' }}</div>
            <!-- trace -->
            <div v-if="m.trace_id" class="msg-trace">trace: {{ m.trace_id }}</div>

            <div v-if="m.error" class="msg-error">{{ m.error }}</div>
          </div>
        </div>
      </div>
      <div v-if="loading" class="msg-bubble assistant"><div class="msg-role">NQE</div><div class="msg-content"><el-icon class="is-loading"><Loading /></el-icon> 处理中...</div></div>
    </div>

    <div class="input-area">
      <el-input v-model="question" type="textarea" :rows="2" placeholder="输入经营计划相关问题..." @keyup.enter.ctrl="send" :disabled="loading" />
      <div class="input-actions"><el-button type="primary" @click="send" :loading="loading" :disabled="loading">发送</el-button><el-button v-if="loading" type="danger" @click="stop">停止</el-button></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onUnmounted } from 'vue'
import { Loading } from '@element-plus/icons-vue'

interface Step { label:string; status:string; detail?:string }
interface Message { role:'user'|'assistant'; text?:string; answer?:string; progress?:Step[]; columns?:string[]; rows?:any[]; row_count?:number; metrics?:any[]; chart?:any; fallback_used?:boolean; fallback_reason?:string; trace_id?:string; error?:string; disambiguation?:any }

const question = ref(''); const loading = ref(false); const messages = ref<Message[]>([]); const msgList = ref<HTMLElement|null>(null)
let es: EventSource|null = null

const STEP_ORDER = ['domain_routed','metadata_loaded','sql_generated','safety_checked','explain_checked','sql_executed','result']
const STEP_LABELS: Record<string,string> = {domain_routed:'领域识别',metadata_loaded:'加载元数据',sql_generated:'生成SQL',safety_checked:'安全校验',explain_checked:'EXPLAIN校验',sql_corrected:'修正SQL',sql_executed:'执行查询',result:'完成'}

const scrollToBottom = () => nextTick(()=>{const el=msgList.value;if(el)el.scrollTop=el.scrollHeight})
const addMsg = (m:Message) => { messages.value.push(m); scrollToBottom() }

const send = () => {
  if(!question.value.trim()||loading.value) return
  const q = question.value.trim(); question.value=''; addMsg({role:'user',text:q})
  loading.value=true; if(es){es.close();es=null}
  const progress:Step[] = STEP_ORDER.map(s=>({label:STEP_LABELS[s]||s,status:'pending' as string,detail:''})); let curIdx=0
  const url = `/api/v1/nqe/query/stream?question=${encodeURIComponent(q)}&trace_id=nqe-${Date.now()}`
  es=new EventSource(url)
  es.addEventListener('progress',(e:any)=>{const d=JSON.parse(e.data);const s=d.step||'';const i=STEP_ORDER.indexOf(s);if(i>=0){for(let j=curIdx;j<i;j++)progress[j].status='success';progress[i].status='running';curIdx=i}})
  es.addEventListener('sql_generated',(e:any)=>{const d=JSON.parse(e.data);const i=STEP_ORDER.indexOf('sql_generated');if(i>=0){progress[i].status='success';progress[i].detail=(d.sql||'').slice(0,80);curIdx=i+1}})
  es.addEventListener('safety_checked',()=>{const i=STEP_ORDER.indexOf('safety_checked');if(i>=0){progress[i].status='success';curIdx=i+1}})
            es.addEventListener('explain_checked', (e:any)=>{const d=JSON.parse(e.data);const i=STEP_ORDER.indexOf('explain_checked');if(i>=0){progress[i].status=d.passed?'success':'error';curIdx=i+1}})
            
            // NQE-FE-5: disambiguation
            es.addEventListener('disambiguation_required', (e:any) => {
              const d = JSON.parse(e.data)
              const cands = d.candidates || []
              addMsg({role:'assistant',progress:[...progress],answer:`请选择 (${d.scope||''}):`,disambiguation:{scope:d.scope,message:d.message,candidates:cands,trace_id:d.trace_id}})
            })
            
            es.addEventListener('sql_executed', (e:any)=>{const d=JSON.parse(e.data);const i=STEP_ORDER.indexOf('sql_executed');if(i>=0){progress[i].status='success';progress[i].detail=`${d.row_count}行`;curIdx=i+1}})
            es.addEventListener('result', (e:any)=>{const d=JSON.parse(e.data);progress.forEach(p=>{if(p.status==='pending'||p.status==='running')p.status='success'});addMsg({role:'assistant',progress:[...progress],answer:d.answer,columns:d.columns,rows:d.rows,row_count:d.row_count,metrics:d.metrics,chart:d.chart,fallback_used:d.fallback_used,fallback_reason:d.fallback_reason,trace_id:d.trace_id});loading.value=false;es?.close();es=null})
  es.addEventListener('error',(e:any)=>{const d=e.data?JSON.parse(e.data):{};addMsg({role:'assistant',error:d.error||'查询失败',trace_id:d.trace_id});loading.value=false;es?.close();es=null})
  es.addEventListener('done',()=>{if(loading.value){progress.forEach(p=>{if(p.status==='pending'||p.status==='running')p.status='success'});addMsg({role:'assistant',progress:[...progress],answer:'完成'});loading.value=false}es?.close();es=null})
  es.onerror=()=>{if(loading.value){addMsg({role:'assistant',error:'连接中断'});loading.value=false}es?.close();es=null}
}
const stop = ()=>{if(es){es.close();es=null};loading.value=false}
onUnmounted(()=>{if(es){es.close();es=null}})

// NQE-FE-5R: real candidate selection via continue API
const selectCandidate = (msg: Message, candidate: any) => {
  if (loading.value) return
  const continueToken = msg.disambiguation?.continue_token || ''
  if (!continueToken) { msg.disambiguation = { ...msg.disambiguation, error: 'continue_token missing' }; return }
  
  msg.disambiguation = { ...msg.disambiguation, selected: candidate }
  loading.value = true
  if (es) { es.close(); es = null }

  const progress: Step[] = STEP_ORDER.map(s => ({ label: STEP_LABELS[s]||s, status: 'pending' as string, detail: '' }))
  const url = `/api/v1/nqe/query/stream/continue?continue_token=${encodeURIComponent(continueToken)}&candidate_key=${encodeURIComponent(candidate.candidate_key||'')}`
  es = new EventSource(url)
  
  es.addEventListener('progress',(e:any)=>{const d=JSON.parse(e.data);const s=d.step||'';const i=STEP_ORDER.indexOf(s);if(i>=0){for(let j=0;j<i;j++)progress[j].status='success';progress[i].status='running'}})
  es.addEventListener('sql_generated',(e:any)=>{const d=JSON.parse(e.data);const i=STEP_ORDER.indexOf('sql_generated');if(i>=0){progress[i].status='success';progress[i].detail=(d.sql||'').slice(0,80)}})
  es.addEventListener('safety_checked',()=>{const i=STEP_ORDER.indexOf('safety_checked');if(i>=0)progress[i].status='success'})
  es.addEventListener('explain_checked',(e:any)=>{const d=JSON.parse(e.data);const i=STEP_ORDER.indexOf('explain_checked');if(i>=0)progress[i].status=d.passed?'success':'error'})
  es.addEventListener('sql_executed',(e:any)=>{const d=JSON.parse(e.data);const i=STEP_ORDER.indexOf('sql_executed');if(i>=0){progress[i].status='success';progress[i].detail=`${d.row_count}行`}})
  es.addEventListener('result',(e:any)=>{const d=JSON.parse(e.data);addMsg({role:'assistant',progress:[...progress],answer:d.answer,columns:d.columns,rows:d.rows,row_count:d.row_count,metrics:d.metrics,chart:d.chart,fallback_used:d.fallback_used,fallback_reason:d.fallback_reason,trace_id:d.trace_id});loading.value=false;es?.close();es=null})
  es.addEventListener('error',(e:any)=>{const d=e.data?JSON.parse(e.data):{};addMsg({role:'assistant',error:d.error||'continue失败',trace_id:d.trace_id});loading.value=false;es?.close();es=null})
  es.addEventListener('done',()=>{if(loading.value){addMsg({role:'assistant',progress:[...progress],answer:'完成'});loading.value=false}es?.close();es=null})
  es.onerror=()=>{if(loading.value){addMsg({role:'assistant',error:'连接中断'});loading.value=false}es?.close();es=null}
}
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
.msg-fallback{color:#e6a23c;font-size:12px;margin-top:8px}
.msg-trace{color:#c0c4cc;font-size:11px;margin-top:4px}
.progress-timeline{padding:4px 0}
.timeline-step{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:13px}
.step-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.step-dot.pending{background:#dcdfe6}.step-dot.running{background:#409eff;animation:pulse 1s infinite}.step-dot.success{background:#67c23a}.step-dot.error{background:#f56c6c}
.step-label{color:#606266;min-width:80px}.step-detail{color:#909399;font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:300px}
.timeline-step.running .step-label{color:#409eff;font-weight:600}.timeline-step.error .step-label{color:#f56c6c}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
.metric-cards{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}
.metric-card{background:#fff;border:1px solid #e4e7ed;border-radius:8px;padding:12px 16px;min-width:120px}
.metric-label{font-size:12px;color:#909399}.metric-value{font-size:20px;font-weight:700;color:#303133}
.result-table-wrap{margin:8px 0}
.table-meta{font-size:12px;color:#909399;margin-top:4px}
.chart-area{padding:20px;background:#fff;border:1px dashed #dcdfe6;border-radius:8px;margin:8px 0;text-align:center;color:#909399}
/* disambiguation */
.disambig-panel{margin:8px 0;padding:12px;background:#fdf6ec;border:1px solid #faecd8;border-radius:8px}
.disambig-header{font-size:13px;color:#e6a23c;margin-bottom:8px}
.disambig-candidates{display:flex;flex-wrap:wrap;gap:6px}
.candidate-btn{margin:0}
.selected-info{font-size:13px;color:#67c23a;margin-top:8px}
.input-area{padding:12px 0;border-top:1px solid #e4e7ed}
.input-actions{display:flex;gap:8px;margin-top:8px}
</style>
