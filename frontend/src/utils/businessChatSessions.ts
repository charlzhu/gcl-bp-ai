export type BusinessChatDomain = 'auto' | 'logistics' | 'plan_bom' | 'business_analysis'
export type BusinessChatMessageRole = 'user' | 'assistant' | 'system'

export interface BusinessChatMessage {
  id: string
  role: BusinessChatMessageRole
  content: string
  domain: BusinessChatDomain
  status?: string
  presentation?: Record<string, any> | null
  createdAt: string
  rawResponse?: Record<string, any> | null
  loading?: boolean
  error?: string
}

export interface BusinessChatSession {
  id: string
  title: string
  domain: BusinessChatDomain
  createdAt: string
  updatedAt: string
  messages: BusinessChatMessage[]
  isNew: boolean
  isPinned?: boolean
  lastQuestion?: string
}

export interface BusinessChatSessionSummary {
  id: string
  title: string
  domain: BusinessChatDomain
  updatedAt: string
  isNew: boolean
  lastQuestion?: string
}

const BUSINESS_CHAT_SESSION_LIST_KEY = 'business-chat:sessions'
const BUSINESS_CHAT_SESSION_DATA_PREFIX = 'business-chat:session:'
const BUSINESS_CHAT_ACTIVE_SESSION_KEY = 'business-chat:active-session'
const BUSINESS_CHAT_SESSION_EVENT = 'business-chat-sessions-updated'
const MAX_SESSION_COUNT = 20
const MAX_MESSAGE_COUNT_PER_SESSION = 80
const FALLBACK_SESSION_COUNT_ON_QUOTA = 6
let businessChatMessageFallbackSeq = 0

/**
 * 读取智能问答窗口摘要列表。
 *
 * 返回：
 *   会话摘要数组，按最近更新时间倒序。
 */
export function listBusinessChatSessions(): BusinessChatSessionSummary[] {
  const raw = localStorage.getItem(BUSINESS_CHAT_SESSION_LIST_KEY)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isSessionSummary).sort(sortSessionSummary)
  } catch (_error) {
    return []
  }
}

/**
 * 读取指定智能问答窗口完整数据。
 *
 * 参数：
 *   sessionId: 会话窗口 ID。
 *
 * 返回：
 *   合法会话；不存在或结构异常时返回 null。
 */
export function getBusinessChatSession(sessionId: string): BusinessChatSession | null {
  const raw = localStorage.getItem(`${BUSINESS_CHAT_SESSION_DATA_PREFIX}${sessionId}`)
  if (!raw) return null
  try {
    return normalizeSession(JSON.parse(raw))
  } catch (_error) {
    return null
  }
}

/**
 * 保存智能问答窗口，并同步刷新二级菜单摘要。
 *
 * 参数：
 *   session: 会话完整数据。
 *
 * 返回：
 *   归一化后的会话；结构非法时返回 null。
 */
export function saveBusinessChatSession(session: BusinessChatSession): BusinessChatSession | null {
  const normalized = normalizeSession(session)
  if (!normalized) return null
  upsertSessionSummary(normalized)
  trimBusinessChatSessions()
  const saved = persistBusinessChatSessionData(normalized)
  if (!saved) return null
  emitBusinessChatSessionUpdated()
  return normalized
}

/**
 * 确保至少存在一个智能问答窗口。
 *
 * 返回：
 *   当前激活窗口；如果没有则自动创建空白窗口。
 */
export function ensureBusinessChatSession(): BusinessChatSession {
  const activeId = getActiveBusinessChatSessionId()
  const active = activeId ? getBusinessChatSession(activeId) : null
  if (active) return active
  const latest = listBusinessChatSessions()[0]
  if (latest) {
    setActiveBusinessChatSessionId(latest.id)
    const session = getBusinessChatSession(latest.id)
    if (session) return session
  }
  return createBlankBusinessChatSession()
}

