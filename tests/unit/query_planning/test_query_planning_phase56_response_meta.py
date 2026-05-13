from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from backend.app.domains.logistics.api.endpoints import data_qa as logistics_data_qa_endpoint
from backend.app.domains.logistics.api.endpoints.data_qa import logistics_data_qa_query
from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaPlan,
    LogisticsDataQaQueryRequest,
    LogisticsDataQaResult,
    LogisticsDataQaStatus,
    LogisticsDataQaTable,
)
from backend.app.domains.plan_bom.api.endpoints import qa as plan_bom_qa_endpoint
from backend.app.domains.plan_bom.api.endpoints.qa import ask_plan_bom
from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate, PlanBomQaRequest, PlanBomQaResponse, PlanBomQaStatus
from backend.app.domains.query_planning.services import response_meta_exposure_service


class _FakeRequest:
    """模拟 FastAPI Request，仅提供 state.trace_id。"""

    def __init__(self, trace_id: str = "trace-p56") -> None:
        self.state = SimpleNamespace(trace_id=trace_id, request_id=trace_id)


class _FakeLogisticsQaService:
    """返回固定物流结果，避免测试触发真实查询。"""

    def __init__(self, result: LogisticsDataQaResult) -> None:
        self.result = result
        self.seen_payloads: list[LogisticsDataQaQueryRequest] = []

    def query(self, payload: LogisticsDataQaQueryRequest, *, trace_id: str | None = None) -> LogisticsDataQaResult:
        self.seen_payloads.append(payload)
        self.result.history_log_id = 8801
        self.result.history_ready = True
        return self.result

    def write_error_log(self, *, question: str, trace_id: str | None, message: str) -> int:  # pragma: no cover
        raise AssertionError("测试不应进入错误日志分支")


class _FakePlanBomQaService:
    """返回固定 BOM 结果，避免测试触发真实查询。"""

    def __init__(self, response: PlanBomQaResponse) -> None:
        self.response = response
        self.seen_questions: list[str] = []

    def ask(self, question: str, *, use_llm: bool = True, trace_id: str | None = None) -> PlanBomQaResponse:
        self.seen_questions.append(question)
        return self.response

    def write_error_log(self, *, question: str, trace_id: str | None, message: str) -> int:  # pragma: no cover
        raise AssertionError("测试不应进入错误日志分支")


class _FakeBusinessAnswerStreamService:
    """流式答案表达测试替身，不触发真实 LLM。"""

    def stream_answer(
        self,
        *,
        domain: str,
        question: str,
        deterministic_payload: dict[str, Any],
        fallback_answer: str | None = None,
    ):
        yield fallback_answer or deterministic_payload.get("answer_summary") or "流式兜底答案"

    def apply_streamed_answer(
        self,
        *,
        domain: str,
        deterministic_payload: dict[str, Any],
        streamed_answer: str,
    ) -> dict[str, Any]:
        payload = deepcopy(deterministic_payload)
        payload["answer_summary"] = streamed_answer or payload.get("answer_summary")
        return payload


