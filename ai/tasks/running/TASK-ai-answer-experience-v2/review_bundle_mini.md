# AI Answer Experience V2 Mini Review Bundle

Scope: upgrade existing deterministic-query + LLM-expression answer pipeline. Facts/status/tables/cards/chart remain deterministic. LLM may only rewrite visible narrative answer after validation.

Changed files in task scope:
- backend/app/services/business_answer_stream_service.py (new/untracked in current dirty branch but task-scoped)
- backend/app/domains/logistics/services/llm_answer_presentation_service.py
- backend/app/domains/logistics/schemas/data_qa.py
- frontend/src/api/logistics.ts
- frontend/src/api/planBom.ts
- frontend/src/utils/businessChatSessions.ts
- frontend/src/views/business-chat/BusinessChatPage.vue
- tests/business_acceptance/test_business_chat_answer_format_preference.py (new/untracked but task-scoped)

Verification already run:
- python -m pytest tests/business_acceptance/test_business_chat_answer_format_preference.py -q => 10 passed
- python -m pytest tests/business_acceptance -q => 173 passed, 2 warnings
- cd frontend && npm run build => passed
- browser E2E on fresh backend/Vite: ordinary logistics numeric question defaults to narrative, no cards/table/chart expanded; buttons enabled; localStorage rawResponse keys=[result_table], no query_plan/debug; console no errors.

Static scan of task patch:
- hardcoded_secrets=2, both are tests with api_key="test-key".
- shell_injection=0, eval_exec=0, pickle=0, SQL string formatting=0.

Key safety design:
1) BusinessAnswerStreamService.stream_answer() validates final streamed text before yielding. Invalid LLM output falls back to deterministic answer.
2) apply_streamed_answer() deep-copies deterministic payload and only updates presentation.answer and presentation.debug stream fields.
3) Stream validator rejects visible technical leaks: SQL, query_key, planner, guardrail, ods_/dwd_/dws_/dim_/fact_ table-like terms, and internal field names.
4) Stream validator rejects numeric hallucination by comparing numbers in answer text against deterministic payload/fallback/question context.
5) Logistics presentation defaults ordinary OK answers to display_type=narrative. table/cards/chart only when user explicitly requests table/cards/chart and payload supports them. Invalid LLM display type or visible leak falls back.
6) Caveats are split into caveat_items levels info/warning/danger. Generic “异常值归入其他” is not danger; danger is reserved for result-unusable or severe failure wording.
7) Frontend BusinessChat uses presentation.answer as main text. Cards/table/chart render only when backend display type says so or user manually expands detail. Data basis defaults folded.
8) Session persistence does NOT keep full rawResponse. It whitelists only rawResponse.result_table {columns, rows} for secondary details/export, preventing query_plan/debug from being stored/replayed.

Reviewer questions:
- Does this design preserve deterministic facts while improving expression?
- Any security concern from storing whitelisted result_table for audit/export?
- Any logic error in fail-closed stream validation or narrative-default UI?

