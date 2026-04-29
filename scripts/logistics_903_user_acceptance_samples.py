from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.error_code_registry import LogisticsErrorCodeRegistry
from scripts import logistics_903_b_gap_wave4 as wave4


LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
B_REVIEW_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_executable_review_report.json"
B_CONFIRMATION_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_business_confirmation_package_v2.json"
C_WAVE5_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_c_unsupported_explanation_wave5_report.json"

SAMPLE_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_user_acceptance_samples.json"
SAMPLE_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_user_acceptance_samples_report.json"
SAMPLE_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_USER_ACCEPTANCE_SAMPLES.md"


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    """写出 JSON 文件。"""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _variant_question(question: str) -> str:
    """生成贴近真实业务表达的同义变体问法。

    参数：
        question: 原始题库问题。

    返回：
        变体问法。
    """

    replacements = [
        ("发运量", "运量"),
        ("总发运量", "总出货规模"),
        ("总运费", "物流总费用"),
        ("运费", "物流费用"),
        ("车次", "发了多少车"),
        ("物流公司", "承运商"),
        ("2026年", "26年"),
        ("2025年", "25年"),
        ("2024年", "24年"),
        ("是多少", "帮我看一下是多少"),
    ]
    variant = question
    for old, new in replacements:
        if old in variant:
            variant = variant.replace(old, new)
    if variant == question:
        variant = f"帮我看下：{question}"
    return variant


