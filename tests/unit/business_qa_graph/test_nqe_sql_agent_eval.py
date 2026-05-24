"""NQE 物流评测集回归验证。

本模块对物流 903 题 master ledger 做 NQE SQL Agent 链路回归，
不连接真实数据库、不修改旧链路。
"""

from __future__ import annotations

import json
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.app.domains.business_qa_graph.nqe_logistics_gray import (
    COMPARISON_NQE_BLOCKED_BY_SAFETY,
    COMPARISON_NQE_EXPLAIN_FAILED,
    COMPARISON_NQE_GRAPH_ERROR,
    COMPARISON_NQE_SUCCESS,
    run_nqe_logistics_graph,
)

MASTER_LEDGER_PATH = Path(__file__).resolve().parents[3] / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
SAMPLE_SIZE = 50  # 抽取前 N 条做聚焦评测


@dataclass
class EvalResult:
    question_id: str = ""
    question: str = ""
    nqe_status: str = ""
    domain: str = ""
    duration_ms: int = 0
    safety_status: str = ""
    explain_status: str = ""
    comparison: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "question": self.question[:100],
            "nqe_status": self.nqe_status,
            "domain": self.domain,
            "duration_ms": self.duration_ms,
            "safety_status": self.safety_status,
            "explain_status": self.explain_status,
            "comparison": self.comparison,
            "error": self.error,
        }


@dataclass
class EvalReport:
    total: int = 0
    passed: int = 0
    failed: int = 0
    results: list[EvalResult] = field(default_factory=list)
    failure_categories: Counter = field(default_factory=Counter)


def load_questions() -> list[dict[str, Any]]:
    with open(MASTER_LEDGER_PATH, encoding="utf-8") as f:
        ledger = json.load(f)
    items = ledger.get("items", [])
    return items[:SAMPLE_SIZE]


def run_eval(questions: list[dict[str, Any]]) -> EvalReport:
    report = EvalReport(total=len(questions))

    for item in questions:
        qid = item.get("question_id", "?")
        question = item.get("question", "")
        result = EvalResult(question_id=qid, question=question)

        start = time.monotonic()
        nqe_result = run_nqe_logistics_graph(question, f"eval-{qid}")
        result.duration_ms = int((time.monotonic() - start) * 1000)

        result.nqe_status = nqe_result.get("terminal_status", "unknown")
        result.domain = nqe_result.get("selected_domain") or ""
        result.safety_status = nqe_result.get("sql_safety_status") or ""
        result.explain_status = nqe_result.get("explain_status") or ""
        result.error = nqe_result.get("error") or ""

        # 分类
        if result.nqe_status == "completed":
            result.comparison = COMPARISON_NQE_SUCCESS
            report.passed += 1
        elif result.nqe_status == "safety_reject":
            result.comparison = COMPARISON_NQE_BLOCKED_BY_SAFETY
            report.failed += 1
            report.failure_categories["safety_blocked"] += 1
        elif result.nqe_status == "error" and result.explain_status == "fail":
            result.comparison = COMPARISON_NQE_EXPLAIN_FAILED
            report.failed += 1
            report.failure_categories["explain_failed"] += 1
        else:
            result.comparison = COMPARISON_NQE_GRAPH_ERROR
            report.failed += 1
            report.failure_categories["graph_or_unknown_error"] += 1

        report.results.append(result)

    return report


def build_report_summary(report: EvalReport) -> dict[str, Any]:
    return {
        "source": str(MASTER_LEDGER_PATH.name),
        "sample_size": report.total,
        "passed": report.passed,
        "failed": report.failed,
        "pass_rate": f"{report.passed / max(report.total, 1) * 100:.1f}%",
        "failure_categories": dict(report.failure_categories),
        "avg_duration_ms": int(sum(r.duration_ms for r in report.results) / max(len(report.results), 1)),
        "failure_samples": [r.to_dict() for r in report.results if r.comparison != COMPARISON_NQE_SUCCESS][:10],
    }


# ── 评测测试 ──


def test_eval_runs_on_sample() -> None:
    """评测应在抽取样本上运行并产生结构化报告。"""
    questions = load_questions()
    assert len(questions) > 0, "master ledger 不可为空"

    report = run_eval(questions)
    summary = build_report_summary(report)

    assert report.total == len(questions)
    assert report.passed + report.failed == report.total
    assert summary["sample_size"] == report.total
    assert "pass_rate" in summary
    assert "failure_categories" in summary
    assert len(report.results) == report.total


def test_eval_results_have_required_fields() -> None:
    """每条评测结果必须包含必要字段。"""
    questions = load_questions()
    report = run_eval(questions)

    for result in report.results:
        d = result.to_dict()
        assert "question_id" in d
        assert "question" in d
        assert "nqe_status" in d
        assert "comparison" in d
        assert "duration_ms" in d
        assert "domain" in d


def test_eval_does_not_fail_on_empty_questions() -> None:
    """空问题输入不应导致评测崩溃。"""
    report = run_eval([])
    assert report.total == 0
    assert report.passed == 0
    assert report.failed == 0
