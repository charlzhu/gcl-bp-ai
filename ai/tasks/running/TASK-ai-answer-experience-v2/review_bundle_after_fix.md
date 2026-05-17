# AI Answer Experience V2 Mini Review Bundle After Fix

Scope: upgrade deterministic-query + LLM-expression answer pipeline. Facts/status/tables/cards/chart remain deterministic. LLM may only rewrite visible narrative answer after validation.

Verification after reviewer fixes:
- TDD RED reproduced two reviewer findings before fix: presentation debug persistence and caveatItems undefined guard.
- Focused reviewer-fix tests => 2 passed.
- python -m pytest tests/business_acceptance/test_business_chat_answer_format_preference.py -q => 11 passed.
- python -m pytest tests/business_acceptance -q => 174 passed, 2 warnings.
- cd frontend && npm run build => passed.
- browser E2E fresh backend/Vite: default narrative, no cards/table/chart expanded, secondary buttons enabled, localStorage presentation keys contain no debug, rawResponse keys=[result_table], no raw query_plan/debug, console no errors.

Static scan of task patch:
- hardcoded_secrets=2, both are tests with api_key="test-key".
- shell_injection=0, eval_exec=0, pickle=0, SQL string formatting=0.

Previous independent Codex review findings and fixes:
1) Finding: session persistence could persist presentation.debug. Fix: normalizeMessage() now uses normalizeMessagePresentation(raw.presentation), top-level whitelist + recursive removal of debug/trace/planner/guardrail/sql.
2) Finding: getCaveatItemsByLevel used presentation.caveatItems.length without old-payload guard. Fix: Array.isArray(presentation.caveatItems) guard and caveats fallback guard.

Reviewer questions: Any remaining security_concerns or logic_errors? If none, passed=true.

