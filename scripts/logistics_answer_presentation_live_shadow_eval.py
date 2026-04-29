from __future__ import annotations

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaPlan,
    LogisticsDataQaQueryRequest,
    LogisticsDataQaResult,
    LogisticsDataQaStatus,
    LogisticsDataQaTable,
)
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.llm_answer_presentation_service import (
    LogisticsLlmAnswerPresentationService,
)


REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_answer_presentation_live_shadow_eval_report.json"
ACCEPTANCE_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_answer_presentation_live_llm_acceptance_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_ANSWER_PRESENTATION_LIVE_SHADOW_EVAL.md"
ACCEPTANCE_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_ANSWER_PRESENTATION_LIVE_LLM_ACCEPTANCE.md"
FRONTEND_PAGE = PROJECT_ROOT / "frontend/src/views/logistics-data-qa/LogisticsDataQaPage.vue"
MANDATORY_QUESTION = "请将 2026 年 1 月到三月，这三个月的运量综合用折线图统计出来"


def _resolve_presentation_model() -> tuple[str, str]:
    """解析答案表达层模型名。

    返回：
        (模型名, 模型来源)。模型来源只用于验收报告，不包含任何密钥。
    """

    if settings.llm_answer_presentation_model:
        return settings.llm_answer_presentation_model, "LLM_ANSWER_PRESENTATION_MODEL"
    if settings.llm_answer_presentation_enabled and settings.llm_model:
        return settings.llm_model, "LLM_MODEL"
    return "", "not_configured"


def _live_llm_config() -> dict[str, Any]:
    """返回脱敏后的 live LLM 配置状态。"""

    model, model_source = _resolve_presentation_model()
    configured = bool(
        settings.llm_answer_presentation_enabled
        and settings.llm_base_url
        and settings.llm_api_key
        and model
    )
    return {
        "answer_presentation_enabled": settings.llm_answer_presentation_enabled,
        "llm_base_url_configured": bool(settings.llm_base_url),
        "llm_base_url": settings.llm_base_url or None,
        "llm_api_key_configured": bool(settings.llm_api_key),
        "llm_model_configured": bool(model),
        "llm_answer_presentation_model_configured": bool(settings.llm_answer_presentation_model),
        "resolved_model": model or None,
        "resolved_model_source": model_source,
        "live_llm_configured": configured,
    }


class _FakeMessage:
    """模拟 OpenAI SDK message 对象。"""

    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    """模拟 OpenAI SDK choice 对象。"""

    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    """模拟 OpenAI SDK completion 对象。"""

    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    """模拟 chat.completions.create。

    参数：
        content: 返回文本。
        error: 是否模拟 LLM 调用失败。
    """

    def __init__(self, content: str, *, error: bool = False) -> None:
        self.content = content
        self.error = error

    def create(self, **_: Any) -> _FakeCompletion:
        """返回模拟 completion，或抛出模拟异常。"""

        if self.error:
            raise RuntimeError("fake live llm error")
        return _FakeCompletion(self.content)


class _FakeChat:
    """模拟 OpenAI SDK chat 对象。"""

    def __init__(self, content: str, *, error: bool = False) -> None:
        self.completions = _FakeCompletions(content, error=error)


class _FakeClient:
    """模拟 OpenAI 兼容客户端。"""

    def __init__(self, content: str, *, error: bool = False) -> None:
        self.chat = _FakeChat(content, error=error)


def _status(code: str, message: str, *, success: bool = True) -> LogisticsDataQaStatus:
    """构造 data-qa 状态。"""

    return LogisticsDataQaStatus(
        code=code,
        message=message,
        success=success,
        severity="success" if success else "info",
    )


def _plan(
    *,
    intent: str = "aggregate",
    query_key: str | None = "sys_mw_and_trip_count",
    filters: dict[str, Any] | None = None,
    needs_clarification: bool = False,
    unsupported_reason: str | None = None,
    unsupported_suggestions: list[str] | None = None,
) -> LogisticsDataQaPlan:
    """构造测试用受控计划。"""

    return LogisticsDataQaPlan(
        intent=intent,
        query_key=query_key,
        metrics=["shipment_mw"],
        dimensions=["biz_month"],
        filters=filters or {"year": 2026, "months": [1, 2, 3]},
        needs_clarification=needs_clarification,
        clarification_questions=["请补充统计时间范围和指标口径。"] if needs_clarification else [],
        clarification_missing_slots=["time_range"] if needs_clarification else [],
        unsupported_reason=unsupported_reason,
        unsupported_suggestions=unsupported_suggestions or [],
    )