/**
 * 创建或聚焦唯一空白新窗口。
 *
 * 说明：
 *   同一时间只允许一个 messages 为空且 isNew=true 的窗口。
 *
 * 返回：
 *   已创建或已聚焦的空白窗口。
 */
export function createOrFocusBlankBusinessChatSession(): BusinessChatSession {
  const blank = findBlankBusinessChatSession()
  if (blank) {
    setActiveBusinessChatSessionId(blank.id)
    emitBusinessChatSessionUpdated()
    return blank
  }
  return createBlankBusinessChatSession()
}

/**
 * 创建一个新的空白智能问答窗口。
 *
 * 返回：
 *   新会话窗口。
 */
export function createBlankBusinessChatSession(): BusinessChatSession {
  const now = new Date().toISOString()
  const session: BusinessChatSession = {
    id: buildBusinessChatSessionId(),
    title: '新对话',
    domain: 'auto',
    createdAt: now,
    updatedAt: now,
    messages: [],
    isNew: true,
  }
  saveBusinessChatSession(session)
  setActiveBusinessChatSessionId(session.id)
  emitBusinessChatSessionUpdated()
  return session
}

/**
 * 更新窗口标题。
 *
 * 参数：
 *   sessionId: 会话窗口 ID；
 *   title: 新标题。
 *
 * 返回：
 *   更新是否成功。
 */
export function renameBusinessChatSession(sessionId: string, title: string): boolean {
  const session = getBusinessChatSession(sessionId)
  if (!session) return false
  const safeTitle = normalizeTitle(title)
  if (!safeTitle) return false
  saveBusinessChatSession({
    ...session,
    title: safeTitle,
    updatedAt: new Date().toISOString(),
  })
  return true
}

/**
 * 删除指定窗口，并保证删除后仍有可展示窗口。
 *
 * 参数：
 *   sessionId: 会话窗口 ID。
 *
 * 返回：
 *   删除后应激活的窗口。
 */
export function removeBusinessChatSession(sessionId: string): BusinessChatSession {
  localStorage.removeItem(`${BUSINESS_CHAT_SESSION_DATA_PREFIX}${sessionId}`)
  const summaries = listBusinessChatSessions().filter((item) => item.id !== sessionId)
  localStorage.setItem(BUSINESS_CHAT_SESSION_LIST_KEY, JSON.stringify(summaries))

  const nextSummary = summaries[0] || null
  if (nextSummary) {
    setActiveBusinessChatSessionId(nextSummary.id)
    emitBusinessChatSessionUpdated()
    return getBusinessChatSession(nextSummary.id) || createBlankBusinessChatSession()
  }
  clearActiveBusinessChatSessionId()
  // 删除唯一会话时不能先广播“空列表”状态，否则布局页和聊天页监听器会同时 ensure 并抢先创建一个新会话；
  // 这里直接创建唯一兜底会话，由 createBlankBusinessChatSession 负责统一设置激活 ID 和广播更新。
  return createBlankBusinessChatSession()
}

/**
 * 设置当前激活窗口。
 *
 * 参数：
 *   sessionId: 会话窗口 ID。
 */
export function setActiveBusinessChatSessionId(sessionId: string) {
  localStorage.setItem(BUSINESS_CHAT_ACTIVE_SESSION_KEY, sessionId)
  emitBusinessChatSessionUpdated()
}

/**
 * 读取当前激活窗口 ID。
 *
 * 返回：
 *   会话 ID；没有则为空字符串。
 */
export function getActiveBusinessChatSessionId() {
  return localStorage.getItem(BUSINESS_CHAT_ACTIVE_SESSION_KEY) || ''
}

/**
 * 清理当前激活窗口 ID。
 */
export function clearActiveBusinessChatSessionId() {
  localStorage.removeItem(BUSINESS_CHAT_ACTIVE_SESSION_KEY)
}

/**
 * 派发会话更新事件，供布局和页面同步。
 */
