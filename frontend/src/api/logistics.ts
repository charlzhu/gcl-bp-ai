import { http } from '@/utils/http'

/**
 * 自然语言查询请求体。
 */
export interface LogisticsNLQueryPayload {
  question: string
}

/**
 * 物流数据问答请求体。
 * 说明：
 * 当前正式页只支持单个自然语言问题输入，不扩展复杂表单。
 */
export interface LogisticsDataQaPayload {
  question: string
}

/**
 * 物流数据问答结果表。
 */
export interface LogisticsDataQaTable {
  columns: string[]
  rows: Record<string, any>[]
}

/**
 * 物流数据问答查询计划。
 * 说明：
 * 前端只展示，不参与任何业务推断。
 */
export interface LogisticsDataQaPlan {
  domain: 'logistics'
  intent: string
  query_key?: string | null
  metrics: string[]
  dimensions: string[]
  filters: Record<string, any>
  group_by: string[]
  sort: Array<Record<string, any>>
  limit?: number | null
  needs_clarification: boolean
  clarification_questions: string[]
  unsupported_reason?: string | null
}

/**
 * 物流数据问答状态。
 * 说明：
 * 前端正式页直接使用这个状态做成功、澄清、暂不支持、空结果和错误态展示。
 */
export interface LogisticsDataQaStatus {
  code: string
  message: string
  success: boolean
  severity: string
}

/**
 * 物流数据问答结果。
 */
export interface LogisticsDataQaResult {
  answer_summary: string
  result_table: LogisticsDataQaTable
  calculation_logic: string[]
  data_scope: Record<string, any>
  query_plan: LogisticsDataQaPlan
  warnings: string[]
  needs_clarification: boolean
  clarification_questions: string[]
  supported: boolean
  status?: LogisticsDataQaStatus | null
  history_log_id?: number | null
  history_ready?: boolean
}

/**
 * 结构化统计查询请求体。
 * 说明：
 * 这里只保留前端第二版最常用字段，后续可以按后端 schema 扩展。
 */
export interface LogisticsAggregatePayload {
  metric_type: string
  source_scope: string
  year_month_list?: string[]
  start_date?: string | null
  end_date?: string | null
  customer_name?: string | null
  logistics_company_name?: string | null
  region_name?: string | null
  origin_place?: string | null
  transport_mode?: string | null
  group_by?: string[]
  order_direction?: 'asc' | 'desc'
  limit?: number
}

/**
 * 结构化统计结果。
 * 说明：
 * 1. 在原有 summary / items 基础上，逐步补齐与 NL_QUERY 对齐的最小契约；
 * 2. 当前优先给条件查询页使用，不扩大到 detail / compare；
 * 3. 保留索引签名，避免阻断现有额外字段透传。
 */
export interface LogisticsAggregateResult {
  query_type: string
  metric_type: string
  source_scope: string
  execution_mode?: string | null
  summary?: Record<string, any>
  items?: Record<string, any>[]
  filters?: Record<string, any>
  status?: Record<string, any> | null
  result_explanation?: Record<string, any> | null
  no_result_analysis?: Record<string, any> | null
  response_meta?: Record<string, any> | null
  compatibility_notice?: string[] | null
  [key: string]: any
}

/**
 * 查询历史过滤条件。
 */
export interface QueryHistoryParams {
  limit?: number
  page?: number
  page_size?: number
  query_type?: string
  status?: string
  trace_id?: string
  keyword?: string
}

/**
 * 查询历史单条记录。
 */
export interface QueryHistoryItem {
  id: number
  trace_id?: string | null
  query_type: string
  question: string
  execution_mode?: string | null
  route_type?: string | null
  metric_type?: string | null
  result_count: number
  status: string
  status_code?: string | null
  status_message?: string | null
  template_hit?: boolean
  template_id?: string | null
  message?: string | null
  created_at?: string | null
  parsed?: Record<string, any> | null
  execution_binding?: Record<string, any> | null
  execution_summary?: Record<string, any> | null
  request_payload_json?: Record<string, any> | null
}

/**
 * 查询历史详情。
 * 说明：
 * 1. 详情接口会补齐前端直接依赖的 response_meta 与 query_result 快照；
 * 2. query_result 属于历史快照，不代表再次实时执行的最新结果；
 * 3. 这里沿用列表项字段，避免前端维护两套完全独立的结构。
 */
export interface QueryHistoryDetailResponse extends QueryHistoryItem {
  response_meta?: Record<string, any> | null
  query_result?: Record<string, any> | null
}

/**
 * 查询历史列表。
 */
export interface QueryHistoryResponse {
  total: number
  page?: number
  page_size?: number
  items: QueryHistoryItem[]
  load_warning?: string | null
}

/**
 * 自然语言查询。
 */
export async function fetchNLQuery(payload: LogisticsNLQueryPayload) {
  const resp = await http.post('/logistics/nl2query/parse-and-query', payload)
  return resp.data
}

/**
 * 物流数据问答正式页查询。
 * 说明：
 * 1. 只对接当前已验收通过的 logistics data-qa 后端接口；
 * 2. 返回值保持 ApiResponse 外层结构，页面层自行取 data；
 * 3. 不在前端做任何字段推断或业务补算。
 */
export async function fetchLogisticsDataQaQuery(payload: LogisticsDataQaPayload) {
  const resp = await http.post('/logistics/data-qa/query', payload)
  return resp.data as {
    code: number
    message: string
    trace_id?: string | null
    data?: LogisticsDataQaResult | null
  }
}

/**
 * 读取物流数据问答历史列表。
 * 说明：
 * 这里直接复用统一查询历史接口，只固定筛选 `DATA_QA`。
 */
export async function fetchLogisticsDataQaHistory(params: QueryHistoryParams = {}) {
  return fetchQueryHistory({
    ...params,
    query_type: 'DATA_QA',
  })
}

/**
 * 读取单条物流数据问答历史详情。
 * 说明：
 * 回放优先读取历史快照，不重新执行后端查询。
 */
export async function fetchLogisticsDataQaHistoryDetail(logId: number) {
  return fetchQueryHistoryDetail(logId)
}

/**
 * 结构化统计查询。
 */
export async function fetchAggregateQuery(payload: LogisticsAggregatePayload) {
  const resp = await http.post('/logistics/query-service/aggregate', payload)
  return resp.data as { data?: LogisticsAggregateResult } | LogisticsAggregateResult
}

/**
 * 查询历史导入任务列表。
 */
export async function fetchHistoryTasks() {
  const resp = await http.get('/logistics/data/hist/import/tasks')
  return resp.data
}

/**
 * 查询系统同步任务列表。
 */
export async function fetchSystemSyncTasks() {
  const resp = await http.get('/logistics/data/sys/sync/tasks')
  return resp.data
}

/**
 * 查询历史记录。
 * 说明：
 * 这里默认对接通用日志接口；如果你的后端接口路径不同，只需要改这个函数。
 */
export async function fetchQueryHistory(params: QueryHistoryParams = {}) {
  const resp = await http.get('/sys/query/log', { params })
  return resp.data
}

/**
 * 查询单条历史详情。
 */
export async function fetchQueryHistoryDetail(logId: number) {
  const resp = await http.get(`/sys/query/log/${logId}`)
  return resp.data
}
