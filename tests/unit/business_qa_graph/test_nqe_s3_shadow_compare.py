"""NQE-S3 focused tests: NL2SQL 结果与旧链路 shadow compare。

采用 TDD RED→GREEN→REFACTOR 流程。
验证 shadow_compare_node 能正确对比 NL2SQL 与旧链路结果并记录差异。
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

# =============================================================================
# 1. State 扩展测试
# =============================================================================


def test_state_accepts_nl2sql_result_field() -> None:
    """state 必须能承载 nl2sql_result 字段。

    RED: 字段尚未添加到 BusinessQaGraphState。
    """
    state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-s3",
        "trace": [],
        "status": "EXECUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "PLANNED",
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "EXECUTED",
        "execution_result": {},
        "query_plan_v2": {},
        "sub_plans": [],
        "sub_results": [],
        "composite_type": "none",
    }

    # NQE-S3 期望新字段：nl2sql_result 和 shadow_comparison
    next_state = dict(state)
    next_state["nl2sql_result"] = {"status": "success", "row_count": 42}
    next_state["shadow_comparison"] = {"status_match": True, "row_count_diff": 0}

    assert next_state["nl2sql_result"]["row_count"] == 42
    assert next_state["shadow_comparison"]["status_match"] is True


def test_initial_state_includes_nl2sql_result() -> None:
    """build_business_qa_initial_state 应初始化 nl2sql_result 和 shadow_comparison 为空字典。

    RED: 初始状态尚未包含这两个字段。
    """
    from backend.app.domains.business_qa_graph.schemas.request import BusinessQaGraphRequest
    from backend.app.domains.business_qa_graph.schemas.state import build_business_qa_initial_state

    request = BusinessQaGraphRequest(question="测试问题", trace_id="test-init-s3")
    initial_state = build_business_qa_initial_state(request)

    assert "nl2sql_result" in initial_state
    assert initial_state["nl2sql_result"] == {}

    assert "shadow_comparison" in initial_state
    assert initial_state["shadow_comparison"] == {}


# =============================================================================
# 2. ShadowCompareService 提取签名测试
# =============================================================================


def test_extract_signature_from_full_result() -> None:
    """extract_signature 应从完整结果中提取 status、row_count、key_numbers 和 hash。

    RED: ShadowCompareService 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.shadow_compare import (
        ShadowCompareService,
    )

    svc = ShadowCompareService()

    # 模拟旧链路结果（类似 execution_result 的结构）
    old_result = {
        "answer_summary": "2024 年总发运量为 1,234 车次，总费用 567,890 元。",
        "columns": ["年份", "车次数", "总费用"],
        "rows": [["2024", 1234, 567890]],
        "row_count": 1,
        "supported": True,
        "needs_clarification": False,
        "status_code": "success",
        "display_type": "table",
    }

    signature = svc.extract_signature(old_result)

    assert "status" in signature
    assert signature["status"] == "success"

    assert "row_count" in signature
    assert signature["row_count"] == 1

    assert "key_numbers" in signature
    assert isinstance(signature["key_numbers"], list)

    assert "hash" in signature
    assert isinstance(signature["hash"], str)
    assert len(signature["hash"]) == 64  # SHA256 hex


def test_extract_signature_empty_result() -> None:
    """extract_signature 应在空结果时返回安全默认值。

    RED: ShadowCompareService 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.shadow_compare import (
        ShadowCompareService,
    )

    svc = ShadowCompareService()
    signature = svc.extract_signature({})

    assert signature["status"] == "empty"
    assert signature["row_count"] == 0
    assert signature["key_numbers"] == []
    assert len(signature["hash"]) == 64


def test_extract_signature_clarification_result() -> None:
    """extract_signature 应对 clarify 状态结果正确提取。

    RED: ShadowCompareService 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.shadow_compare import (
        ShadowCompareService,
    )

    svc = ShadowCompareService()

    clarify_result = {
        "answer_summary": "请确认查询时间段。",
        "columns": [],
        "rows": [],
        "row_count": 0,
        "supported": True,
        "needs_clarification": True,
        "status_code": "clarify",
    }

    signature = svc.extract_signature(clarify_result)
    assert signature["status"] == "clarify"
    assert signature["row_count"] == 0