export function emitBusinessChatSessionUpdated() {
  window.dispatchEvent(new CustomEvent(BUSINESS_CHAT_SESSION_EVENT))
}

/**
 * 返回会话更新事件名。
 */
export function getBusinessChatSessionEventName() {
  return BUSINESS_CHAT_SESSION_EVENT
}

/**
 * 生成会话窗口 ID。
 */
export function buildBusinessChatSessionId() {
  return `business-chat-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

/**
 * 生成智能问答消息 ID。
 *
 * 说明：
 *   局域网 HTTP 地址不一定具备安全上下文，不能假设 crypto.randomUUID 始终可用。
 *
 * 返回：
 *   当前浏览器环境可用的消息 ID。
 */
export function buildBusinessChatMessageId() {
  const randomUuid = globalThis.crypto?.randomUUID
  if (typeof randomUuid === 'function') {
    return randomUuid.call(globalThis.crypto)
  }
  businessChatMessageFallbackSeq = (businessChatMessageFallbackSeq + 1) % 1000000
  return `business-chat-message-${Date.now()}-${businessChatMessageFallbackSeq}-${Math.random().toString(36).slice(2, 10)}`
}

/**
 * 根据问题和业务域生成窗口标题。
 *
 * 参数：
 *   question: 第一条用户问题；
 *   domain: 当前业务域。
 *
 * 返回：
 *   适合二级菜单展示的短标题。
 */
export function buildBusinessChatSessionTitle(question: string, domain: BusinessChatDomain) {
  const normalized = question.trim()
  if (normalized) return normalizeTitle(normalized) || '新对话'
  if (domain === 'logistics') return '物流问答'
  if (domain === 'plan_bom') return 'BOM 问答'
  return '新对话'
}

/**
 * 规范化窗口标题。
 *
 * 参数：
 *   title: 原始标题。
 *
 * 返回：
 *   1-18 字符的标题；空标题返回空字符串。
 */
export function normalizeTitle(title: string) {
  const normalized = title.trim().replace(/\s+/g, ' ')
  if (!normalized) return ''
  return normalized.length > 18 ? `${normalized.slice(0, 18)}…` : normalized
}

/**
 * 查找当前唯一空白新窗口。
 */
function findBlankBusinessChatSession(): BusinessChatSession | null {
  for (const summary of listBusinessChatSessions()) {
    const session = getBusinessChatSession(summary.id)
    if (session?.isNew && session.messages.length === 0) return session
  }
  return null
}

/**
 * 新增或更新二级菜单摘要。
 */
function upsertSessionSummary(session: BusinessChatSession) {
  const summaries = listBusinessChatSessions().filter((item) => item.id !== session.id)
  summaries.unshift({
    id: session.id,
    title: session.title,
    domain: session.domain,
    updatedAt: session.updatedAt,
    isNew: session.isNew,
    lastQuestion: session.lastQuestion,
  })
  localStorage.setItem(BUSINESS_CHAT_SESSION_LIST_KEY, JSON.stringify(summaries.slice(0, MAX_SESSION_COUNT)))
}

/**
 * 控制本地窗口数量，避免 localStorage 无限增长。
 */
function trimBusinessChatSessions(maxCount = MAX_SESSION_COUNT, preserveSessionId = '') {
  const summaries = listBusinessChatSessions()
  if (summaries.length <= maxCount) return
  const preserved = preserveSessionId ? summaries.filter((item) => item.id === preserveSessionId) : []
  const candidates = summaries.filter((item) => item.id !== preserveSessionId)
  const kept = [...preserved, ...candidates].slice(0, maxCount)
  const keptIds = new Set(kept.map((item) => item.id))
  const removed = summaries.filter((item) => !keptIds.has(item.id))
  removed.forEach((item) => localStorage.removeItem(`${BUSINESS_CHAT_SESSION_DATA_PREFIX}${item.id}`))
  localStorage.setItem(BUSINESS_CHAT_SESSION_LIST_KEY, JSON.stringify(kept))
}

/**
 * 归一化会话窗口。
 */
function normalizeSession(value: unknown): BusinessChatSession | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const raw = value as Record<string, any>
  if (typeof raw.id !== 'string' || typeof raw.title !== 'string') return null
  const messages = Array.isArray(raw.messages)
    ? raw.messages.map(normalizeMessage).filter((item): item is BusinessChatMessage => Boolean(item)).slice(-MAX_MESSAGE_COUNT_PER_SESSION)
    : []
  return {
    id: raw.id,
    title: normalizeTitle(raw.title) || '新对话',
    domain: isDomain(raw.domain) ? raw.domain : 'auto',
    createdAt: typeof raw.createdAt === 'string' ? raw.createdAt : new Date().toISOString(),
    updatedAt: typeof raw.updatedAt === 'string' ? raw.updatedAt : new Date().toISOString(),
    messages,
    isNew: Boolean(raw.isNew) && messages.length === 0,
    isPinned: Boolean(raw.isPinned),
    lastQuestion: typeof raw.lastQuestion === 'string' ? raw.lastQuestion : '',
  }
}

/**
 * 保存会话详情，遇到浏览器配额上限时先清理旧窗口再重试。
 */
function persistBusinessChatSessionData(session: BusinessChatSession) {
  const key = `${BUSINESS_CHAT_SESSION_DATA_PREFIX}${session.id}`
  const payload = JSON.stringify(session)
  try {
    localStorage.setItem(key, payload)
    return true
  } catch (_error) {
    trimBusinessChatSessions(FALLBACK_SESSION_COUNT_ON_QUOTA, session.id)
    try {
      localStorage.setItem(key, payload)
      return true
    } catch (_retryError) {
      return false
    }
  }
}

const persistablePresentationKeys = new Set([
  'displayType',
  'display_type',
  'title',
  'answer',
  'highlights',
  'cards',
  'chart',
  'chart_spec',
  'table',
  'table_spec',
  'followUps',
  'follow_up',
  'suggestions',
  'caveats',
  'caveatItems',
  'caveat_items',
])

/**
 * 归一化助手消息中可持久化的展示协议。
 *
 * 参数：value 前端已适配后的 presentation。
 * 返回：仅包含页面重放需要的展示字段；没有有效字段时返回 null。
 * 说明：会话历史只保存业务可见展示字段，避免把后端调试、链路追踪等内部信息写入浏览器本地存储。
 */
function normalizeMessagePresentation(value: unknown): Record<string, any> | null {
  if (!isPlainObject(value)) return null
  const next: Record<string, any> = {}
  persistablePresentationKeys.forEach((key) => {
    if (!(key in value)) return
    const normalized = normalizePersistablePresentationValue(value[key])
    if (normalized !== undefined) next[key] = normalized
  })
  return Object.keys(next).length ? next : null
}

/**
 * 归一化可持久化展示值。
 *
 * 参数：value 展示字段原始值。
 * 返回：适合 JSON 持久化的基础类型、数组或普通对象。
 */
function normalizePersistablePresentationValue(value: unknown): any {
  if (value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value
  if (Array.isArray(value)) return value.map(normalizePersistablePresentationValue).filter((item) => item !== undefined)
  if (!isPlainObject(value)) return undefined
  const next: Record<string, any> = {}
  Object.entries(value).forEach(([key, entry]) => {
    if (key === 'debug' || key === 'trace' || key === 'planner' || key === 'guardrail' || key === 'sql') return
    const normalized = normalizePersistablePresentationValue(entry)
    if (normalized !== undefined) next[key] = normalized
  })
  return next
}

/**
 * 归一化助手消息中可持久化的原始响应。
 *
 * 参数：value 后端返回的原始业务响应。
 * 返回：仅包含安全明细表的最小对象；无可用明细时返回 null。
 * 说明：聊天历史不能持久化完整响应，避免内部规划、调试字段和大对象泄露；
 *       但需要保留 result_table 供“展开明细”和“导出 Excel”二级操作使用。
 */
function normalizeMessageRawResponse(value: unknown): Record<string, any> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const raw = value as Record<string, any>
  const safeResultTable = normalizeSafeResultTable(raw.result_table)
  if (!safeResultTable) return null
  return { result_table: safeResultTable }
}

/**
 * 白名单保留结果明细表。
 *
 * 参数：value 候选表格对象。
 * 返回：只含 columns/rows 的表格；没有行数据时返回 null。
 */
function normalizeSafeResultTable(value: unknown): { columns: string[]; rows: Array<Record<string, string | number | boolean | null>> } | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const raw = value as Record<string, unknown>
  if (!Array.isArray(raw.rows)) return null
  const rawRows = raw.rows.filter(isPlainObject)
  if (!rawRows.length) return null

  const rawColumns = Array.isArray(raw.columns) ? raw.columns : Object.keys(rawRows[0] || {})
  const columns = rawColumns
    .map((column) => String(column || '').trim())
    .filter((column, index, source) => Boolean(column) && source.indexOf(column) === index)
  if (!columns.length) return null

  const rows = rawRows.map((row) => {
    const next: Record<string, string | number | boolean | null> = {}
    columns.forEach((column) => {
      next[column] = normalizeSafeResultCell(row[column])
    })
    return next
  })
  return { columns, rows }
}

/** 判断候选值是否为普通对象。 */
function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
}

/**
 * 归一化可持久化的表格单元格。
 *
 * 参数：value 原始单元格值。
 * 返回：浏览器本地安全保存和导出的基础类型。
 */
function normalizeSafeResultCell(value: unknown): string | number | boolean | null {
  if (value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value
  if (value === undefined) return ''
  return String(value)
}

/**
 * 规范化消息并移除不参与展示的原始接口大对象。
 */
function normalizeMessage(value: unknown): BusinessChatMessage | null {
  if (!isMessage(value)) return null
  const raw = value as Record<string, any>
  return {
    id: raw.id,
    role: raw.role,
    content: raw.content,
    domain: raw.domain,
    status: typeof raw.status === 'string' ? raw.status : undefined,
    presentation: normalizeMessagePresentation(raw.presentation),
    createdAt: raw.createdAt,
    rawResponse: normalizeMessageRawResponse(raw.rawResponse),
    loading: Boolean(raw.loading),
    error: typeof raw.error === 'string' ? raw.error : undefined,
  }
}

/**
 * 判断摘要结构是否合法。
 */
function isSessionSummary(value: unknown): value is BusinessChatSessionSummary {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const raw = value as Record<string, unknown>
  return (
    typeof raw.id === 'string' &&
    typeof raw.title === 'string' &&
    isDomain(raw.domain) &&
    typeof raw.updatedAt === 'string' &&
    typeof raw.isNew === 'boolean'
  )
}

/**
 * 判断消息结构是否合法。
 */
function isMessage(value: unknown): value is BusinessChatMessage {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false
  const raw = value as Record<string, unknown>
  return (
    typeof raw.id === 'string' &&
    typeof raw.role === 'string' &&
    ['user', 'assistant', 'system'].includes(raw.role) &&
    typeof raw.content === 'string' &&
    isDomain(raw.domain) &&
    typeof raw.createdAt === 'string'
  )
}

/**
 * 判断业务域是否合法。
 */
function isDomain(value: unknown): value is BusinessChatDomain {
  return value === 'auto' || value === 'logistics' || value === 'plan_bom'
}

/**
 * 会话摘要按更新时间倒序。
 */
function sortSessionSummary(left: BusinessChatSessionSummary, right: BusinessChatSessionSummary) {
  return new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime()
}