## Snippet frontend/src/utils/businessChatSessions.ts:397-476
```
397|}
398|
399|/**
400| * 归一化助手消息中可持久化的原始响应。
401| *
402| * 参数：value 后端返回的原始业务响应。
403| * 返回：仅包含安全明细表的最小对象；无可用明细时返回 null。
404| * 说明：聊天历史不能持久化完整响应，避免内部规划、调试字段和大对象泄露；
405| *       但需要保留 result_table 供“展开明细”和“导出 Excel”二级操作使用。
406| */
407|function normalizeMessageRawResponse(value: unknown): Record<string, any> | null {
408|  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
409|  const raw = value as Record<string, any>
410|  const safeResultTable = normalizeSafeResultTable(raw.result_table)
411|  if (!safeResultTable) return null
412|  return { result_table: safeResultTable }
413|}
414|
415|/**
416| * 白名单保留结果明细表。
417| *
418| * 参数：value 候选表格对象。
419| * 返回：只含 columns/rows 的表格；没有行数据时返回 null。
420| */
421|function normalizeSafeResultTable(value: unknown): { columns: string[]; rows: Array<Record<string, string | number | boolean | null>> } | null {
422|  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
423|  const raw = value as Record<string, unknown>
424|  if (!Array.isArray(raw.rows)) return null
425|  const rawRows = raw.rows.filter(isPlainObject)
426|  if (!rawRows.length) return null
427|
428|  const rawColumns = Array.isArray(raw.columns) ? raw.columns : Object.keys(rawRows[0] || {})
429|  const columns = rawColumns
430|    .map((column) => String(column || '').trim())
431|    .filter((column, index, source) => Boolean(column) && source.indexOf(column) === index)
432|  if (!columns.length) return null
433|
434|  const rows = rawRows.map((row) => {
435|    const next: Record<string, string | number | boolean | null> = {}
436|    columns.forEach((column) => {
437|      next[column] = normalizeSafeResultCell(row[column])
438|    })
439|    return next
440|  })
441|  return { columns, rows }
442|}
443|
444|/** 判断候选值是否为普通对象。 */
445|function isPlainObject(value: unknown): value is Record<string, unknown> {
446|  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
447|}
448|
449|/**
450| * 归一化可持久化的表格单元格。
451| *
452| * 参数：value 原始单元格值。
453| * 返回：浏览器本地安全保存和导出的基础类型。
454| */
455|function normalizeSafeResultCell(value: unknown): string | number | boolean | null {
456|  if (value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value
457|  if (value === undefined) return ''
458|  return String(value)
459|}
460|
461|/**
462| * 规范化消息并移除不参与展示的原始接口大对象。
463| */
464|function normalizeMessage(value: unknown): BusinessChatMessage | null {
465|  if (!isMessage(value)) return null
466|  const raw = value as Record<string, any>
467|  return {
468|    id: raw.id,
469|    role: raw.role,
470|    content: raw.content,
471|    domain: raw.domain,
472|    status: typeof raw.status === 'string' ? raw.status : undefined,
473|    presentation: raw.presentation && typeof raw.presentation === 'object' && !Array.isArray(raw.presentation) ? raw.presentation : null,
474|    createdAt: raw.createdAt,
475|    rawResponse: normalizeMessageRawResponse(raw.rawResponse),
476|    loading: Boolean(raw.loading),
```

