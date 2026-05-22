"""统一业务问法评测集（NQE-Eval）模块。

业务逻辑：
    本模块定义跨业务域（物流、计划BOM、功率预测）的统一评测集标准格式，
    支持问题-预期结果-评测结果-评测报告的完整生命周期。

NQE-E2 新增：EvalGraphRunner 评测运行器，遍历评测套件调用 GraphRunner。
NQE-E6 新增：ReportGenerator（报告生成）、CIGate（CI 门禁）、EvalHistory（历史对比）。
"""

from backend.app.domains.qa_evaluation.ci_gate import CIGate, GateResult
from backend.app.domains.qa_evaluation.eval_runner import EvalGraphRunner
from backend.app.domains.qa_evaluation.history import EvalHistory, HistoryComparison
from backend.app.domains.qa_evaluation.report_generator import ReportGenerator
from backend.app.domains.qa_evaluation.schema import (
    ConsistencyGrade,
    EvaluationCase,
    EvaluationReport,
    EvaluationResult,
    EvaluationSuite,
)

__all__ = [
    "CIGate",
    "ConsistencyGrade",
    "EvalGraphRunner",
    "EvalHistory",
    "EvaluationCase",
    "EvaluationSuite",
    "EvaluationResult",
    "EvaluationReport",
    "GateResult",
    "HistoryComparison",
    "ReportGenerator",
]