## Snippet frontend/src/utils/businessChatSessions.ts:397-535
```
397|}
398|
399|const persistablePresentationKeys = new Set([
400|  'displayType',
401|  'display_type',
402|  'title',
403|  'answer',
404|  'highlights',
405|  'cards',
406|  'chart',
407|  'chart_spec',
408|  'table',
409|  'table_spec',
410|  'followUps',
411|  'follow_up',
412|  'suggestions',
413|  'caveats',
414|  'caveatItems',
415|  'caveat_items',
416|])
417|
418|/**
419| * 归一化助手消息中可持久化的展示协议。
420| *
421| * 参数：value 前端已适配后的 presentation。
422| * 返回：仅包含页面重放需要的展示字段；没有有效字段时返回 null。
423| * 说明：会话历史只保存业务可见展示字段，避免把后端调试、链路追踪等内部信息写入浏览器本地存储。
424| */
425|function normalizeMessagePresentation(value: unknown): Record<string, any> | null {
426|  if (!isPlainObject(value)) return null
427|  const next: Record<string, any> = {}
428|  persistablePresentationKeys.forEach((key) => {
429|    if (!(key in value)) return
430|    const normalized = normalizePersistablePresentationValue(value[key])
431|    if (normalized !== undefined) next[key] = normalized
432|  })
433|  return Object.keys(next).length ? next : null
434|}
435|
436|/**
437| * 归一化可持久化展示值。
438| *
439| * 参数：value 展示字段原始值。
440| * 返回：适合 JSON 持久化的基础类型、数组或普通对象。
441| */
442|function normalizePersistablePresentationValue(value: unknown): any {
443|  if (value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value
444|  if (Array.isArray(value)) return value.map(normalizePersistablePresentationValue).filter((item) => item !== undefined)
445|  if (!isPlainObject(value)) return undefined
446|  const next: Record<string, any> = {}
447|  Object.entries(value).forEach(([key, entry]) => {
448|    if (key === 'debug' || key === 'trace' || key === 'planner' || key === 'guardrail' || key === 'sql') return
449|    const normalized = normalizePersistablePresentationValue(entry)
450|    if (normalized !== undefined) next[key] = normalized
451|  })
452|  return next
453|}
454|
455|/**
456| * 归一化助手消息中可持久化的原始响应。
457| *
458| * 参数：value 后端返回的原始业务响应。
459| * 返回：仅包含安全明细表的最小对象；无可用明细时返回 null。
460| * 说明：聊天历史不能持久化完整响应，避免内部规划、调试字段和大对象泄露；
461| *       但需要保留 result_table 供“展开明细”和“导出 Excel”二级操作使用。
462| */
463|function normalizeMessageRawResponse(value: unknown): Record<string, any> | null {
464|  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
465|  const raw = value as Record<string, any>
466|  const safeResultTable = normalizeSafeResultTable(raw.result_table)
467|  if (!safeResultTable) return null
468|  return { result_table: safeResultTable }
469|}
470|
471|/**
472| * 白名单保留结果明细表。
473| *
474| * 参数：value 候选表格对象。
475| * 返回：只含 columns/rows 的表格；没有行数据时返回 null。
476| */
477|function normalizeSafeResultTable(value: unknown): { columns: string[]; rows: Array<Record<string, string | number | boolean | null>> } | null {
478|  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
479|  const raw = value as Record<string, unknown>
480|  if (!Array.isArray(raw.rows)) return null
481|  const rawRows = raw.rows.filter(isPlainObject)
482|  if (!rawRows.length) return null
483|
484|  const rawColumns = Array.isArray(raw.columns) ? raw.columns : Object.keys(rawRows[0] || {})
485|  const columns = rawColumns
486|    .map((column) => String(column || '').trim())
487|    .filter((column, index, source) => Boolean(column) && source.indexOf(column) === index)
488|  if (!columns.length) return null
489|
490|  const rows = rawRows.map((row) => {
491|    const next: Record<string, string | number | boolean | null> = {}
492|    columns.forEach((column) => {
493|      next[column] = normalizeSafeResultCell(row[column])
494|    })
495|    return next
496|  })
497|  return { columns, rows }
498|}
499|
500|/** 判断候选值是否为普通对象。 */
501|function isPlainObject(value: unknown): value is Record<string, unknown> {
502|  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
503|}
504|
505|/**
506| * 归一化可持久化的表格单元格。
507| *
508| * 参数：value 原始单元格值。
509| * 返回：浏览器本地安全保存和导出的基础类型。
510| */
511|function normalizeSafeResultCell(value: unknown): string | number | boolean | null {
512|  if (value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value
513|  if (value === undefined) return ''
514|  return String(value)
515|}
516|
517|/**
518| * 规范化消息并移除不参与展示的原始接口大对象。
519| */
520|function normalizeMessage(value: unknown): BusinessChatMessage | null {
521|  if (!isMessage(value)) return null
522|  const raw = value as Record<string, any>
523|  return {
524|    id: raw.id,
525|    role: raw.role,
526|    content: raw.content,
527|    domain: raw.domain,
528|    status: typeof raw.status === 'string' ? raw.status : undefined,
529|    presentation: normalizeMessagePresentation(raw.presentation),
530|    createdAt: raw.createdAt,
531|    rawResponse: normalizeMessageRawResponse(raw.rawResponse),
532|    loading: Boolean(raw.loading),
533|    error: typeof raw.error === 'string' ? raw.error : undefined,
534|  }
535|}
```