def _synthetic_success_result() -> LogisticsDataQaResult:
    """构造包含三个月按月 rows 的 A 类确定性结果。"""

    rows = [
        {"biz_month": "2026-01", "shipment_mw": 864.728, "shipment_trip_count": 564},
        {"biz_month": "2026-02", "shipment_mw": 259.844, "shipment_trip_count": 220},
        {"biz_month": "2026-03", "shipment_mw": 631.754, "shipment_trip_count": 846},
    ]
    return LogisticsDataQaResult(
        answer_summary="2026年1月、2月、3月运量和车次已按月返回，合计发运量为1756.327MW，合计车次为1,630。",
        result_table=LogisticsDataQaTable(columns=["biz_month", "shipment_mw", "shipment_trip_count"], rows=rows),
        calculation_logic=[
            "MW = SUM(ship_product.power * ship_product.quantity) / 1,000,000。",
            "按月趋势使用 pickup_date 对应业务月份分组。",
        ],
        data_scope={"year": 2026, "months": [1, 2, 3], "table": "2026系统数据"},
        query_plan=_plan(),
        warnings=[],
        supported=True,
        status=_status("OK", "查询成功"),
    )


def _synthetic_empty_result() -> LogisticsDataQaResult:
    """构造空结果。"""

    return LogisticsDataQaResult(
        answer_summary="查询成功，但当前条件下暂无符合条件的数据。",
        result_table=LogisticsDataQaTable(columns=["biz_month", "shipment_mw"], rows=[]),
        calculation_logic=["已按 2026 年 12 月筛选。"],
        data_scope={"year": 2026, "months": [12]},
        query_plan=_plan(filters={"year": 2026, "months": [12]}),
        warnings=[],
        supported=True,
        status=_status("EMPTY_RESULT", "暂无数据"),
    )


def _synthetic_error_result() -> LogisticsDataQaResult:
    """构造错误态结果，用于验证表达层降级不暴露内部异常。"""

    return LogisticsDataQaResult(
        answer_summary="当前查询失败，请稍后重试或联系维护人员。",
        result_table=LogisticsDataQaTable(),
        calculation_logic=[],
        data_scope={"question": "模拟接口异常"},
        query_plan=_plan(),
        warnings=[],
        supported=False,
        status=_status("EXECUTION_ERROR", "当前查询失败", success=False),
    )


