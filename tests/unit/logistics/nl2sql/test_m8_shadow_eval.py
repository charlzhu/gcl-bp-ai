from __future__ import annotations

import json

from backend.app.domains.logistics.services.nl2sql.m8_shadow_eval import (
    DEFAULT_M8_RECORDS_FILENAME,
    DEFAULT_M8_REPORT_FILENAME,
    M8_SHADOW_EVAL_VERSION,
    build_default_logistics_nl2sql_m8_shadow_eval_samples,
    run_logistics_nl2sql_m8_shadow_eval,
)


def test_m8_default_shadow_eval_samples_cover_business_metrics_and_fail_closed_guards() -> None:
    """M8 默认样例集应覆盖常见物流指标/维度，并保留 fail-closed 负例。"""

    samples = build_default_logistics_nl2sql_m8_shadow_eval_samples()
    sample_ids = [sample.sample_id for sample in samples]

    assert M8_SHADOW_EVAL_VERSION == "logistics_nl2sql_m8_shadow_eval.v1"
    assert len(samples) >= 8
    assert sample_ids[:6] == [
        "m8_success_yearly_shipment_mw_by_year",
        "m8_success_carrier_avg_fee_per_trip",
        "m8_success_monthly_total_fee_trend",
        "m8_success_region_transport_mode_shipment_fee",
        "m8_validation_tonnage_unit_rejected",
        "m8_validation_unknown_price_metric_rejected",
    ]
    assert "m8_success_carrier_rank_by_mw" in sample_ids
    assert "m8_success_origin_customer_topn_detail" in sample_ids
    assert "m8_validation_quote_metric_requires_supported_hist_scope" in sample_ids
    assert "m8_safety_forbidden_update_sql_blocked" in sample_ids
    assert all(sample.offline_only is True for sample in samples)
    assert {sample.category for sample in samples} >= {"trend", "ranking", "breakdown", "detail", "validation", "safety"}
    assert {sample.metric_family for sample in samples} >= {
        "shipment_volume",
        "total_fee",
        "trip_count",
        "average_freight",
        "unit_price",
        "unsupported",
        "safety_negative",
    }
    assert all(sample.expected_status for sample in samples)

    run = run_logistics_nl2sql_m8_shadow_eval(samples=samples)
    by_sample = {outcome.sample.sample_id: outcome.result.status for outcome in run.outcomes}

    assert by_sample["m8_success_yearly_shipment_mw_by_year"] == "success"
    assert by_sample["m8_success_carrier_avg_fee_per_trip"] == "success"
    assert by_sample["m8_success_monthly_total_fee_trend"] == "success"
    assert by_sample["m8_success_region_transport_mode_shipment_fee"] == "success"
    assert by_sample["m8_success_carrier_rank_by_mw"] == "success"
    assert by_sample["m8_success_origin_customer_topn_detail"] == "success"
    assert by_sample["m8_validation_tonnage_unit_rejected"] == "validation_failed"
    assert by_sample["m8_validation_unknown_price_metric_rejected"] == "validation_failed"
    assert by_sample["m8_validation_quote_metric_requires_supported_hist_scope"] == "validation_failed"
    assert by_sample["m8_safety_forbidden_update_sql_blocked"] == "safety_failed"
    safety_outcome = next(
        outcome for outcome in run.outcomes if outcome.sample.sample_id == "m8_safety_forbidden_update_sql_blocked"
    )
    assert safety_outcome.executor_call_count_after == safety_outcome.executor_call_count_before
    assert safety_outcome.result.explain_ok is False
    assert safety_outcome.result.trial_ok is False
    assert run.report.success_count >= 6
    assert run.report.fail_closed_count >= 4
    assert run.report.expected_status_mismatch_count == 0


def test_m8_evaluation_report_tracks_catalog_metric_dimension_and_table_coverage(tmp_path) -> None:
    """M8 报告应新增 catalog 维度评估：指标、业务维度、表覆盖与 catalog ref 覆盖率。"""

    run = run_logistics_nl2sql_m8_shadow_eval(artifact_dir=tmp_path)
    report = run.report

    assert run.records_path == tmp_path / DEFAULT_M8_RECORDS_FILENAME
    assert run.report_path == tmp_path / DEFAULT_M8_REPORT_FILENAME
    assert run.records_path.exists()
    assert run.report_path.exists()
    assert len(run.records_path.read_text(encoding="utf-8").splitlines()) == len(run.outcomes)

    assert report.by_metric_id["shipment_mw"] >= 2
    assert report.by_metric_id["total_fee"] >= 2
    assert report.by_metric_id["avg_fee_per_trip"] >= 1
    assert report.by_metric_id["shipment_trip_count"] >= 1
    assert report.by_dimension_id["biz_year"] >= 1
    assert report.by_dimension_id["biz_month"] >= 1
    assert report.by_dimension_id["logistics_company_name"] >= 1
    assert report.by_dimension_id["region_name"] >= 1
    assert report.by_dimension_id["transport_mode"] >= 1
    assert report.by_table_id["dws_logistics_detail_union"] >= 1
    assert report.by_category["ranking"] >= 1
    assert report.by_category["safety"] >= 1
    assert report.by_metric_family["shipment_volume"] >= 1
    assert report.by_metric_family["average_freight"] >= 1
    assert report.by_metric_family["unit_price"] >= 1
    assert report.expected_status_match_count == report.total
    assert report.expected_status_match_rate == 1.0
    assert report.safety_pass_count >= report.success_count
    assert report.safety_block_count >= 1
    assert report.executor_touched_count >= report.success_count
    assert report.executor_not_touched_count >= report.fail_closed_count
    assert report.catalog_ref_coverage >= 0.75
    assert report.distinct_catalog_ref_count >= 8

    markdown = run.render_markdown()
    assert "## By Metric" in markdown
    assert "avg_fee_per_trip" in markdown
    assert "## By Dimension" in markdown
    assert "transport_mode" in markdown
    assert "## By Category" in markdown
    assert "## By Metric Family" in markdown


def test_m8_shadow_eval_artifacts_remain_shadow_only_and_redacted(tmp_path) -> None:
    """M8 固定 runner 写出的 JSONL/Markdown 只保留脱敏摘要，不泄露 SQL、参数值或连接信息。"""

    run = run_logistics_nl2sql_m8_shadow_eval(artifact_dir=tmp_path)
    payload = (
        run.records_path.read_text(encoding="utf-8")
        + run.report_path.read_text(encoding="utf-8")
        + json.dumps(run.report.model_dump(mode="json"), ensure_ascii=False)
    )

    assert run.live_smoke_executed is False
    assert run.shadow_only is True
    assert "SELECT" not in payload
    assert "UPDATE" not in payload
    assert "mysql://" not in payload
    assert "MYSQL_PASSWORD" not in payload
    assert "unit-password" not in payload
    assert "tok_unitsecret" not in payload
    assert "raw_param_value" not in payload
    assert "正式物流 QA 主链路" not in payload
