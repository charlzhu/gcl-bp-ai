import { http } from '@/utils/http'

/** 产销存导入结果。 */
export interface InventorySalesProductionImportReport {
  workbook_id: number
  import_status: string
  business_year: number
  data_cutoff_month: number
  sheet_count: number
  monthly_fact_count: number
  source_file_name: string
}

/** 导入历史记录。 */
export interface ImportHistoryItem {
  id: number
  source_file_name: string
  business_year: number
  data_cutoff_month: number
  sheet_count: number
  upload_batch_no: string
  created_at: string
  import_status: string
}

/** 导入历史响应。 */
export interface ImportHistoryResponse {
  history: ImportHistoryItem[]
}

/**
 * 上传并导入产销存 Excel 文件。
 * 说明：直接上传文件流，后端解析后入库。
 */
export async function uploadInventorySalesProductionExcel(
  file: File,
): Promise<InventorySalesProductionImportReport> {
  const formData = new FormData()
  formData.append('file', file)
  const resp = await http.post(
    '/business-analysis/inventory-sales-production/import/import',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  )
  return (resp.data as { data?: InventorySalesProductionImportReport }).data
    ?? resp.data as unknown as InventorySalesProductionImportReport
}

/**
 * 查询产销存 Excel 导入历史。
 */
export async function fetchImportHistory(): Promise<ImportHistoryResponse> {
  const resp = await http.get(
    '/business-analysis/inventory-sales-production/import/import/history',
  )
  return (resp.data as { data?: ImportHistoryResponse }).data
    ?? resp.data as unknown as ImportHistoryResponse
}
