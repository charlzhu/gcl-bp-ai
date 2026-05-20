from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from backend.app.domains.business_analysis.services.inventory_sales_production import m5_shadow_compare
from backend.app.domains.business_analysis.services.inventory_sales_production.m5_shadow_compare import (
    DEFAULT_M5_ISP_RECORDS_FILENAME,
    DEFAULT_M5_ISP_REPORT_FILENAME,
    M5_ISP_SHADOW_COMPARE_VERSION,
    InventorySalesProductionM5ShadowCompareSample,
    build_default_inventory_sales_production_m5_shadow_samples,
    render_safe_m5_shadow_compare_summary_json,
    run_inventory_sales_production_m5_shadow_compare,
)


def test_m5_shadow_default_samples_cover_m4_6_real_questions_and_fail_closed_guards(tmp_path: Path) -> None:
    """M5-3 默认 shadow 样例应来自 M4-6 真实问法，并覆盖成功、暂不支持、澄清和脱敏负例。"""

    samples = build_default_inventory_sales_production_m5_shadow_samples()
    sample_ids = [sample.sample_id for sample in samples]

    assert M5_ISP_SHADOW_COMPARE_VERSION == "business_analysis_inventory_sales_production_m5_shadow_compare.v1"
    assert sample_ids[:10] == [
        "m4_6_sales_year_summary",
        "m4_6_sales_quarter_summary",
        "m4_6_sales_ytd_summary",
        "m4_6_inventory_snapshot",
        "m4_6_consigned_inventory_snapshot",
        "m4_6_budget_achievement",
        "m4_6_invoice_sales_summary",
        "m4_6_unsupported_yoy",
        "m4_6_unsupported_month_range",
        "m4_6_clarification_inventory_turnover",
    ]
    assert {sample.question_category for sample in samples} >= {
        "sales_summary",
        "inventory_snapshot",
        "budget_achievement",
        "unsupported_guard",
        "clarification_guard",
        "redaction_guard",
    }
    assert all(sample.expected_status for sample in samples)

    run = run_inventory_sales_production_m5_shadow_compare(samples=samples, artifact_dir=tmp_path)
    by_sample = {outcome.sample.sample_id: outcome.record.status for outcome in run.outcomes}
    assert by_sample["m4_6_sales_year_summary"] == "matched"
    assert by_sample["m4_6_sales_quarter_summary"] == "matched"
    assert by_sample["m4_6_sales_ytd_summary"] == "matched"
    assert by_sample["m4_6_inventory_snapshot"] == "matched"
    assert by_sample["m4_6_consigned_inventory_snapshot"] == "matched"
    assert by_sample["m4_6_budget_achievement"] == "matched"
    assert by_sample["m4_6_invoice_sales_summary"] == "matched"
    assert by_sample["m4_6_unsupported_yoy"] == "queryplan_unsupported"
    assert by_sample["m4_6_unsupported_month_range"] == "queryplan_unsupported"
    assert by_sample["m4_6_clarification_inventory_turnover"] == "queryplan_clarification"
    assert by_sample["m5_redaction_sql_payload_blocked"] == "sqlplan_validation_failed"

    assert run.shadow_only is True
    assert run.formal_qa_executed is False
    assert run.live_db_executed is False
    assert run.report["total"] == len(samples)
    assert run.report["matched_count"] >= 7
    assert run.report["fail_closed_count"] >= 3
    assert run.report["expected_status_mismatch_count"] == 0


def test_m5_shadow_default_runner_uses_independent_sqlplan_fixtures(tmp_path: Path) -> None:
    """默认 M5 shadow 候选必须独立于 QueryPlan，不能用 QueryPlan 反向生成候选后自我比较。"""

    assert not hasattr(m5_shadow_compare, "_candidate_from_query_plan")

    run = run_inventory_sales_production_m5_shadow_compare(artifact_dir=tmp_path)

    assert run.report["expected_status_mismatch_count"] == 0
    assert run.report["matched_count"] >= 7


def test_m5_shadow_fails_closed_when_independent_sqlplan_candidate_missing(monkeypatch, tmp_path: Path) -> None:
    """自定义可回答样例若缺少独立 SQLPlan 候选，必须 fail-closed，不能回退到 QueryPlan 自我比较。"""

    assert not hasattr(m5_shadow_compare, "_candidate_from_query_plan")
    monkeypatch.setattr(m5_shadow_compare, "_signature_from_query_plan", lambda query_plan: {"safe": "query"})
    sample = InventorySalesProductionM5ShadowCompareSample(
        sample_id="regression_missing_independent_candidate",
        description="缺少独立 SQLPlan 候选时保守失败",
        question="2024年销量是多少？",
        question_category="candidate_source_guard",
        expected_status="sqlplan_candidate_unavailable",
    )

    run = run_inventory_sales_production_m5_shadow_compare(samples=[sample], artifact_dir=tmp_path)

    assert run.outcomes[0].record.status == "sqlplan_candidate_unavailable"
    assert run.outcomes[0].record.candidate_signature is None
    assert "sqlplan_candidate_unavailable" in run.outcomes[0].record.error_codes