def _build_real_samples() -> list[dict[str, Any]]:
    """构造真实 data-qa 展示验收样例。

    返回：
        样例列表；每条样例由真实主链路执行，表达层只做 shadow 展示编排。
    """

    return [
        {"name": "mandatory_line_chart", "question": MANDATORY_QUESTION, "expect": {"status": "OK", "display": {"line_chart", "mixed"}, "chart": "line"}},
        {"name": "a_narrative", "question": "2026年1月份总发运量是多少MW？总共发了多少车次？", "expect": {"status": "OK"}},
        {"name": "a_summary_cards", "question": "帮我汇总一下2026年1月发运量和车次", "expect": {"status": "OK", "display": {"summary_cards", "mixed"}}},
        {"name": "a_table_request", "question": "用表格列出2026年1月到3月运量综合", "expect": {"status": "OK", "display": {"table", "mixed"}}},
        {"name": "a_line_request", "question": "用折线图统计2026年1月至3月运量综合", "expect": {"status": "OK", "display": {"line_chart", "mixed"}, "chart": "line"}},
        {"name": "a_bar_request", "question": "用柱状图展示2026年1月至3月运量综合", "expect": {"status": "OK", "display": {"bar_chart", "mixed"}, "chart": "bar"}},
        {"name": "a_compare_request", "question": "对比一下2026年1月至3月运量综合", "expect": {"status": "OK"}},
        {"name": "a_monthly_total", "question": "26年1月发了多少MW，多少车？", "expect": {"status": "OK"}},
        {"name": "a_business_tone", "question": "帮我看下 26 年 1 月运量和车次", "expect": {"status": "OK"}},
        {"name": "b_no_year_real_tone", "question": "1 月份物流总出货规模和总车数是多少", "expect": {"status": "CLARIFICATION_REQUIRED", "display": {"clarification"}}},
        {"name": "b_clarification_cost_recent", "question": "最近物流成本是不是变高了？", "expect": {"status": "CLARIFICATION_REQUIRED", "display": {"clarification"}}},
        {"name": "b_clarification_worst_carrier", "question": "哪个承运商最差？", "expect": {"status": "CLARIFICATION_REQUIRED", "display": {"clarification"}}},
        {"name": "b_clarification_abnormal", "question": "华东发运有没有异常？", "expect": {"status": "CLARIFICATION_REQUIRED", "display": {"clarification"}}},
        {"name": "b_clarification_problem_tasks", "question": "哪些任务有问题？", "expect": {"status": "CLARIFICATION_REQUIRED", "display": {"clarification"}}},
        {"name": "b_followup_slot", "question": "物流费用情况怎么样？", "expect": {"status": "CLARIFICATION_REQUIRED", "display": {"clarification"}}},
        {"name": "c_forecast", "question": "预测下个月物流费用会是多少？", "expect": {"status": "UNSUPPORTED_QUESTION", "display": {"unsupported"}}},
        {"name": "c_eta", "question": "当前在途任务预计什么时候到？", "expect": {"status": "UNSUPPORTED_QUESTION", "display": {"unsupported"}}},
        {"name": "c_risk_model", "question": "设计一个在途风险评分模型", "expect": {"status": "UNSUPPORTED_QUESTION", "display": {"unsupported"}}},
        {"name": "c_open_reason", "question": "做一下物流成本上涨的原因分析", "expect": {"status": "UNSUPPORTED_QUESTION", "display": {"unsupported"}}},
        {"name": "c_discussion", "question": "物流治理原则应该怎么设计？", "expect": {"status": "UNSUPPORTED_QUESTION", "display": {"unsupported"}}},
        {"name": "a_table_direct", "question": "2026年1月发运量和车次用表格列出来", "expect": {"status": "OK", "display": {"table", "mixed"}}},
        {"name": "a_summary_direct", "question": "汇总一下2026年1月发运量", "expect": {"status": "OK", "display": {"summary_cards", "mixed", "narrative"}}},
        {"name": "a_chart_business_variant", "question": "26年一月到三月运量趋势用折线图看一下", "expect": {"status": "OK", "display": {"line_chart", "mixed"}, "chart": "line"}},
        {"name": "a_bar_business_variant", "question": "26年1月到3月运量按月份用柱状图展示", "expect": {"status": "OK", "display": {"bar_chart", "mixed"}, "chart": "bar"}},
    ]


