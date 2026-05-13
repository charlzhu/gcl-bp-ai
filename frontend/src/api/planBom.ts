import { http } from '@/utils/http'
import { postJsonLineStream, type JsonLineStreamHandlers } from '@/utils/streamingApi'

/**
 * 计划 BOM 明细查询请求体。
 * 说明：
 * 1. 页面主输入只暴露 order_no / review_no / order_name；
 * 2. order_identity_key / file_instance_key / version_no 只在候选选择后由前端透传；
 * 3. material_categories 当前默认查询 5 类核心材料，不在 MVP 中暴露复杂筛选器。
 */
export interface PlanBomDetailQueryPayload {
  order_no?: string | null
  review_no?: string | null
  order_name?: string | null
  order_identity_key?: string | null
  file_instance_key?: string | null
  version_no?: string | null
  material_categories?: string[]
  candidate_limit?: number
}

/**
 * 计划 BOM 状态对象。
 */
export interface PlanBomStatus {
  code: string
  message: string
  success: boolean
  severity: 'info' | 'warning' | 'error'
  extras?: Record<string, any>
}

/**
 * 计划 BOM 候选项。
 */
export interface PlanBomCandidate {
  order_identity_key: string
  file_instance_key?: string | null
  order_no: string
  order_display_label?: string | null
  order_name?: string | null
  version_no: string
  effective_date?: string | null
  source_type: string
  source_tag?: string | null
  file_no?: string | null
  raw_file_name?: string | null
  match_reason: string
}

/**
 * 已命中的 BOM 版本信息。
 */
export interface PlanBomSelectedVersion {
  order_identity_key: string
  file_instance_key?: string | null
  order_no: string
  order_display_label?: string | null
  order_name?: string | null
  version_no: string
  effective_date?: string | null
  source_type: string
  source_tag?: string | null
  file_no?: string | null
  raw_file_name?: string | null
  import_batch_id?: string | null
}

/**
 * 计划 BOM 单条材料行。
 */
export interface PlanBomMaterialItem {
  order_no: string
  version_no: string
  file_instance_key?: string | null
  sap_code: string
  line_no?: string | null
  material_category?: string | null
  material_category_label?: string | null
  material_name: string
  description?: string | null
  standard_usage?: string | null
  unit?: string | null
  production_loss?: string | null
  remark?: string | null
  replacement_marker?: string | null
  source_type: string
  source_tag?: string | null
  import_batch_id?: string | null
  raw_row_no?: number | null
}

/**
 * 计划 BOM 明细查询响应。
 */
export interface PlanBomDetailQueryResponse {
  query_type: 'detail' | 'candidate_list'
  domain: string
  execution_mode: string
  status: PlanBomStatus
  result_explanation?: Record<string, any>
  no_result_analysis?: Record<string, any> | null
  response_meta?: Record<string, any>
  candidate_scope?: 'order_identity' | 'file_instance' | 'version' | null
  selected_version?: PlanBomSelectedVersion | null
  candidates: PlanBomCandidate[]
  candidate_total_hint: number
  items: PlanBomMaterialItem[]
  total: number
}

/**
 * 调用计划 BOM 明细查询接口。
 * 说明：
 * 统一透传后端 detail 查询请求，页面不自行推断候选和版本。
 */
export async function fetchPlanBomDetailQuery(payload: PlanBomDetailQueryPayload) {
  const resp = await http.post('/plan-bom/query/detail', payload)
  return resp.data as { data?: PlanBomDetailQueryResponse } | PlanBomDetailQueryResponse
}

/**
 * 计划 BOM 自然语言问答请求。
 */
export interface PlanBomQaPayload {
  question: string
}

/**
 * 计划 BOM 自然语言问答响应。
 */
export interface PlanBomQaResponse {
  question: string
  domain: 'plan_bom'
  classification: 'A' | 'B' | 'C' | 'D'
  status: PlanBomStatus
  answer_summary: string
  result_table?: {
    columns: string[]
    rows: Array<Record<string, any>>
  }
  presentation?: {
    display_type: string
    title: string
    answer: string
    highlights?: string[]
    table_spec?: {
      columns: string[]
      rows: Array<Record<string, any>>
    } | null
    follow_up?: Record<string, any> | null
    unsupported_explanation?: Record<string, any> | null
    caveats?: string[]
    caveat_items?: Array<{ level?: 'info' | 'warning' | 'danger'; text?: string }>
    debug?: Record<string, any>
  } | null
  nlu?: Record<string, any>
  raw_result?: Record<string, any>
  warnings?: string[]
  trace_events?: Array<Record<string, any>>
}

/**
 * 调用计划 BOM 自然语言问答接口。
 */
export async function askPlanBomQuestion(payload: PlanBomQaPayload) {
  const resp = await http.post('/plan-bom/qa/ask', payload)
  return resp.data as { data?: PlanBomQaResponse } | PlanBomQaResponse
}

/**
 * 调用计划 BOM 自然语言问答流式接口。
 * 说明：后端先完成 BOM 查询/功率计算，再把“提问 + 确定性结果”交给 LLM 流式表达。
 */
export async function streamPlanBomQuestion(
  payload: PlanBomQaPayload,
  handlers: JsonLineStreamHandlers<PlanBomQaResponse>,
) {
  return postJsonLineStream<PlanBomQaResponse>('/plan-bom/qa/ask/stream', payload, handlers)
}

/**
 * 上传计划 BOM Excel 文件。
 */
export interface PlanBomUploadOptions {
  business_type?: string
  source?: string
  overwrite?: boolean
  remark?: string
  onUploadProgress?: (percentage: number) => void
}