def test_m5_shadow_default_artifact_dir_uses_current_kanban_task(monkeypatch, tmp_path: Path) -> None:
    """未显式传 artifact_dir 时应写入当前看板任务 outbox，不能默认写到旧任务目录。"""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HERMES_KANBAN_TASK", "t_3ca95bf9")
    monkeypatch.setattr(m5_shadow_compare, "build_default_inventory_sales_production_m5_shadow_samples", lambda: [])

    run = run_inventory_sales_production_m5_shadow_compare()

    assert run.records_path == tmp_path / "ai/outbox/kanban/t_3ca95bf9" / DEFAULT_M5_ISP_RECORDS_FILENAME
    assert run.report_path == tmp_path / "ai/outbox/kanban/t_3ca95bf9" / DEFAULT_M5_ISP_REPORT_FILENAME


def test_m5_shadow_persisted_signatures_redact_period_values(tmp_path: Path) -> None:
    """持久化签名只保留安全形状，不写出具体年份、月份等抽取参数值。"""

    run = run_inventory_sales_production_m5_shadow_compare(artifact_dir=tmp_path)
    records = [json.loads(line) for line in run.records_path.read_text(encoding="utf-8").splitlines() if line]

    for record in records:
        for signature_name in ("queryplan_signature", "candidate_signature"):
            signature = record.get(signature_name)
            if signature is None:
                continue
            assert "year" not in signature
            assert "months" not in signature
            assert "business_flag_values" not in signature
            assert "period_value_bucket" in signature


def test_m5_shadow_compare_distinguishes_ytd_from_same_month_count_annual_plan(tmp_path: Path) -> None:
    """对比签名必须区分 YTD 与年度期间，避免 2026 已发布 1-4 月时错误匹配。"""

    annual_candidate = m5_shadow_compare._build_sqlplan_candidate_payload(
        query_key="ba_isp_metric_summary",
        metrics=["shipment_volume"],
        dimensions=[],
        period_type="year",
        year=2026,
    )
    sample = InventorySalesProductionM5ShadowCompareSample(
        sample_id="regression_ytd_not_annual",
        description="同月数 YTD 和年度计划不能误判一致",
        question="2026年截至4月累计销量是多少？",
        question_category="period_semantics_guard",
        expected_status="plan_mismatch",
        candidate_override=annual_candidate,
    )

    run = run_inventory_sales_production_m5_shadow_compare(samples=[sample], artifact_dir=tmp_path)

    assert run.outcomes[0].record.status == "plan_mismatch"
    assert "queryplan_sqlplan_signature_mismatch" in run.outcomes[0].record.error_codes


def test_m5_shadow_compare_distinguishes_redacted_period_parameters(tmp_path: Path) -> None:
    """对比签名必须比较期间参数安全指纹，不能因脱敏而把不同年月/季度/YTD 截止月判一致。"""

    samples = [
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="regression_wrong_year",
            description="年度候选年份不同不能匹配",
            question="2024年销量是多少？",
            question_category="period_parameter_guard",
            expected_status="plan_mismatch",
            candidate_override=m5_shadow_compare._build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["shipment_volume"],
                dimensions=[],
                period_type="year",
                year=2025,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="regression_wrong_quarter",
            description="季度候选季度不同不能匹配",
            question="2025年Q1销量是多少？",
            question_category="period_parameter_guard",
            expected_status="plan_mismatch",
            candidate_override=m5_shadow_compare._build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["shipment_volume"],
                dimensions=[],
                period_type="quarter",
                year=2025,
                quarter=2,
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="regression_wrong_month",
            description="月度候选月份不同不能匹配",
            question="2026年4月存货合计是多少？",
            question_category="period_parameter_guard",
            expected_status="plan_mismatch",
            candidate_override=m5_shadow_compare._build_sqlplan_candidate_payload(
                query_key="ba_isp_inventory_snapshot",
                metrics=["ending_inventory_volume"],
                dimensions=[],
                period_type="month",
                year=2026,
                month=3,
                business_rules=["period_end_inventory_snapshot"],
            ),
        ),
        InventorySalesProductionM5ShadowCompareSample(
            sample_id="regression_wrong_ytd_end_month",
            description="YTD 候选截止月不同不能匹配",
            question="2026年截至4月累计销量是多少？",
            question_category="period_parameter_guard",
            expected_status="plan_mismatch",
            candidate_override=m5_shadow_compare._build_sqlplan_candidate_payload(
                query_key="ba_isp_metric_summary",
                metrics=["shipment_volume"],
                dimensions=[],
                period_type="ytd",
                year=2026,
                month_filter_values=[1, 2, 3],
                business_rules=["ytd_by_published_months"],
            ),
        ),
    ]

    run = run_inventory_sales_production_m5_shadow_compare(samples=samples, artifact_dir=tmp_path)

    assert [outcome.record.status for outcome in run.outcomes] == ["plan_mismatch"] * len(samples)
    assert all("queryplan_sqlplan_signature_mismatch" in outcome.record.error_codes for outcome in run.outcomes)
    persisted = run.records_path.read_text(encoding="utf-8")
    for raw_value in ('"year":', '"month":', '"months":', "2024", "2025", "2026"):
        assert raw_value not in persisted
    assert "period_value_fingerprint" in persisted