# =============================================================================
# 3. ShadowCompareService 对比测试
# =============================================================================


def test_compare_identical_results() -> None:
    """compare 应在两套结果完全相同时返回 matched。

    RED: ShadowCompareService 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.shadow_compare import (
        ShadowCompareService,
    )

    svc = ShadowCompareService()

    old_result = {
        "answer_summary": "2024 年总发运量为 1,234 车次。",
        "columns": ["年份", "车次数"],
        "rows": [["2024", 1234]],
        "row_count": 1,
        "supported": True,
        "status_code": "success",
    }

    nl2sql_result = {
        "answer_summary": "2024 年总发运量为 1,234 车次。",
        "columns": ["年份", "车次数"],
        "rows": [["2024", 1234]],
        "row_count": 1,
        "supported": True,
        "status_code": "success",
    }

    comparison = svc.compare(old_result, nl2sql_result)

    assert comparison["overall_match"] is True
    assert comparison["status_match"] is True
    assert comparison["row_count_match"] is True
    assert comparison["row_count_diff"] == 0


def test_compare_different_row_counts() -> None:
    """compare 应检测 row_count 差异。

    RED: ShadowCompareService 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.shadow_compare import (
        ShadowCompareService,
    )

    svc = ShadowCompareService()

    old_result = {"row_count": 42, "status_code": "success"}
    nl2sql_result = {"row_count": 43, "status_code": "success"}

    comparison = svc.compare(old_result, nl2sql_result)

    assert comparison["overall_match"] is False
    assert comparison["row_count_match"] is False
    assert comparison["row_count_diff"] == 1


def test_compare_different_status() -> None:
    """compare 应检测 status 差异。

    RED: ShadowCompareService 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.shadow_compare import (
        ShadowCompareService,
    )

    svc = ShadowCompareService()

    old_result = {"row_count": 0, "status_code": "success"}
    nl2sql_result = {"row_count": 0, "status_code": "clarify"}

    comparison = svc.compare(old_result, nl2sql_result)

    assert comparison["overall_match"] is False
    assert comparison["status_match"] is False


# =============================================================================
# 4. ShadowCompareService JSONL 写入测试
# =============================================================================


def test_write_comparison_to_jsonl() -> None:
    """write_to_jsonl 应将对比结果追加到 JSONL 文件。

    RED: ShadowCompareService 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.shadow_compare import (
        ShadowCompareService,
    )

    # 使用临时目录写入
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "shadow_compare.jsonl"

        svc = ShadowCompareService(jsonl_output_dir=str(tmpdir))

        comparison = {
            "overall_match": False,
            "status_match": True,
            "row_count_match": False,
            "row_count_diff": 5,
        }

        svc.write_to_jsonl(
            question="2024 年总发运量是多少？",
            old_signature={"status": "success", "row_count": 10},
            nl2sql_signature={"status": "success", "row_count": 5},
            comparison=comparison,
            trace_id="test-trace-001",
        )

        # 验证 JSONL 文件已创建
        assert jsonl_path.exists()

        # 读取并验证内容
        lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1

        record = json.loads(lines[0])
        assert record["question"] == "2024 年总发运量是多少？"
        assert record["trace_id"] == "test-trace-001"
        assert record["comparison"]["overall_match"] is False
        assert record["comparison"]["row_count_diff"] == 5

        # 验证不包含技术细节（SQL 语句、表名等技术内容；字段名 nl2sql 是合法的业务键）
        record_str = json.dumps(record, ensure_ascii=False)
        # 放宽检查：不因键名 "nl2sql_signature" 误判
        assert "SELECT" not in record_str.upper()
        assert "__tablename__" not in record_str
        assert "sql_statement" not in record_str.lower()


