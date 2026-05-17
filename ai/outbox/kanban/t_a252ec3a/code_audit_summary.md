# 代码只读审计摘要

## backend/app/core/config.py (present)
- lines: 447, markers: logistics, SQL, whitelist, 白名单
- class Settings methods: _normalize_logistics_query_planner_v2_mode, _parse_logistics_query_planner_v2_allowed_query_keys, _normalize_llm_guardrail_mode, _parse_llm_guardrail_a_querykey_whitelist, _normalize_llm_clarification_assist_mode, _parse_llm_clarification_assist_category_whitelist, _normalize_llm_unsupported_assist_mode, _parse_llm_unsupported_assist_category_whitelist, ensure_runtime_dirs, mysql_dsn, source_mysql_dsn, resolved_source_mysql_dsn, APP_HOST, APP_NAME, APP_ENV, APP_DEBUG, APP_VERSION, APP_PORT
- functions: get_settings

## backend/app/db/session.py (present)
- lines: 41, markers: SQL
- functions: get_db, get_source_db

## backend/app/api/router.py (present)
- lines: 18, markers: plan_bom, logistics

## backend/app/domains/logistics/api/router.py (present)
- lines: 21, markers: logistics

## backend/app/domains/logistics/api/endpoints/data_qa.py (present)
- lines: 121, markers: logistics, StreamingResponse, query_plan_v2
- functions: logistics_data_qa_query, logistics_data_qa_query_stream

## backend/app/domains/logistics/api/endpoints/sync_system.py (present)
- lines: 27, markers: logistics
- functions: run_system_sync

## backend/app/domains/logistics/api/endpoints/import_history.py (present)
- lines: 35, markers: logistics
- functions: import_history_excel, run_history_import

## backend/app/domains/logistics/api/endpoints/query.py (present)
- lines: 55, markers: logistics
- functions: aggregate_query, detail_query, compare_query

## backend/app/domains/logistics/api/endpoints/nl2query.py (present)
- lines: 20, markers: logistics
- functions: parse_and_query

## backend/app/domains/logistics/repositories/data_qa_repository.py (present)
- lines: 3661, markers: source_type, logistics, SQL, 白名单
- class LogisticsDataQaRepository methods: __init__, ensure_runtime_columns, _ensure_column, verify_assets, hist_total_fee_city_rank, hist_avg_fee_by_month, hist_avg_fee_per_watt_by_transport, hist_extra_fee_ratio_peak_month, hist_total_fee_by_origin_and_carrier, hist_top_customers_fee_and_mw_by_province, hist_total_fee_by_province, hist_total_fee_summary, hist_carrier_kpi_by_year, hist_mw_summary, hist_mw_by_year, mixed_mw_summary_2023_2026, mixed_total_fee_summary_2023_2026, hist_product_spec_mw_summary

## backend/app/domains/logistics/repositories/query_repository.py (present)
- lines: 628, markers: source_type, sys_query_log, plan_bom, logistics, SQL, 白名单, query_plan_v2
- class LogisticsQueryRepository methods: aggregate, detail, exists_detail_business_no, compare, write_query_log, list_query_logs, list_query_logs_for_query_planning_gray, get_query_log_detail, _aggregate_for_side_total, _aggregate_for_side_by_dim, _merge_compare_rows_by_dim, _build_source_filter, _build_common_filters

## backend/app/domains/logistics/repositories/sync_repository.py (present)
- lines: 1064, markers: sys_task_log, logistics, SQL
- class LogisticsSyncRepository methods: __init__, ensure_extended_columns, ensure_sync_dedup_constraints, _dedupe_by_source_id, _ensure_unique_index, _table_has_columns, get_latest_local_source_updated_at, _ensure_column, create_task_log, finish_task_log, create_error_log, fetch_companies, fetch_warehouses, fetch_ship_tasks, fetch_ship_products_by_task_ids, fetch_assign_tasks_by_ship_task_ids, fetch_assign_details_by_assign_task_ids, upsert_ods_companies