class _BrokenShadowSnapshotBuilder:
    """用于验证响应 meta 构建失败时 fail-soft。"""

    def build_logistics_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("broken shadow snapshot")

    def build_plan_bom_snapshot(self, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("broken shadow snapshot")


async def _collect_stream_events(streaming_response: Any) -> list[dict[str, Any]]:
    """消费 StreamingResponse 的 NDJSON 事件。"""

    chunks: list[str] = []
    async for chunk in streaming_response.body_iterator:
        chunks.append(chunk.decode("utf-8") if isinstance(chunk, bytes) else str(chunk))
    return [json.loads(line) for line in "".join(chunks).splitlines() if line]


def _done_event(events: list[dict[str, Any]]) -> dict[str, Any]:
    """提取流式响应 done 事件。"""

    for event in events:
        if event.get("event") == "done":
            return event
    raise AssertionError("streaming response missing done event")


def _logistics_result() -> LogisticsDataQaResult:
    """构造可直答的物流结果。"""

    return LogisticsDataQaResult(
        answer_summary="已统计 2025 年各承运商发运量。",
        result_table=LogisticsDataQaTable(columns=["承运商", "发运量"], rows=[{"承运商": "A", "发运量": 1}]),
        query_plan=LogisticsDataQaPlan(
            intent="aggregate",
            query_key="hist_mw_by_carrier",
            metrics=["shipment_mw"],
            dimensions=["carrier"],
            filters={"year": 2025},
        ),
        status=LogisticsDataQaStatus(code="OK", message="查询成功", success=True),
    )


def _plan_bom_response() -> PlanBomQaResponse:
    """构造可直答的 BOM 结果。"""

    return PlanBomQaResponse(
        question="订单 ABC 的玻璃是什么？",
        classification="A",
        status=PlanBomQaStatus(code="OK", message="查询成功", success=True),
        nlu=PlanBomNluCandidate(
            question="订单 ABC 的玻璃是什么？",
            intent="single_order_material_specs",
            slots={"order_id": "ABC", "material_category": ["玻璃"]},
            confidence=0.91,
            provider_mode="rule",
        ),
        answer_summary="已查询订单 ABC 的玻璃规格。",
    )


def _assert_safe_query_plan_meta(meta: dict[str, Any], *, domain: str) -> None:
    """校验可暴露 meta 只包含轻量审计摘要，不包含 raw payload 或完整 trace。"""

    assert meta["schema_version"] == "query_plan_v2.response_meta.v1"
    assert meta["domain"] == domain
    assert meta["enabled"] is True
    assert meta["shadow_only"] is True
    assert meta["llm_can_execute"] is False
    assert meta["sql_generation_allowed"] is False
    assert "strategy" in meta
    assert "comparison" in meta
    assert "risk_tags" in meta

    forbidden_keys = {
        "query_plan_v2_shadow",
        "request_payload",
        "query_result",
        "trace_events",
        "raw_result",
        "original_question",
        "question",
        "answer_summary",
    }
    assert forbidden_keys.isdisjoint(meta.keys())
    assert forbidden_keys.isdisjoint(meta["comparison"].keys())


def test_logistics_query_plan_v2_meta_is_hidden_by_default(monkeypatch) -> None:
    """默认关闭时，正式物流响应不应暴露 query_plan_v2_meta。"""

    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "local", raising=False)

    api_response = logistics_data_qa_query(
        LogisticsDataQaQueryRequest(question="2025年各承运商发运量是多少？"),
        _FakeRequest(),
        _FakeLogisticsQaService(_logistics_result()),
    )

    data = api_response.data
    assert isinstance(data, dict)
    assert "query_plan_v2_meta" not in data
    assert data["answer_summary"] == "已统计 2025 年各承运商发运量。"
    assert data["status"]["code"] == "OK"
    assert data["result_table"]["rows"] == [{"承运商": "A", "发运量": 1}]


def test_logistics_query_plan_v2_meta_can_be_exposed_when_flag_and_request_enabled(monkeypatch) -> None:
    """非生产环境中，开关和请求参数同时开启时才暴露轻量 meta。"""

    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "local", raising=False)

    api_response = logistics_data_qa_query(
        LogisticsDataQaQueryRequest(
            question="2025年各承运商发运量是多少？",
            include_query_plan_v2_meta=True,
        ),
        _FakeRequest("trace-p56-logistics"),
        _FakeLogisticsQaService(_logistics_result()),
    )

    data = api_response.data
    assert isinstance(data, dict)
    meta = data["query_plan_v2_meta"]
    _assert_safe_query_plan_meta(meta, domain="logistics")
    assert meta["trace_id"] == "trace-p56-logistics"
    assert meta["history_log_id"] == 8801
    assert meta["strategy"] == "DIRECT_RETRIEVAL"
    assert meta["comparison"]["formal_query_key"] == "hist_mw_by_carrier"
    assert meta["comparison"]["shadow_query_key"] == "hist_mw_by_carrier"
    assert meta["comparison"]["matched"] is True


def test_query_plan_v2_meta_stays_hidden_when_feature_flag_is_off(monkeypatch) -> None:
    """即使请求参数显式开启，只要 feature flag 关闭，正式响应也不能暴露 meta。"""

    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", False, raising=False)
    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "local", raising=False)

    api_response = logistics_data_qa_query(
        LogisticsDataQaQueryRequest(
            question="2025年各承运商发运量是多少？",
            include_query_plan_v2_meta=True,
        ),
        _FakeRequest("trace-p56-flag-off"),
        _FakeLogisticsQaService(_logistics_result()),
    )

    assert isinstance(api_response.data, dict)
    assert "query_plan_v2_meta" not in api_response.data


def test_query_plan_v2_meta_hides_in_production_alias(monkeypatch) -> None:
    """生产环境别名也必须 fail-closed，避免环境命名差异导致 meta 暴露。"""

    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "Production", raising=False)

    service = response_meta_exposure_service.QueryPlanningV2ResponseMetaExposureService()

    assert service.should_expose(requested=True) is False


