from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
BACKEND = ROOT / "backend" / "app"


def test_bom_data_management_exposes_separate_power_model_upload_entry_without_token() -> None:
    """BOM 数据管理页必须保留独立功率模型上传入口，并移除临时管理 token 输入。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")

    assert "BOM 文件上传" in page
    assert "上传功率模型" in page
    assert "请选择功率模型 xlsm 文件" in page
    assert "uploadPowerModelFile" in page
    assert "uploadPowerModelResult" in page
    assert "powerModelSelectedFile" in page
    assert "show-password" not in page
    assert "powerModelAdminToken" not in page
    assert "admin-token-row" not in page
    assert "功率模型管理 Token" not in page
    assert "bomUploadProgress" in page
    assert "powerModelUploadProgress" in page
    assert "<el-progress" in page
    assert "uploadSuccessMessage" in page
    assert "powerModelUploadSuccessMessage" in page
    assert "上传成功" in page
    assert "上传失败" in page


def test_bom_excel_upload_supports_batch_files_end_to_end_contract() -> None:
    """BOM Excel 上传应支持一次选择多个文件，并由后端返回批量汇总与逐文件结果。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")
    query_page = (FRONTEND / "views" / "plan-bom" / "PlanBomDetailQueryPage.vue").read_text(encoding="utf-8")
    api = (FRONTEND / "api" / "planBom.ts").read_text(encoding="utf-8")
    endpoint = (BACKEND / "domains" / "plan_bom" / "api" / "endpoints" / "import_excel.py").read_text(encoding="utf-8")

    assert "type=\"file\"" in page
    assert "multiple" in page
    assert "selectedFiles" in page
    assert "请选择 1 个或多个 BOM Excel 文件" in page
    assert "uploadPlanBomExcelBatch" in page
    assert "uploadBatchResult" in page
    assert "批量上传" in page
    assert "逐文件结果" in page
    assert "BOM Excel 批量上传导入" in query_page
    assert "multiple @change=\"handleUploadInputChange\"" in query_page
    assert "uploadPlanBomExcelBatch(files)" in query_page
    assert "files.forEach" in api
    assert "formData.append('files', file)" in api
    assert "uploadPlanBomExcelBatch(files: File[]" in api
    assert "total_files" in endpoint
    assert "success_count" in endpoint
    assert "failed_count" in endpoint
    assert "items" in endpoint
    assert "files: list[UploadFile] | None = File(default=None)" in endpoint
    assert "file: UploadFile | None = File(default=None)" in endpoint


def test_bom_data_management_progress_and_status_are_isolated_per_upload_type() -> None:
    """BOM 和功率模型上传必须分别维护进度与提示，避免两个入口状态串扰。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")

    assert "handleBomUploadProgress" in page
    assert "handlePowerModelUploadProgress" in page
    assert "bomUploadProgress.value = 0" in page
    assert "powerModelUploadProgress.value = 0" in page
    assert "bomUploadProgress.value = 100" in page
    assert "powerModelUploadProgress.value = 100" in page
    assert "uploadSuccessMessage.value" in page
    assert "powerModelUploadSuccessMessage.value" in page
    assert "uploadError.value" in page
    assert "powerModelUploadError.value" in page


def test_bom_data_management_exposes_upload_history_and_power_activation_controls() -> None:
    """BOM 数据管理页应能查看 BOM/功率模型历史，并对功率模型版本执行生效切换。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")

    assert "上传历史" in page
    assert "BOM 上传历史" in page
    assert "功率模型版本历史" in page
    assert "loadUploadHistory" in page
    assert "bomUploadHistory" in page
    assert "powerModelVersions" in page
    assert "activatePowerModelVersion" in page
    assert "设为生效" in page
    assert "当前生效" in page
    assert "已默认生效" in page
    assert "<el-table" in page