def _build_fake_payload_cases() -> list[dict[str, Any]]:
    """构造表达层安全边界样例。

    返回：
        使用 fake client 的样例列表，用于稳定验证降级路径。
    """

    base = _synthetic_success_result()
    rows = base.result_table.rows
    line_payload = {
        "status_code": "OK",
        "display_type": "line_chart",
        "title": "2026年1月到3月发运量趋势",
        "answer": "2026年1月到3月发运量趋势已返回，所有数据来自后端 rows。",
        "highlights": ["共返回3个月份的数据。"],
        "chart_spec": {
            "chart_type": "line",
            "title": "发运量趋势",
            "x_axis": "biz_month",
            "y_axis": ["shipment_mw"],
            "series": [
                {
                    "name": "发运量",
                    "field": "shipment_mw",
                    "data": [{"x": row["biz_month"], "y": row["shipment_mw"]} for row in rows],
                }
            ],
            "unit": "MW",
            "data": rows,
        },
        "caveats": ["年份和月份是筛选条件，指标值只来自后端结果。"],
        "debug": {},
    }
    status_changed = dict(line_payload)
    status_changed["status_code"] = "UNSUPPORTED_QUESTION"
    number_changed = dict(line_payload)
    number_changed["answer"] = "2026年1月到3月发运量为9999MW。"
    invalid_chart = dict(line_payload)
    invalid_chart["chart_spec"] = {
        "chart_type": "line",
        "title": "发运量趋势",
        "x_axis": "月份",
        "y_axis": ["发运量"],
        "series": [{"name": "发运量", "field": "发运量", "data": [{"x": "2026-01", "y": 864.728}]}],
        "data": [{"月份": "2026-01", "发运量": 864.728}],
    }
    display_mismatch = dict(line_payload)
    display_mismatch["display_type"] = "narrative"
    return [
        {"name": "fake_llm_valid_line", "question": MANDATORY_QUESTION, "payload": line_payload, "result": _synthetic_success_result(), "expect_fallback": None},
        {"name": "fake_llm_status_override", "question": MANDATORY_QUESTION, "payload": status_changed, "result": _synthetic_success_result(), "expect_fallback": "llm_status_changed"},
        {"name": "fake_llm_number_hallucination", "question": MANDATORY_QUESTION, "payload": number_changed, "result": _synthetic_success_result(), "expect_fallback": "llm_text_number_hallucination"},
        {"name": "fake_llm_invalid_json", "question": MANDATORY_QUESTION, "payload": "不是 JSON", "result": _synthetic_success_result(), "expect_fallback_prefix": "llm_error"},
        {"name": "fake_llm_invalid_chart_fields", "question": MANDATORY_QUESTION, "payload": invalid_chart, "result": _synthetic_success_result(), "expect_fallback": "llm_chart_data_not_from_backend"},
        {"name": "fake_llm_display_mismatch", "question": MANDATORY_QUESTION, "payload": display_mismatch, "result": _synthetic_success_result(), "expect_fallback": "llm_display_type_ignores_user_request"},
        {"name": "fake_llm_error_fallback", "question": "2026年1月发运量", "payload": "{}", "result": _synthetic_success_result(), "expect_fallback_prefix": "llm_error", "error": True},
        {"name": "synthetic_empty_result", "question": "2026年12月发运量", "payload": None, "result": _synthetic_empty_result(), "expect_display": "empty_result"},
        {"name": "synthetic_error_result", "question": "模拟接口错误", "payload": None, "result": _synthetic_error_result(), "expect_display": "error"},
    ]


def _presentation_debug(result: LogisticsDataQaResult) -> dict[str, Any]:
    """提取 presentation debug。"""

    if not result.presentation:
        return {}
    return result.presentation.debug or {}


def _result_status(result: LogisticsDataQaResult) -> str | None:
    """提取状态码。"""

    return result.status.code if result.status else None


def _evaluate_real_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """执行真实 data-qa 样例并评估 presentation。"""

    name = sample["name"]
    question = sample["question"]
    expect = sample.get("expect", {})
    failed: list[str] = []
    try:
        # 每个并发样例使用独立 DB session，避免 SQLAlchemy session 在线程间复用。
        with SessionLocal() as db:
            db_service = LogisticsDataQaService(db=db)
            result = db_service.query(LogisticsDataQaQueryRequest(question=question), trace_id=f"live-shadow-{name}")
    except Exception as exc:  # noqa: BLE001
        return {
            "case": name,
            "question": question,
            "source": "real_data_qa",
            "passed": False,
            "failed_checks": [f"execution_error:{exc}"],
        }
    status_code = _result_status(result)
    presentation = result.presentation
    display_type = presentation.display_type if presentation else None
    if expect.get("status") and status_code != expect["status"]:
        failed.append(f"status_expected_{expect['status']}_got_{status_code}")
    if expect.get("display") and display_type not in expect["display"]:
        failed.append(f"display_expected_{sorted(expect['display'])}_got_{display_type}")
    if expect.get("chart"):
        if not presentation or not presentation.chart_spec:
            failed.append("chart_missing")
        elif presentation.chart_spec.chart_type != expect["chart"]:
            failed.append(f"chart_expected_{expect['chart']}_got_{presentation.chart_spec.chart_type}")
    if name == "mandatory_line_chart":
        failed.extend(_validate_mandatory_line_case(result))
    if not presentation:
        failed.append("presentation_missing")
    debug = _presentation_debug(result)
    return {
        "case": name,
        "question": question,
        "source": "real_data_qa",
        "status_code": status_code,
        "query_key": result.query_plan.query_key,
        "display_type": display_type,
        "chart_type": presentation.chart_spec.chart_type if presentation and presentation.chart_spec else None,
        "presentation_source": debug.get("presentation_source"),
        "fallback_reason": debug.get("fallback_reason"),
        "row_count": len(result.result_table.rows),
        "columns": result.result_table.columns,
        "passed": not failed,
        "failed_checks": failed,
    }


