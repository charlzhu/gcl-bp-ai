import { http } from '@/utils/http'

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
    debug?: Record<string, any>
  } | null
}

/**
 * 调用计划 BOM 自然语言问答接口。
 */
export async function askPlanBomQuestion(payload: PlanBomQaPayload) {
  const resp = await http.post('/plan-bom/qa/ask', payload)
  return resp.data as { data?: PlanBomQaResponse } | PlanBomQaResponse
}

/**
 * 上传计划 BOM Excel 文件。
 */
export interface PlanBomUploadOptions {
  business_type?: string
  source?: string
  overwrite?: boolean
  remark?: string
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
  formData.append('business_type', options.business_type || 'plan_bom')
  formData.append('source', options.source || 'manual_upload')
  formData.append('overwrite', String(options.overwrite ?? true))
  if (options.remark) {
    formData.append('remark', options.remark)
  }
  const resp = await http.post('/plan-bom/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return resp.data
}