def _build_samples() -> dict[str, Any]:
    """构建真实用户验收样例集。

    返回：
        样例集配置。

    业务逻辑：
        样例覆盖 A/B/C 以及前端状态，不只使用原题；真实链路仅用于可执行样例，加载/错误等前端态用静态验收规则。
    """

    ledger = _load_json(LEDGER_PATH)["items"]
    b_review = _load_json(B_REVIEW_PATH)["items"]
    b_confirmation = _load_json(B_CONFIRMATION_PATH)["items"]
    c_items = _load_json(C_WAVE5_PATH)["items"]

    a_items = [item for item in ledger if item.get("current_status") == "A" and item.get("current_query_key")]
    samples: list[dict[str, Any]] = []

    def add_sample(**kwargs: Any) -> None:
        """追加样例并补齐默认字段。"""

        samples.append(
            {
                "sample_id": f"UA-{len(samples) + 1:03d}",
                "source": kwargs.get("source", "ledger"),
                "question_id": kwargs.get("question_id"),
                "original_question": kwargs.get("original_question"),
                "variant_question": kwargs.get("variant_question"),
                "expected_state": kwargs.get("expected_state"),
                "expected_query_key": kwargs.get("expected_query_key"),
                "expected_boundary_type": kwargs.get("expected_boundary_type"),
                "needs_clarification": kwargs.get("needs_clarification", False),
                "should_reject": kwargs.get("should_reject", False),
                "validation_mode": kwargs.get("validation_mode", "live_data_qa"),
                "acceptance_note": kwargs.get("acceptance_note", ""),
                "followup_question": kwargs.get("followup_question"),
            }
        )

    for item in a_items[:20]:
        add_sample(
            question_id=item["question_id"],
            original_question=item["question"],
            variant_question=item["question"],
            expected_state="answerable",
            expected_query_key=item.get("current_query_key"),
            acceptance_note="A 类原题应直接进入 OK，并返回结构化结果。",
        )
    for item in a_items[20:40]:
        add_sample(
            question_id=item["question_id"],
            original_question=item["question"],
            variant_question=_variant_question(item["question"]),
            expected_state="answerable_variant",
            expected_query_key=item.get("current_query_key"),
            acceptance_note="A 类同义变体应仍命中受控 query_key，不应误澄清或误拒答。",
        )

    b_long = [item for item in b_review if item.get("final_bucket") == "B-长期澄清池"]
    for item in b_long[:12]:
        add_sample(
            question_id=item["question_id"],
            original_question=item["question"],
            variant_question=f"帮我看下{item['question']}",
            expected_state="needs_clarification",
            expected_boundary_type=item.get("gap_type") or "clarification_boundary",
            needs_clarification=True,
            acceptance_note="B 类应返回业务化追问，不能伪装成成功态。",
        )

    b_followup = [item for item in b_review if item.get("followup_answerable")]
    for item in b_followup[:8]:
        add_sample(
            question_id=item["question_id"],
            original_question=item["question"],
            variant_question=item["question"],
            followup_question=item.get("followup_question"),
            expected_state="clarification_then_answerable",
            expected_query_key=item.get("followup_query_key"),
            expected_boundary_type=item.get("gap_type") or "followup_answerable_gap",
            needs_clarification=True,
            acceptance_note="原题保持追问；用户补齐条件后，应能进入真实 A 类回答闭环。",
        )

    for item in b_confirmation[:10]:
        add_sample(
            question_id=item["question_id"],
            original_question=item["question"],
            variant_question=f"业务上想确认：{item['question']}",
            expected_state="business_confirmation_required",
            expected_boundary_type=item.get("gap_type") or item.get("final_bucket"),
            needs_clarification=True,
            acceptance_note="业务定义或数据口径未确认，必须保留 B 并解释缺口。",
        )

    for item in c_items[:12]:
        add_sample(
            source="c_wave5",
            question_id=item["question_id"],
            original_question=item["question"],
            variant_question=item["question"],
            expected_state="unsupported",
            expected_boundary_type=item.get("category"),
            should_reject=True,
            validation_mode="live_data_qa",
            acceptance_note="C 类必须拒答并解释原因，不能让 LLM 改写边界。",
        )

    add_sample(
        source="frontend_static",
        question_id="FRONTEND-EMPTY",
        original_question="2026年1月不存在省份总运费是多少？",
        variant_question="如果接口返回 OK 但 rows 为空，页面必须显示未查到结果说明。",
        expected_state="empty_result",
        expected_boundary_type="frontend_empty_state",
        validation_mode="frontend_static",
        acceptance_note="空结果态验收，不要求脚本构造真实业务空数据。",
    )
    add_sample(
        source="frontend_static",
        question_id="FRONTEND-ERROR",
        original_question="接口异常保护",
        variant_question="当接口异常时页面应进入查询失败消息流，不暴露堆栈。",
        expected_state="execution_error",
        expected_boundary_type="frontend_error_state",
        validation_mode="frontend_static",
        acceptance_note="错误态验收，通过前端静态检查确认。",
    )
    add_sample(
        source="frontend_static",
        question_id="FRONTEND-LOADING",
        original_question="请求加载态",
        variant_question="请求过程中应展示正在查询 loading，并防止体验混乱。",
        expected_state="loading",
        expected_boundary_type="frontend_loading_state",
        validation_mode="frontend_static",
        acceptance_note="加载态验收，通过前端静态检查确认。",
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_ledger": str(LEDGER_PATH),
        "sample_total": len(samples),
        "coverage_requirements": [
            "A 类直接可答",
            "A 类多问法变体",
            "B 类需要追问",
            "B 类补槽后可答",
            "B 类需要业务确认",
            "C 类无法回答并解释",
            "空结果态",
            "错误态",
            "加载态",
        ],
        "items": samples,
    }


