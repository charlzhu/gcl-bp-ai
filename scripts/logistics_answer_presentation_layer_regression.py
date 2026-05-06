from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaPlan,
    LogisticsDataQaResult,
    LogisticsDataQaStatus,
    LogisticsDataQaTable,
)
from backend.app.domains.logistics.services.llm_answer_presentation_service import (
    LogisticsLlmAnswerPresentationService,
)


REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_answer_presentation_layer_regression_report.json"


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
    """模拟 chat.completions.create 调用。

    参数：
        content: 需要返回给表达层的 LLM 文本。
        error: 是否模拟 LLM 调用异常。
    """

    def __init__(self, content: str, *, error: bool = False) -> None:
        self.content = content
        self.error = error

    def create(self, **_: Any) -> _FakeCompletion:
        """返回模拟 completion，或抛出模拟异常。"""

        if self.error:
            raise RuntimeError("fake llm unavailable")
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
    """构造 data-qa 状态。

    参数：
        code: 状态码。
        message: 业务提示。
        success: 是否成功。

    返回：
        状态对象。
    """

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
    needs_clarification: bool = False,
    clarification_questions: list[str] | None = None,
    unsupported_reason: str | None = None,
    unsupported_suggestions: list[str] | None = None,
) -> LogisticsDataQaPlan:
    """构造受控查询计划。

    参数：
        intent: 当前意图。
        query_key: 受控 query_key。
        needs_clarification: 是否需要澄清。
        clarification_questions: 澄清问题。
        unsupported_reason: 不支持原因。
        unsupported_suggestions: 可改问方向。

    返回：
        查询计划对象。
    """

    return LogisticsDataQaPlan(
        intent=intent,
        query_key=query_key,
        metrics=["shipment_mw", "shipment_trip_count"],
        dimensions=[],
        filters={"year": 2026, "month": 1},
        group_by=[],
        sort=[],
        needs_clarification=needs_clarification,
        clarification_questions=clarification_questions or [],
        clarification_missing_slots=["time_range"] if needs_clarification else [],
        unsupported_reason=unsupported_reason,
        unsupported_suggestions=unsupported_suggestions or [],
    )


def _success_result(*, rows: list[dict[str, Any]] | None = None) -> LogisticsDataQaResult:
    """构造 A 类成功结果。

    参数：
        rows: 结构化 rows。

    返回：
        data-qa 结果。
    """

    rows = rows or [
        {"biz_month": "2026-01", "shipment_mw": 864.728, "trip_count": 564},
    ]
    return LogisticsDataQaResult(
        answer_summary="2026年1月合计发运量为864.728MW，合计车次为564。",
        result_table=LogisticsDataQaTable(columns=list(rows[0].keys()), rows=rows),
        calculation_logic=["发运量按MW统计，车次按任务车辆记录统计。"],
        data_scope={"year": 2026, "months": ["01"], "table": "2026系统数据"},
        query_plan=_plan(),
        warnings=[],
        needs_clarification=False,
        clarification_questions=[],
        supported=True,
        status=_status("OK", "查询成功"),
    )


def _monthly_total_fee_result() -> LogisticsDataQaResult:
    """构造 2026 月度总费用条形图反馈样例。

    返回：
        使用真实反馈形态的 data-qa 结果，只模拟后端 rows，不引入 mock 业务答案。
    """

    rows = [
        {"biz_month": "2026-01", "total_fee": 5731112.00, "task_count": 368, "parse_fail_count": 7, "price_missing_count": 7},
        {"biz_month": "2026-02", "total_fee": 1893970.00, "task_count": 135, "parse_fail_count": 1, "price_missing_count": 0},
        {"biz_month": "2026-03", "total_fee": 3038117.00, "task_count": 257, "parse_fail_count": 2, "price_missing_count": 0},
    ]
    return LogisticsDataQaResult(
        answer_summary="2026年1月、2月、3月总运费已按月返回，合计总运费为10,663,199.00元。",
        result_table=LogisticsDataQaTable(columns=list(rows[0].keys()), rows=rows),
        calculation_logic=["系统总运费口径沿用当前正式系统计算方式：ship_product.price × project_name 解析总车数。"],
        data_scope={"year": 2026, "months": [1, 2, 3]},
        query_plan=LogisticsDataQaPlan(
            intent="aggregate",
            query_key="sys_total_fee_by_filters",
            metrics=["total_fee"],
            dimensions=["biz_month"],
            filters={"year": 2026, "months": [1, 2, 3], "monthly_breakdown": True},
            group_by=["biz_month"],
            sort=[{"field": "biz_month", "direction": "asc"}],
        ),
        warnings=[],
        needs_clarification=False,
        clarification_questions=[],
        supported=True,
        status=_status("OK", "查询成功"),
    )