def test_m5_shadow_safe_text_redaction_handles_lowercase_sql_and_secret_shapes() -> None:
    """错误/告警清洗必须大小写无关地处理 SQL、DSN、Bearer 和 key/value 密钥形态。"""

    safe_values = m5_shadow_compare._dedupe_safe_texts(
        [
            "select * from table where token='abc123'",
            "SAP_ORACLE_DSN=prod-host/service",
            "MYSQL_PASSWORD=abc123",
            "access_token: abc123",
            "secret_key='abc123'",
            "api-key=abc123",
            "apiKey=abc123",
            "bearer abc123",
        ]
    )
    rendered = "\n".join(safe_values).lower()

    assert "select" not in rendered
    assert "prod-host" not in rendered
    assert "abc123" not in rendered
    assert "bearer abc123" not in rendered
    assert "sap_oracle_dsn=prod-host/service" not in rendered
    assert "mysql_password=abc123" not in rendered
    assert "access_token: abc123" not in rendered
    assert "secret_key='abc123'" not in rendered
    assert "api-key=abc123" not in rendered
    assert "apikey=abc123" not in rendered


def test_m5_shadow_artifacts_are_shadow_only_and_redacted(tmp_path: Path) -> None:
    """JSONL/Markdown artifacts 只写脱敏评估摘要，不泄露 SQL、问题原文、真实参数值或连接信息。"""

    run = run_inventory_sales_production_m5_shadow_compare(artifact_dir=tmp_path)

    assert run.records_path == tmp_path / DEFAULT_M5_ISP_RECORDS_FILENAME
    assert run.report_path == tmp_path / DEFAULT_M5_ISP_REPORT_FILENAME
    assert run.records_path.exists()
    assert run.report_path.exists()

    records = [json.loads(line) for line in run.records_path.read_text(encoding="utf-8").splitlines() if line]
    assert records
    assert all(record["shadow_only"] is True for record in records)
    assert all(record["formal_qa_executed"] is False for record in records)
    assert all(record["live_db_executed"] is False for record in records)
    assert all("question_category" in record for record in records)
    assert all("raw_question" not in record for record in records)
    assert all("raw_param_value" not in record for record in records)
    assert all("sql" not in {key.lower() for key in record} for record in records)

    payload = (
        run.records_path.read_text(encoding="utf-8")
        + "\n"
        + run.report_path.read_text(encoding="utf-8")
        + "\n"
        + render_safe_m5_shadow_compare_summary_json(run)
    )
    forbidden_fragments = (
        "SELECT",
        "UPDATE",
        " FROM ",
        " WHERE ",
        "mysql://",
        "MYSQL_PASSWORD",
        "Bearer ",
        "sk-",
        "api_key",
        "password",
        "token",
        "raw_param_value",
        "正式产销存 QA 主链路",
        "InventorySalesProductionQaService.ask",
        "2024年销量是多少",
        "2025年Q1销量是多少",
        "2026年4月存货合计是多少",
        "2027年销量是多少",
    )
    for forbidden in forbidden_fragments:
        assert forbidden not in payload


def test_m5_shadow_runner_does_not_call_formal_qa_main_chain(monkeypatch, tmp_path: Path) -> None:
    """M5-3 对比 runner 只能执行离线 planner/sqlplan validator，不得调用正式 QA ask 主链路。"""

    from backend.app.domains.business_analysis.services.inventory_sales_production import qa_service

    def fail_if_called(*args, **kwargs):  # pragma: no cover - only executed on regression
        raise AssertionError("formal QA main chain must not be called by M5 shadow compare")

    monkeypatch.setattr(qa_service.InventorySalesProductionQaService, "ask", fail_if_called)

    run = run_inventory_sales_production_m5_shadow_compare(artifact_dir=tmp_path)

    assert run.formal_qa_executed is False
    assert run.live_db_executed is False
    assert run.report["expected_status_mismatch_count"] == 0


def test_m5_shadow_dev_runner_cli_exposes_repeatable_smoke_flags() -> None:
    """固定 smoke runner 应支持重复指定 artifact_dir，并默认离线 shadow-only。"""

    script_path = Path(__file__).resolve().parents[3] / "scripts/dev/run_inventory_sales_production_m5_shadow_compare.py"
    result = subprocess.run([sys.executable, str(script_path), "--help"], capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "--artifact-dir" in result.stdout
    assert "--max-samples" in result.stdout
    assert "shadow-only" in result.stdout