def test_frontend_api_wraps_upload_history_and_power_version_endpoints_without_token() -> None:
    """前端 API 应封装历史与版本生效接口，且不再透传功率模型管理 token 请求头。"""
    api = (FRONTEND / "api" / "planBom.ts").read_text(encoding="utf-8")

    assert "uploadPlanPowerModel" in api
    assert "fetchPlanBomUploadHistory" in api
    assert "fetchPlanPowerModelVersions" in api
    assert "activatePlanPowerModelVersion" in api
    assert "'/plan-bom/power-model/import'" in api
    assert "'/plan-bom/upload/history'" in api
    assert "'/plan-bom/power-model/versions'" in api
    assert "`/plan-bom/power-model/versions/${versionId}/activate`" in api
    assert "X-Plan-Power-Admin-Token" not in api
    assert "adminToken" not in api
    assert "multipart/form-data" in api
    assert "onUploadProgress" in api
    assert "Math.round" in api
    assert "options.onUploadProgress" in api


def test_power_model_upload_and_activation_reject_nonzero_or_failed_domain_responses() -> None:
    """功率模型上传/激活不能把 ApiResponse 失败包或解析失败版本误提示为成功。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")

    assert "maybeResponse?.code !== undefined && maybeResponse.code !== 0" in page
    assert "maybeResponse?.data === null" in page
    assert "throw new Error" in page
    assert "isPowerModelImportFailed" in page
    assert "version?.parse_status === 'failed'" in page
    assert "version?.error_count" in page
    assert "功率模型解析失败" in page
    assert "const activatedVersion = unwrapResponseData" in page
    assert "powerModelUploadProgress.value = 100" in page
    assert "powerModelUploadProgress.value = Math.max" in page
    assert "uploadPowerModelResult.version?.parse_status" in page
    assert "powerModelResultNextAction" in page
    assert "已保留历史，未设为生效" in page
    assert "uploadPowerModelResult.import_status" not in page
    assert "uploadPowerModelResult.detail?.issues?.length" in page


def test_bom_data_management_page_defines_own_vertical_scroll_container() -> None:
    """BOM 数据管理内容超过视口时，应在页面内提供垂直滚动条。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")

    assert "height: calc(100vh - 64px);" in page
    assert "overflow-y: auto;" in page
    assert "overflow-x: hidden;" in page
    assert "display: grid;" in page
    assert "grid-auto-rows: max-content;" in page
    assert "gap: 20px;" in page
    assert "padding: 24px 28px 36px;" in page
    assert "margin: 0 auto;" in page


def test_bom_data_management_history_uses_tabs_and_pagination_for_dense_tables() -> None:
    """BOM 上传历史与功率模型版本历史应拆成 tab，并提供分页以承载企业级历史数据量。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")

    assert "<el-tabs" in page
    assert "historyActiveTab" in page
    assert "label=\"上传数据\"" in page
    assert "label=\"查看历史\"" in page
    assert "name=\"bom_upload_history\"" in page
    assert "name=\"power_model_versions\"" in page
    assert "pagedBomUploadHistory" in page
    assert "pagedPowerModelVersions" in page
    assert "<el-pagination" in page
    assert "handleBomHistoryPageChange" in page
    assert "handlePowerHistoryPageChange" in page


def test_bom_data_management_page_uses_clean_workspace_without_duplicate_chips() -> None:
    """BOM 数据管理首屏应去掉重复标签和英文装饰，用紧凑状态条与统一上传卡片突出操作。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")
    template = page.split("<script setup", 1)[0]

    assert "bom-page bom-page--clean" in template
    assert "primaryOverviewCards" in page
    assert "compact-status-row" in template
    assert "upload-dropzone" in template
    assert "upload-action-button" in template
    assert "BOM 文件上传" in page
    assert "功率模型上传" in page
    assert "BOM 上传批次" in page
    assert "当前生效模型" in page
    assert "v-for=\"item in primaryOverviewCards\"" in template
    assert "hero-tags" not in template
    assert "secondary-status-strip" not in template
    assert "DATA WORKSPACE" not in template
    assert "POWER" not in template
    assert template.count("文件隔离") <= 1


