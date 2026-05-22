"""评测 Graph 运行器（EvalGraphRunner）。

业务逻辑：
    遍历评测套件中的每条用例，调用 GraphRunner 获取实际回答，
    生成 EvaluationResult 并输出 JSONL 评测报告。

设计原则：
    1. 不改变现有 GraphRunner 行为。
    2. 评测结果独立可审计，每条 JSONL 行包含完整的 case+result。
    3. GraphRunner 异常不中断整体评测流程。
    4. 技术泄露检查为默认开启的安全防护。

使用示例：
    >>> from backend.app.domains.business_qa_graph.runner import BusinessQaGraphRunner
    >>> from backend.app.domains.qa_evaluation.schema import EvaluationSuite
    >>> graph_runner = BusinessQaGraphRunner(enabled=True)
    >>> suite = load_logistics_suite()  # 加载物流评测套件
    >>> runner = EvalGraphRunner(graph_runner=graph_runner, suite=suite, output_jsonl="eval.jsonl")
    >>> report = runner.run()
    >>> print(f"通过率: {report.pass_rate:.1%}")
"""

from __future__ import annotations

import json
import logging
import traceback
from pathlib import Path
from typing import Any

from backend.app.domains.business_qa_graph.schemas.request import BusinessQaGraphRequest
from backend.app.domains.business_qa_graph.schemas.response import BusinessQaGraphResponse
from backend.app.domains.qa_evaluation.schema import (
    EvaluationCase,
    EvaluationReport,
    EvaluationResult,
    EvaluationSuite,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 技术泄露检测关键词黑名单
# ---------------------------------------------------------------------------
"""技术泄露检测关键词列表：
    用户可见回答中不得包含 SQL 关键字、表名模式、字段名模式、
    query_key、planner、guardrail、schema、raw/debug、LLM 等技术细节。
"""
_LEAK_KEYWORDS: tuple[str, ...] = (
    "SELECT ",
    "FROM ",
    "WHERE ",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "query_key",
    "planner",
    "guardrail",
    "schema",
    "raw_response",
    "debug",
    "LLM",
    "nl2sql",
    "SQLPlan",
)


class EvalGraphRunner:
    """评测 Graph 运行器。

    遍历评测套件中的每条用例，调用 GraphRunner 获取实际回答，
    生成 EvaluationResult 并输出 JSONL 评测报告。

    参数：
        graph_runner: GraphRunner 可调用对象，接受 BusinessQaGraphRequest 返回 BusinessQaGraphResponse。
        suite: 评测套件，包含目标业务域和多条 EvaluationCase。
        output_jsonl: 可选的 JSONL 输出路径，用于持久化评测结果。
        enable_leak_check: 是否启用技术泄露检查，默认 True。

    返回：
        调用 run() 后返回 EvaluationReport，包含全部用例的评测结果和通过率统计。
    """

    def __init__(
        self,
        *,
        graph_runner: Any,
        suite: EvaluationSuite,
        output_jsonl: str | None = None,
        enable_leak_check: bool = True,
    ) -> None:
        """初始化评测运行器。

        参数：
            graph_runner: 已配置的 GraphRunner 实例（或兼容的 callable）。
            suite: 包含多条的评测套件。
            output_jsonl: JSONL 输出路径，可选。
            enable_leak_check: 技术泄露检查开关。
        """
        self._graph_runner = graph_runner
        self._suite = suite
        self._output_jsonl = output_jsonl
        self._enable_leak_check = enable_leak_check

    # -----------------------------------------------------------------------
    # 公共方法
    # -----------------------------------------------------------------------

    def run(self) -> EvaluationReport:
        """执行全量评测，遍历套件中每条 case。

        参数：无。
        返回：EvaluationReport，包含全部评测结果和通过率统计。
        业务逻辑：
            1. 遍历 suite.cases。
            2. 对每条 case 构造 BusinessQaGraphRequest。
            3. 调用 graph_runner.run() 获取回答。
            4. 生成 EvaluationResult。
            5. 汇总为 EvaluationReport。
            6. 若指定 output_jsonl，写入 JSONL 文件。
            7. 若 graph_runner 抛异常，捕获并记录 error 结果。
        """
        results: list[EvaluationResult] = []
        passed_count = 0
        failed_count = 0

        for case in self._suite.cases:
            try:
                request = BusinessQaGraphRequest(
                    question=case.question,
                    domain_hint=case.domain,
                )
                response = self._graph_runner.run(request)
                result = self._evaluate_case(case, response)
            except Exception as exc:
                # 异常兜底：记录 error 结果，不中断评测流程
                logger.error(
                    "评测用例执行异常 case_id=%s question=%s error=%s",
                    case.case_id,
                    case.question[:60],
                    exc,
                )
                result = self._error_result(
                    case=case,
                    exc=exc,
                )

            results.append(result)
            if result.matched_status:
                passed_count += 1
            else:
                failed_count += 1

        # 构造评测报告
        report = EvaluationReport(
            suite_name=self._suite.name,
            domain=self._suite.domain,
            total_cases=len(results),
            passed_cases=passed_count,
            failed_cases=failed_count,
            results=results,
        )

        # 执行一致性分级（fail/pass/warning）
        report.evaluate_consistency()

        # 输出 JSONL（如果指定）—— 写入失败不中断评测
        if self._output_jsonl:
            try:
                self._write_jsonl(report, self._output_jsonl)
            except Exception as exc:
                logger.error(
                    "JSONL 写入失败 path=%s error=%s",
                    self._output_jsonl,
                    exc,
                )

        return report

    # -----------------------------------------------------------------------
    # 单条评测逻辑
    # -----------------------------------------------------------------------

    def _evaluate_case(
        self,
        case: EvaluationCase,
        response: BusinessQaGraphResponse,
    ) -> EvaluationResult:
        """评估单条 case 的实际回答。

        参数：
            case: 评测用例，包含预期状态、可选的预期文本和行数。
            response: GraphRunner 返回的实际回答。
        返回：
            EvaluationResult，包含匹配结果、文本相似度、泄露检查等。
        业务逻辑：
            1. 提取实际状态（success/clarification/unsupported/error）。
            2. 与预期状态对比，记录 matched_status。
            3. 对比预期行数（如果 case 指定了 expected_row_count）。
            4. 对比预期文本（如果 case 指定了 expected_text）。
            5. 技术泄露检查（默认开启）。
            6. 生成差异说明。
        """
        actual_status = self._map_response_status(response)
        actual_row_count = self._extract_row_count(response)
        actual_answer = self._extract_answer_summary(response)

        # 状态匹配判断
        matched_status = actual_status == case.expected_status

        # 行数匹配判断
        key_numbers_match: bool | None = None
        if case.expected_row_count is not None:
            key_numbers_match = actual_row_count == case.expected_row_count

        # 文本相似度计算
        text_similarity: float | None = None
        if case.expected_text is not None and actual_answer is not None:
            text_similarity = self._compute_text_similarity(
                expected=case.expected_text,
                actual=actual_answer,
            )

        # 技术泄露检查
        leak_found = False
        if self._enable_leak_check:
            leak_found = self._check_leak(response)

        # 泄露视为严重问题 → matched_status 强制 False
        if leak_found:
            matched_status = False

        # 差异说明
        mismatch_detail = self._build_mismatch_detail(
            case=case,
            matched_status=matched_status,
            key_numbers_match=key_numbers_match,
            text_similarity=text_similarity,
            leak_found=leak_found,
            actual_status=actual_status,
            expected_status=case.expected_status,
        )

        return EvaluationResult(
            case_id=case.case_id,
            matched_status=matched_status,
            key_numbers_match=key_numbers_match,
            text_similarity=text_similarity,
            leak_found=leak_found,
            actual_status=actual_status,
            actual_answer_summary=actual_answer,
            actual_row_count=actual_row_count,
            mismatch_detail=mismatch_detail,
        )

    # -----------------------------------------------------------------------
    # 内部工具方法
    # -----------------------------------------------------------------------

    @staticmethod
    def _map_response_status(response: BusinessQaGraphResponse) -> str:
        """将 Graph 响应状态映射为评测用实际状态。

        参数：
            response: GraphRunner 返回的响应。
        返回：
            评测实际状态字符串（success/clarification/unsupported/empty_result/error）。
        业务逻辑：
            - EXECUTED + execution_result 有数据 → success
            - EXECUTED + execution_result 行数=0 → empty_result
            - CLARIFY → clarification
            - UNSUPPORTED → unsupported
            - ERROR → error
            - 其他状态兜底为 error
        """
        status = response.status

        if status == "EXECUTED":
            # 区分有数据成功与空结果
            row_count = EvalGraphRunner._extract_row_count(response)
            if row_count is not None and row_count == 0:
                return "empty_result"
            return "success"

        if status == "CLARIFY":
            return "clarification"

        if status == "UNSUPPORTED":
            return "unsupported"

        if status == "ERROR":
            return "error"

        # 兜底：其他状态（RECEIVED/DOMAIN_ROUTED/PLAN_BUILT/DISABLED）视为异常
        return "error"

    @staticmethod
    def _extract_row_count(response: BusinessQaGraphResponse) -> int | None:
        """从 Graph 响应中提取实际行数。

        参数：
            response: GraphRunner 返回的响应。
        返回：
            实际行数，如果 execution_result 中无 row_count 则返回 None。
        """
        if response.execution_result and isinstance(response.execution_result, dict):
            return response.execution_result.get("row_count")
        return None

    @staticmethod
    def _extract_answer_summary(response: BusinessQaGraphResponse) -> str | None:
        """从 Graph 响应中提取回答摘要文本。

        参数：
            response: GraphRunner 返回的响应。
        返回：
            回答摘要字符串，如果无 execution_result 则返回 None。
        """
        if response.execution_result and isinstance(response.execution_result, dict):
            return response.execution_result.get("answer_summary")
        return None

    @staticmethod
    def _compute_text_similarity(*, expected: str, actual: str) -> float:
        """计算预期文本与实际回答的相似度。

        参数：
            expected: 预期的关键文本。
            actual: 实际回答摘要。
        返回：
            相似度（0.0~1.0），基于子串匹配或长度比例计算。
        业务逻辑：
            - 预期文本作为子串出现在实际回答中 → 相似度按覆盖比例计算。
            - 预期文本未出现 → 0.0。
        """
        if not expected or not actual:
            return 0.0

        # 简单子串匹配
        if expected in actual:
            # 相似度 = 预期文本长度 / 实际回答长度，上限 1.0
            return min(1.0, len(expected) / len(actual))

        return 0.0

    @staticmethod
    def _check_leak(response: BusinessQaGraphResponse) -> bool:
        """检查回答中是否存在技术泄露（SQL/表名/字段名等）。

        参数：
            response: GraphRunner 返回的响应。
        返回：
            True 表示发现技术泄露，False 表示安全。
        业务逻辑：
            遍历 execution_result 和 answer_summary 的文本，检测黑名单关键词。
        """
        # 提取所有可见文本
        texts: list[str] = []

        if response.execution_result and isinstance(response.execution_result, dict):
            answer = response.execution_result.get("answer_summary", "")
            if answer:
                texts.append(str(answer))

        combined = " ".join(texts)
        if not combined:
            return False

        # 大小写不敏感匹配
        combined_upper = combined.upper()
        for keyword in _LEAK_KEYWORDS:
            if keyword.upper() in combined_upper:
                logger.warning("技术泄露检测到关键词: %s", keyword)
                return True

        return False

    @staticmethod
    def _build_mismatch_detail(
        *,
        case: EvaluationCase,
        matched_status: bool,
        key_numbers_match: bool | None,
        text_similarity: float | None,
        leak_found: bool,
        actual_status: str,
        expected_status: str,
    ) -> str | None:
        """生成人类可读的差异说明。

        参数：
            case: 源评测用例。
            matched_status: 状态是否匹配。
            key_numbers_match: 行数是否匹配。
            text_similarity: 文本相似度。
            leak_found: 是否发现泄露。
            actual_status: 实际状态。
            expected_status: 预期状态。
        返回：
            差异说明字符串，全部匹配时返回 None。
        """
        parts: list[str] = []

        if not matched_status:
            parts.append(
                f"状态不匹配：预期 {expected_status}，实际 {actual_status}"
            )

        if key_numbers_match is False:
            parts.append(
                f"行数不匹配：预期 {case.expected_row_count} 行，实际不符"
            )

        if text_similarity is not None and text_similarity == 0.0:
            parts.append(
                f"预期文本「{case.expected_text}」未出现在回答中"
            )

        if leak_found:
            parts.append("检测到技术泄露（SQL/表名/字段名等）")

        return "；".join(parts) if parts else None

    @staticmethod
    def _error_result(
        *,
        case: EvaluationCase,
        exc: Exception,
    ) -> EvaluationResult:
        """构造异常情况下的 error 评测结果。

        参数：
            case: 出错的评测用例。
            exc: 捕获的异常对象。
        返回：
            EvaluationResult，标记为 error 状态。
        """
        # 提取异常简要信息
        exc_name = type(exc).__name__
        exc_msg = str(exc)[:200]  # 截断防止过长
        detail = f"{exc_name}: {exc_msg}"

        return EvaluationResult(
            case_id=case.case_id,
            matched_status=False,
            leak_found=False,
            actual_status="error",
            mismatch_detail=detail,
        )

    # -----------------------------------------------------------------------
    # JSONL 持久化
    # -----------------------------------------------------------------------

    @staticmethod
    def _write_jsonl(report: EvaluationReport, output_path: str) -> None:
        """将评测报告以 JSONL 格式写入文件。

        参数：
            report: 评测报告，包含 results 列表。
            output_path: 目标文件路径。
        业务逻辑：
            每条 EvaluationResult 序列化为一行 JSON，覆盖写入。
            文件以 UTF-8 编码，确保中文可读。
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            for result in report.results:
                # 使用 mode="json" 确保字段序列化正确（如 UUID → str）
                line = json.dumps(
                    result.model_dump(mode="json"),
                    ensure_ascii=False,
                )
                f.write(line + "\n")

        logger.info(
            "评测 JSONL 已写入 %s，%d 条结果",
            output_path,
            len(report.results),
        )
