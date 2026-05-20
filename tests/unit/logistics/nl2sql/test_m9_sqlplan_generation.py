from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation as m9_module
from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
    LogisticsCatalogRecallDocumentBuilder,
    LogisticsCatalogRecallHit,
    LogisticsCatalogRecallResult,
)
from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import (
    M9_SHADOW_SQLPLAN_GENERATION_VERSION,
    LogisticsNl2SqlDomainRouter,
    LogisticsNl2SqlM9ShadowSample,
    LogisticsNl2SqlQueryRewriteService,
    LogisticsSqlPlanGenerator,
    build_default_logistics_nl2sql_m9_shadow_samples,
    run_logistics_nl2sql_m9_shadow_sqlplan_generation,
)
from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.shadow_pipeline import LogisticsNl2SqlShadowPipeline


CATALOG_VERSION = "logistics_nl2sql_catalog.v1"


def test_query_rewrite_preserves_constraints_and_adds_default_time_hint() -> None:
    """Query Rewrite 只能归一术语和补默认时间提示，不能删除用户显式业务约束。"""

    result = LogisticsNl2SqlQueryRewriteService().rewrite("苏州晶茂物流发货量最多的是哪几年？")

    assert result.original_question == "苏州晶茂物流发货量最多的是哪几年？"
    assert "苏州晶茂物流" in result.normalized_question
    assert "发运量" in result.normalized_question
    assert result.default_years == [2023, 2024, 2025, 2026]
    assert result.normalized_terms["发货量"] == "发运量"
    assert result.removed_constraints == []
    assert result.unsupported_flags == []


def test_query_rewrite_marks_tonnage_without_substituting_to_mw() -> None:
    """吨数当前不支持，rewrite 必须保留风险标记，不能把吨数静默替换成 MW。"""

    result = LogisticsNl2SqlQueryRewriteService().rewrite("2025年各承运商运输吨位排名")

    assert "吨" in result.normalized_question or "吨位" in result.normalized_question
    assert "unsupported_tonnage" in result.unsupported_flags
    assert result.requested_unit == "吨"
    assert result.normalized_terms.get("吨数") != "MW"


def test_domain_router_allows_only_logistics_middle_db_shadow_route() -> None:
    """M9 只允许物流 + 中间库 + shadow；非物流或直查源库请求必须跳过。"""

    router = LogisticsNl2SqlDomainRouter()

    allowed = router.route("2025年各承运商发运量排名")
    assert allowed.should_process is True
    assert allowed.domain == "logistics"
    assert allowed.source_system == "middle_db"
    assert allowed.mode == "shadow"
    assert allowed.reason_code is None

    bom = router.route("BOM 615功率预测是多少？")
    assert bom.should_process is False
    assert bom.domain == "plan_bom"
    assert bom.reason_code == "m9_domain_not_supported::plan_bom"

    oracle = router.route("直查 SAP Oracle MID 物流源表")
    assert oracle.should_process is False
    assert oracle.source_system in {"sap_oracle_mid", "oracle_mid"}
    assert oracle.reason_code == "m9_source_not_allowed::sap_oracle_mid"


def test_domain_router_fail_closed_for_non_logistics_domains_without_blocking_department_name() -> None:
    """M9 必须拦截物管/经营分析问题，但不能把物流口径中的“经营计划”部门误判为经营分析。"""

    router = LogisticsNl2SqlDomainRouter()

    material = router.route("物管库存和出入库情况查一下")
    assert material.should_process is False
    assert material.domain == "material_management"
    assert material.reason_code == "m9_domain_not_supported::material_management"

    business = router.route("经营分析收入利润预算达成率怎么看？")
    assert business.should_process is False
    assert business.domain == "business_analysis"
    assert business.reason_code == "m9_domain_not_supported::business_analysis"

    logistics_department = router.route("经营计划部门 2025 年发运量是多少 MW？")
    assert logistics_department.should_process is True
    assert logistics_department.domain == "logistics"