## Snippet frontend/src/views/business-chat/BusinessChatPage.vue:1841-1918
```
1841|/**
1842| * 判断是否展示二级操作。
1843| *
1844| * 参数：message 当前助手消息。
1845| * 返回：存在数据口径或审计明细时返回 true，把结构化结果放到主回答下方的次级入口。
1846| */
1847|function shouldShowSecondaryActions(message: BusinessChatMessage): boolean {
1848|  return Boolean(message.presentation && (hasAssistantBasis(message) || getAssistantAuditTable(message)?.rows.length))
1849|}
1850|
1851|/** 判断当前回答是否有可展开的数据口径。 */
1852|function hasAssistantBasis(message: BusinessChatMessage): boolean {
1853|  return getCaveatItemsByLevel(message, 'info').length > 0
1854|}
1855|
1856|/** 判断“数据口径”折叠区是否由二级按钮展开。 */
1857|function isAssistantBasisExpanded(message: BusinessChatMessage): boolean {
1858|  return expandedBasisMessageIds.value.has(message.id)
1859|}
1860|
1861|/** 切换“查看数据依据”折叠区，只影响 UI 展开状态，不改变后端事实。 */
1862|function toggleAssistantBasisDetails(message: BusinessChatMessage) {
1863|  expandedBasisMessageIds.value = toggleMessageIdSet(expandedBasisMessageIds.value, message.id)
1864|}
1865|
1866|/** 按等级读取口径提醒；没有新协议 caveatItems 时兼容旧 caveats。 */
1867|function getCaveatItemsByLevel(message: BusinessChatMessage, level: CaveatItem['level']): CaveatItem[] {
1868|  const presentation = message.presentation as UnifiedResult | null | undefined
1869|  if (!presentation) return []
1870|  const items = presentation.caveatItems.length ? presentation.caveatItems : normalizeCaveatItems([], presentation.caveats)
1871|  return items.filter((item) => item.level === level)
1872|}
1873|
1874|/** 获取审计/导出可用的明细表；叙事回答默认不展示，但仍保留给用户手动展开和导出。 */
1875|function getAssistantAuditTable(message: BusinessChatMessage): UnifiedTable | null {
1876|  const presentation = message.presentation as UnifiedResult | null | undefined
1877|  const presentationTable = normalizeTable(presentation?.table || null)
1878|  if (presentationTable) return presentationTable
1879|  const rawResponse = message.rawResponse as Record<string, any> | null | undefined
1880|  return normalizeTable((rawResponse?.result_table || rawResponse?.data?.result_table || null) as UnifiedTable | null)
1881|}
1882|
1883|/** 判断明细表当前是否应展开；显式表格问题默认展开，普通叙事问题需用户点击“展开明细”。 */
1884|function isAssistantTableExpanded(message: BusinessChatMessage): boolean {
1885|  if (collapsedTableMessageIds.value.has(message.id)) return false
1886|  const presentation = message.presentation as UnifiedResult | null | undefined
1887|  const hasRows = Boolean(getAssistantAuditTable(message)?.rows.length)
1888|  if (presentation && tableDisplayTypes.has(presentation.displayType) && hasRows) return true
1889|  return expandedTableMessageIds.value.has(message.id)
1890|}
1891|
1892|/** 切换明细展开状态，支持显式表格回答收起、叙事回答手动展开。 */
1893|function toggleAssistantTable(message: BusinessChatMessage) {
1894|  if (!getAssistantAuditTable(message)?.rows.length) return
1895|  if (isAssistantTableExpanded(message)) {
1896|    const nextExpanded = new Set(expandedTableMessageIds.value)
1897|    nextExpanded.delete(message.id)
1898|    expandedTableMessageIds.value = nextExpanded
1899|    collapsedTableMessageIds.value = addMessageIdToSet(collapsedTableMessageIds.value, message.id)
1900|    return
1901|  }
1902|  expandedTableMessageIds.value = addMessageIdToSet(expandedTableMessageIds.value, message.id)
1903|  collapsedTableMessageIds.value = removeMessageIdFromSet(collapsedTableMessageIds.value, message.id)
1904|}
1905|
1906|/** 获取当前助手消息的可见明细表；默认只在显式表格或用户手动展开时返回。 */
1907|function getAssistantResultTable(message: BusinessChatMessage): UnifiedTable | null {
1908|  const presentation = message.presentation as UnifiedResult | null | undefined
1909|  if (!presentation || !isAssistantTableExpanded(message)) return null
1910|  if (tableDisplayTypes.has(presentation.displayType)) return getAssistantAuditTable(message)
1911|  return expandedTableMessageIds.value.has(message.id) ? getAssistantAuditTable(message) : null
1912|}
1913|
1914|/** 表格只在后端返回有效列和行且当前允许展开时展示，避免空表占据叙事型回答空间。 */
1915|function shouldShowResultTable(message: BusinessChatMessage): boolean {
1916|  const table = getAssistantResultTable(message)
1917|  return Boolean(table?.columns.length && table.rows.length)
1918|}
```