## backend/app/domains/logistics/repositories/import_repository.py (present)
- lines: 411, markers: sys_task_log, logistics, SQL
- class LogisticsHistoryImportRepository methods: __init__, create_task_log, finish_task_log, create_error_log, file_md5, create_excel_file_record, delete_batch, batch_insert_ods_rows, batch_insert_dwd_rows, _normalize_dwd_row, _normalize_product_spec_and_accessory, _truncate_varchar_fields, _clean_text, _merge_text, _log_truncation

## backend/app/domains/logistics/services/data_qa_service.py (present)
- lines: 2719, markers: sys_query_log, logistics, 白名单, query_plan_v2
- class LogisticsDataQaService methods: __init__, query, write_error_log, verify_assets, _finalize_result, _resolve_plan_with_guardrail, _resolve_status, _plan_trace_payload, _guardrail_trace_payload, _write_history_snapshot, _resolve_history_row_status, _execute_plan, _resolve_clarification_with_assist, _resolve_unsupported_with_assist, _build_unsupported_answer_summary, _build_unsupported_warnings, _execute_composite_decomposed_plan, _build_result

## backend/app/domains/logistics/services/data_qa_planner.py (present)
- lines: 4010, markers: logistics, SQL, 白名单
- class LogisticsDataQaPlanner methods: __init__, build_plan, build_plan_from_guardrail_candidate, _build_composite_plan_from_llm_result, _find_llm_sub_plan_payload, _extract_llm_source_clause, _llm_source_clauses_cover_original_question, _locate_non_overlapping_source_spans, _high_fee_clause_contains_procurement_ask, _high_fee_clause_has_unsupported_qualifier, _filters_have_nonempty_unsupported_keys, _procurement_clause_has_unsupported_filter, _procurement_clause_has_unsupported_business_residue, _procurement_clause_has_leading_unsupported_qualifier, _coerce_int, _split_composite_clauses, _is_high_fee_address_clause, _is_procurement_mw_clause

## backend/app/domains/logistics/services/query_executor.py (present)
- lines: 118, markers: logistics, SQL, 白名单
- class LogisticsQueryExecutor methods: __init__, execute

## backend/app/domains/logistics/services/sql_renderer.py (present)
- lines: 64, markers: logistics, SQL
- class LogisticsSQLRenderer methods: render_preview, _to_sql_literal

## backend/app/domains/logistics/services/sql_whitelist.py (present)
- lines: 47, markers: logistics, SQL, 白名单
- class LogisticsSQLWhitelist methods: __init__, check

## backend/app/domains/logistics/services/sql_template_registry.py (present)
- lines: 23, markers: SQL
- class LogisticsSQLTemplateRegistry methods: __init__, get_template_path, load_sql, describe

## backend/app/domains/logistics/services/sync_service.py (present)
- lines: 481, markers: sys_task_log, logistics, SQL
- class SyncStats methods: 
- class LogisticsSystemSyncService methods: sync_formal_data, _resolve_updated_since, _ensure_source_db_alive, _safe_log_failure, _fetch_all_ship_tasks, _chunked, _normalize_company_row, _normalize_warehouse_row, _normalize_ship_task_row, _normalize_ship_product_row, _normalize_assign_task_row, _normalize_assign_detail_row, _normalize_decimal

## backend/app/domains/logistics/services/import_service.py (present)
- lines: 441, markers: logistics, SQL
- class LogisticsHistoryImportService methods: __init__, import_excel, run_import, _resolve_file_path, _safe_log_failure, _json_safe_value, _progress_step, _chunked, _emit_progress

## backend/app/domains/logistics/services/query_planner_v2/planner.py (present)
- lines: 140, markers: logistics, 白名单, query_plan_v2
- class LogisticsQueryPlannerV2 methods: __init__, should_use, build_shadow_plan, _normalize_mode