def test_query_plan_v2_meta_build_failure_is_fail_soft(monkeypatch) -> None:
    """shadow meta 构建异常时，正式响应仍成功且不附加 meta。"""

    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "local", raising=False)
    monkeypatch.setattr(
        response_meta_exposure_service,
        "QueryPlanningV2ShadowSnapshotBuilder",
        lambda: _BrokenShadowSnapshotBuilder(),
    )

    api_response = logistics_data_qa_query(
        LogisticsDataQaQueryRequest(
            question="2025年各承运商发运量是多少？",
            include_query_plan_v2_meta=True,
        ),
        _FakeRequest("trace-p56-fail-soft"),
        _FakeLogisticsQaService(_logistics_result()),
    )

    assert isinstance(api_response.data, dict)
    assert api_response.data["answer_summary"] == "已统计 2025 年各承运商发运量。"
    assert api_response.data["status"]["code"] == "OK"
    assert "query_plan_v2_meta" not in api_response.data


def test_logistics_stream_done_payload_exposes_query_plan_v2_meta_when_enabled(monkeypatch) -> None:
    """物流流式 done payload 与同步接口保持同样的可选 meta 语义。"""

    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "local", raising=False)
    monkeypatch.setattr(logistics_data_qa_endpoint, "BusinessAnswerStreamService", _FakeBusinessAnswerStreamService)

    streaming_response = logistics_data_qa_endpoint.logistics_data_qa_query_stream(
        LogisticsDataQaQueryRequest(
            question="2025年各承运商发运量是多少？",
            include_query_plan_v2_meta=True,
        ),
        _FakeRequest("trace-p56-logistics-stream"),
        _FakeLogisticsQaService(_logistics_result()),
    )
    done = _done_event(asyncio.run(_collect_stream_events(streaming_response)))

    meta = done["data"]["data"]["query_plan_v2_meta"]
    _assert_safe_query_plan_meta(meta, domain="logistics")
    assert meta["trace_id"] == "trace-p56-logistics-stream"
    assert meta["comparison"]["matched"] is True


def test_plan_bom_stream_done_payload_hides_query_plan_v2_meta_in_prod(monkeypatch) -> None:
    """BOM 流式 done payload 在生产环境同样 fail-closed。"""

    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "prod", raising=False)
    monkeypatch.setattr(plan_bom_qa_endpoint, "BusinessAnswerStreamService", _FakeBusinessAnswerStreamService)

    streaming_response = plan_bom_qa_endpoint.ask_plan_bom_stream(
        PlanBomQaRequest(
            question="订单 ABC 的玻璃是什么？",
            include_query_plan_v2_meta=True,
        ),
        _FakeRequest("trace-p56-bom-stream-prod"),
        _FakePlanBomQaService(_plan_bom_response()),
    )
    done = _done_event(asyncio.run(_collect_stream_events(streaming_response)))

    assert "query_plan_v2_meta" not in done["data"]["data"]
    assert done["data"]["data"]["status"]["code"] == "OK"


def test_plan_bom_query_plan_v2_meta_can_be_exposed_without_raw_payload(monkeypatch) -> None:
    """BOM 响应显式开启时也只暴露安全摘要，不泄露 raw_result/trace。"""

    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "dev", raising=False)

    api_response = ask_plan_bom(
        PlanBomQaRequest(
            question="订单 ABC 的玻璃是什么？",
            include_query_plan_v2_meta=True,
            trace_id="trace-p56-bom-request",
        ),
        _FakeRequest("trace-p56-bom"),
        _FakePlanBomQaService(_plan_bom_response()),
    )

    data = api_response.data
    assert isinstance(data, dict)
    meta = data["query_plan_v2_meta"]
    _assert_safe_query_plan_meta(meta, domain="plan_bom")
    assert meta["trace_id"] == "trace-p56-bom"
    assert meta["strategy"] == "DIRECT_RETRIEVAL"
    assert meta["comparison"]["formal_query_key"] == "single_order_material_specs"
    assert data["answer_summary"] == "已查询订单 ABC 的玻璃规格。"
    assert data["status"]["code"] == "OK"


def test_query_plan_v2_meta_is_fail_closed_in_prod_even_when_requested(monkeypatch) -> None:
    """生产环境未接入正式权限模块前必须 fail-closed，不能因请求参数暴露 meta。"""

    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "prod", raising=False)

    logistics_response = logistics_data_qa_query(
        LogisticsDataQaQueryRequest(
            question="2025年各承运商发运量是多少？",
            include_query_plan_v2_meta=True,
        ),
        _FakeRequest("trace-prod-logistics"),
        _FakeLogisticsQaService(_logistics_result()),
    )
    bom_response = ask_plan_bom(
        PlanBomQaRequest(
            question="订单 ABC 的玻璃是什么？",
            include_query_plan_v2_meta=True,
        ),
        _FakeRequest("trace-prod-bom"),
        _FakePlanBomQaService(_plan_bom_response()),
    )

    assert isinstance(logistics_response.data, dict)
    assert isinstance(bom_response.data, dict)
    assert "query_plan_v2_meta" not in logistics_response.data
    assert "query_plan_v2_meta" not in bom_response.data
