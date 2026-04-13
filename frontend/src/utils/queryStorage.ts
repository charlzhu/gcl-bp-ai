const STORAGE_KEY = 'logistics:last-query-context'

/**
 * 最近一次查询的上下文结构。
 */
export interface QueryContextPayload {
  sourcePage: 'nl-query' | 'structured-query'
  question?: string
  requestPayload?: Record<string, any> | null
  rawResponse?: Record<string, any> | null
  parsed?: Record<string, any> | null
  queryResult?: Record<string, any> | null
  selectedRow?: Record<string, any> | null
}

/**
 * 保存最近一次查询上下文，便于在明细页中复用。
 */
export function saveLastQueryContext(payload: QueryContextPayload) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

/**
 * 读取最近一次查询上下文。
 */
export function getLastQueryContext(): QueryContextPayload | null {
  const raw = sessionStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch (_error) {
    return null
  }
}

/**
 * 清理最近一次查询上下文。
 */
export function clearLastQueryContext() {
  sessionStorage.removeItem(STORAGE_KEY)
}
