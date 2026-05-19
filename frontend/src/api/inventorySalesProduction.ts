import { http } from '@/utils/http'
import { postJsonLineStream, type JsonLineStreamHandlers } from '@/utils/streamingApi'

/**
 * 产销存自然语言问答请求体。
 * 说明：前端只透传用户原问题，业务域识别、参数抽取和事实查询都由后端受控服务完成。
 */
export interface InventorySalesProductionQaPayload {
  question: string
}

/**
 * 产销存问答状态。
 * 说明：用于页面展示成功、空结果、需要澄清、暂不支持和错误等业务状态。
 */
export interface InventorySalesProductionQaStatus {
  code: string
  message: string
  success: boolean
  severity: 'info' | 'warning' | 'error' | string
}

/**
 * 产销存结果表。
 * 说明：列名和行数据均来自后端确定性结果，前端不做补算或反推。
 */
export interface InventorySalesProductionQaTable {
  columns: string[]
  rows: Array<Record<string, any>>
}

/**
 * 产销存展示层协议。
 * 说明：LLM 只参与回答表达，表格、卡片、图表和状态仍以后端确定性数据为准。
 */
export interface InventorySalesProductionQaPresentation {
  display_type?: string
  title?: string
  answer?: string
  highlights?: string[]
  table_spec?: InventorySalesProductionQaTable | null
  chart_spec?: {
    chart_type?: 'line' | 'bar' | 'pie' | null
    title?: string
    x_axis?: string
    y_axis?: string[]
    series?: Array<Record<string, any>>
    unit?: string | null
    data?: Record<string, any>[]
  } | null
  cards?: Array<{
    label: string
    value: any
    unit?: string | null
    description?: string | null
  }>
  follow_up?: {
    questions?: string[]
    examples?: string[]
  } | null
  unsupported_explanation?: {
    reason?: string
    suggestions?: string[]
  } | null
  caveats?: string[]
  caveat_items?: Array<{ level?: 'info' | 'warning' | 'danger'; text?: string }>
  debug?: Record<string, any>
}

/**
 * 产销存自然语言问答响应。
 * 说明：保留后端返回的最小业务字段，页面统一适配为 BusinessChat 展示结构。
 */
export interface InventorySalesProductionQaResponse {
  question: string
  domain: 'business_analysis'
  classification?: 'A' | 'B' | 'C' | 'D' | string
  status: InventorySalesProductionQaStatus
  answer_summary: string
  result_table?: InventorySalesProductionQaTable | null
  presentation?: InventorySalesProductionQaPresentation | null
  warnings?: string[]
  query_plan?: Record<string, any> | null
  raw_result?: Record<string, any> | null
  trace_events?: Array<Record<string, any>>
}

/**
 * 调用产销存自然语言问答接口。
 * 说明：非流式接口用于后续调试或页面降级，正式聊天优先使用流式接口。
 */
export async function askInventorySalesProductionQuestion(payload: InventorySalesProductionQaPayload) {
  const resp = await http.post('/business-analysis/inventory-sales-production/qa/ask', payload)
  return resp.data as { data?: InventorySalesProductionQaResponse } | InventorySalesProductionQaResponse
}

/**
 * 调用产销存自然语言问答流式接口。
 * 说明：后端先执行受控 QueryPlan 查询中间库，再把确定性结果交给表达层流式输出。
 */
export async function streamInventorySalesProductionQuestion(
  payload: InventorySalesProductionQaPayload,
  handlers: JsonLineStreamHandlers<InventorySalesProductionQaResponse>,
) {
  return postJsonLineStream<InventorySalesProductionQaResponse>(
    '/business-analysis/inventory-sales-production/qa/ask/stream',
    payload,
    handlers,
  )
}
