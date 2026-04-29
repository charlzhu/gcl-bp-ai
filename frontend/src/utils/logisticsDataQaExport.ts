import * as XLSX from 'xlsx'
import type { LogisticsDataQaResult } from '@/api/logistics'

export interface LogisticsDataQaExportPayload {
  question: string
  queryTime: string
  statusLabel: string
  answerSummary: string
  result: LogisticsDataQaResult
  columnLabelResolver?: (column: string) => string
}

/**
 * 导出物流数据问答结果为 CSV。
 * 说明：
 * 1. 当前只做最小正式导出能力，优先保证业务可读；
 * 2. 主区域先导出问题、时间、摘要、提醒和结果表格；
 * 3. 计算说明、数据范围和查询计划放在后面的补充区，避免压主表第一页。
 */
export function exportLogisticsDataQaResultAsCsv(payload: LogisticsDataQaExportPayload) {
  const rows = buildCsvRows(payload)

  const csvContent = '\uFEFF' + rows.map(buildCsvLine).join('\r\n')
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
  const fileName = buildExportFileName(payload.queryTime, 'csv', payload.question)
  downloadBlob(blob, fileName)
}

/**
 * 导出物流数据问答结果为 Excel。
 * 说明：
 * 1. 主工作表优先保证业务可读，先展示问题、时间、摘要和结果表格；
 * 2. 补充工作表用于承载结果提醒、计算说明、数据范围和查询计划；
 * 3. 历史回放和当前查询共用同一套导出结构，避免导出内容漂移。
 */
export function exportLogisticsDataQaResultAsXlsx(payload: LogisticsDataQaExportPayload) {
  const workbook = XLSX.utils.book_new()
  const mainSheetRows = buildMainSheetRows(payload)
  const detailSheetRows = buildDetailSheetRows(payload)

  const resultSheet = XLSX.utils.aoa_to_sheet(mainSheetRows)
  const detailSheet = XLSX.utils.aoa_to_sheet(detailSheetRows)

  resultSheet['!cols'] = buildColumnWidths(mainSheetRows)
  detailSheet['!cols'] = buildColumnWidths(detailSheetRows)

  XLSX.utils.book_append_sheet(workbook, resultSheet, '查询结果')
  XLSX.utils.book_append_sheet(workbook, detailSheet, '结果说明')

  const fileName = buildExportFileName(payload.queryTime, 'xlsx', payload.question)
  XLSX.writeFile(workbook, fileName)
}

/**
 * 把单个单元格序列化成业务可读文本。
 */
function stringifyCell(value: unknown): string {
  if (value === null || value === undefined || value === '') return ''
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(4)
  if (Array.isArray(value)) return value.join('，')
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

/**
 * 构造单行 CSV。
 * 说明：
 * 所有值统一做转义，避免逗号、换行和引号破坏文件结构。
 */
function buildCsvLine(values: string[]) {
  return values
    .map((value) => `"${String(value).replace(/"/g, '""')}"`)
    .join(',')
}

/**
 * 生成 CSV 导出内容。
 */
function buildCsvRows(payload: LogisticsDataQaExportPayload) {
  return [...buildMainSheetRows(payload), [], ...buildDetailSheetRows(payload)]
}

/**
 * 生成 Excel 主工作表内容。
 * 说明：
 * 第一张表优先给业务人员和领导直接看，不把技术信息压到第一页。
 */
function buildMainSheetRows(payload: LogisticsDataQaExportPayload): string[][] {
  const rows: string[][] = [
    ['物流数据问答查询结果'],
    [],
    ['原始问题', payload.question],
    ['查询时间', payload.queryTime],
    ['查询状态', payload.statusLabel],
    ['查询摘要', payload.answerSummary],
    [],
    ['结果表格'],
  ]

  if (payload.result.result_table.columns.length) {
    const headers = payload.result.result_table.columns.map((column) =>
      payload.columnLabelResolver ? payload.columnLabelResolver(column) : column,
    )
    rows.push(headers)
    payload.result.result_table.rows.forEach((row) => {
      rows.push(
        payload.result.result_table.columns.map((column) =>
          stringifyCell(row[column]),
        ),
      )
    })
  } else {
    rows.push(['当前没有可导出的结果表格数据'])
  }

  return rows
}

/**
 * 生成 Excel 补充说明工作表内容。
 */
function buildDetailSheetRows(payload: LogisticsDataQaExportPayload): string[][] {
  const rows: string[][] = [
    ['物流数据问答结果说明'],
    [],
    ['原始问题', payload.question],
    ['查询时间', payload.queryTime],
    ['查询状态', payload.statusLabel],
    [],
  ]

  rows.push(['结果提醒'])
  if (payload.result.warnings.length) {
    payload.result.warnings.forEach((item) => {
      rows.push([item])
    })
  } else {
    rows.push(['当前没有结果提醒'])
  }

  rows.push([])
  rows.push(['计算说明'])
  if (payload.result.calculation_logic.length) {
    payload.result.calculation_logic.forEach((item) => {
      rows.push([item])
    })
  } else {
    rows.push(['当前没有补充计算说明'])
  }

  rows.push([])
  rows.push(['数据范围'])
  const scopeEntries = Object.entries(payload.result.data_scope || {})
  if (scopeEntries.length) {
    scopeEntries.forEach(([key, value]) => {
      rows.push([key, stringifyCell(value)])
    })
  } else {
    rows.push(['当前没有额外数据范围说明'])
  }

  rows.push([])
  rows.push(['查询计划'])
  if (payload.result.query_plan) {
    rows.push([JSON.stringify(payload.result.query_plan, null, 2)])
  } else {
    rows.push(['当前没有可展示的查询计划'])
  }

  return rows
}

/**
 * 按查询时间生成导出文件名。
 */
function buildExportFileName(queryTime: string, extension: 'csv' | 'xlsx', question?: string) {
  const safeTime = queryTime.replace(/[^\d]/g, '').slice(0, 14) || Date.now().toString()
  const safeQuestion = buildQuestionSlug(question)
  return `物流数据问答结果_${safeTime}${safeQuestion ? `_${safeQuestion}` : ''}.${extension}`
}

/**
 * 生成业务可读的文件名主题。
 */
function buildQuestionSlug(question?: string) {
  if (!question) return ''
  return question
    .replace(/[\\/:*?"<>|]/g, '')
    .replace(/\s+/g, '')
    .slice(0, 18)
}

/**
 * 根据工作表内容生成列宽。
 */
function buildColumnWidths(rows: string[][]) {
  const maxColumns = rows.reduce((max, row) => Math.max(max, row.length), 0)
  return Array.from({ length: maxColumns }, (_, columnIndex) => {
    const maxLength = rows.reduce((max, row) => {
      const cell = row[columnIndex] ?? ''
      return Math.max(max, String(cell).length)
    }, 0)
    return { wch: Math.min(Math.max(maxLength + 2, 12), 40) }
  })
}

/**
 * 触发浏览器下载。
 */
function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
