/**
 * 查询结果展示输入。
 * 说明：
 * 1. 用于统一自然语言查询页与条件查询页的结果展示视图；
 * 2. 当后端没有完整返回 status / result_explanation / no_result_analysis 时，
 *    这里做最小前端兼容，不改动后端接口主结构；
 * 3. 所有兼容字段仅服务页面展示，不回写后端。
 */
export interface QueryResultPresentationInput {
  queryResult: Record<string, any> | null
  parsed?: Record<string, any> | null
  question?: string | null
  requestPayload?: Record<string, any> | null
  responseMeta?: Record<string, any> | null
}

/**
 * 统一状态结构。
 */
export interface QueryResultStatusView {
  code: string
  message: string
  success: boolean
  severity: string
  execution_mode?: string | null
}

/**
 * 结果解释结构。
 */
export interface QueryResultExplanationView {
  summary: string
  highlights: string[]
  notes: string[]
  result_count: number
  query_type?: string | null
  metric_type?: string | null
  source_scope?: string | null
  execution_mode?: string | null
}

/**
 * 空结果分析结构。
 */
export interface QueryResultNoDataView {
  question: string
  possible_reasons: string[]
  suggestions: string[]
  execution_mode?: string | null
  is_empty_result: boolean
}

/**
 * 模板命中展示结构。
 */
export interface QueryTemplateInfoView {
  template_hit: boolean
  template_id?: string | null
  template_name?: string | null
  template_score?: number | null
  template_match_reasons: string[]
}

/**
 * 汇总项展示结构。
 */
export interface QuerySummaryEntryView {
  key: string
  label: string
  value: unknown
}

/**
 * 查询结果页面统一展示结构。
 */
export interface QueryResultPresentationView {
  status: QueryResultStatusView
  executionMode: string | null
  queryType: string | null
  metricType: string | null
  sourceScope: string | null
  resultCount: number
  hasItems: boolean
  showCompareSummary: boolean
  compatibilityNotice: string[]
  resultExplanation: QueryResultExplanationView | null
  noResultAnalysis: QueryResultNoDataView | null
  templateInfo: QueryTemplateInfoView | null
  summaryEntries: QuerySummaryEntryView[]
}

const SUMMARY_LABELS: Record<string, string> = {
  shipment_watt: '运量',
  shipment_count: '发货件数',
  shipment_trip_count: '车次',
  total_fee: '总费用',
  extra_fee: '附加费',
  row_count: '记录数',
}

/**
 * 构建统一的查询结果展示视图。
 */
export function buildQueryResultPresentation(
  input: QueryResultPresentationInput,
): QueryResultPresentationView {
  const queryResult = normalizeObject(input.queryResult) || {}
  const responseMeta =
    normalizeObject(input.responseMeta) ||
    normalizeObject(queryResult.response_meta) ||
    {}
  const parsed = normalizeObject(input.parsed) || {}
  const executionMode =
    readString(queryResult.execution_mode) ||
    readString(responseMeta?.status?.execution_mode) ||
    null
  const queryType =
    readString(queryResult.query_type) ||
    readString(responseMeta?.mode) ||
    readString(parsed?.mode) ||
    null
  const metricType =
    readString(queryResult.metric_type) ||
    readString(responseMeta?.metric_type) ||
    readString(parsed?.metric_type) ||
    readString(input.requestPayload?.metric_type) ||
    null
  const sourceScope =
    readString(queryResult.source_scope) ||
    readString(responseMeta?.source_scope) ||
    readString(parsed?.source_scope) ||
    readString(input.requestPayload?.source_scope) ||
    null
  const resultCount = resolveResultCount(queryResult)
  const hasItems = Array.isArray(queryResult.items) && queryResult.items.length > 0
  const showCompareSummary = Boolean(
    !hasItems &&
      (queryResult.left_value !== undefined ||
        queryResult.right_value !== undefined ||
        queryResult.diff_value !== undefined),
  )

  const status = resolveStatus({
    queryResult,
    responseMeta,
    executionMode,
  })

  const resultExplanation =
    normalizeExplanation(queryResult.result_explanation) ||
    buildSyntheticExplanation({
      queryResult,
      status,
      executionMode,
      queryType,
      metricType,
      sourceScope,
      resultCount,
    })

  const noResultAnalysis =
    normalizeNoResultAnalysis(queryResult.no_result_analysis) ||
    buildSyntheticNoResultAnalysis({
      status,
      queryType,
      executionMode,
      question: readString(input.question) || buildSyntheticQuestion(input.requestPayload, queryType),
      requestPayload: normalizeObject(input.requestPayload),
    })

  const compatibilityNotice = collectCompatibilityNotice({
    queryResult,
    hasSyntheticStatus: !queryResult.status,
    hasSyntheticExplanation: !queryResult.result_explanation,
    hasSyntheticNoResultAnalysis: !queryResult.no_result_analysis && Boolean(noResultAnalysis),
  })

  return {
    status,
    executionMode,
    queryType,
    metricType,
    sourceScope,
    resultCount,
    hasItems,
    showCompareSummary,
    compatibilityNotice,
    resultExplanation,
    noResultAnalysis,
    templateInfo: buildTemplateInfo(parsed),
    summaryEntries: buildSummaryEntries(queryResult.summary),
  }
}