def _clarification_result() -> LogisticsDataQaResult:
    """构造 B 类澄清结果。"""

    questions = ["请补充要查询的时间范围，例如2026年1月或2025年全年。"]
    return LogisticsDataQaResult(
        answer_summary="我需要先确认时间范围，避免把不同期间的数据混在一起统计。",
        result_table=LogisticsDataQaTable(),
        calculation_logic=["缺少时间范围时不直接统计。"],
        data_scope={"question": "最近物流费用怎么样"},
        query_plan=_plan(
            intent="clarification",
            query_key=None,
            needs_clarification=True,
            clarification_questions=questions,
        ),
        warnings=[],
        needs_clarification=True,
        clarification_questions=questions,
        supported=True,
        status=_status("CLARIFICATION_REQUIRED", "需要补充条件", success=False),
    )


def _unsupported_result() -> LogisticsDataQaResult:
    """构造 C 类拒答结果。"""

    return LogisticsDataQaResult(
        answer_summary="当前不支持预测下个月物流费用。",
        result_table=LogisticsDataQaTable(),
        calculation_logic=["当前只支持已发生物流数据的结构化统计。"],
        data_scope={"question": "预测下个月物流费用"},
        query_plan=_plan(
            intent="unsupported",
            query_key=None,
            unsupported_reason="当前没有预测模型和已锁定预测口径。",
            unsupported_suggestions=["可以改问历史月份的运费合计或单位成本。"],
        ),
        warnings=["不会编造预测结果。"],
        needs_clarification=False,
        clarification_questions=[],
        supported=False,
        status=_status("UNSUPPORTED_QUESTION", "当前暂不支持", success=False),
    )


def _empty_result() -> LogisticsDataQaResult:
    """构造空结果。"""

    return LogisticsDataQaResult(
        answer_summary="查询成功，但当前条件下暂无符合条件的数据。",
        result_table=LogisticsDataQaTable(columns=["biz_month", "shipment_mw"], rows=[]),
        calculation_logic=["已按2026年12月筛选。"],
        data_scope={"year": 2026, "months": ["12"]},
        query_plan=_plan(),
        warnings=[],
        needs_clarification=False,
        clarification_questions=[],
        supported=True,
        status=_status("EMPTY_RESULT", "暂无数据", success=True),
    )


def _run_case(name: str, question: str, result: LogisticsDataQaResult, checks: list[tuple[str, bool]]) -> dict[str, Any]:
    """生成单条用例结果。

    参数：
        name: 用例名。
        question: 原问题。
        result: data-qa 结果。
        checks: 断言列表。

    返回：
        结构化用例报告。
    """

    failed = [label for label, ok in checks if not ok]
    return {
        "case": name,
        "question": question,
        "status_code": result.status.code if result.status else None,
        "display_type": result.presentation.display_type if result.presentation else None,
        "passed": not failed,
        "failed_checks": failed,
        "fallback_reason": (result.presentation.debug or {}).get("fallback_reason") if result.presentation else None,
    }


def _service(*, content: str = "{}", error: bool = False) -> LogisticsLlmAnswerPresentationService:
    """构造启用 LLM 的表达层服务。

    参数：
        content: fake LLM 返回文本。
        error: 是否模拟异常。

    返回：
        服务实例。
    """

    return LogisticsLlmAnswerPresentationService(
        enabled=True,
        base_url="http://fake.local/v1",
        api_key="fake-key",
        model="fake-model",
        client=_FakeClient(content, error=error),
        timeout_seconds=1,
        max_retries=0,
    )


