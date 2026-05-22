"""LQG-8 focused tests：统一业务问数流式接口。

测试覆盖：
1. BusinessQaStreamRequest schema 校验
2. 统一流式端点路由逻辑
3. 流式事件序列与 stage 常量
4. 旧接口兼容性（不破坏现有 logistics/plan_bom 独立端点）
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from backend.app.schemas.business_qa import (
    UNIFIED_STREAM_STAGES,
    BusinessQaStreamRequest,
)


# ---- Schema 校验测试 ----


class TestBusinessQaStreamRequest:
    """BusinessQaStreamRequest 请求体验证。"""

    def test_valid_request_with_auto_hint(self) -> None:
        """默认 domain_hint 为 auto 时正常通过。"""
        req = BusinessQaStreamRequest(question="2023年物流运费最高的承运商是哪些")
        assert req.question == "2023年物流运费最高的承运商是哪些"
        assert req.domain_hint == "auto"

    def test_valid_request_with_logistics_hint(self) -> None:
        """显式 logistics domain_hint 正常通过。"""
        req = BusinessQaStreamRequest(question="物流车次统计", domain_hint="logistics")
        assert req.domain_hint == "logistics"

    def test_valid_request_with_plan_bom_hint(self) -> None:
        """显式 plan_bom domain_hint 正常通过。"""
        req = BusinessQaStreamRequest(question="BOM评审号查询", domain_hint="plan_bom")
        assert req.domain_hint == "plan_bom"

    def test_empty_question_raises_validation_error(self) -> None:
        """空问题触发校验错误。"""
        with pytest.raises(ValueError, match="question must not be blank"):
            BusinessQaStreamRequest(question="   ")

    def test_question_whitespace_trimmed(self) -> None:
        """问题首尾空白自动去除。"""
        req = BusinessQaStreamRequest(question="  2023年物流运费  ")
        assert req.question == "2023年物流运费"

    def test_extra_fields_forbidden(self) -> None:
        """不允许额外字段。"""
        with pytest.raises(ValueError):
            BusinessQaStreamRequest(question="test", unknown_field="value")


# ---- 流式事件 stage 常量测试 ----


class TestUnifiedStreamStages:
    """UNIFIED_STREAM_STAGES 常量。"""

    def test_stages_include_all_required(self) -> None:
        """所有必要 stage 都存在。"""
        assert "received" in UNIFIED_STREAM_STAGES
        assert "understanding" in UNIFIED_STREAM_STAGES
        assert "plan_ready" in UNIFIED_STREAM_STAGES
        assert "deterministic_result_ready" in UNIFIED_STREAM_STAGES
        assert "answer_streaming" in UNIFIED_STREAM_STAGES
        assert "done" in UNIFIED_STREAM_STAGES
        assert "error" in UNIFIED_STREAM_STAGES

    def test_stage_order_is_stable(self) -> None:
        """stage 顺序稳定。"""
        assert UNIFIED_STREAM_STAGES == (
            "received",
            "understanding",
            "plan_ready",
            "deterministic_result_ready",
            "answer_streaming",
            "done",
            "error",
        )


# ---- 领域路由测试 ----


class TestDomainRouting:
    """统一端点领域路由逻辑（使用 BusinessQaDomainRegistry）。"""

    @pytest.fixture
    def registry(self) -> Any:
        from backend.app.domains.business_qa_graph.domain_registry import BusinessQaDomainRegistry
        return BusinessQaDomainRegistry.default()

    def test_logistics_question_routes_to_logistics(self, registry: Any) -> None:
        """物流问题正确路由到 logistics 域。"""
        result = registry.route("2023年物流运费统计")
        assert result.status == "ROUTED"
        assert result.domain == "logistics"

    def test_bom_question_routes_to_plan_bom(self, registry: Any) -> None:
        """BOM 问题正确路由到 plan_bom 域。"""
        result = registry.route("BOM评审号12345的玻璃配置")
        assert result.status == "ROUTED"
        assert result.domain == "plan_bom"

    def test_power_question_routes_to_plan_bom(self, registry: Any) -> None:
        """功率预测问题路由到 plan_bom 域（功率归属计划 BOM 子能力）。"""
        result = registry.route("615W功率预测")
        assert result.status == "ROUTED"
        assert result.domain == "plan_bom"

    def test_explicit_logistics_hint_overrides_auto(self, registry: Any) -> None:
        """显式 logistics 提示覆盖自动识别。"""
        result = registry.route("BOM配置", domain_hint="logistics")
        assert result.status == "ROUTED"
        assert result.domain == "logistics"

    def test_explicit_plan_bom_hint_overrides_auto(self, registry: Any) -> None:
        """显式 plan_bom 提示覆盖自动识别。"""
        result = registry.route("物流运费", domain_hint="plan_bom")
        assert result.status == "ROUTED"
        assert result.domain == "plan_bom"

    def test_ambiguous_question_clarifies(self, registry: Any) -> None:
        """无法识别的问题返回 CLARIFY。"""
        result = registry.route("今天的天气怎么样")
        assert result.status == "CLARIFY"

    def test_unsupported_hint_clarifies(self, registry: Any) -> None:
        """不支持的 domain_hint 返回 CLARIFY。"""
        result = registry.route("物流运费", domain_hint="business_analysis")
        assert result.status == "CLARIFY"


# ---- 旧接口兼容性测试 ----


class TestBackwardCompatibility:
    """确保旧接口不受影响。"""

    def test_logistics_stream_endpoint_still_registered(self) -> None:
        """物流旧流式端点仍可用。"""
        from backend.app.api.router import api_router
        routes = [r.path for r in api_router.routes]
        assert "/logistics/data-qa/query/stream" in routes or any(
            "/logistics/data-qa/query/stream" in getattr(r, "path", "") for r in api_router.routes
        )

    def test_plan_bom_stream_endpoint_still_registered(self) -> None:
        """计划 BOM 旧流式端点仍可用。"""
        from backend.app.api.router import api_router
        routes = [r.path for r in api_router.routes]
        assert "/plan-bom/qa/ask/stream" in routes or any(
            "/plan-bom/qa/ask/stream" in getattr(r, "path", "") for r in api_router.routes
        )

    def test_business_qa_stream_endpoint_registered(self) -> None:
        """LQG-8 统一流式端点已注册。"""
        from backend.app.api.router import api_router
        routes = [r.path for r in api_router.routes]
        assert "/business-qa/stream" in routes or any(
            "/business-qa/stream" in getattr(r, "path", "") for r in api_router.routes
        )


# ---- build_json_line_event 兼容性 ----


class TestJsonLineEvent:
    """build_json_line_event 输出格式兼容现有前端 NDJSON 解析器。"""

    def test_meta_event_format(self) -> None:
        """meta 事件为单行 JSON。"""
        from backend.app.services.business_answer_stream_service import build_json_line_event
        line = build_json_line_event("meta", {"stage": "received", "trace_id": "abc"})
        parsed = json.loads(line.strip())
        assert parsed["event"] == "meta"
        assert parsed["data"]["stage"] == "received"

    def test_delta_event_format(self) -> None:
        """delta 事件为单行 JSON，含 text 字段。"""
        from backend.app.services.business_answer_stream_service import build_json_line_event
        line = build_json_line_event("delta", {"text": "2023年物流运费总计"})
        parsed = json.loads(line.strip())
        assert parsed["event"] == "delta"
        assert parsed["data"]["text"] == "2023年物流运费总计"

    def test_done_event_format(self) -> None:
        """done 事件为单行 JSON，含 answer 和 data 字段。"""
        from backend.app.services.business_answer_stream_service import build_json_line_event
        line = build_json_line_event("done", {"answer": "结果", "data": {"rows": 5}})
        parsed = json.loads(line.strip())
        assert parsed["event"] == "done"
        assert parsed["data"]["answer"] == "结果"
        assert parsed["data"]["data"]["rows"] == 5

    def test_error_event_format(self) -> None:
        """error 事件为单行 JSON，含 message 字段。"""
        from backend.app.services.business_answer_stream_service import build_json_line_event
        line = build_json_line_event("error", {"message": "查询失败"})
        parsed = json.loads(line.strip())
        assert parsed["event"] == "error"
        assert parsed["data"]["message"] == "查询失败"


__all__ = [
    "TestBusinessQaStreamRequest",
    "TestUnifiedStreamStages",
    "TestDomainRouting",
    "TestBackwardCompatibility",
    "TestJsonLineEvent",
]
