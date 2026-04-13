import { http } from '@/utils/http'

/**
 * 自然语言查询请求体。
 */
export interface LogisticsNLQueryPayload {
  question: string
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
 * 查询历史过滤条件。
 */
export interface QueryHistoryParams {
  limit?: number
  query_type?: string
  status?: string
  trace_id?: string
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
  message?: string | null
  created_at?: string | null
  parsed?: Record<string, any> | null
  execution_binding?: Record<string, any> | null
  execution_summary?: Record<string, any> | null
  request_payload_json?: Record<string, any> | null
}

/**
 * 查询历史列表。
 */
export interface QueryHistoryResponse {
  total: number
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
 * 结构化统计查询。
 */
export async function fetchAggregateQuery(payload: LogisticsAggregatePayload) {
  const resp = await http.post('/logistics/query-service/aggregate', payload)
  return resp.data
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