def main() -> int:
    """执行答案表达层回归。

    返回：
        0 表示全部通过；1 表示存在失败。
    """

    report_items: list[dict[str, Any]] = []

    deterministic_service = LogisticsLlmAnswerPresentationService(enabled=True, base_url="", api_key="", model="")

    success = _success_result()
    success.presentation = deterministic_service.build_presentation(question="2026年1月发运量和车次", result=success)
    report_items.append(
        _run_case(
            "success_summary_cards",
            "2026年1月发运量和车次",
            success,
            [
                ("presentation_generated", success.presentation is not None),
                ("display_summary_cards", success.presentation.display_type == "summary_cards"),
                ("status_unchanged", success.status.code == "OK"),
                ("cards_generated", bool(success.presentation.cards)),
            ],
        )
    )

    clarification = _clarification_result()
    clarification.presentation = deterministic_service.build_presentation(question="最近物流费用怎么样", result=clarification)
    report_items.append(
        _run_case(
            "clarification_follow_up",
            "最近物流费用怎么样",
            clarification,
            [
                ("display_clarification", clarification.presentation.display_type == "clarification"),
                ("follow_up_generated", bool(clarification.presentation.follow_up and clarification.presentation.follow_up.questions)),
            ],
        )
    )

    unsupported = _unsupported_result()
    unsupported.presentation = deterministic_service.build_presentation(question="预测下个月物流费用", result=unsupported)
    report_items.append(
        _run_case(
            "unsupported_explanation",
            "预测下个月物流费用",
            unsupported,
            [
                ("display_unsupported", unsupported.presentation.display_type == "unsupported"),
                ("explanation_generated", bool(unsupported.presentation.unsupported_explanation)),
            ],
        )
    )

    empty = _empty_result()
    empty.presentation = deterministic_service.build_presentation(question="2026年12月发运量", result=empty)
    report_items.append(
        _run_case(
            "empty_result",
            "2026年12月发运量",
            empty,
            [("display_empty", empty.presentation.display_type == "empty_result")],
        )
    )

    trend_rows = [
        {"biz_month": "2026-01", "shipment_mw": 864.728},
        {"biz_month": "2026-02", "shipment_mw": 510.12},
        {"biz_month": "2026-03", "shipment_mw": 690.5},
    ]
    line_result = _success_result(rows=trend_rows)
    line_result.presentation = deterministic_service.build_presentation(
        question="请将2026年1月到3月运量用折线图统计出来",
        result=line_result,
    )
    report_items.append(
        _run_case(
            "line_chart_request",
            "请将2026年1月到3月运量用折线图统计出来",
            line_result,
            [
                ("display_line_chart", line_result.presentation.display_type == "line_chart"),
                ("chart_spec_generated", bool(line_result.presentation.chart_spec)),
            ],
        )
    )

    monthly_fee = _monthly_total_fee_result()
    monthly_fee.presentation = deterministic_service.build_presentation(
        question="2026 年 1-3 月每月总费用，帮我用条形图展示",
        result=monthly_fee,
    )
    monthly_fee_first_row_numbers = {
        str(monthly_fee.result_table.rows[0].get("total_fee")),
        str(monthly_fee.result_table.rows[0].get("task_count")),
        str(monthly_fee.result_table.rows[0].get("parse_fail_count")),
        str(monthly_fee.result_table.rows[0].get("price_missing_count")),
    }
    monthly_fee_card_numbers = {
        str(card.value)
        for card in monthly_fee.presentation.cards
        if str(card.value) in monthly_fee_first_row_numbers
    }
    monthly_fee_chart = monthly_fee.presentation.chart_spec
    report_items.append(
        _run_case(
            "monthly_total_fee_bar_chart_hygiene",
            "2026 年 1-3 月每月总费用，帮我用条形图展示",
            monthly_fee,
            [
                ("display_bar_chart", monthly_fee.presentation.display_type == "bar_chart"),
                ("chart_spec_generated", bool(monthly_fee_chart)),
                ("chart_type_bar", monthly_fee_chart.chart_type == "bar" if monthly_fee_chart else False),
                (
                    "primary_series_total_fee",
                    monthly_fee_chart.series[0].get("field") == "total_fee" if monthly_fee_chart and monthly_fee_chart.series else False,
                ),
                ("single_chart_metric", monthly_fee_chart.y_axis == ["total_fee"] if monthly_fee_chart else False),
                ("answer_not_repeated_in_highlights", monthly_fee.presentation.answer not in monthly_fee.presentation.highlights),
                ("cards_not_first_month_detail", not monthly_fee_card_numbers),
            ],
        )
    )

    llm_monthly_bad_payload = {
        "status_code": "OK",
        "display_type": "bar_chart",
        "title": "2026年1-3月总运费",
        "answer": monthly_fee.answer_summary,
        "highlights": [monthly_fee.answer_summary],
        "chart_spec": monthly_fee.presentation.chart_spec.model_dump(mode="json") if monthly_fee.presentation.chart_spec else {},
        "cards": [
            {"label": "总运费", "value": 5731112.00, "unit": "元"},
            {"label": "任务数", "value": 368, "unit": "次"},
        ],
        "debug": {},
    }
    llm_monthly_bad = _monthly_total_fee_result()
    llm_monthly_bad.presentation = _service(content=json.dumps(llm_monthly_bad_payload, ensure_ascii=False)).build_presentation(
        question="2026 年 1-3 月每月总费用，帮我用条形图展示",
        result=llm_monthly_bad,
    )
    report_items.append(
        _run_case(
            "llm_monthly_bar_hygiene_fallback",
            "2026 年 1-3 月每月总费用，帮我用条形图展示",
            llm_monthly_bad,
            [
                (
                    "hygiene_fallback_used",
                    llm_monthly_bad.presentation.debug.get("fallback_reason")
                    in {"llm_repeated_text", "llm_cards_from_first_row"},
                ),
                ("fallback_still_bar", llm_monthly_bad.presentation.display_type == "bar_chart"),
                (
                    "fallback_primary_series_total_fee",
                    llm_monthly_bad.presentation.chart_spec.series[0].get("field") == "total_fee"
                    if llm_monthly_bad.presentation.chart_spec and llm_monthly_bad.presentation.chart_spec.series
                    else False,
                ),
            ],
        )
    )

    llm_line_payload = {
        "status_code": "OK",
        "display_type": "line_chart",
        "title": "2026年1月到3月发运量趋势",
        "answer": "2026年1月到3月发运量趋势已返回，数据均来自后端确定性结果。",
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
                    "data": [
                        {"x": row["biz_month"], "y": row["shipment_mw"]}
                        for row in trend_rows
                    ],
                }
            ],
            "unit": "MW",
            "data": trend_rows,
        },
        "caveats": ["月份数字属于筛选条件，指标值只来自后端 rows。"],
        "debug": {},
    }
    llm_context_numbers = _success_result(rows=trend_rows)
    llm_context_numbers.presentation = _service(content=json.dumps(llm_line_payload, ensure_ascii=False)).build_presentation(
        question="请将2026年1月到3月运量用折线图统计出来",
        result=llm_context_numbers,
    )
    report_items.append(
        _run_case(
            "llm_context_date_numbers_allowed",
            "请将2026年1月到3月运量用折线图统计出来",
            llm_context_numbers,
            [
                ("llm_used", llm_context_numbers.presentation.debug.get("presentation_source") == "llm"),
                ("display_line_chart", llm_context_numbers.presentation.display_type == "line_chart"),
                ("chart_uses_backend_fields", llm_context_numbers.presentation.chart_spec.x_axis == "biz_month"),
            ],
        )
    )

    display_mismatch_payload = dict(llm_line_payload)
    display_mismatch_payload["display_type"] = "narrative"
    display_mismatch = _success_result(rows=trend_rows)
    display_mismatch.presentation = _service(content=json.dumps(display_mismatch_payload, ensure_ascii=False)).build_presentation(
        question="请将2026年1月到3月运量用折线图统计出来",
        result=display_mismatch,
    )
    report_items.append(
        _run_case(
            "llm_display_mismatch_fallback",
            "请将2026年1月到3月运量用折线图统计出来",
            display_mismatch,
            [
                (
                    "display_request_enforced",
                    display_mismatch.presentation.debug.get("fallback_reason") == "llm_display_type_ignores_user_request",
                ),
                ("fallback_line_chart", display_mismatch.presentation.display_type == "line_chart"),
            ],
        )
    )

    invalid_chart_payload = dict(llm_line_payload)
    invalid_chart_payload["chart_spec"] = {
        "chart_type": "line",
        "title": "发运量趋势",
        "x_axis": "月份",
        "y_axis": ["发运量"],
        "series": [{"name": "发运量", "field": "发运量", "data": [{"x": "2026-01", "y": 864.728}]}],
        "data": [{"月份": "2026-01", "发运量": 864.728}],
    }
    invalid_chart = _success_result(rows=trend_rows)
    invalid_chart.presentation = _service(content=json.dumps(invalid_chart_payload, ensure_ascii=False)).build_presentation(
        question="请将2026年1月到3月运量用折线图统计出来",
        result=invalid_chart,
    )
    report_items.append(
        _run_case(
            "llm_invalid_chart_field_fallback",
            "请将2026年1月到3月运量用折线图统计出来",
            invalid_chart,
            [
                ("chart_field_rejected", invalid_chart.presentation.debug.get("fallback_reason") == "llm_chart_data_not_from_backend"),
                ("fallback_line_chart", invalid_chart.presentation.display_type == "line_chart"),
            ],
        )
    )

    table_result = _success_result(rows=trend_rows)
    table_result.presentation = deterministic_service.build_presentation(
        question="用表格列出2026年1月到3月运量",
        result=table_result,
    )
    report_items.append(
        _run_case(
            "table_request",
            "用表格列出2026年1月到3月运量",
            table_result,
            [
                ("display_table", table_result.presentation.display_type == "table"),
                ("table_spec_generated", bool(table_result.presentation.table_spec and table_result.presentation.table_spec.rows)),
            ],
        )
    )

    llm_ok_payload = {
        "status_code": "OK",
        "display_type": "summary_cards",
        "title": "1月物流发运概览",
        "answer": "2026年1月合计发运量为864.728MW，合计车次为564。",
        "highlights": ["发运量864.728MW", "车次564"],
        "cards": [
            {"label": "发运量", "value": 864.728, "unit": "MW"},
            {"label": "车次", "value": 564, "unit": "次"},
        ],
        "caveats": ["发运量按MW统计。"],
        "debug": {},
    }
    llm_success = _success_result()
    llm_success.presentation = _service(content=json.dumps(llm_ok_payload, ensure_ascii=False)).build_presentation(
        question="帮我汇总2026年1月发运量和车次",
        result=llm_success,
    )
    report_items.append(
        _run_case(
            "llm_valid_payload",
            "帮我汇总2026年1月发运量和车次",
            llm_success,
            [
                ("llm_used", llm_success.presentation.debug.get("presentation_source") == "llm"),
                ("status_unchanged", llm_success.status.code == "OK"),
            ],
        )
    )

    llm_error = _success_result()
    llm_error.presentation = _service(error=True).build_presentation(question="2026年1月发运量", result=llm_error)
    report_items.append(
        _run_case(
            "llm_error_fallback",
            "2026年1月发运量",
            llm_error,
            [
                ("fallback_used", str(llm_error.presentation.debug.get("fallback_reason", "")).startswith("llm_error")),
                ("display_safe", llm_error.presentation.display_type == "summary_cards"),
            ],
        )
    )

    llm_bad_json = _success_result()
    llm_bad_json.presentation = _service(content="不是 JSON").build_presentation(question="2026年1月发运量", result=llm_bad_json)
    report_items.append(
        _run_case(
            "llm_json_parse_fallback",
            "2026年1月发运量",
            llm_bad_json,
            [
                ("fallback_used", str(llm_bad_json.presentation.debug.get("fallback_reason", "")).startswith("llm_error")),
            ],
        )
    )

    changed_status_payload = dict(llm_ok_payload)
    changed_status_payload["status_code"] = "CLARIFICATION_REQUIRED"
    changed_status = _success_result()
    changed_status.presentation = _service(content=json.dumps(changed_status_payload, ensure_ascii=False)).build_presentation(
        question="2026年1月发运量",
        result=changed_status,
    )
    report_items.append(
        _run_case(
            "llm_status_change_fallback",
            "2026年1月发运量",
            changed_status,
            [
                ("status_change_rejected", changed_status.presentation.debug.get("fallback_reason") == "llm_status_changed"),
                ("display_safe", changed_status.presentation.display_type == "summary_cards"),
            ],
        )
    )

    changed_number_payload = dict(llm_ok_payload)
    changed_number_payload["answer"] = "2026年1月发运量为9999MW。"
    changed_number = _success_result()
    changed_number.presentation = _service(content=json.dumps(changed_number_payload, ensure_ascii=False)).build_presentation(
        question="2026年1月发运量",
        result=changed_number,
    )
    report_items.append(
        _run_case(
            "llm_number_change_fallback",
            "2026年1月发运量",
            changed_number,
            [
                ("number_change_rejected", changed_number.presentation.debug.get("fallback_reason") == "llm_text_number_hallucination"),
                ("display_safe", changed_number.presentation.display_type == "summary_cards"),
            ],
        )
    )

    passed = sum(1 for item in report_items if item["passed"])
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "total": len(report_items),
            "passed": passed,
            "failed": len(report_items) - passed,
            "llm_live_called": False,
            "mode": "fake-client + deterministic fallback",
        },
        "items": report_items,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if passed == len(report_items) else 1


if __name__ == "__main__":
    raise SystemExit(main())