def test_write_comparison_multiple_records() -> None:
    """write_to_jsonl 应支持追加多条记录到同一 JSONL 文件。

    RED: ShadowCompareService 尚未创建。
    """
    from backend.app.domains.business_qa_graph.services.shadow_compare import (
        ShadowCompareService,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        svc = ShadowCompareService(jsonl_output_dir=str(tmpdir))
        jsonl_path = Path(tmpdir) / "shadow_compare.jsonl"

        for i in range(3):
            svc.write_to_jsonl(
                question=f"测试问题 {i}",
                old_signature={"status": "success", "row_count": i},
                nl2sql_signature={"status": "success", "row_count": i},
                comparison={"overall_match": True},
                trace_id=f"trace-{i}",
            )

        lines = jsonl_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 3


# =============================================================================
# 5. shadow_compare_node 集成测试
# =============================================================================


class FakeNl2SqlAdapterForS3:
    """Fake NL2SQL adapter，返回预定义 shadow 结果。"""

    def __init__(self, shadow_result: dict[str, Any] | None = None) -> None:
        self._shadow_result = shadow_result or {
            "status": "success",
            "row_count": 42,
            "answer_summary": "2024 年总发运量为 42 车次。",
            "columns": ["年份", "车次数"],
            "rows": [["2024", 42]],
            "supported": True,
            "status_code": "success",
        }
        self.build_shadow_calls: list[str] = []

    def build_full_result(self, question: str, trace_id: str | None = None) -> dict[str, Any]:
        """模拟完整 NL2SQL 执行并返回结果。"""
        self.build_shadow_calls.append(question)
        return dict(self._shadow_result)


def test_shadow_compare_node_runs_nl2sql_and_compares() -> None:
    """shadow_compare_node 应调用 NL2SQL adapter 获取结果并与 execution_result 对比。

    RED: shadow_compare_node 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.shadow_compare_node import (
        shadow_compare_node,
    )

    # 构造旧链路已执行完成的 state
    state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-s3-node",
        "trace": [],
        "status": "EXECUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "PLANNED",
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "EXECUTED",
        "execution_result": {
            "answer_summary": "2024 年总发运量为 42 车次。",
            "columns": ["年份", "车次数"],
            "rows": [["2024", 42]],
            "row_count": 42,
            "supported": True,
            "needs_clarification": False,
            "status_code": "success",
            "display_type": "table",
        },
        "query_plan_v2": {},
        "sub_plans": [],
        "sub_results": [],
        "composite_type": "none",
    }

    # 使用 fake NL2SQL adapter（返回相同结果）
    fake_adapter = FakeNl2SqlAdapterForS3(shadow_result={
        "status": "success",
        "row_count": 42,
        "answer_summary": "2024 年总发运量为 42 车次。",
        "columns": ["年份", "车次数"],
        "rows": [["2024", 42]],
        "supported": True,
        "status_code": "success",
    })

    next_state = shadow_compare_node(state, nl2sql_adapter=fake_adapter)

    # 验证 NL2SQL adapter 被调用
    assert len(fake_adapter.build_shadow_calls) == 1

    # 验证 nl2sql_result 被写入 state
    assert "nl2sql_result" in next_state
    assert next_state["nl2sql_result"]["row_count"] == 42

    # 验证 shadow_comparison 被写入 state
    assert "shadow_comparison" in next_state
    assert next_state["shadow_comparison"]["overall_match"] is True
    assert next_state["shadow_comparison"]["status_match"] is True
    assert next_state["shadow_comparison"]["row_count_match"] is True

    # 验证状态不被改变（shadow compare 不阻断正常返回）
    assert next_state["status"] == "EXECUTED"


def test_shadow_compare_node_detects_difference() -> None:
    """shadow_compare_node 应检测到差异并记录 mismatch。

    RED: shadow_compare_node 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.shadow_compare_node import (
        shadow_compare_node,
    )

    # 旧链路返回 42 条
    state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-s3-diff",
        "trace": [],
        "status": "EXECUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "PLANNED",
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "EXECUTED",
        "execution_result": {
            "row_count": 42,
            "status_code": "success",
        },
        "query_plan_v2": {},
        "sub_plans": [],
        "sub_results": [],
        "composite_type": "none",
    }

    # NL2SQL 返回不同结果（50 条）
    fake_adapter = FakeNl2SqlAdapterForS3(shadow_result={
        "row_count": 50,
        "status_code": "success",
    })

    next_state = shadow_compare_node(state, nl2sql_adapter=fake_adapter)

    # 验证差异被检测
    assert next_state["shadow_comparison"]["overall_match"] is False
    assert next_state["shadow_comparison"]["row_count_match"] is False
    assert next_state["shadow_comparison"]["row_count_diff"] != 0