## backend/app/domains/logistics/services/query_planner_v2/validator.py (present)
- lines: 290, markers: logistics, 白名单
- class LogisticsQueryPlannerV2ValidationResult methods: 
- class LogisticsQueryPlannerV2Validator methods: __init__, validate, _validate_filters, _validate_collection, _validate_question_years, _extract_candidate_years, _extract_years_from_text, _dedupe_ints, _validate_time_scope, _validate_normalized_entities, _is_policy_locked_question, _has_multi_hop_route, _dedupe

## backend/app/domains/logistics/services/query_planner_v2/capability_registry.py (present)
- lines: 180, markers: 白名单
- class LogisticsQueryPlannerV2Capability methods: to_prompt_dict
- class LogisticsQueryPlannerV2CapabilityRegistry methods: __init__, get, allowed_query_keys, prompt_payload, _default_capabilities

## backend/app/domains/plan_bom/models.py (present)
- lines: 528, markers: source_type, EXCEL, sys_query_log, plan_bom, SQL
- class PlanBomImportBatch methods: 
- class PlanBomHeader methods: 
- class PlanBomMaterialLine methods: 
- class PlanBomRevision methods: 
- class PlanBomExportTask methods: 
- class PlanBomExportFile methods: 
- class PlanPowerModelVersion methods: 
- class PlanPowerModelSheet methods: 
- class PlanPowerFactorOption methods: 
- class PlanPowerSupplierEfficiencyDistribution methods: 
- class PlanPowerPowerBin methods: 
- class PlanPowerBenchmarkFactor methods: 

## backend/app/domains/plan_bom/api/router.py (present)
- lines: 13, markers: plan_bom

## backend/app/domains/plan_bom/api/endpoints/qa.py (present)
- lines: 184, markers: sys_query_log, plan_bom, StreamingResponse, SQL, query_plan_v2
- functions: _plan_bom_fallback_has_technical_leak, _resolve_plan_bom_stream_fallback_answer, ask_plan_bom, ask_plan_bom_stream

## backend/app/domains/plan_bom/api/endpoints/query.py (present)
- lines: 69, markers: sys_query_log, plan_bom
- functions: detail_query, compare_query, compare_replay

## backend/app/domains/plan_bom/api/endpoints/import_excel.py (present)
- lines: 377, markers: EXCEL, plan_bom
- functions: _upload_failure_payload, _build_quality_summary, _upload_success_payload, _import_one_upload_file, _batch_upload_payload, _business_type_failure_response, import_plan_bom_excel, list_plan_bom_upload_history, upload_plan_bom_excel

## backend/app/domains/plan_bom/services/qa_service.py (present)
- lines: 1975, markers: sys_query_log, plan_bom, logistics, query_plan_v2
- class PlanBomQaService methods: __init__, ask, _single_order_response, _multi_or_scope_response, _compare_response, _expanded_candidate_compare_response, _can_expand_compare_candidates, _expanded_compare_payload_for_candidate, _compare_side_request_from_candidate, _compare_side_request_from_context, _compare_side_label, _compare_side_name, _is_description_compare_question, _compare_rows_for_pair, _compare_pair_row, _expanded_pair_summary, _presence_response, _infer_single_model_code_from_power_candidates

## backend/app/domains/plan_bom/services/detail_query_service.py (missing)

## backend/app/domains/plan_bom/services/import_service.py (missing)

## backend/app/domains/plan_bom/services/repository.py (missing)

## backend/app/models/sys_task_log.py (present)
- lines: 42, markers: sys_task_log, logistics, SQL
- class SysTaskLog methods: 

## backend/app/models/sys_task_error_log.py (present)
- lines: 32, markers: -
- class SysTaskErrorLog methods: 

## backend/app/models/sys_query_log.py (present)
- lines: 36, markers: sys_query_log
- class SysQueryLog methods: 

## backend/app/models/sys_data_source.py (missing)

## frontend/src/router/index.ts (present)
- lines: 60, markers: logistics
- path: '/',
- path: '/smart-chat',
- path: '/logistics/data-qa',
- path: '/logistics/data-qa/history',
- path: '/nl-query',
- path: '/structured-query',
- path: '/tasks',
- path: '/history',
- path: '/detail-view',
- path: '/plan-bom/detail-query',
- path: '/bom-data',
- path: '/trial-guide',