def test_bom_data_management_visual_layout_uses_separate_cards_and_refined_tabs() -> None:
    """BOM 页面首屏应把概览区和操作区拉开，指标卡与 tab 应采用统一的企业级组件样式。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")
    template = page.split("<script setup", 1)[0]

    assert "bom-hero-card" in template
    assert "bom-workspace-card" in template
    assert template.index("bom-hero-card") < template.index("bom-workspace-card")
    assert "management-tabs management-tabs--segmented" in template
    assert "overview-card__top" in template
    assert "overview-card__badge" in template
    assert "overview-card__value" in template
    assert "workspace-card-head" in template
    assert "workspace-tab-label" in template
    assert ".bom-page--clean" in page
    assert ".bom-hero-card" in page
    assert ".bom-workspace-card" in page
    assert "gap: 20px" in page
    assert "box-shadow: 0 10px 28px" in page


def test_bom_data_management_typography_is_restrained_and_business_readable() -> None:
    """BOM 页面应收敛字号和装饰，避免超大标题、强渐变和过重阴影造成花哨感。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")

    assert "font-size: clamp(34px, 4vw, 52px);" not in page
    assert "font-size: clamp(28px, 2.6vw, 38px);" not in page
    assert "font-size: 24px;" not in page
    assert "font-size: 17px;" not in page
    assert "font-size: 18px;" not in page
    assert "radial-gradient" not in page
    assert ".overview-card::after" not in page
    assert "width: 320px;" not in page
    assert "box-shadow: 0 18px 50px" not in page
    assert "box-shadow: 0 16px 42px" not in page
    assert "font-size: clamp(26px, 2.4vw, 34px);" in page
    assert "font-size: clamp(22px, 2vw, 30px);" in page
    assert "font-size: 20px;" in page
    assert "font-size: 14px;" in page


