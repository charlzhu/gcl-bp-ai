"""business_qa_graph 节点集合。"""

from backend.app.domains.business_qa_graph.nodes.clarify_node import clarify_node
# NQE-S2 新增：复合问题分解节点（在 question_understanding 之后，plan_validate 之前）
from backend.app.domains.business_qa_graph.nodes.decomposition_node import decomposition_node
from backend.app.domains.business_qa_graph.nodes.domain_route_node import domain_route_node
from backend.app.domains.business_qa_graph.nodes.error_node import error_node
from backend.app.domains.business_qa_graph.nodes.execute_node import execute_node
from backend.app.domains.business_qa_graph.nodes.plan_build_node import plan_build_node
from backend.app.domains.business_qa_graph.nodes.plan_validate_node import plan_validate_node
# NQE-S2 新增：子结果合并展示节点（在 execute 之后，END 之前）
from backend.app.domains.business_qa_graph.nodes.presentation_node import presentation_node
from backend.app.domains.business_qa_graph.nodes.question_understanding_node import question_understanding_node
from backend.app.domains.business_qa_graph.nodes.receive_node import receive_node
from backend.app.domains.business_qa_graph.nodes.unsupported_node import unsupported_node

__all__ = [
    "receive_node",
    "domain_route_node",
    "question_understanding_node",
    "decomposition_node",
    "plan_build_node",
    "plan_validate_node",
    "clarify_node",
    "unsupported_node",
    "error_node",
    "execute_node",
    "presentation_node",
]