def _validate_mandatory_line_case(result: LogisticsDataQaResult) -> list[str]:
    """校验指定折线图代表样例。"""

    failed: list[str] = []
    if result.query_plan.query_key != "sys_mw_and_trip_count":
        failed.append("mandatory_query_key_not_sys_mw_and_trip_count")
    if result.query_plan.filters.get("months") != [1, 2, 3]:
        failed.append("mandatory_months_not_1_2_3")
    expected_months = ["2026-01", "2026-02", "2026-03"]
    row_months = [row.get("biz_month") for row in result.result_table.rows]
    if row_months != expected_months:
        failed.append(f"mandatory_monthly_rows_invalid:{row_months}")
    presentation = result.presentation
    if not presentation:
        failed.append("mandatory_presentation_missing")
        return failed
    if presentation.display_type not in {"line_chart", "mixed"}:
        failed.append(f"mandatory_display_invalid:{presentation.display_type}")
    if not presentation.chart_spec:
        failed.append("mandatory_chart_missing")
        return failed
    if presentation.chart_spec.chart_type != "line":
        failed.append(f"mandatory_chart_type_invalid:{presentation.chart_spec.chart_type}")
    if presentation.chart_spec.x_axis != "biz_month":
        failed.append(f"mandatory_x_axis_invalid:{presentation.chart_spec.x_axis}")
    backend_rows = {json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) for row in result.result_table.rows}
    chart_rows = {
        json.dumps(row, sort_keys=True, ensure_ascii=False, default=str)
        for row in (presentation.chart_spec.data or result.result_table.rows)
    }
    if chart_rows and not chart_rows.issubset(backend_rows):
        failed.append("mandatory_chart_data_not_from_backend_rows")
    return failed


def _evaluate_fake_sample(sample: dict[str, Any]) -> dict[str, Any]:
    """执行 fake client 安全边界样例。"""

    payload = sample.get("payload")
    result: LogisticsDataQaResult = sample["result"]
    if payload is None:
        service = LogisticsLlmAnswerPresentationService(enabled=True, base_url="", api_key="", model="")
    else:
        content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        service = LogisticsLlmAnswerPresentationService(
            enabled=True,
            base_url="http://fake.local/v1",
            api_key="fake-key",
            model="fake-model",
            client=_FakeClient(content, error=bool(sample.get("error"))),
            timeout_seconds=1,
            max_retries=0,
        )
    result.presentation = service.build_presentation(question=sample["question"], result=result, trace_id=f"fake-{sample['name']}")
    debug = _presentation_debug(result)
    fallback_reason = debug.get("fallback_reason")
    failed: list[str] = []
    if sample.get("expect_fallback") is not None and fallback_reason != sample["expect_fallback"]:
        failed.append(f"fallback_expected_{sample['expect_fallback']}_got_{fallback_reason}")
    if sample.get("expect_fallback_prefix") is not None and not str(fallback_reason).startswith(sample["expect_fallback_prefix"]):
        failed.append(f"fallback_prefix_expected_{sample['expect_fallback_prefix']}_got_{fallback_reason}")
    if sample.get("expect_fallback") is None and sample.get("expect_fallback_prefix") is None and sample.get("payload") is not None:
        if debug.get("presentation_source") != "llm":
            failed.append(f"llm_expected_got_{debug.get('presentation_source')}")
    if sample.get("expect_display") and result.presentation.display_type != sample["expect_display"]:
        failed.append(f"display_expected_{sample['expect_display']}_got_{result.presentation.display_type}")
    return {
        "case": sample["name"],
        "question": sample["question"],
        "source": "fake_or_synthetic",
        "status_code": _result_status(result),
        "display_type": result.presentation.display_type if result.presentation else None,
        "presentation_source": debug.get("presentation_source"),
        "fallback_reason": fallback_reason,
        "passed": not failed,
        "failed_checks": failed,
    }