## Snippet frontend/src/views/business-chat/BusinessChatPage.vue:1866-1918
```
1866|/** 按等级读取口径提醒；没有新协议 caveatItems 时兼容旧 caveats。 */
1867|function getCaveatItemsByLevel(message: BusinessChatMessage, level: CaveatItem['level']): CaveatItem[] {
1868|  const presentation = message.presentation as UnifiedResult | null | undefined
1869|  if (!presentation) return []
1870|  const safeCaveatItems = Array.isArray(presentation.caveatItems) ? presentation.caveatItems : []
1871|  const items = safeCaveatItems.length ? safeCaveatItems : normalizeCaveatItems([], Array.isArray(presentation.caveats) ? presentation.caveats : [])
1872|  return items.filter((item) => item.level === level)
1873|}
1874|
1875|/** 获取审计/导出可用的明细表；叙事回答默认不展示，但仍保留给用户手动展开和导出。 */
1876|function getAssistantAuditTable(message: BusinessChatMessage): UnifiedTable | null {
1877|  const presentation = message.presentation as UnifiedResult | null | undefined
1878|  const presentationTable = normalizeTable(presentation?.table || null)
1879|  if (presentationTable) return presentationTable
1880|  const rawResponse = message.rawResponse as Record<string, any> | null | undefined
1881|  return normalizeTable((rawResponse?.result_table || rawResponse?.data?.result_table || null) as UnifiedTable | null)
1882|}
1883|
1884|/** 判断明细表当前是否应展开；显式表格问题默认展开，普通叙事问题需用户点击“展开明细”。 */
1885|function isAssistantTableExpanded(message: BusinessChatMessage): boolean {
1886|  if (collapsedTableMessageIds.value.has(message.id)) return false
1887|  const presentation = message.presentation as UnifiedResult | null | undefined
1888|  const hasRows = Boolean(getAssistantAuditTable(message)?.rows.length)
1889|  if (presentation && tableDisplayTypes.has(presentation.displayType) && hasRows) return true
1890|  return expandedTableMessageIds.value.has(message.id)
1891|}
1892|
1893|/** 切换明细展开状态，支持显式表格回答收起、叙事回答手动展开。 */
1894|function toggleAssistantTable(message: BusinessChatMessage) {
1895|  if (!getAssistantAuditTable(message)?.rows.length) return
1896|  if (isAssistantTableExpanded(message)) {
1897|    const nextExpanded = new Set(expandedTableMessageIds.value)
1898|    nextExpanded.delete(message.id)
1899|    expandedTableMessageIds.value = nextExpanded
1900|    collapsedTableMessageIds.value = addMessageIdToSet(collapsedTableMessageIds.value, message.id)
1901|    return
1902|  }
1903|  expandedTableMessageIds.value = addMessageIdToSet(expandedTableMessageIds.value, message.id)
1904|  collapsedTableMessageIds.value = removeMessageIdFromSet(collapsedTableMessageIds.value, message.id)
1905|}
1906|
1907|/** 获取当前助手消息的可见明细表；默认只在显式表格或用户手动展开时返回。 */
1908|function getAssistantResultTable(message: BusinessChatMessage): UnifiedTable | null {
1909|  const presentation = message.presentation as UnifiedResult | null | undefined
1910|  if (!presentation || !isAssistantTableExpanded(message)) return null
1911|  if (tableDisplayTypes.has(presentation.displayType)) return getAssistantAuditTable(message)
1912|  return expandedTableMessageIds.value.has(message.id) ? getAssistantAuditTable(message) : null
1913|}
1914|
1915|/** 表格只在后端返回有效列和行且当前允许展开时展示，避免空表占据叙事型回答空间。 */
1916|function shouldShowResultTable(message: BusinessChatMessage): boolean {
1917|  const table = getAssistantResultTable(message)
1918|  return Boolean(table?.columns.length && table.rows.length)
```

## Snippet tests/business_acceptance/test_business_chat_answer_format_preference.py:301-330
```
301|def test_business_chat_session_keeps_only_safe_audit_table_for_secondary_actions() -> None:
302|    """会话持久化不能丢失明细依据，但只能白名单保留 result_table，避免暴露 query_key/debug。"""
303|
304|    page = "frontend/src/utils/businessChatSessions.ts"
305|    with open(page, encoding="utf-8") as file:
306|        sessions = file.read()
307|
308|    assert "rawResponse: normalizeMessageRawResponse(raw.rawResponse)" in sessions
309|    assert "presentation: normalizeMessagePresentation(raw.presentation)" in sessions
310|    assert "function normalizeMessagePresentation" in sessions
311|    assert "function normalizeMessageRawResponse" in sessions
312|    assert "result_table: safeResultTable" in sessions
313|    assert "query_plan" not in sessions
314|    assert "presentation?.debug" not in sessions
315|    assert "presentation: raw.presentation &&" not in sessions
316|    assert "rawResponse: null" not in sessions
317|
318|
319|def test_business_chat_frontend_caveat_items_guard_old_payloads() -> None:
320|    """旧会话或旧服务端 payload 没有 caveatItems 时，前端应回落到 caveats 而不是读取 undefined.length。"""
321|
322|    page = "frontend/src/views/business-chat/BusinessChatPage.vue"
323|    with open(page, encoding="utf-8") as file:
324|        chat = file.read()
325|
326|    assert "Array.isArray(presentation.caveatItems)" in chat
327|    assert "presentation.caveatItems.length ? presentation.caveatItems" not in chat
```
