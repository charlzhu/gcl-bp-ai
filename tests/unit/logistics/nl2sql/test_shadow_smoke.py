from __future__ import annotations

import json
from typing import Any

from backend.app.domains.logistics.services.nl2sql.shadow_smoke import (
    DEFAULT_LOGISTICS_NL2SQL_SHADOW_SMOKE_SAMPLE_IDS,
    LogisticsNl2SqlShadowSmokeSample,
    build_default_logistics_nl2sql_shadow_smoke_samples,
    run_logistics_nl2sql_shadow_smoke,
)


def test_shadow_smoke_runner_executes_full_default_sample_set_in_order_and_builds_report() -> None:
    """M6 smoke runner 应离线顺序执行全量默认样例，并返回每条结果、日志与汇总报表。"""

    samples = build_default_logistics_nl2sql_shadow_smoke_samples()

    run = run_logistics_nl2sql_shadow_smoke(samples=samples)

    assert [outcome.sample.sample_id for outcome in run.outcomes] == list(DEFAULT_LOGISTICS_NL2SQL_SHADOW_SMOKE_SAMPLE_IDS)
    assert len(run.outcomes) == len(samples) >= 10
    assert len(run.evaluation_log_records) == len(samples)
    assert run.report.total == len(samples)
    assert run.report.success_count == 1
    assert run.report.by_status["success"] == 1
    assert run.report.by_status["skipped"] >= 2
    assert run.report.by_status["validation_failed"] >= 1
    assert run.report.by_status["safety_failed"] >= 1
    assert run.report.by_status["explain_failed"] >= 1
    assert run.report.by_status["trial_failed"] >= 1
    assert run.report.safety_block_count >= 1
    assert run.report.execution_failure_count >= 2
    assert run.report.sql_hash_coverage == 1.0


def test_shadow_smoke_default_samples_cover_required_status_families_and_do_not_use_real_db_config() -> None:
    """默认样例必须覆盖 success/skipped/validation/safety/explain/trial，且默认 fake executor 不读取真实配置。"""

    run = run_logistics_nl2sql_shadow_smoke()
    by_sample = {outcome.sample.sample_id: outcome.result for outcome in run.outcomes}

    assert by_sample["success_valid_plan"].status == "success"
    assert by_sample["skipped_missing_candidate"].status == "skipped"
    assert by_sample["skipped_non_logistics_domain"].status == "skipped"
    assert by_sample["skipped_non_middle_db_source"].status == "skipped"
    assert by_sample["validation_failed_unknown_metric"].status == "validation_failed"
    assert by_sample["safety_failed_select_star"].status == "safety_failed"
    assert by_sample["explain_failed_fake_executor"].status == "explain_failed"
    assert by_sample["trial_failed_fake_executor"].status == "trial_failed"
    assert any(result.status == "unsupported" for result in by_sample.values())
    assert all(outcome.sample.offline_only is True for outcome in run.outcomes)


def test_shadow_smoke_report_json_markdown_redacts_question_errors_warnings_sql_and_param_values() -> None:
    """默认脱敏样例最终报表 JSON/Markdown 不能泄露 question/error/warning 中的 SQL、DSN 或密钥。"""

    run = run_logistics_nl2sql_shadow_smoke()
    json_payload = json.dumps(run.report.model_dump(mode="json"), ensure_ascii=False)
    markdown = run.render_markdown()
    payload = json_payload + markdown

    assert "SELECT" not in payload
    assert "dws_logistics_detail_union" not in payload
    assert "mysql://" not in payload
    assert "unit-password" not in payload
    assert "tok_unitsecret" not in payload
    assert "pass123" not in payload
    assert "bearer-secret-value" not in payload
    assert "raw_param_value" not in payload
    assert "[REDACTED]" in payload or "[SQL_REDACTED]" in payload or "[DSN_REDACTED]" in payload


def test_shadow_smoke_runner_converts_single_sample_exception_to_controlled_outcome() -> None:
    """单条样例执行异常不能导致全局崩溃，runner 应生成受控失败日志并继续后续样例。"""

    samples = [
        LogisticsNl2SqlShadowSmokeSample(
            sample_id="factory_crashes",
            description="executor 工厂异常样例",
            request={"question": "异常样例", "candidate": None},
        ),
        build_default_logistics_nl2sql_shadow_smoke_samples()[0],
    ]

    def _factory(sample: LogisticsNl2SqlShadowSmokeSample) -> Any:
        if sample.sample_id == "factory_crashes":
            password_key = "pass" + "word"
            raise RuntimeError(f"factory crashed {password_key}=unit-password")
        return None

    run = run_logistics_nl2sql_shadow_smoke(samples=samples, executor_factory=_factory)

    assert [outcome.sample.sample_id for outcome in run.outcomes] == ["factory_crashes", "success_valid_plan"]
    assert run.outcomes[0].result.status == "render_failed"
    assert run.outcomes[0].result.stage == "runner"
    assert "shadow_smoke_sample_failed" in run.outcomes[0].result.error_codes
    assert run.outcomes[1].result.status == "success"
    payload = run.outcomes[0].result.model_dump_json() + run.outcomes[0].evaluation_log_record.model_dump_json()
    assert "unit-password" not in payload
    assert "[REDACTED]" in payload
