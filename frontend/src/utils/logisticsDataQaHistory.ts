import type { LogisticsDataQaResult, QueryHistoryDetailResponse, QueryHistoryItem } from '@/api/logistics'

/**
 * 从历史详情中提取物流数据问答快照。
 * 说明：
 * 1. 回放优先读取历史快照，不重新执行后端查询；
 * 2. 如果快照结构缺失，则返回 null，由页面层决定如何提示；
 * 3. 这里只做最小结构判断，不在前端补算业务结果。
 */
export function extractLogisticsDataQaReplaySnapshot(detail: QueryHistoryDetailResponse | null) {
  if (!detail?.query_result || typeof detail.query_result !== 'object') return null
  return detail.query_result as LogisticsDataQaResult
}

/**
 * 解析物流数据问答历史记录摘要。
 * 说明：
 * 1. 优先使用历史快照里的 answer_summary；
 * 2. 如果快照未写入，再降级到 message / status_message；
 * 3. 不在前端拼接新的业务摘要。
 */
export function resolveLogisticsDataQaHistorySummary(item: QueryHistoryItem) {
  const snapshotSummary = item.request_payload_json?.query_result?.answer_summary
  return snapshotSummary || item.message || item.status_message || '当前无摘要'
}

/**
 * 解析物流数据问答历史状态文案。
 * 说明：
 * 历史列表要继续保持业务化表达，不直接把技术状态码暴露给业务人员。
 */
export function resolveLogisticsDataQaHistoryStatusLabel(item: QueryHistoryItem) {
  const code = item.status_code || item.status
  const mapping: Record<string, string> = {
    OK: '查询成功',
    CLARIFICATION_REQUIRED: '需要补充条件',
    UNSUPPORTED_QUESTION: '当前暂不支持',
    EMPTY_RESULT: '未查到结果',
    EXECUTION_ERROR: '查询失败',
    SUCCESS: '查询成功',
    CLARIFICATION: '需要补充条件',
    UNSUPPORTED: '当前暂不支持',
    ERROR: '查询失败',
  }
  return mapping[code || ''] || (item.status_message ? item.status_message : '结果状态')
}

/**
 * 解析物流数据问答历史状态颜色。
 * 说明：
 * 颜色只作为阅读辅助，不改变状态本身含义。
 */
export function resolveLogisticsDataQaHistoryTagType(item: QueryHistoryItem) {
  const code = item.status_code || item.status
  if (code === 'OK' || code === 'SUCCESS') return 'success'
  if (code === 'CLARIFICATION_REQUIRED' || code === 'CLARIFICATION') return 'warning'
  if (code === 'EMPTY_RESULT') return 'warning'
  if (code === 'EXECUTION_ERROR' || code === 'ERROR') return 'danger'
  return 'info'
}

/**
 * 统一格式化时间展示。
 * 说明：
 * 历史页和正式查询页都复用这一格式，避免同一模块出现多套时间样式。
 */
export function formatLogisticsDataQaDateTime(value: string | null | undefined) {
  if (!value) return ''
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  return parsed.toLocaleString('zh-CN', { hour12: false })
}
