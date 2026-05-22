"""统一业务问数 LangGraph 编排骨架。

本包只承载外层 orchestration 骨架；物流、计划 BOM、经营分析、NL2SQL/QueryPlanningV2/SQLPlan
等受控查询能力仍由既有领域服务负责，不能在这里绕过中间库或生成自由 SQL。
"""

from backend.app.domains.business_qa_graph.builder import build_business_qa_graph
from backend.app.domains.business_qa_graph.runner import BusinessQaGraphRunner

__all__ = ["BusinessQaGraphRunner", "build_business_qa_graph"]