/**
 * 上传进度事件的最小结构。
 */
interface UploadProgressEventLike {
  loaded: number
  total?: number
}

/**
 * 把浏览器上传进度事件转换为 0-99 的百分比。
 * 说明：
 * 1. 请求真正完成后由页面置为 100；
 * 2. total 缺失时给出中间态，避免界面完全没有反馈；
 * 3. 不在这里读取或记录任何文件内容。
 */
function emitUploadProgress(event: UploadProgressEventLike, callback?: (percentage: number) => void) {
  if (!callback) return
  if (event.total && event.total > 0) {
    const percentage = Math.round((event.loaded / event.total) * 100)
    callback(Math.max(0, Math.min(99, percentage)))
    return
  }
  if (event.loaded > 0) {
    callback(50)
  }
}

/**
 * 上传计划 BOM Excel 文件。
 * 说明：
 * 1. 默认参数保持原有试运行链路；
 * 2. 页面可透传 source / remark，方便业务人员理解上传来源；
 * 3. 不在前端解析 Excel 内容，事实解析仍交给后端真实上传接口。
 */
export async function uploadPlanBomExcel(file: File, options: PlanBomUploadOptions = {}) {
  const formData = new FormData()
  formData.append('file', file)
  appendPlanBomUploadFields(formData, options)
  const resp = await http.post('/plan-bom/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => emitUploadProgress(event, options.onUploadProgress),
  })
  return resp.data
}

/**
 * 批量上传计划 BOM Excel 文件。
 * 说明：
 * 1. 多个文件统一使用后端 files 字段，后端逐文件解析并返回汇总；
 * 2. 前端不解析 Excel 内容，只负责选择文件、上传和展示逐文件结果；
 * 3. 继续复用单文件上传的 source / overwrite / remark / 进度参数。
 */
export async function uploadPlanBomExcelBatch(files: File[], options: PlanBomUploadOptions = {}) {
  const formData = new FormData()
  files.forEach((file) => {
    formData.append('files', file)
  })
  appendPlanBomUploadFields(formData, options)
  const resp = await http.post('/plan-bom/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => emitUploadProgress(event, options.onUploadProgress),
  })
  return resp.data
}

/**
 * 追加 BOM 上传公共表单字段。
 */
function appendPlanBomUploadFields(formData: FormData, options: PlanBomUploadOptions) {
  formData.append('business_type', options.business_type || 'plan_bom')
  formData.append('source', options.source || 'manual_upload')
  formData.append('overwrite', String(options.overwrite ?? true))
  if (options.remark) {
    formData.append('remark', options.remark)
  }
}

/**
 * 功率模型导入选项。
 */
export interface PlanPowerModelUploadOptions {
  onUploadProgress?: (percentage: number) => void
}

/**
 * BOM 上传历史摘要。
 */
export interface PlanBomUploadHistoryItem {
  batch_id: string
  source_type: string
  source_tag: string
  file_name: string
  file_hash?: string | null
  status: string
  total_files: number
  total_headers: number
  total_lines: number
  error_message?: string | null
  created_at?: string | null
  finished_at?: string | null
}

/**
 * BOM 上传历史响应。
 */
export interface PlanBomUploadHistoryResponse {
  items: PlanBomUploadHistoryItem[]
  total: number
}

/**
 * 功率模型版本摘要。
 */
export interface PlanPowerModelVersionSummary {
  id: number
  file_name: string
  file_hash: string
  source_type: string
  business_version_label?: string | null
  formula_policy: string
  vba_project_sha256?: string | null
  is_active: boolean
  parse_status: string
  sheet_count: number
  model_sheet_count: number
  warning_count: number
  error_count: number
  created_at?: string | null
  activated_at?: string | null
}

/**
 * 功率模型版本列表响应。
 */
export interface PlanPowerModelVersionListResponse {
  items: PlanPowerModelVersionSummary[]
  total: number
}

/**
 * 上传计划 BOM 功率模型 xlsm 文件。
 * 说明：
 * 1. 该接口对应后端 /plan-bom/power-model/import，与普通 BOM Excel 上传隔离；
 * 2. 临时管理令牌已移除，后续由用户权限模块统一控制上传权限；
 * 3. 前端不解析、不中转计算 Excel 内容，解析和版本化仍由后端确定性服务完成。
 */
export async function uploadPlanPowerModel(file: File, options: PlanPowerModelUploadOptions = {}) {
  const formData = new FormData()
  formData.append('file', file)
  const resp = await http.post('/plan-bom/power-model/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (event) => emitUploadProgress(event, options.onUploadProgress),
  })
  return resp.data
}

/**
 * 查询 BOM Excel 上传历史。
 */
export async function fetchPlanBomUploadHistory(limit = 50) {
  const resp = await http.get('/plan-bom/upload/history', { params: { limit } })
  return resp.data as { data?: PlanBomUploadHistoryResponse } | PlanBomUploadHistoryResponse
}

/**
 * 查询功率模型版本历史。
 */
export async function fetchPlanPowerModelVersions() {
  const resp = await http.get('/plan-bom/power-model/versions')
  return resp.data as { data?: PlanPowerModelVersionListResponse } | PlanPowerModelVersionListResponse
}

/**
 * 手动切换功率模型生效版本。
 */
export async function activatePlanPowerModelVersion(versionId: number) {
  const resp = await http.post(`/plan-bom/power-model/versions/${versionId}/activate`)
  return resp.data as { data?: PlanPowerModelVersionSummary } | PlanPowerModelVersionSummary
}
