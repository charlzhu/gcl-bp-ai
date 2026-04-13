const STORAGE_KEY = 'logistics:last-query-context'
const PAGE_DRAFT_KEY_PREFIX = 'logistics:page-draft:'

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
 * 查询页草稿缓存结构。
 * 说明：
 * 1. 用于保存表单输入中的临时状态；
 * 2. 当前只服务自然语言查询页和条件查询页；
 * 3. 不承担结果存储职责，结果仍通过 QueryContextPayload 单独缓存。
 */
export interface QueryPageDraftPayload {
  sourcePage: 'nl-query' | 'structured-query'
  formData: Record<string, any>
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

/**
 * 保存页面草稿。
 * 说明：
 * 查询未提交前，也要尽量保住用户已输入的条件，避免切页后全部丢失。
 */
export function saveQueryPageDraft(payload: QueryPageDraftPayload) {
  const key = `${PAGE_DRAFT_KEY_PREFIX}${payload.sourcePage}`
  sessionStorage.setItem(key, JSON.stringify(payload))
}

/**
 * 读取页面草稿。
 */
export function getQueryPageDraft(
  sourcePage: QueryPageDraftPayload['sourcePage'],
): QueryPageDraftPayload | null {
  const key = `${PAGE_DRAFT_KEY_PREFIX}${sourcePage}`
  const raw = sessionStorage.getItem(key)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch (_error) {
    return null
  }
}

/**
 * 清理指定页面草稿。
 */
export function clearQueryPageDraft(sourcePage: QueryPageDraftPayload['sourcePage']) {
  const key = `${PAGE_DRAFT_KEY_PREFIX}${sourcePage}`
  sessionStorage.removeItem(key)
}
