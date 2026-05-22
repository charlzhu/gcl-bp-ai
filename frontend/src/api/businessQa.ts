/**
 * LQG-8：统一业务问数流式接口前端适配层。
 *
 * 说明：
 * 1. 统一入口 POST /api/v1/business-qa/stream 接管 logistics 与 plan_bom 两个域；
 * 2. 前端仍使用同一 postJsonLineStream 消费 NDJSON 流，事件名仍为 meta/delta/done/error；
 * 3. meta 事件增加 stage 字段，前端可据此展示理解进度；
 * 4. 经营分析/产销存暂不纳入本接口，继续使用原有独立流式入口。
 */

import { postJsonLineStream, type JsonLineStreamHandlers } from '@/utils/streamingApi'

/* ---- 请求类型 ---- */

/** 统一业务问数请求体。 */
export interface BusinessQaPayload {
  /** 用户自然语言问题。 */
  question: string
  /** 业务域提示：auto（自动识别）、logistics（物流）或 plan_bom（计划 BOM）。 */
  domain_hint?: 'auto' | 'logistics' | 'plan_bom'
}

/* ---- 流式事件中的 stage 常量（与后端 UNIFIED_STREAM_STAGES 对齐）---- */

/** 统一流式事件 stage 值。 */
export type BusinessQaStreamStage =
  | 'received'
  | 'understanding'
  | 'plan_ready'
  | 'deterministic_result_ready'
  | 'answer_streaming'
  | 'done'
  | 'error'

/* ---- done 事件返回的 data 字段 ---- */

/**
 * 统一流式 done 事件的 data 字段。
 * 根据实际业务域，其中包含 logistics 或 plan_bom 的确定性结果。
 */
export type BusinessQaStreamDoneData = Record<string, any>

/* ---- 流式事件 data 类型 ---- */

/** meta/delta/done/error 事件中 data 字段的联合类型 */
export interface BusinessQaStreamEventData {
  stage?: BusinessQaStreamStage
  trace_id?: string
  question?: string
  domain?: string
  domain_hint?: string
  confidence?: number
  route_status?: string
  status_code?: string
  text?: string
  answer?: string
  message?: string
  /** done 事件中携带的完整确定性结果。 */
  data?: BusinessQaStreamDoneData
  [key: string]: any
}

/* ---- 对外 API ---- */

/**
 * 调用统一业务问数流式接口。
 *
 * 参数：
 *   payload: 请求体，包含 question 和可选的 domain_hint。
 *   handlers: meta/delta/done/error 事件回调，用法与现有 domain 流式接口一致。
 *
 * 返回：
 *   Promise<void>，流式消费完成后结束。
 *
 * 说明：
 *   后端按统一事件序列输出：
 *     received → understanding → plan_ready →
 *     deterministic_result_ready → answer_streaming (delta) → done
 *   前端 handlers.onDone 收到的 data.data 字段即为完整确定性结果，
 *   可交由现有 adaptLogisticsResult / adaptPlanBomResult 适配为 UnifiedResult。
 */
export async function streamBusinessQa(
  payload: BusinessQaPayload,
  handlers: JsonLineStreamHandlers<BusinessQaStreamDoneData>,
) {
  return postJsonLineStream<BusinessQaStreamDoneData>(
    '/business-qa/stream',
    payload,
    handlers,
  )
}