## Snippet tests/business_acceptance/test_business_chat_answer_format_preference.py:206-315
```
206|def test_streamed_answer_rejects_new_numbers_and_keeps_structured_fields() -> None:
207|    """LLM 流式表达新增确定性上下文外数值时，必须降级且不改结构化事实。"""
208|
209|    payload = _stream_payload()
210|    fallback_answer = str(payload["answer_summary"])
211|    service = BusinessAnswerStreamService(
212|        enabled=True,
213|        base_url="http://llm.local",
214|        api_key="test-key",
215|        model="test-model",
216|        client=_FakeStreamClient(["华东 120.5MW，华南 88.2MW，另有华北 999MW。"]),
217|    )
218|
219|    streamed_answer = "".join(
220|        service.stream_answer(
221|            domain="logistics",
222|            question="统计2026年各区域发运量",
223|            deterministic_payload=payload,
224|            fallback_answer=fallback_answer,
225|        )
226|    )
227|    final_payload = service.apply_streamed_answer(
228|        domain="logistics",
229|        deterministic_payload=payload,
230|        streamed_answer=streamed_answer,
231|    )
232|
233|    assert streamed_answer == fallback_answer
234|    assert final_payload["presentation"]["answer"] == fallback_answer
235|    assert final_payload["result_table"] == payload["result_table"]
236|    assert final_payload["presentation"]["table_spec"] == payload["presentation"]["table_spec"]
237|    assert final_payload["presentation"]["debug"]["stream_answer_source"] == "deterministic_fallback"
238|    assert final_payload["presentation"]["debug"]["stream_fallback_reason"] == "stream_text_number_hallucination"
239|
240|
241|def test_streamed_answer_rejects_visible_technical_leaks() -> None:
242|    """LLM 流式表达暴露 SQL、query_key、planner 或数仓表名时，必须降级到确定性答案。"""
243|
244|    payload = _stream_payload()
245|    fallback_answer = str(payload["answer_summary"])
246|    service = BusinessAnswerStreamService(
247|        enabled=True,
248|        base_url="http://llm.local",
249|        api_key="test-key",
250|        model="test-model",
251|        client=_FakeStreamClient(["planner 命中 query_key=sys_region_mw，SQL 来自 dws_logistics_detail_union。"]),
252|    )
253|
254|    streamed_answer = "".join(
255|        service.stream_answer(
256|            domain="logistics",
257|            question="统计2026年各区域发运量",
258|            deterministic_payload=payload,
259|            fallback_answer=fallback_answer,
260|        )
261|    )
262|    final_payload = service.apply_streamed_answer(
263|        domain="logistics",
264|        deterministic_payload=payload,
265|        streamed_answer=streamed_answer,
266|    )
267|
268|    assert streamed_answer == fallback_answer
269|    assert final_payload["presentation"]["answer"] == fallback_answer
270|    assert final_payload["presentation"]["debug"]["stream_answer_source"] == "deterministic_fallback"
271|    assert final_payload["presentation"]["debug"]["stream_fallback_reason"] == "stream_technical_visible_leak"
272|
273|
274|def test_business_chat_frontend_uses_caveat_levels_secondary_actions_and_stream_stages() -> None:
275|    """前端主回答应以 answer 为主，并把口径、明细和导出放到二级动作中。"""
276|
277|    page = "frontend/src/views/business-chat/BusinessChatPage.vue"
278|    with open(page, encoding="utf-8") as file:
279|        chat = file.read()
280|    template = chat.split("<script setup", 1)[0]
281|
282|    assert "caveatItems" in chat
283|    assert "data-testid=\"answer-secondary-actions\"" in template
284|    assert "查看数据依据" in template
285|    assert "展开明细" in template
286|    assert "getAssistantAuditTable" in chat
287|    assert "result-caveats--info" in chat
288|    assert "result-caveats--warning" in chat
289|    assert "result-caveats--danger" in chat
290|    assert "function resolveLoadingText" in chat
291|    assert "function updateAssistantStreamMeta" in chat
292|    assert "正在理解问题" in chat
293|    assert "正在查询数据" in chat
294|    assert "正在组织回答" in chat
295|    assert "正在生成回答" in chat
296|    assert "onMeta:" in chat
297|    assert "rawResponse?.query_plan" not in chat
298|    assert "rawResponse?.presentation?.debug" not in chat
299|
300|
301|def test_business_chat_session_keeps_only_safe_audit_table_for_secondary_actions() -> None:
302|    """会话持久化不能丢失明细依据，但只能白名单保留 result_table，避免暴露 query_key/debug。"""
303|
304|    page = "frontend/src/utils/businessChatSessions.ts"
305|    with open(page, encoding="utf-8") as file:
306|        sessions = file.read()
307|
308|    assert "rawResponse: normalizeMessageRawResponse(raw.rawResponse)" in sessions
309|    assert "function normalizeMessageRawResponse" in sessions
310|    assert "result_table: safeResultTable" in sessions
311|    assert "query_plan" not in sessions
312|    assert "presentation?.debug" not in sessions
313|    assert "rawResponse: null" not in sessions
```