## frontend/src/layouts/AppLayout.vue (present)
- lines: 599, markers: -
- <el-sub-menu index="smart-chat" class="chat-submenu" data-testid="nav-smart-chat">
- :index="`chat:${session.id}`"
- <el-menu-item index="/bom-data" data-testid="nav-bom-data">
- <el-menu-item index="/trial-guide" data-testid="nav-trial-guide">
- title: 'BOM 数据管理',
- description: '上传治理、版本追溯与模型生效管理',
- title: '试运行说明',
- description: '试运行范围、验收口径与操作边界',
- title: '智能问答',
- description: '经营计划、物流与计划 BOM 的统一问答入口',
- :deep(.menu .el-sub-menu__title:hover),

## frontend/src/views/business-chat/BusinessChatPage.vue (present)
- lines: 3121, markers: plan_bom, logistics, SQL
- <el-radio-group v-model="domainMode" size="small" class="domain-switch" data-testid="domain-switch">
- <el-radio-button value="auto" data-testid="domain-auto">自动识别</el-radio-button>
- <el-radio-button value="logistics" data-testid="domain-logistics">物流数据</el-radio-button>
- <el-radio-button value="plan_bom" data-testid="domain-plan-bom">计划 BOM</el-radio-button>
- title: string
- path: string
- const domainMode = computed<BusinessChatDomain>({
- domainMode.value = item.mode
- title: presentation?.title || '物流数据问答结果',
- title: presentation?.title || `计划 BOM 问答结果（${data.classification || '未知'}）`,
- title: value.title || '',
- title: typeof chart.title === 'string' ? chart.title : '',
- path: buildPieSlicePath(110, 110, 84, start, cursor),
- description: '规格描述',
- left_description: '左侧规格',
- right_description: '右侧规格',
- :deep(.domain-switch .el-radio-button__inner) {
- :deep(.domain-switch .el-radio-button__original-radio:checked + .el-radio-button__inner) {

## frontend/src/api/logistics.ts (present)
- lines: 338, markers: logistics
- import { postJsonLineStream, type JsonLineStreamHandlers } from '@/utils/streamingApi'
- const resp = await http.post('/logistics/nl2query/parse-and-query', payload)
- const resp = await http.post('/logistics/data-qa/query', payload)
- return postJsonLineStream<LogisticsDataQaResult>('/logistics/data-qa/query/stream', payload, handlers)
- const resp = await http.post('/logistics/query-service/aggregate', payload)
- const resp = await http.get('/logistics/data/hist/import/tasks')
- const resp = await http.get('/logistics/data/sys/sync/tasks')
- const resp = await http.get('/sys/query/log', { params })
- const resp = await http.get(`/sys/query/log/${logId}`)

## frontend/src/api/planBom.ts (present)
- lines: 372, markers: source_type, plan_bom
- import { postJsonLineStream, type JsonLineStreamHandlers } from '@/utils/streamingApi'
- const resp = await http.post('/plan-bom/query/detail', payload)
- title: string
- const resp = await http.post('/plan-bom/qa/ask', payload)
- return postJsonLineStream<PlanBomQaResponse>('/plan-bom/qa/ask/stream', payload, handlers)
- const resp = await http.post('/plan-bom/upload', formData, {
- const resp = await http.post('/plan-bom/upload', formData, {
- const resp = await http.post('/plan-bom/power-model/import', formData, {
- const resp = await http.get('/plan-bom/upload/history', { params: { limit } })
- const resp = await http.get('/plan-bom/power-model/versions')
- const resp = await http.post(`/plan-bom/power-model/versions/${versionId}/activate`)

## frontend/src/components/ResultTable.vue (present)
- lines: 370, markers: source_type, logistics
- title: '结果表格',

## frontend/src/utils/streamingApi.ts (present)
- lines: 106, markers: -
- *   path: 后端相对 API 路径。
- export async function postJsonLineStream<TDone>(
- path: string,