/**
 * 统一处理对象空值。
 */
function normalizeObject(value: unknown): Record<string, any> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, any>
}

/**
 * 读取字符串字段。
 */
function readString(value: unknown): string | null {
  if (typeof value !== 'string') return null
  const normalized = value.trim()
  return normalized ? normalized : null
}

/**
 * 解析结果条数。
 * 说明：
 * 1. 优先沿用后端明确返回的数量字段；
 * 2. 没有时再退回 items 长度或汇总记录数；
 * 3. 这样条件查询直返 aggregate 时也能稳定展示数量。
 */
function resolveResultCount(queryResult: Record<string, any> | null): number {
  if (!queryResult) return 0

  const candidates = [
        queryResult.result_explanation?.result_count,
        queryResult.item_count,
        queryResult.record_count,
        queryResult.total,
      ]

  for (const candidate of candidates) {
    const parsedNumber = toNumber(candidate)
    if (parsedNumber !== null) return parsedNumber
  }

  if (Array.isArray(queryResult.items)) {
    return queryResult.items.length
  }

  const rowCount = toNumber(queryResult.summary?.row_count)
  if (rowCount !== null) return rowCount

  return 0
}

/**
 * 解析数值。
 */
function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string' && value.trim()) {
    const normalized = Number(value)
    if (Number.isFinite(normalized)) return normalized
  }
  return null
}

/**
 * 判断当前结果是否具备实际数据。
 */
function hasMeaningfulResult(queryResult: Record<string, any> | null): boolean {
  if (!queryResult) return false
  if (Array.isArray(queryResult.items) && queryResult.items.length > 0) return true
  if (
    queryResult.left_value !== undefined ||
    queryResult.right_value !== undefined ||
    queryResult.diff_value !== undefined
  ) {
    return true
  }

  const rowCount = toNumber(queryResult.summary?.row_count)
  if (rowCount !== null) {
    return rowCount > 0
  }

  const summary = normalizeObject(queryResult.summary)
  if (!summary) return false

  return Object.values(summary).some((value) => {
    const numberValue = toNumber(value)
    return numberValue !== null && numberValue !== 0
  })
}

/**
 * 归一化状态字段。
 */
function resolveStatus(params: {
  queryResult: Record<string, any> | null
  responseMeta: Record<string, any> | null
  executionMode: string | null
}): QueryResultStatusView {
  const fromQueryResult = normalizeStatus(params.queryResult?.status)
  if (fromQueryResult) return fromQueryResult

  const fromMeta = normalizeStatus(params.responseMeta?.status)
  if (fromMeta) return fromMeta

  if (!hasMeaningfulResult(params.queryResult)) {
    return {
      code: 'EMPTY_RESULT',
      message: '当前查询已执行完成，但未返回匹配数据。',
      success: true,
      severity: 'warning',
      execution_mode: params.executionMode,
    }
  }

  return {
    code: 'OK',
    message: '查询执行成功。',
    success: true,
    severity: 'info',
    execution_mode: params.executionMode,
  }
}

/**
 * 归一化后端状态对象。
 */
function normalizeStatus(value: unknown): QueryResultStatusView | null {
  const status = normalizeObject(value)
  if (!status) return null
  return {
    code: readString(status.code) || 'UNKNOWN',
    message: readString(status.message) || '-',
    success: Boolean(status.success),
    severity: readString(status.severity) || 'info',
    execution_mode: readString(status.execution_mode),
  }
}