def _frontend_static_check() -> dict[str, Any]:
    """静态检查前端展示能力。"""

    if not FRONTEND_PAGE.exists():
        return {"passed": False, "failed_checks": ["frontend_page_missing"]}
    text = FRONTEND_PAGE.read_text(encoding="utf-8")
    required_markers = {
        "line_chart": "buildLineChartPoints",
        "bar_chart": "buildBarChartRects",
        "table": "getDisplayTableRows",
        "summary_cards": "presentation-cards",
        "clarification": "getPresentationFollowUpQuestions",
        "unsupported": "getPresentationUnsupportedReason",
        "empty_result": "isTurnEmpty",
        "legacy_compat": "getPresentation(turn)?.table_spec",
    }
    failed = [label for label, marker in required_markers.items() if marker not in text]
    banned_main_text = ["已留痕", "收起技术详情", "需要补充条件"]
    for banned in banned_main_text:
        if banned in text:
            failed.append(f"main_technical_text_still_present:{banned}")
    return {
        "passed": not failed,
        "failed_checks": failed,
        "checked_file": str(FRONTEND_PAGE),
        "required_markers": required_markers,
    }


def _summarize(items: list[dict[str, Any]], *, frontend_check: dict[str, Any]) -> dict[str, Any]:
    """汇总报告指标。"""

    llm_config = _live_llm_config()
    fallback_reasons = Counter(str(item.get("fallback_reason") or "none") for item in items)
    display_types = Counter(str(item.get("display_type") or "none") for item in items)
    status_override_intercepts = sum(1 for item in items if item.get("fallback_reason") == "llm_status_changed")
    number_intercepts = sum(1 for item in items if item.get("fallback_reason") in {"llm_text_number_hallucination", "llm_card_number_hallucination"})
    chart_intercepts = sum(1 for item in items if item.get("fallback_reason") == "llm_chart_data_not_from_backend")
    real_sample_count = sum(1 for item in items if item.get("source") == "real_data_qa")
    return {
        "sample_total": len(items),
        "passed": sum(1 for item in items if item.get("passed")),
        "failed": sum(1 for item in items if not item.get("passed")),
        "live_llm_configured": llm_config["live_llm_configured"],
        "live_llm_model_configured": llm_config["llm_model_configured"],
        "live_llm_model_source": llm_config["resolved_model_source"],
        "live_llm_model": llm_config["resolved_model"],
        "live_llm_called": bool(llm_config["live_llm_configured"] and real_sample_count),
        "live_llm_success_count": sum(1 for item in items if item.get("presentation_source") == "llm" and item.get("source") == "real_data_qa"),
        "fallback_count": sum(1 for item in items if item.get("fallback_reason") not in {None, "none"}),
        "fallback_reason_distribution": dict(fallback_reasons),
        "display_type_distribution": dict(display_types),
        "chart_samples_passed": sum(1 for item in items if item.get("display_type") in {"line_chart", "bar_chart", "mixed"} and item.get("passed")),
        "table_samples_passed": sum(1 for item in items if item.get("display_type") == "table" and item.get("passed")),
        "clarification_samples_passed": sum(1 for item in items if item.get("status_code") == "CLARIFICATION_REQUIRED" and item.get("passed")),
        "unsupported_samples_passed": sum(1 for item in items if item.get("status_code") == "UNSUPPORTED_QUESTION" and item.get("passed")),
        "status_override_intercepts": status_override_intercepts,
        "number_hallucination_intercepts": number_intercepts,
        "invalid_chart_data_intercepts": chart_intercepts,
        "frontend_static_check_passed": frontend_check.get("passed"),
        "live_llm_effect_ready": any(item.get("presentation_source") == "llm" and item.get("source") == "real_data_qa" for item in items)
        and all(item.get("passed") for item in items),
        "trial_display_ready": all(item.get("passed") for item in items) and bool(frontend_check.get("passed")),
    }