def test_bom_data_management_copy_stays_minimal_business_friendly_and_hierarchy_first() -> None:
    """BOM 数据管理页应减少说明文字和英文技术词，用业务动作、短标签和视觉层次突出重点。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")
    template = page.split("<script setup", 1)[0]

    assert "primaryOverviewCards" in page
    assert "compact-status-row" in page
    assert "<ol>" not in template
    assert "统一管理计划 BOM 数据导入与功率模型版本" not in template
    assert "普通 BOM Excel 用于明细查询和智能问答。" not in template
    assert "BOM 上传历史与功率模型版本历史采用 tab 页分区展示" not in template
    assert "当前表格按上传时间倒序展示" not in template
    assert 'label="Warning"' not in template
    assert 'label="Error"' not in template
    assert "Issue 数" not in template
    assert "文件 Hash" not in template
    assert "版本 ID" not in template
    assert "{{ row.status }}" not in template
    assert 'prop="source_tag" label="来源" min-width="120" show-overflow-tooltip />' not in template
    assert "formatStatusLabel(row.status)" in template
    assert "formatSourceTagLabel(row.source_tag)" in template
    assert "formatStatusLabel(row.parse_status)" in template
    assert "formatStatusLabel(uploadPowerModelResult.version?.parse_status)" in template
    assert "uploadPowerModelResult.version?.parse_status || '-'" not in template
    assert "问题数" in page
    assert "文件指纹" in page
    assert "版本编号" in page
    assert "手动上传" in page
    assert "选择文件后可上传" in page
    assert "选择模型后可上传" in page
    assert template.count("。") <= 6


def test_app_layout_uses_chatgpt_like_neutral_shell_and_richer_palette() -> None:
    """全局壳层应接近 ChatGPT 的简洁侧栏+内容画布，并减少单一绿色依赖。"""
    layout = (FRONTEND / "layouts" / "AppLayout.vue").read_text(encoding="utf-8")
    styles = (FRONTEND / "styles" / "index.css").read_text(encoding="utf-8")
    template = layout.split("<script setup", 1)[0]

    assert "chatgpt-like-shell" in layout
    assert "chatgpt-sidebar" in layout
    assert "chatgpt-canvas" in layout
    assert "workspace-switcher" in layout
    assert "nav-section-label" in layout
    assert "topbar-metrics" not in template
    assert "--accent-blue" in styles
    assert "--accent-violet" in styles
    assert "--accent-amber" in styles
    assert "--accent-coral" in styles


def test_business_chat_assistant_response_layout_is_adaptive_not_fixed_template() -> None:
    """智能问答回复应按问题结果动态选择叙事、数据、图表或追问布局，而非永远固定指标卡+结论+明细。"""
    chat = (FRONTEND / "views" / "business-chat" / "BusinessChatPage.vue").read_text(encoding="utf-8")
    template = chat.split("<script setup", 1)[0]

    assert "resolveAssistantResultLayout" in chat
    assert "shouldShowMetricCards" in chat
    assert "shouldShowResultTable" in chat
    assert "resolveAssistantReplyKicker" in chat
    assert "ai-response-card--narrative" in chat
    assert "ai-response-card--data" in chat
    assert "ai-response-card--chart" in chat
    assert "assistant-prose" in template
    assert "v-if=\"shouldShowMetricCards(message)\"" in template
    assert "v-if=\"shouldShowResultTable(message)\"" in template
    assert "v-if=\"message.presentation.cards.length\" class=\"metric-grid\"" not in template
    assert "v-if=\"message.presentation.table\" class=\"result-table-card\"" not in template


def test_business_chat_detail_table_can_export_excel_when_rows_exist() -> None:
    """智能助手回复中存在明细表格时，业务用户应能直接导出 Excel 文件。"""
    chat = (FRONTEND / "views" / "business-chat" / "BusinessChatPage.vue").read_text(encoding="utf-8")
    template = chat.split("<script setup", 1)[0]

    package_json = (ROOT / "frontend" / "package.json").read_text(encoding="utf-8")

    assert "import * as XLSX from 'xlsx-js-style'" in chat
    assert "\"xlsx-js-style\"" in package_json
    assert "import { ElMessage } from 'element-plus'" in chat
    assert "data-testid=\"export-result-table-excel\"" in template
    assert "导出 Excel" in template
    assert "@click=\"exportAssistantTableToExcel(message)\"" in template
    assert "shouldShowResultTable(message)" in template
    assert "function getAssistantResultTable" in chat
    assert "getAssistantResultTable(message)?.rows.length || 0" in template
    assert ":disabled=\"!getAssistantResultTable(message)?.rows.length\"" in template
    assert "function exportAssistantTableToExcel" in chat
    assert "function buildAssistantTableExportRows" in chat
    assert "function applyAssistantTableExportAlignment" in chat
    assert "XLSX.utils.decode_range" in chat
    assert "XLSX.utils.encode_cell" in chat
    assert "vertical: 'center'" in chat
    assert "horizontal: 'left'" in chat
    assert "cell.s =" in chat
    assert "function buildAssistantTableExportMerges" in chat
    assert "worksheet['!merges']" in chat
    assert "mergedSubRow && !isFallRatioEstimateColumn(column) ? ''" in chat
    assert "function buildAssistantTableExportFileName" in chat
    assert "XLSX.utils.json_to_sheet" in chat
    assert "XLSX.utils.book_append_sheet" in chat
    assert "XLSX.writeFile" in chat
    assert "ctm值: 'CTM 值'" in chat
    assert "ctm_值: 'CTM 值'" in chat
    assert "落档比例预估: '落档比例预估'" in chat
    assert "function isMultiLineTableColumn" in chat
    assert ":show-overflow-tooltip=\"!isMultiLineTableColumn(column)\"" in template
    assert "result-table__cell--multi-line" in chat
    assert "white-space: pre-line" in chat
    assert "ElMessage.warning('当前回答没有可导出的明细数据')" in chat
    assert "ElMessage.success(`已导出 ${table.rows.length} 行明细数据`)" in chat
    assert "智能助手明细数据" in chat
    assert "xlsx" in chat


def test_business_chat_fall_ratio_estimate_uses_excel_like_irregular_rows() -> None:
    """落档比例预估应像附件 Excel 一样另起真实行，并让其它列纵向合并。"""
    chat = (FRONTEND / "views" / "business-chat" / "BusinessChatPage.vue").read_text(encoding="utf-8")
    template = chat.split("<script setup", 1)[0]

    assert "function isFallRatioEstimateColumn" in chat
    assert "function splitFallRatioEstimateLines" in chat
    assert "function expandFallRatioEstimateRows" in chat
    assert "function shouldUseIrregularResultTable" in chat
    assert re.search(
        r"function shouldUseIrregularResultTable\(message: BusinessChatMessage\) \{[^}]*const table = getAssistantResultTable\(message\)",
        chat,
        re.S,
    )
    assert "function shouldRenderIrregularResultTableCell" in chat
    assert "function getIrregularResultTableCellRowSpan" in chat
    assert "function buildIrregularResultTableRowKey" in chat
    assert "v-if=\"shouldUseIrregularResultTable(message)\"" in template
    assert "getAssistantResultTable(message)?.columns || []" in template
    assert "getAssistantResultTable(message)?.rows || []" in template
    assert "<table" in template
    assert "class=\"result-table result-table--irregular\"" in template
    assert ":rowspan=\"getIrregularResultTableCellRowSpan(row, column)\"" in template
    assert "v-if=\"shouldRenderIrregularResultTableCell(row, column)\"" in template
    assert "v-else" in template
    assert "v-for=\"(line, lineIndex) in splitFallRatioEstimateLines(scope.row[column])\"" not in template
    assert "result-table__fall-ratio-line" not in template
    assert "result-table__cell--fall-ratio" in chat
    assert "vertical-align: middle" in chat
    assert "white-space: nowrap" in chat
    assert "overflow-x: auto" in chat



def test_business_chat_uses_backend_llm_streaming_answer_pipeline() -> None:
    """智能助手应优先消费后端 LLM 流式答案，并在前端增量展示，不再只等同步接口一次性返回。"""
    chat = (FRONTEND / "views" / "business-chat" / "BusinessChatPage.vue").read_text(encoding="utf-8")
    template = chat.split("<script setup", 1)[0]
    logistics_api = (FRONTEND / "api" / "logistics.ts").read_text(encoding="utf-8")
    plan_bom_api = (FRONTEND / "api" / "planBom.ts").read_text(encoding="utf-8")
    streaming_api = (FRONTEND / "utils" / "streamingApi.ts").read_text(encoding="utf-8")

    assert "streamLogisticsDataQaQuery" in logistics_api
    assert "streamPlanBomQuestion" in plan_bom_api
    assert "postJsonLineStream" in streaming_api
    assert "ReadableStream" in streaming_api
    assert "TextDecoder" in streaming_api
    assert "/logistics/data-qa/query/stream" in logistics_api
    assert "/plan-bom/qa/ask/stream" in plan_bom_api
    assert "streamLogisticsDataQaQuery" in chat
    assert "streamPlanBomQuestion" in chat
    assert "function updateAssistantStreamingContent" in chat
    assert "AI 正在生成回答" in template
    assert "'streaming-answer': message.role === 'assistant' && message.loading" in template
    assert "message.content && !message.presentation" in template
    assert "completeAssistantMessage" in chat


def test_power_model_token_dependency_removed_from_current_backend_sources() -> None:
    """临时功率模型 token 功能应从当前后端源码移除，后续改由用户权限模块接管。"""
    deps = (BACKEND / "api" / "deps.py").read_text(encoding="utf-8")
    settings = (BACKEND / "core" / "config.py").read_text(encoding="utf-8")
    power_api = (BACKEND / "domains" / "plan_bom" / "api" / "endpoints" / "power_model.py").read_text(encoding="utf-8")

    assert "require_plan_power_admin" not in deps
    assert "plan_power_admin_token" not in settings
    assert "X-Plan-Power-Admin-Token" not in power_api
    assert "require_plan_power_admin" not in power_api