/**
 * 归一化后端结果解释。
 */
function normalizeExplanation(value: unknown): QueryResultExplanationView | null {
  const explanation = normalizeObject(value)
  if (!explanation) return null
  return {
    summary: readString(explanation.summary) || '-',
    highlights: normalizeStringArray(explanation.highlights),
    notes: normalizeStringArray(explanation.notes),
    result_count: toNumber(explanation.result_count) || 0,
    query_type: readString(explanation.query_type),
    metric_type: readString(explanation.metric_type),
    source_scope: readString(explanation.source_scope),
    execution_mode: readString(explanation.execution_mode),
  }
}

/**
 * 构建前端兼容结果解释。
 */
function buildSyntheticExplanation(params: {
  queryResult: Record<string, any> | null
  status: QueryResultStatusView
  executionMode: string | null
  queryType: string | null
  metricType: string | null
  sourceScope: string | null
  resultCount: number
}): QueryResultExplanationView {
  const queryTypeLabel = formatQueryTypeLabel(params.queryType)
  const hasData = hasMeaningfulResult(params.queryResult)
  const suffix = resolveResultSuffix(params.queryType)
  const summary = hasData
    ? `当前${queryTypeLabel}已执行完成，返回 ${params.resultCount} 条${suffix}。`
    : `当前${queryTypeLabel}已执行完成，但未返回匹配数据。`

  return {
    summary,
    highlights: buildSummaryHighlights(params.queryResult?.summary),
    notes: ['当前结果解释由前端根据现有接口返回结构兼容生成。'],
    result_count: params.resultCount,
    query_type: params.queryType,
    metric_type: params.metricType,
    source_scope: params.sourceScope,
    execution_mode: params.executionMode,
  }
}

/**
 * 归一化后端空结果分析。
 */
function normalizeNoResultAnalysis(value: unknown): QueryResultNoDataView | null {
  const analysis = normalizeObject(value)
  if (!analysis) return null
  return {
    question: readString(analysis.question) || '-',
    possible_reasons: normalizeStringArray(analysis.possible_reasons),
    suggestions: normalizeStringArray(analysis.suggestions),
    execution_mode: readString(analysis.execution_mode),
    is_empty_result: Boolean(analysis.is_empty_result),
  }
}

/**
 * 构建前端兼容空结果分析。
 */
function buildSyntheticNoResultAnalysis(params: {
  status: QueryResultStatusView
  queryType: string | null
  executionMode: string | null
  question: string
  requestPayload: Record<string, any> | null
}): QueryResultNoDataView | null {
  if (params.status.code !== 'EMPTY_RESULT') return null

  const possibleReasons: string[] = []
  const suggestions: string[] = []

  const yearMonthList = Array.isArray(params.requestPayload?.year_month_list)
    ? params.requestPayload?.year_month_list.filter(Boolean)
    : []
  if (yearMonthList.length > 0) {
    possibleReasons.push(`当前已按月份 ${yearMonthList.join('、')} 过滤，可能该时间段没有匹配数据。`)
  }

  if (readString(params.requestPayload?.customer_name)) {
    possibleReasons.push(`当前已按客户“${params.requestPayload?.customer_name}”过滤，可能该客户在所选条件下没有记录。`)
  }
  if (readString(params.requestPayload?.logistics_company_name)) {
    possibleReasons.push(`当前已按物流公司“${params.requestPayload?.logistics_company_name}”过滤，可能该公司没有匹配数据。`)
  }
  if (readString(params.requestPayload?.region_name)) {
    possibleReasons.push(`当前已按区域“${params.requestPayload?.region_name}”过滤，可能筛选条件过窄。`)
  }

  if (possibleReasons.length === 0) {
    possibleReasons.push(`当前${formatQueryTypeLabel(params.queryType)}在现有筛选条件下没有命中数据。`)
  }

  suggestions.push('建议先放宽时间范围或移除部分筛选条件后重试。')
  suggestions.push('如需确认数据来源差异，可切换来源范围后再次查询。')

  return {
    question: params.question || '-',
    possible_reasons: possibleReasons,
    suggestions,
    execution_mode: params.executionMode,
    is_empty_result: true,
  }
}

/**
 * 收集兼容提示。
 */