def test_m9_dev_runner_cli_exposes_live_provider_smoke_flags() -> None:
    """M9 dev runner 文档中的 live provider smoke 参数必须真实存在，避免验收命令与脚本不一致。"""

    script_path = Path(__file__).resolve().parents[4] / "scripts/dev/run_logistics_nl2sql_m9_shadow_sqlplan_generation.py"
    result = subprocess.run([sys.executable, str(script_path), "--help"], capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "--live-provider-smoke" in result.stdout
    assert "--max-live-samples" in result.stdout
    assert "--live-provider-timeout-seconds" in result.stdout


def test_semantic_catalog_loads_examples_and_recall_documents_are_sql_free() -> None:
    """examples 应进入 Semantic Catalog 与召回文档，但只能描述 SQLPlan 形状，不能携带 raw SQL。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    examples = {example.example_id: example for example in catalog.examples}

    assert "m9_example_carrier_mw_ranking" in examples
    example = examples["m9_example_carrier_mw_ranking"]
    assert example.domain == "logistics"
    assert example.query_type == "ranking"
    assert example.metrics == ["shipment_mw", "row_count"]
    assert "logistics_company_name" in example.dimensions
    assert "table:dws_logistics_detail_union" in example.catalog_refs
    assert example.sql is None
    assert example.raw_sql is None

    documents = LogisticsCatalogRecallDocumentBuilder().build(catalog)
    example_documents = [document for document in documents if document.doc_type == "example"]
    assert {document.catalog_id for document in example_documents} >= {"example:m9_example_carrier_mw_ranking"}

    payload = json.dumps([document.model_dump(mode="json") for document in example_documents], ensure_ascii=False).lower()
    for forbidden in ("select ", " from ", " where ", "raw_sql", "sql=", "mysql://", "password", "api_key"):
        assert forbidden not in payload


def test_sqlplan_generator_accepts_strict_json_candidate_and_validates_it() -> None:
    """主 LLM 只能输出严格 JSON SQLPlan candidate，随后必须经过现有 SQLPlan validator。"""

    client = _FakeChatClient(json.dumps(_valid_candidate(), ensure_ascii=False))
    generator = LogisticsSqlPlanGenerator(client=client, enabled=True, model="fake-deepseek")
    recall_result = _recall_ok()

    result = generator.generate(
        original_question="哪个物流跑得最多？",
        normalized_question="哪个承运商发运量最多？",
        route=LogisticsNl2SqlDomainRouter().route("哪个物流跑得最多？"),
        recall_result=recall_result,
    )

    assert result.status == "ok", result.error_codes
    assert result.candidate is not None
    assert result.validation_result is not None
    assert result.validation_result.ok is True
    assert result.candidate["plan"]["metrics"] == ["shipment_mw", "row_count"]
    assert result.candidate["plan"]["requested_unit"] == "MW"
    assert client.calls, "generator 必须调用当前主 LLM 客户端"
    messages_text = json.dumps(client.calls[-1]["messages"], ensure_ascii=False)
    assert "只允许返回严格 JSON object" in messages_text
    assert "不能输出 SQL" in messages_text
    assert "example:m9_example_carrier_mw_ranking" in messages_text


def test_sqlplan_generator_requests_provider_json_object_mode() -> None:
    """调用主 LLM 时必须启用 JSON object 模式，降低 live provider 输出不可解析 JSON 的概率。"""

    client = _FakeChatClient(json.dumps(_valid_candidate(), ensure_ascii=False))
    generator = LogisticsSqlPlanGenerator(client=client, enabled=True, model="fake-deepseek")

    result = generator.generate(
        original_question="哪个物流跑得最多？",
        normalized_question="哪个承运商发运量最多？",
        route=LogisticsNl2SqlDomainRouter().route("哪个物流跑得最多？"),
        recall_result=_recall_ok(),
    )

    assert result.status == "ok", result.error_codes
    assert client.calls[-1]["response_format"] == {"type": "json_object"}


def test_sqlplan_generator_prompt_declares_strict_schema_contract_and_field_placement_guards() -> None:
    """Prompt 必须把 SQLPlan candidate 的字段层级讲清楚，防止 live LLM 输出 plan_filters/plan.confidence 等错位字段。"""

    client = _FakeChatClient(json.dumps(_valid_candidate(), ensure_ascii=False))
    generator = LogisticsSqlPlanGenerator(client=client, enabled=True, model="fake-deepseek")

    result = generator.generate(
        original_question="哪个物流跑得最多？",
        normalized_question="哪个承运商发运量最多？",
        route=LogisticsNl2SqlDomainRouter().route("哪个物流跑得最多？"),
        recall_result=_recall_ok(),
    )

    assert result.status == "ok", result.error_codes
    user_payload = json.loads(client.calls[-1]["messages"][1]["content"])
    contract = user_payload["schema_contract"]
    assert contract["allowed_top_level_keys"] == [
        "schema_version",
        "domain",
        "strategy",
        "catalog_version",
        "catalog_refs",
        "plan",
        "clarification_questions",
        "unsupported_reason",
        "confidence",
    ]
    assert contract["allowed_plan_keys"] == [
        "query_type",
        "domain",
        "tables",
        "joins",
        "metrics",
        "dimensions",
        "filters",
        "group_by",
        "order_by",
        "business_rules",
        "explicit_year_buckets",
        "requested_unit",
        "limit",
    ]
    assert "plan_filters" in contract["forbidden_misplaced_keys"]
    assert "plan.confidence" in contract["forbidden_misplaced_keys"]
    assert "_business_rules" in contract["forbidden_misplaced_keys"]
    assert contract["field_placement"]["filters"] == "plan.filters"
    assert contract["array_item_rules"]["plan.dimensions"] == "array<string>"
    assert user_payload["json_schema_contract"]["additionalProperties"] is False
    assert user_payload["valid_sql_direct_example"]["plan"]["dimensions"] == ["logistics_company_name"]


def test_sqlplan_generator_repairs_safe_provider_catalog_shape_before_validation() -> None:
    """真实 provider 常见 catalog 版本/引用遗漏只允许按召回命中做安全补全，再交给 validator。"""

    provider_candidate = _valid_candidate(
        catalog_version="logistics_sql_catalog.v1",
        catalog_refs=[
            {"catalog_id": "example:m9_example_carrier_mw_ranking", "catalog_version": "logistics_sql_catalog.v1"},
            {"catalog_id": "dimension:logistics_company_name", "catalog_version": "logistics_sql_catalog.v1"},
            {"catalog_id": "rule:default_time_range", "catalog_version": "logistics_sql_catalog.v1"},
        ],
        plan={"business_rules": ["businesses: []"]},
    )
    client = _FakeChatClient(json.dumps(provider_candidate, ensure_ascii=False))
    generator = LogisticsSqlPlanGenerator(client=client, enabled=True, model="fake-deepseek")

    result = generator.generate(
        original_question="哪个物流跑得最多？",
        normalized_question="哪个承运商发运量最多？",
        route=LogisticsNl2SqlDomainRouter().route("哪个物流跑得最多？"),
        recall_result=_recall_ok(),
    )

    assert result.status == "ok", result.error_codes
    assert result.validation_result is not None and result.validation_result.ok is True
    assert result.candidate is not None
    assert result.candidate["catalog_version"] == CATALOG_VERSION
    ref_ids = {ref["catalog_id"] for ref in result.candidate["catalog_refs"]}
    assert ref_ids >= {
        "table:dws_logistics_detail_union",
        "metric:shipment_mw",
        "metric:row_count",
        "dimension:biz_year",
        "dimension:logistics_company_name",
        "rule:default_time_range",
    }
    assert all(ref["catalog_version"] == CATALOG_VERSION for ref in result.candidate["catalog_refs"])
    assert result.candidate["plan"]["business_rules"] == ["default_time_range"]


def test_sqlplan_generator_normalizes_known_safe_provider_key_aliases_before_validation() -> None:
    """真实 provider 偶发输出安全别名键时，只按白名单别名归一，仍交给 validator 校验。"""

    provider_candidate = _valid_candidate()
    provider_candidate["catalog refs"] = provider_candidate.pop("catalog_refs")
    provider_candidate["unsupported_reasonalityReason"] = None
    client = _FakeChatClient(json.dumps(provider_candidate, ensure_ascii=False))
    generator = LogisticsSqlPlanGenerator(client=client, enabled=True, model="fake-deepseek")

    result = generator.generate(
        original_question="哪个物流跑得最多？",
        normalized_question="哪个承运商发运量最多？",
        route=LogisticsNl2SqlDomainRouter().route("哪个物流跑得最多？"),
        recall_result=_recall_ok(),
    )

    assert result.status == "ok", result.error_codes
    assert result.candidate is not None
    assert "catalog refs" not in result.candidate
    assert "unsupported_reasonalityReason" not in result.candidate
    assert result.candidate["catalog_refs"]


def test_sqlplan_generator_deduplicates_safe_explicit_year_buckets_before_validation() -> None:
    """live provider 若只重复输出已请求年份，应安全去重后再交给 validator。"""

    provider_candidate = _valid_candidate(plan={"explicit_year_buckets": [2023, 2024, 2025, 2025, 2026]})
    client = _FakeChatClient(json.dumps(provider_candidate, ensure_ascii=False))
    generator = LogisticsSqlPlanGenerator(client=client, enabled=True, model="fake-deepseek")

    result = generator.generate(
        original_question="哪个物流跑得最多？",
        normalized_question="哪个承运商发运量最多？",
        route=LogisticsNl2SqlDomainRouter().route("哪个物流跑得最多？"),
        recall_result=_recall_ok(),
    )

    assert result.status == "ok", result.error_codes
    assert result.validation_result is not None and result.validation_result.ok is True
    assert result.candidate is not None
    assert result.candidate["plan"]["explicit_year_buckets"] == [2023, 2024, 2025, 2026]


def test_sqlplan_generator_keeps_unsafe_explicit_year_buckets_fail_closed() -> None:
    """年份桶只有与 biz_year 过滤完全同集时才能去重；多给、少给、非法值都继续失败。"""

    unsafe_cases = [
        [2023, 2024, 2025, 2026, 2027],
        [2023, 2024, 2026],
        [2023, 2024, "bad", 2026],
    ]
    for explicit_year_buckets in unsafe_cases:
        provider_candidate = _valid_candidate(plan={"explicit_year_buckets": explicit_year_buckets})
        client = _FakeChatClient(json.dumps(provider_candidate, ensure_ascii=False))
        generator = LogisticsSqlPlanGenerator(client=client, enabled=True, model="fake-deepseek")

        result = generator.generate(
            original_question="哪个物流跑得最多？",
            normalized_question="哪个承运商发运量最多？",
            route=LogisticsNl2SqlDomainRouter().route("哪个物流跑得最多？"),
            recall_result=_recall_ok(),
        )

        assert result.status == "validation_failed", explicit_year_buckets
        assert result.validation_result is not None and result.validation_result.ok is False
        assert result.candidate is None
        assert result.error_codes


def test_sqlplan_generator_normalizes_live_yearly_breakdown_provider_drift() -> None:
    """真实 provider 对多年拆分偶发混入原始表和默认时间规则时，只做可证明安全的收敛归一。"""

    provider_candidate = _valid_candidate(
        catalog_refs=[
            {"catalog_id": "example:m9_example_yearly_mw_breakdown", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "table:dwd_logistics_hist_shipment_detail", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "rule:default_time_range", "catalog_version": CATALOG_VERSION},
        ],
        plan={
            "query_type": "aggregate",
            "tables": ["dws_logistics_detail_union", "dwd_logistics_hist_shipment_detail"],
            "joins": [],
            "metrics": ["shipment_mw", "row_count"],
            "dimensions": ["biz_year"],
            "filters": [{"dimension": "biz_year", "operator": "in", "values": [2023, 2024, 2025], "source": "user_explicit"}],
            "group_by": ["biz_year"],
            "order_by": [{"dimension": "biz_year", "direction": "asc"}],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [2023, 2024, 2025],
            "requested_unit": "MW",
            "limit": 20,
        },
    )
    client = _FakeChatClient(json.dumps(provider_candidate, ensure_ascii=False))
    generator = LogisticsSqlPlanGenerator(client=client, enabled=True, model="fake-deepseek")

    result = generator.generate(
        original_question="2023年到2025年每年发运量分别是多少？",
        normalized_question="2023年到2025年每年发运量分别是多少？",
        route=LogisticsNl2SqlDomainRouter().route("2023年到2025年每年发运量分别是多少？"),
        recall_result=_recall_by_ids(
            {
                "example:m9_example_yearly_mw_breakdown",
                "table:dwd_logistics_hist_shipment_detail",
                "metric:shipment_mw",
                "rule:default_time_range",
            }
        ),
    )

    assert result.status == "ok", result.error_codes
    assert result.validation_result is not None and result.validation_result.ok is True
    assert result.candidate is not None
    assert result.candidate["plan"]["tables"] == ["dws_logistics_detail_union"]
    assert result.candidate["plan"]["business_rules"] == []
    assert result.candidate["plan"]["explicit_year_buckets"] == [2023, 2024, 2025]


def test_sqlplan_generator_does_not_single_table_normalize_structured_joins() -> None:
    """结构化非空 joins 不是“无 join”，必须保持原样交给 validator fail-closed。"""

    generator = LogisticsSqlPlanGenerator(client=_FakeChatClient("{}"), enabled=True, model="fake-deepseek")
    plan = {
        "tables": ["dws_logistics_detail_union", "dwd_logistics_hist_shipment_detail"],
        "joins": [
            {
                "left_table": "dws_logistics_detail_union",
                "right_table": "dwd_logistics_hist_shipment_detail",
                "on": "dws_logistics_detail_union.biz_year = dwd_logistics_hist_shipment_detail.biz_year",
            }
        ],
        "metrics": ["shipment_mw", "row_count"],
        "dimensions": ["biz_year"],
        "filters": [{"dimension": "biz_year", "operator": "in", "values": [2023, 2024, 2025], "source": "user_explicit"}],
        "group_by": ["biz_year"],
        "order_by": [{"dimension": "biz_year", "direction": "asc"}],
    }

    generator._normalize_single_table_plan_tables(plan)

    assert plan["tables"] == ["dws_logistics_detail_union", "dwd_logistics_hist_shipment_detail"]


def test_sqlplan_generator_does_not_single_table_normalize_invalid_table_items() -> None:
    """tables 中存在非字符串项时不得静默清理，必须保持原样让 schema/validator 拦截。"""

    generator = LogisticsSqlPlanGenerator(client=_FakeChatClient("{}"), enabled=True, model="fake-deepseek")
    plan = {
        "tables": ["dws_logistics_detail_union", "dwd_logistics_hist_shipment_detail", {"table": "unexpected"}],
        "joins": [],
        "metrics": ["shipment_mw", "row_count"],
        "dimensions": ["biz_year"],
        "filters": [{"dimension": "biz_year", "operator": "in", "values": [2023, 2024, 2025], "source": "user_explicit"}],
        "group_by": ["biz_year"],
        "order_by": [{"dimension": "biz_year", "direction": "asc"}],
    }

    generator._normalize_single_table_plan_tables(plan)

    assert plan["tables"] == ["dws_logistics_detail_union", "dwd_logistics_hist_shipment_detail", {"table": "unexpected"}]


def test_sqlplan_generator_does_not_single_table_normalize_malformed_filters() -> None:
    """filters 形态异常或缺失有效维度引用时，不能把多表计划收敛成单表。"""

    generator = LogisticsSqlPlanGenerator(client=_FakeChatClient("{}"), enabled=True, model="fake-deepseek")
    malformed_filter_values = [
        {},
        "",
        False,
        [{}],
        [{"dimension": "  ", "operator": "in", "values": [2023]}],
        [{"dimension": 123, "operator": "in", "values": [2023]}],
        [{"dimension": "unknown_dimension", "operator": "in", "values": [2023]}],
    ]
    for filters in malformed_filter_values:
        plan = _single_table_normalization_plan()
        plan["filters"] = filters

        generator._normalize_single_table_plan_tables(plan)

        assert plan["tables"] == ["dws_logistics_detail_union", "dwd_logistics_hist_shipment_detail"], filters


def test_sqlplan_generator_does_not_single_table_normalize_malformed_order_by() -> None:
    """order_by 形态异常、缺失引用或多引用时，不能把多表计划收敛成单表。"""

    generator = LogisticsSqlPlanGenerator(client=_FakeChatClient("{}"), enabled=True, model="fake-deepseek")
    malformed_order_by_values = [
        {},
        "",
        False,
        [{}],
        [{"metric": "  ", "direction": "desc"}],
        [{"dimension": 123, "direction": "asc"}],
        [{"metric": "unknown_metric", "direction": "desc"}],
        [{"dimension": "unknown_dimension", "direction": "asc"}],
        [{"metric": "shipment_mw", "dimension": "biz_year", "direction": "desc"}],
    ]
    for order_by in malformed_order_by_values:
        plan = _single_table_normalization_plan()
        plan["order_by"] = order_by

        generator._normalize_single_table_plan_tables(plan)

        assert plan["tables"] == ["dws_logistics_detail_union", "dwd_logistics_hist_shipment_detail"], order_by


def test_sqlplan_generator_expands_dependencies_declared_by_recalled_example() -> None:
    """命中 canonical 示例时，可展开示例声明的依赖；这锁定真实 provider gate 的 missing catalog_ref 修复。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    docs = LogisticsCatalogRecallDocumentBuilder().build(catalog)
    recall_result = LogisticsCatalogRecallResult(
        status="ok",
        hits=[
            LogisticsCatalogRecallHit(document=document, vector_score=0.88, rerank_score=0.96, source="rerank")
            for document in docs
            if document.catalog_id == "example:m9_example_carrier_mw_ranking"
        ],
    )
    provider_candidate = _valid_candidate(catalog_refs=[])
    generator = LogisticsSqlPlanGenerator(
        client=_FakeChatClient(json.dumps(provider_candidate, ensure_ascii=False)),
        enabled=True,
        model="fake-deepseek",
    )

    result = generator.generate(
        original_question="哪个物流跑得最多？",
        normalized_question="哪个承运商发运量最多？",
        route=LogisticsNl2SqlDomainRouter().route("哪个物流跑得最多？"),
        recall_result=recall_result,
    )

    assert result.status == "ok", result.error_codes
    assert result.validation_result is not None and result.validation_result.ok is True
    assert result.candidate is not None
    ref_ids = {ref["catalog_id"] for ref in result.candidate["catalog_refs"]}
    assert ref_ids >= {
        "table:dws_logistics_detail_union",
        "metric:shipment_mw",
        "metric:row_count",
        "dimension:biz_year",
        "dimension:logistics_company_name",
        "rule:default_time_range",
        "example:m9_example_carrier_mw_ranking",
    }


def test_sqlplan_generator_does_not_fabricate_catalog_refs_not_returned_or_declared_by_recall() -> None:
    """catalog_refs 安全补全只能来自本次召回命中或其 canonical 依赖，不能凭 LLM plan 自行放开未声明指标。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    docs = LogisticsCatalogRecallDocumentBuilder().build(catalog)
    wanted = {
        "table:dws_logistics_detail_union",
        "metric:shipment_mw",
        "dimension:biz_year",
        "dimension:logistics_company_name",
        "rule:default_time_range",
    }
    recall_result = LogisticsCatalogRecallResult(
        status="ok",
        hits=[
            LogisticsCatalogRecallHit(document=document, vector_score=0.88, rerank_score=0.96, source="rerank")
            for document in docs
            if document.catalog_id in wanted
        ],
    )
    provider_candidate = _valid_candidate(catalog_refs=[])
    generator = LogisticsSqlPlanGenerator(
        client=_FakeChatClient(json.dumps(provider_candidate, ensure_ascii=False)),
        enabled=True,
        model="fake-deepseek",
    )

    result = generator.generate(
        original_question="哪个物流跑得最多？",
        normalized_question="哪个承运商发运量最多？",
        route=LogisticsNl2SqlDomainRouter().route("哪个物流跑得最多？"),
        recall_result=recall_result,
    )

    assert result.status == "validation_failed"
    assert "sqlplan_missing_catalog_ref::metric:row_count" in result.error_codes


def test_sqlplan_generator_rejects_markdown_raw_sql_and_unexpected_fields() -> None:
    """LLM 输出 markdown、raw SQL 或多余解释时必须 fail-closed，不能进入 shadow pipeline。"""

    unsafe_payload = """```json
    {"sql":"SELECT * FROM sys_query_log", "answer":"42"}
    ```"""
    generator = LogisticsSqlPlanGenerator(client=_FakeChatClient(unsafe_payload), enabled=True, model="fake-deepseek")

    result = generator.generate(
        original_question="查一下物流 SQL",
        normalized_question="查一下物流 SQL",
        route=LogisticsNl2SqlDomainRouter().route("查一下物流 SQL"),
        recall_result=_recall_ok(),
    )

    assert result.status == "validation_failed"
    assert result.candidate is None
    assert "m9_llm_output_not_strict_json" in result.error_codes or "m9_forbidden_llm_field::sql" in result.error_codes
    assert all("SELECT" not in error for error in result.error_codes)


def test_m9_shadow_runner_fail_closed_when_recall_unavailable_and_does_not_call_llm(tmp_path) -> None:
    """召回/精排不可用时 M9 必须停在 recall 阶段，不允许降级调用 LLM 生成计划。"""

    generator = _RecordingGenerator()
    sample = LogisticsNl2SqlM9ShadowSample(
        sample_id="m9_recall_disabled",
        question="2025年各承运商发运量排名",
        expected_status="recall_failed",
        category="ranking",
        business_case="carrier_mw_ranking",
    )

    run = run_logistics_nl2sql_m9_shadow_sqlplan_generation(
        samples=[sample],
        artifact_dir=tmp_path,
        recall_service=_DisabledRecallService(),
        generator=generator,
    )

    assert run.version == M9_SHADOW_SQLPLAN_GENERATION_VERSION
    assert run.shadow_only is True
    assert run.report.total == 1
    assert run.report.recall_failed_count == 1
    assert run.outcomes[0].status == "recall_failed"
    assert run.outcomes[0].stage == "recall"
    assert generator.called is False
    assert run.records_path.exists()
    assert run.report_path.exists()


def test_m9_shadow_runner_fail_closed_for_unsupported_tonnage_before_recall_and_generator(tmp_path) -> None:
    """unsupported_tonnage 是确定性停止信号，不能继续进入召回、LLM 生成或 shadow pipeline。"""

    recall = _RecordingRecallService()
    generator = _RecordingStaticGenerator(_valid_candidate())
    pipeline = _RecordingPipeline()
    sample = LogisticsNl2SqlM9ShadowSample(
        sample_id="m9_guard_tonnage_fail_closed",
        question="2025年各承运商运输吨位排名",
        expected_status="validation_failed",
        category="validation",
        business_case="unsupported_tonnage",
    )

    run = run_logistics_nl2sql_m9_shadow_sqlplan_generation(
        samples=[sample],
        artifact_dir=tmp_path,
        recall_service=recall,
        generator=generator,
        pipeline=pipeline,
    )

    assert run.report.total == 1
    assert run.report.validation_failed_count == 1
    assert run.report.expected_status_mismatch_count == 0
    assert run.outcomes[0].status == "validation_failed"
    assert run.outcomes[0].stage == "rewrite"
    assert "m9_rewrite_unsupported::unsupported_tonnage" in run.outcomes[0].error_codes
    assert recall.called is False
    assert generator.called is False
    assert pipeline.called is False


def test_m9_shadow_runner_does_not_construct_default_dependencies_for_unsupported_tonnage(tmp_path, monkeypatch) -> None:
    """unsupported_tonnage 样例必须在默认依赖构造前停止，避免无意义触发外部 provider 适配器。"""

    class _ForbiddenDependency:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("unsupported_tonnage 不应构造默认召回/生成/执行依赖")

    monkeypatch.setattr(m9_module, "LogisticsCatalogRecallService", _ForbiddenDependency)
    monkeypatch.setattr(m9_module, "LogisticsSqlPlanGenerator", _ForbiddenDependency)
    monkeypatch.setattr(m9_module, "LogisticsNl2SqlShadowPipeline", _ForbiddenDependency)
    sample = LogisticsNl2SqlM9ShadowSample(
        sample_id="m9_guard_tonnage_fail_closed",
        question="2025年各承运商运输吨位排名",
        expected_status="validation_failed",
        category="validation",
        business_case="unsupported_tonnage",
    )

    run = run_logistics_nl2sql_m9_shadow_sqlplan_generation(samples=[sample], artifact_dir=tmp_path)

    assert run.report.validation_failed_count == 1
    assert run.report.expected_status_mismatch_count == 0
    assert run.outcomes[0].stage == "rewrite"


def test_m9_dev_runner_default_smoke_covers_tonnage_guard(tmp_path) -> None:
    """dev runner 默认 smoke 必须覆盖吨位 fail-closed guard，不能只跑前两个 happy-path 样例。"""

    script_path = Path(__file__).resolve().parents[4] / "scripts/dev/run_logistics_nl2sql_m9_shadow_sqlplan_generation.py"
    result = subprocess.run(
        [sys.executable, str(script_path), "--artifact-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["total"] == 3
    assert payload["expected_status_mismatch_count"] == 0
    report_text = (tmp_path / "m9-shadow-sqlplan-generation-report.md").read_text(encoding="utf-8")
    assert "m9_guard_tonnage_fail_closed: status=validation_failed" in report_text


def test_m9_shadow_runner_writes_redacted_artifacts_for_fake_success(tmp_path) -> None:
    """M9 fake runner 输出自然语言→SQLPlan→shadow 的脱敏评估材料，不泄露 SQL/参数值/密钥。"""

    run = run_logistics_nl2sql_m9_shadow_sqlplan_generation(
        samples=build_default_logistics_nl2sql_m9_shadow_samples()[:2],
        artifact_dir=tmp_path,
        recall_service=_StaticRecallService(),
        generator=_StaticGenerator(_valid_candidate()),
    )

    assert run.shadow_only is True
    assert run.report.total == 2
    assert run.report.generated_count == 2
    assert run.report.validation_pass_count >= 1
    assert run.report.expected_status_mismatch_count == 0

    payload = (
        run.records_path.read_text(encoding="utf-8")
        + run.report_path.read_text(encoding="utf-8")
        + json.dumps(run.report.model_dump(mode="json"), ensure_ascii=False)
    )
    assert "SELECT" not in payload
    assert "UPDATE" not in payload
    assert "mysql://" not in payload
    assert "MYSQL_PASSWORD" not in payload
    assert "sk-" not in payload
    assert "raw_param_value" not in payload
    assert "正式物流 QA 主链路" not in payload


def test_m9_shadow_runner_summarizes_candidate_sql_gate_without_raw_sql(tmp_path) -> None:
    """M9 runner 传入 raw candidate SQL 时，report/records 只能写 gate 摘要，不能泄露 SQL 原文。"""

    sample = LogisticsNl2SqlM9ShadowSample(
        sample_id="m10b_raw_candidate_sql_rejected",
        question="2025年发运量是多少",
        expected_status="validation_failed",
        category="candidate_sql_gate",
        business_case="raw_candidate_sql_rejected",
        raw_candidate_sql="SELECT password_token_dsn FROM dws_logistics_detail_union LIMIT 9999",
    )

    run = run_logistics_nl2sql_m9_shadow_sqlplan_generation(
        samples=[sample],
        artifact_dir=tmp_path,
        recall_service=_StaticRecallService(),
        generator=_StaticGenerator(_valid_candidate()),
    )
    payload = (
        run.records_path.read_text(encoding="utf-8")
        + run.report_path.read_text(encoding="utf-8")
        + json.dumps(run.report.model_dump(mode="json"), ensure_ascii=False)
    )

    assert run.report.total == 1
    assert run.report.candidate_sql_gate_rejected_count == 1
    assert run.outcomes[0].candidate_sql_gate_rejected is True
    assert run.outcomes[0].candidate_sql_gate_reason_code == "limit_out_of_range"
    assert "candidate_sql_gate_rejected::limit_out_of_range" in run.outcomes[0].error_codes
    assert "SELECT" not in payload
    assert "password_token_dsn" not in payload
    assert "dws_logistics_detail_union LIMIT 9999" not in payload
    assert "candidate_sql_gate_rejected_count" in payload


def _single_table_normalization_plan() -> dict:
    """构造单表归一化 guard 测试使用的多表噪声计划。

    返回：
        包含统一服务表和历史明细噪声表的 provider plan；默认引用均落在统一服务表。
    业务逻辑：
        该 helper 只用于验证 generator 在异常字段形态下保持原样，避免把 malformed plan 静默修正。
    """

    return {
        "tables": ["dws_logistics_detail_union", "dwd_logistics_hist_shipment_detail"],
        "joins": [],
        "metrics": ["shipment_mw", "row_count"],
        "dimensions": ["biz_year"],
        "filters": [{"dimension": "biz_year", "operator": "in", "values": [2023, 2024, 2025], "source": "user_explicit"}],
        "group_by": ["biz_year"],
        "order_by": [{"dimension": "biz_year", "direction": "asc"}],
    }


def _valid_candidate(**overrides) -> dict:
    candidate = {
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": CATALOG_VERSION,
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "metric:shipment_mw", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "metric:row_count", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "dimension:biz_year", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "dimension:logistics_company_name", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "rule:default_time_range", "catalog_version": CATALOG_VERSION},
            {"catalog_id": "example:m9_example_carrier_mw_ranking", "catalog_version": CATALOG_VERSION},
        ],
        "plan": {
            "query_type": "ranking",
            "tables": ["dws_logistics_detail_union"],
            "joins": [],
            "metrics": ["shipment_mw", "row_count"],
            "dimensions": ["logistics_company_name"],
            "filters": [{"dimension": "biz_year", "operator": "in", "values": [2023, 2024, 2025, 2026]}],
            "group_by": ["logistics_company_name"],
            "order_by": [{"metric": "shipment_mw", "direction": "desc"}],
            "business_rules": ["default_time_range"],
            "explicit_year_buckets": [2023, 2024, 2025, 2026],
            "requested_unit": "MW",
            "limit": 20,
        },
        "clarification_questions": [],
        "unsupported_reason": None,
        "confidence": 0.93,
    }
    return _deep_merge(candidate, overrides)


def _recall_by_ids(catalog_ids: set[str]) -> LogisticsCatalogRecallResult:
    """按指定 catalog_id 构造召回结果，用于复现 live provider gate 的局部命中形态。"""

    catalog = LogisticsSemanticCatalogLoader().load()
    docs = LogisticsCatalogRecallDocumentBuilder().build(catalog)
    hits = [
        LogisticsCatalogRecallHit(document=document, vector_score=0.88, rerank_score=0.96, source="rerank")
        for document in docs
        if document.catalog_id in catalog_ids
    ]
    return LogisticsCatalogRecallResult(status="ok", hits=hits)


def _recall_ok() -> LogisticsCatalogRecallResult:
    catalog = LogisticsSemanticCatalogLoader().load()
    docs = LogisticsCatalogRecallDocumentBuilder().build(catalog)
    wanted = {
        "table:dws_logistics_detail_union",
        "metric:shipment_mw",
        "metric:row_count",
        "dimension:biz_year",
        "dimension:logistics_company_name",
        "rule:default_time_range",
        "example:m9_example_carrier_mw_ranking",
    }
    hits = [
        LogisticsCatalogRecallHit(document=document, vector_score=0.88, rerank_score=0.96, source="rerank")
        for document in docs
        if document.catalog_id in wanted
    ]
    return LogisticsCatalogRecallResult(status="ok", hits=hits)


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, owner: "_FakeChatClient") -> None:
        self.owner = owner

    def create(self, **kwargs):
        self.owner.calls.append(kwargs)
        return _FakeCompletion(self.owner.content)


class _FakeChat:
    def __init__(self, owner: "_FakeChatClient") -> None:
        self.completions = _FakeCompletions(owner)


class _FakeChatClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []
        self.chat = _FakeChat(self)


class _DisabledRecallService:
    def recall(self, **kwargs):
        return LogisticsCatalogRecallResult(status="disabled", error="rerank_unavailable")


class _RecordingRecallService:
    def __init__(self) -> None:
        self.called = False

    def recall(self, **kwargs):
        self.called = True
        return _recall_ok()


class _StaticRecallService:
    def recall(self, **kwargs):
        return _recall_ok()


class _RecordingGenerator:
    called = False

    def generate(self, **kwargs):
        self.called = True
        raise AssertionError("recall 失败时不应调用 generator")


class _StaticGenerator:
    def __init__(self, candidate: dict) -> None:
        self.candidate = candidate

    def generate(self, **kwargs):
        from backend.app.domains.logistics.services.nl2sql.m9_sqlplan_generation import LogisticsSqlPlanGenerationResult
        from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator

        validation_result = LogisticsSqlPlanValidator(catalog=LogisticsSemanticCatalogLoader().load()).validate(self.candidate)
        return LogisticsSqlPlanGenerationResult(
            status="ok" if validation_result.ok else "validation_failed",
            candidate=self.candidate if validation_result.ok else None,
            validation_result=validation_result,
            error_codes=validation_result.error_codes,
        )


class _RecordingStaticGenerator(_StaticGenerator):
    def __init__(self, candidate: dict) -> None:
        super().__init__(candidate)
        self.called = False

    def generate(self, **kwargs):
        self.called = True
        return super().generate(**kwargs)


class _RecordingPipeline(LogisticsNl2SqlShadowPipeline):
    def __init__(self) -> None:
        self.called = False

    def run(self, request):
        self.called = True
        raise AssertionError("unsupported_tonnage 不应进入 shadow pipeline")


def _deep_merge(base: dict, overrides: dict) -> dict:
    merged = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