def _write_doc(report: dict[str, Any]) -> None:
    """写入 Markdown 验收报告。"""

    summary = report["summary"]
    llm_config = report["llm_config"]
    mandatory = next((item for item in report["items"] if item["case"] == "mandatory_line_chart"), {})
    content = (
        "\n".join(
            [
                "# 物流答案表达层 live shadow 验收报告",
                "",
                "## 结论",
                f"- live LLM 是否配置：{summary['live_llm_configured']}",
                f"- 是否真实调用 live LLM：{summary['live_llm_called']}",
                f"- base_url：{llm_config.get('llm_base_url') or '未配置'}",
                f"- model：{llm_config.get('resolved_model') or '未配置'}",
                f"- model 来源：{llm_config.get('resolved_model_source')}",
                "- API Key：已脱敏，报告不输出密钥。",
                f"- 样例总数：{summary['sample_total']}",
                f"- 通过：{summary['passed']}",
                f"- 失败：{summary['failed']}",
                f"- fallback 数量：{summary['fallback_count']}",
                f"- 前端静态展示检查：{'通过' if summary['frontend_static_check_passed'] else '未通过'}",
                f"- live LLM 表达效果是否通过：{'是' if summary['live_llm_effect_ready'] else '否'}",
                f"- deterministic fallback 展示是否可用于试运行：{'是' if summary['trial_display_ready'] else '否'}",
                "",
                "## 代表性折线图样例",
                f"- 问题：{MANDATORY_QUESTION}",
                f"- 状态：{mandatory.get('status_code')}",
                f"- query_key：{mandatory.get('query_key')}",
                f"- 展示类型：{mandatory.get('display_type')}",
                f"- 图表类型：{mandatory.get('chart_type')}",
                f"- 是否通过：{mandatory.get('passed')}",
                f"- 失败项：{mandatory.get('failed_checks') or []}",
                "",
                "## fallback 原因分布",
                "```json",
                json.dumps(summary["fallback_reason_distribution"], ensure_ascii=False, indent=2),
                "```",
                "",
                "## display_type 分布",
                "```json",
                json.dumps(summary["display_type_distribution"], ensure_ascii=False, indent=2),
                "```",
                "",
                "## 安全拦截",
                f"- 状态越权拦截：{summary['status_override_intercepts']}",
                f"- 数值幻觉拦截：{summary['number_hallucination_intercepts']}",
                f"- 图表字段/数据非法拦截：{summary['invalid_chart_data_intercepts']}",
                "",
                "## 说明",
                "- 本轮仅验证答案表达层 shadow 展示效果，不改变 planner、query_key、repository、A/B/C 边界或 903 总账。",
                "- 专用模型配置优先使用 `LLM_ANSWER_PRESENTATION_MODEL`；未配置时，在表达层启用且通用 `LLM_MODEL` 存在时兜底使用通用模型。",
                "- 未配置 live LLM 或 provider 调用失败时，脚本仍执行 deterministic fallback 与安全边界验收，并输出可复跑报告。",
            ]
        )
        + "\n"
    )
    DOC_PATH.write_text(content, encoding="utf-8")
    ACCEPTANCE_DOC_PATH.write_text(
        content.replace(
            "# 物流答案表达层 live shadow 验收报告",
            "# 物流答案表达层 live LLM 验收报告",
            1,
        ),
        encoding="utf-8",
    )


def main() -> int:
    """执行答案表达层 live shadow 验收。"""

    # 显式屏蔽迁移类环境开关，确保本脚本只观察表达层，不改变题库总账。
    os.environ.setdefault("LOGISTICS_DISABLE_LEDGER_MUTATION", "1")

    items: list[dict[str, Any]] = []
    real_samples = _build_real_samples()
    # live LLM 样例可能耗时较长；并发只用于 shadow 验收，不改变业务数据和总账。
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_index = {executor.submit(_evaluate_real_sample, sample): index for index, sample in enumerate(real_samples)}
        real_results: list[dict[str, Any] | None] = [None] * len(real_samples)
        for future in as_completed(future_to_index):
            real_results[future_to_index[future]] = future.result()
        items.extend(item for item in real_results if item is not None)
    for sample in _build_fake_payload_cases():
        items.append(_evaluate_fake_sample(sample))

    frontend_check = _frontend_static_check()
    summary = _summarize(items, frontend_check=frontend_check)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "llm_config": _live_llm_config(),
        "summary": summary,
        "frontend_static_check": frontend_check,
        "items": items,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    ACCEPTANCE_REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    _write_doc(report)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["failed"] == 0 and frontend_check.get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