function collectCompatibilityNotice(params: {
  queryResult: Record<string, any> | null
  hasSyntheticStatus: boolean
  hasSyntheticExplanation: boolean
  hasSyntheticNoResultAnalysis: boolean
}): string[] {
  const notices = normalizeStringArray(params.queryResult?.compatibility_notice)
  if (
    params.queryResult?.query_type === 'aggregate' &&
    (params.hasSyntheticStatus || params.hasSyntheticExplanation || params.hasSyntheticNoResultAnalysis)
  ) {
    notices.push('当前条件查询直连 aggregate 接口，状态与结果解释由前端按现有返回结构兼容生成。')
  }
  return Array.from(new Set(notices))
}

/**
 * 生成模板命中展示信息。
 */
function buildTemplateInfo(parsed: Record<string, any> | null): QueryTemplateInfoView | null {
  if (!parsed) return null
  if (!parsed.template_id && parsed.template_hit === undefined) return null
  return {
    template_hit: Boolean(parsed.template_hit),
    template_id: readString(parsed.template_id),
    template_name: readString(parsed.template_name),
    template_score: toNumber(parsed.template_score),
    template_match_reasons: normalizeStringArray(parsed.template_match_reasons),
  }
}

/**
 * 构建汇总项展示列表。
 */
function buildSummaryEntries(summary: unknown): QuerySummaryEntryView[] {
  const summaryObject = normalizeObject(summary)
  if (!summaryObject) return []

  return Object.entries(summaryObject).map(([key, value]) => ({
    key,
    label: SUMMARY_LABELS[key] || key,
    value,
  }))
}

/**
 * 根据汇总生成简短亮点。
 */
function buildSummaryHighlights(summary: unknown): string[] {
  const entries = buildSummaryEntries(summary)
  return entries
    .filter((entry) => {
      const numberValue = toNumber(entry.value)
      return numberValue === null || numberValue !== 0
    })
    .slice(0, 3)
    .map((entry) => `${entry.label}：${formatInlineValue(entry.value)}`)
}

/**
 * 归一化字符串数组。
 */
function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((item) => readString(item))
    .filter((item): item is string => Boolean(item))
}

/**
 * 生成兼容问题描述。
 */
function buildSyntheticQuestion(
  requestPayload: Record<string, any> | null | undefined,
  queryType: string | null,
): string {
  if (!requestPayload) return formatQueryTypeLabel(queryType)

  const yearMonthList = Array.isArray(requestPayload.year_month_list)
    ? requestPayload.year_month_list.filter(Boolean)
    : []
  const metricType = formatMetricTypeLabel(readString(requestPayload.metric_type))
  if (yearMonthList.length > 0) {
    return `${yearMonthList.join('、')} 的 ${metricType}`
  }
  return `${formatQueryTypeLabel(queryType)}：${metricType}`
}

/**
 * 结果文案后缀。
 */
function resolveResultSuffix(queryType: string | null): string {
  if (queryType === 'detail') return '明细记录'
  if (queryType === 'compare') return '对比结果'
  return '结果'
}

/**
 * 查询类型中文名。
 */
export function formatQueryTypeLabel(value: string | null | undefined): string {
  if (value === 'aggregate') return '结构化统计'
  if (value === 'detail') return '明细查询'
  if (value === 'compare') return '对比查询'
  if (value === 'nl_query') return '自然语言查询'
  return value || '-'
}

/**
 * 指标中文名。
 */
export function formatMetricTypeLabel(value: string | null | undefined): string {
  if (value === 'shipment_watt') return '运量（瓦数）'
  if (value === 'shipment_trip_count') return '车次'
  if (value === 'shipment_count') return '发货件数'
  if (value === 'total_fee') return '总费用'
  if (value === 'extra_fee') return '附加费'
  return value || '-'
}

/**
 * 来源范围中文名。
 */
export function formatSourceScopeLabel(value: string | null | undefined): string {
  if (value === 'hist') return '历史 Excel'
  if (value === 'sys') return '正式系统'
  if (value === 'all') return '历史 + 系统'
  return value || '-'
}

/**
 * 执行模式中文名。
 */
export function formatExecutionModeLabel(value: string | null | undefined): string {
  if (value === 'database') return '数据库'
  if (value === 'fallback') return '兼容模式'
  if (value === 'error_fallback') return '错误兜底'
  return value || '-'
}

/**
 * 行内展示值格式化。
 */
function formatInlineValue(value: unknown): string {
  const numberValue = toNumber(value)
  if (numberValue !== null) return numberValue.toLocaleString()
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}