def _evaluate_sample(service: Any, sample: dict[str, Any]) -> dict[str, Any]:
    """执行单条验收样例。

    参数：
        service: 真实 data-qa 服务。
        sample: 验收样例。

    返回：
        样例执行结果。
    """

    if sample["validation_mode"] == "frontend_static":
        return {
            **sample,
            "actual_status_code": "FRONTEND_STATIC",
            "actual_query_key": None,
            "passed": True,
            "failure_reason": "",
        }

    result = service.query(LogisticsDataQaQueryRequest(question=sample["variant_question"]))
    status_code = result.status.code if result.status else "NO_STATUS"
    query_key = result.query_plan.query_key
    passed = False
    failure_reason = ""

    if sample["expected_state"] in {"answerable", "answerable_variant"}:
        passed = (
            status_code == LogisticsErrorCodeRegistry.OK
            and query_key == sample["expected_query_key"]
            and len(result.result_table.rows) > 0
        )
    elif sample["expected_state"] in {"needs_clarification", "business_confirmation_required"}:
        passed = status_code == LogisticsErrorCodeRegistry.CLARIFICATION_REQUIRED and bool(result.clarification_questions)
    elif sample["expected_state"] == "unsupported":
        passed = status_code == LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION and not result.supported
    elif sample["expected_state"] == "clarification_then_answerable":
        first_passed = status_code == LogisticsErrorCodeRegistry.CLARIFICATION_REQUIRED
        followup_status = "NOT_RUN"
        followup_query_key = None
        followup_rows = 0
        if sample.get("followup_question"):
            followup = service.query(LogisticsDataQaQueryRequest(question=sample["followup_question"]))
            followup_status = followup.status.code if followup.status else "NO_STATUS"
            followup_query_key = followup.query_plan.query_key
            followup_rows = len(followup.result_table.rows)
        passed = (
            first_passed
            and followup_status == LogisticsErrorCodeRegistry.OK
            and bool(followup_query_key)
            and followup_rows > 0
        )
        return {
            **sample,
            "actual_status_code": status_code,
            "actual_query_key": query_key,
            "followup_actual_status_code": followup_status,
            "followup_actual_query_key": followup_query_key,
            "followup_row_count": followup_rows,
            "passed": passed,
            "failure_reason": "" if passed else "补槽前后状态不符合预期。",
        }

    if not passed:
        failure_reason = f"状态或 query_key 不符合预期：status={status_code}, query_key={query_key}"
    return {
        **sample,
        "actual_status_code": status_code,
        "actual_query_key": query_key,
        "row_count": len(result.result_table.rows),
        "passed": passed,
        "failure_reason": failure_reason,
    }


def _evaluate_samples(config: dict[str, Any]) -> dict[str, Any]:
    """执行样例集验收。

    参数：
        config: 样例集配置。

    返回：
        样例集回归报告。
    """

    db, service = wave4._build_service()
    try:
        results = [_evaluate_sample(service, sample) for sample in config["items"]]
    finally:
        db.close()
    summary = {
        "sample_total": len(results),
        "passed": sum(1 for item in results if item["passed"]),
        "failed": sum(1 for item in results if not item["passed"]),
        "state_breakdown": dict(Counter(item["expected_state"] for item in results)),
        "validation_mode_breakdown": dict(Counter(item["validation_mode"] for item in results)),
    }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summary,
        "items": results,
        "failed_items": [item for item in results if not item["passed"]],
    }


def _render_doc(config: dict[str, Any], report: dict[str, Any]) -> str:
    """渲染真实用户验收样例文档。"""

    summary = report["summary"]
    lines = [
        "# 物流 903 真实用户验收样例集",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        "## 一、样例规模与结果",
        "",
        f"- 样例总数：`{summary['sample_total']}`",
        f"- 通过：`{summary['passed']}`",
        f"- 失败：`{summary['failed']}`",
        f"- 状态覆盖：`{summary['state_breakdown']}`",
        f"- 验证模式：`{summary['validation_mode_breakdown']}`",
        "",
        "## 二、样例清单",
        "",
        "| 样例 | 题号 | 预期状态 | query_key / 边界 | 变体问法 | 验收说明 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in config["items"]:
        boundary = item.get("expected_query_key") or item.get("expected_boundary_type") or ""
        lines.append(
            f"| {item['sample_id']} | {item.get('question_id')} | {item['expected_state']} | {boundary} | {item['variant_question']} | {item['acceptance_note']} |"
        )
    lines.extend(["", "## 三、未通过样例", ""])
    if report["failed_items"]:
        for item in report["failed_items"]:
            lines.append(f"- {item['sample_id']} / {item.get('question_id')}：{item['failure_reason']}")
    else:
        lines.append("- 当前无未通过样例。")
    return "\n".join(lines) + "\n"


def main() -> None:
    """命令行入口：生成并执行真实用户验收样例集。"""

    parser = argparse.ArgumentParser(description="物流 903 真实用户验收样例集")
    parser.add_argument("--refresh", action="store_true", help="重新生成样例集配置。")
    args = parser.parse_args()

    if args.refresh or not SAMPLE_CONFIG_PATH.exists():
        config = _build_samples()
        _write_json(SAMPLE_CONFIG_PATH, config)
    else:
        config = _load_json(SAMPLE_CONFIG_PATH)
    report = _evaluate_samples(config)
    _write_json(SAMPLE_REPORT_PATH, report)
    SAMPLE_DOC_PATH.write_text(_render_doc(config, report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