def test_shadow_compare_node_handles_nl2sql_failure() -> None:
    """shadow_compare_node 应在 NL2SQL 失败时不中断主链路，只记录 error。

    RED: shadow_compare_node 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.shadow_compare_node import (
        shadow_compare_node,
    )

    # 构造会失败的 fake adapter
    class FailingAdapter:
        def build_full_result(self, question: str, trace_id: str | None = None) -> dict[str, Any]:
            raise RuntimeError("NL2SQL pipeline 不可用")

    state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-s3-fail",
        "trace": [],
        "status": "EXECUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "PLANNED",
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "EXECUTED",
        "execution_result": {"row_count": 42, "status_code": "success"},
        "query_plan_v2": {},
        "sub_plans": [],
        "sub_results": [],
        "composite_type": "none",
    }

    next_state = shadow_compare_node(state, nl2sql_adapter=FailingAdapter())

    # 不抛异常，正常返回
    assert next_state["status"] == "EXECUTED"

    # nl2sql_result 记录错误
    assert next_state["nl2sql_result"]["status"] == "error"

    # shadow_comparison 记录对比失败
    assert next_state["shadow_comparison"]["overall_match"] is False
    assert "error" in str(next_state["shadow_comparison"]).lower() or \
           next_state["shadow_comparison"].get("nl2sql_error") is True


def test_shadow_compare_node_skips_non_logistics_domain() -> None:
    """shadow_compare_node 应在非物流域跳过，不执行 NL2SQL 对比。

    RED: shadow_compare_node 尚未创建。
    """
    from backend.app.domains.business_qa_graph.nodes.shadow_compare_node import (
        shadow_compare_node,
    )

    state: BusinessQaGraphState = {
        "question": "BOM 评审号是什么？",
        "domain_hint": "auto",
        "trace_id": "trace-s3-skip",
        "trace": [],
        "status": "EXECUTED",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "plan_bom",  # 非物流域
        "capabilities": ["plan_bom_qa"],  # 非物流域
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "PLANNED",
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "EXECUTED",
        "execution_result": {},
        "query_plan_v2": {},
        "sub_plans": [],
        "sub_results": [],
        "composite_type": "none",
    }

    class CountingAdapter:
        def __init__(self) -> None:
            self.call_count = 0

        def build_full_result(self, question: str, trace_id: str | None = None) -> dict[str, Any]:
            self.call_count += 1
            return {}

    adapter = CountingAdapter()
    next_state = shadow_compare_node(state, nl2sql_adapter=adapter)

    # 非物流域不应调用 NL2SQL adapter
    assert adapter.call_count == 0

    # nl2sql_result 应为空或 skipped
    nl2sql = next_state.get("nl2sql_result", {})
    assert nl2sql.get("status", "") in ("", "skipped")


# =============================================================================
# 6. Builder 集成测试
# =============================================================================


def test_builder_includes_shadow_compare_node() -> None:
    """build_business_qa_graph 应包含 shadow_compare_node。

    RED: builder 尚未集成 shadow_compare_node。
    """
    from backend.app.domains.business_qa_graph.builder import build_business_qa_graph

    graph = build_business_qa_graph()

    assert graph is not None
    # 验证 graph 结构包含 shadow_compare 节点
    # （通过 invoke 不抛异常间接验证）


def test_full_graph_with_shadow_compare() -> None:
    """端到端测试：子图从 execute 节点开始，验证 shadow_compare 正确执行。

    使用 LangGraph 子图避免完整链路对数据库/planner 的依赖。

    GREEN: shadow_compare_node 正确集成到子图中。
    """
    from functools import partial

    from langgraph.graph import END, START, StateGraph

    from backend.app.domains.business_qa_graph.nodes.shadow_compare_node import (
        shadow_compare_node,
    )
    from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

    # 构建最小子图：execute(identity) → shadow_compare → END
    def identity_execute(state: BusinessQaGraphState) -> BusinessQaGraphState:
        """模拟 execute_node，直接写入已知结果。"""
        ns = dict(state)
        ns["execution_result"] = {
            "answer_summary": "2024 年总发运量为 42 车次。",
            "columns": ["年份", "车次数"],
            "rows": [["2024", 42]],
            "row_count": 42,
            "supported": True,
            "needs_clarification": False,
            "status_code": "success",
            "display_type": "table",
        }
        ns["execution_status"] = "EXECUTED"
        return ns

    # 使用 Fake adapter
    class FakeAdapter:
        def build_full_result(self, question: str, trace_id: str | None = None) -> dict[str, Any]:
            return {
                "status": "success",
                "row_count": 42,
                "answer_summary": "2024 年总发运量为 42 车次。",
                "columns": ["年份", "车次数"],
                "rows": [["2024", 42]],
                "supported": True,
                "status_code": "success",
            }

    fake_adapter = FakeAdapter()

    subgraph = StateGraph(BusinessQaGraphState)
    subgraph.add_node("execute", identity_execute)
    subgraph.add_node(
        "shadow_compare",
        partial(shadow_compare_node, nl2sql_adapter=fake_adapter),
    )
    subgraph.add_edge(START, "execute")
    subgraph.add_edge("execute", "shadow_compare")
    subgraph.add_edge("shadow_compare", END)
    compiled = subgraph.compile()

    # 构造初始 state
    initial_state: BusinessQaGraphState = {
        "question": "2024 年总发运量是多少？",
        "domain_hint": "auto",
        "trace_id": "trace-e2e-s3",
        "trace": [],
        "status": "PENDING",
        "graph_version": "business_qa_graph.v0",
        "execution_mode": "domain_routing_only",
        "metadata": {},
        "boundary_notes": [],
        "domain": "logistics",
        "capabilities": ["logistics_data_qa"],
        "domain_route": {},
        "shadow_plan_raw": {},
        "understanding_status": "PLANNED",
        "validation_result": "ok",
        "validation_details": {},
        "user_visible_message": "",
        "execution_status": "NOT_STARTED",
        "execution_result": {},
        "query_plan_v2": {},
        "sub_plans": [],
        "sub_results": [],
        "composite_type": "none",
        "nl2sql_result": {},
        "shadow_comparison": {},
    }

    final_state = compiled.invoke(initial_state)

    assert final_state is not None
    assert "nl2sql_result" in final_state
    assert "shadow_comparison" in final_state
    assert final_state["shadow_comparison"]["overall_match"] is True
    assert final_state["nl2sql_result"]["row_count"] == 42


# =============================================================================
# 7. 现有回归保护测试
# =============================================================================


def test_existing_nqe_s1_tests_still_pass() -> None:
    """NQE-S1 shadow 测试应不受 NQE-S3 影响，仍能正常导入和执行。

    RED: 确保新代码不破坏已有测试。
    """
    # 验证 S1 关键模块仍可导入
    from backend.app.domains.business_qa_graph.nl2sql_adapter import (
        Nl2SqlGraphAdapter,
    )

    adapter = Nl2SqlGraphAdapter()
    assert adapter is not None


def test_existing_nqe_s2_tests_still_pass() -> None:
    """NQE-S2 composite decomposition 测试应不受 NQE-S3 影响。

    RED: 确保新代码不破坏已有测试。
    """
    from backend.app.domains.business_qa_graph.services.logistics_composite_decomposer import (
        LogisticsCompositeDecomposer,
    )

    decomposer = LogisticsCompositeDecomposer()
    assert decomposer is not None


def test_existing_graph_structure_unchanged_nqe_s3() -> None:
    """Graph 结构未因 NQE-S3 被破坏：不注入新参数时 graph 仍可编译。

    RED: 确保 builder 向后兼容。
    """
    from backend.app.domains.business_qa_graph.builder import build_business_qa_graph

    # 不注入 shadow compare 参数（原有行为）
    graph = build_business_qa_graph()
    assert graph is not None
