from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"
BACKEND = ROOT / "backend" / "app"


def test_bom_data_management_exposes_separate_power_model_upload_entry_without_token() -> None:
    """BOM 数据管理页必须保留独立功率模型上传入口，并移除临时管理 token 输入。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")

    assert "上传 BOM Excel" in page
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
    assert "padding: 32px" in page
    assert "margin: 0 auto;" in page


def test_bom_data_management_history_uses_tabs_and_pagination_for_dense_tables() -> None:
    """BOM 上传历史与功率模型版本历史应拆成 tab，并提供分页以承载企业级历史数据量。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")

    assert "<el-tabs" in page
    assert "historyActiveTab" in page
    assert "name=\"bom_upload_history\"" in page
    assert "name=\"power_model_versions\"" in page
    assert "pagedBomUploadHistory" in page
    assert "pagedPowerModelVersions" in page
    assert "<el-pagination" in page
    assert "handleBomHistoryPageChange" in page
    assert "handlePowerHistoryPageChange" in page


def test_bom_data_management_page_focuses_on_two_primary_metrics_and_status_chips() -> None:
    """BOM 数据管理页不应堆叠过多指标卡，应只保留少量主指标和轻量状态。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")
    template = page.split("<script setup", 1)[0]

    assert "primaryOverviewCards" in page
    assert "secondary-status-strip" in page
    assert "upload-zone-card" in page
    assert "BOM 数据导入" in page
    assert "功率模型版本" in page
    assert "BOM 上传批次" in page
    assert "当前生效模型" in page
    assert "v-for=\"item in primaryOverviewCards\"" in template
    assert "hero-metric-strip" not in template
    assert "ops-overview-grid" not in template
    assert "文件隔离" in page
    assert "温和校验" in page
    assert "版本追溯" in page


def test_bom_data_management_copy_stays_minimal_and_hierarchy_first() -> None:
    """BOM 数据管理页应减少说明文字，用指标、短标签和视觉层次突出重点。"""
    page = (FRONTEND / "views" / "plan-bom" / "BomDataManagementPage.vue").read_text(encoding="utf-8")
    template = page.split("<script setup", 1)[0]

    assert "primaryOverviewCards" in page
    assert "secondary-status-strip" in page
    assert "<ol>" not in template
    assert "统一管理计划 BOM 数据导入与功率模型版本" not in template
    assert "普通 BOM Excel 用于明细查询和智能问答。" not in template
    assert "BOM 上传历史与功率模型版本历史采用 tab 页分区展示" not in template
    assert "当前表格按上传时间倒序展示" not in template
    assert template.count("。") <= 8


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


def test_power_model_token_dependency_removed_from_current_backend_sources() -> None:
    """临时功率模型 token 功能应从当前后端源码移除，后续改由用户权限模块接管。"""
    deps = (BACKEND / "api" / "deps.py").read_text(encoding="utf-8")
    settings = (BACKEND / "core" / "config.py").read_text(encoding="utf-8")
    power_api = (BACKEND / "domains" / "plan_bom" / "api" / "endpoints" / "power_model.py").read_text(encoding="utf-8")

    assert "require_plan_power_admin" not in deps
    assert "plan_power_admin_token" not in settings
    assert "X-Plan-Power-Admin-Token" not in power_api
    assert "require_plan_power_admin" not in power_api
