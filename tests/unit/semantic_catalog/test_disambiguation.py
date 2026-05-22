"""
NQE-N3：多候选消歧统一交互 — 测试用例

测试范围：
    1. DisambiguationCandidate/Request/Response/ResolveRequest Schema 定义正确。
    2. DisambiguationService 生成业务化追问文本（中文）。
    3. DisambiguationService 根据用户选择解析到正确候选。
    4. 未知 candidate_id 抛出明确错误。
    5. 空候选列表时正确处理（不生成追问）。
    6. 现有 semantic_catalog 测试不回退。
"""
from __future__ import annotations

import pytest

from backend.app.domains.semantic_catalog.disambiguation.schema import (
    DisambiguationCandidate,
    DisambiguationRequest,
    DisambiguationResponse,
    DisambiguationResolveRequest,
    DisambiguationResolveResponse,
)
from backend.app.domains.semantic_catalog.disambiguation.service import (
    DisambiguationService,
)
from backend.app.domains.semantic_catalog.disambiguation import (
    DisambiguationError,
)


# ==================== Schema 基础测试 ====================


class TestDisambiguationCandidate:
    """DisambiguationCandidate Schema 定义测试。"""

    def test_create_candidate_minimal(self) -> None:
        """创建最小字段的消歧候选。"""
        cand = DisambiguationCandidate(
            candidate_id="carrier_顺丰物流",
            entity_type="carrier",
            entity_value="顺丰物流有限公司",
            display_label="顺丰物流有限公司",
        )
        assert cand.candidate_id == "carrier_顺丰物流"
        assert cand.entity_type == "carrier"
        assert cand.entity_value == "顺丰物流有限公司"
        assert cand.display_label == "顺丰物流有限公司"
        assert cand.description is None

    def test_create_candidate_with_description(self) -> None:
        """创建带描述的消歧候选。"""
        cand = DisambiguationCandidate(
            candidate_id="order_12345",
            entity_type="order_identity",
            entity_value="SO-2025-001",
            display_label="SO-2025-001 华为2025年光伏项目",
            description="订单号 SO-2025-001，客户华为，版本A0",
        )
        assert cand.description == "订单号 SO-2025-001，客户华为，版本A0"

    def test_create_candidate_order_identity(self) -> None:
        """订单实体候选格式正确。"""
        cand = DisambiguationCandidate(
            candidate_id="order_SO2025001",
            entity_type="order_identity",
            entity_value="SO2025001",
            display_label="SO2025001 华为2025光伏",
        )
        assert cand.entity_type == "order_identity"

    def test_create_candidate_filename(self) -> None:
        """BOM 文件名候选格式正确。"""
        cand = DisambiguationCandidate(
            candidate_id="file_GCL_2025_BOM_v2",
            entity_type="filename",
            entity_value="GCL_2025_BOM_v2.xlsx",
            display_label="GCL_2025_BOM_v2.xlsx",
        )
        assert cand.entity_type == "filename"


class TestDisambiguationRequest:
    """DisambiguationRequest Schema 定义测试。"""

    def test_create_request_valid(self) -> None:
        """构造有效的消歧请求。"""
        candidates = [
            DisambiguationCandidate(
                candidate_id="c1", entity_type="carrier",
                entity_value="顺丰", display_label="顺丰物流",
            ),
            DisambiguationCandidate(
                candidate_id="c2", entity_type="carrier",
                entity_value="德邦", display_label="德邦物流",
            ),
        ]
        req = DisambiguationRequest(
            session_id="session-001",
            question="查顺丰的运费",
            domain="logistics",
            entity_type="carrier",
            candidates=candidates,
        )
        assert req.session_id == "session-001"
        assert req.question == "查顺丰的运费"
        assert req.domain == "logistics"
        assert len(req.candidates) == 2

    def test_create_request_with_context(self) -> None:
        """带额外上下文的消歧请求。"""
        candidates = [
            DisambiguationCandidate(
                candidate_id="c1", entity_type="carrier",
                entity_value="顺丰", display_label="顺丰",
            ),
            DisambiguationCandidate(
                candidate_id="c2", entity_type="carrier",
                entity_value="德邦", display_label="德邦",
            ),
        ]
        req = DisambiguationRequest(
            session_id="s1",
            question="承运商运费",
            domain="logistics",
            entity_type="carrier",
            candidates=candidates,
            context={"user_id": "user-123", "trace_id": "trace-456"},
        )
        assert req.context == {"user_id": "user-123", "trace_id": "trace-456"}


class TestDisambiguationResponse:
    """DisambiguationResponse Schema 定义测试。"""

    def test_response_needs_selection(self) -> None:
        """构造需要用户选择的消歧响应。"""
        candidates = [
            DisambiguationCandidate(
                candidate_id="c1", entity_type="carrier",
                entity_value="顺丰", display_label="顺丰物流",
            ),
            DisambiguationCandidate(
                candidate_id="c2", entity_type="carrier",
                entity_value="德邦", display_label="德邦物流",
            ),
        ]
        resp = DisambiguationResponse(
            session_id="s1",
            status="needs_selection",
            question="查顺丰的运费",
            domain="logistics",
            entity_type="carrier",
            candidates=candidates,
            follow_up_question="找到多个匹配的承运商，请选择一个：",
        )
        assert resp.status == "needs_selection"
        assert resp.resolved_candidate is None
        assert "承运商" in resp.follow_up_question

    def test_response_resolved(self) -> None:
        """构造已消歧完成的响应。"""
        cand = DisambiguationCandidate(
            candidate_id="c1", entity_type="carrier",
            entity_value="顺丰物流有限公司", display_label="顺丰物流有限公司",
        )
        resp = DisambiguationResponse(
            session_id="s1",
            status="resolved",
            question="查顺丰的运费",
            domain="logistics",
            entity_type="carrier",
            candidates=[cand],
            follow_up_question="已选择：顺丰物流有限公司",
            resolved_candidate=cand,
        )
        assert resp.status == "resolved"
        assert resp.resolved_candidate is not None
        assert resp.resolved_candidate.candidate_id == "c1"


class TestDisambiguationResolveRequest:
    """DisambiguationResolveRequest Schema 定义测试。"""

    def test_create_resolve_request(self) -> None:
        """构造消歧确认请求。"""
        req = DisambiguationResolveRequest(
            session_id="session-001",
            selected_candidate_id="c1",
            original_question="查顺丰的运费",
        )
        assert req.session_id == "session-001"
        assert req.selected_candidate_id == "c1"
        assert req.original_question == "查顺丰的运费"

    def test_create_resolve_request_minimal(self) -> None:
        """最小字段的消歧确认请求（original_question 可选）。"""
        req = DisambiguationResolveRequest(
            session_id="s1",
            selected_candidate_id="c2",
        )
        assert req.session_id == "s1"
        assert req.selected_candidate_id == "c2"
        assert req.original_question is None


class TestDisambiguationResolveResponse:
    """DisambiguationResolveResponse Schema 定义测试。"""

    def test_create_resolve_response(self) -> None:
        """构造消歧确认响应。"""
        cand = DisambiguationCandidate(
            candidate_id="c1", entity_type="carrier",
            entity_value="顺丰物流", display_label="顺丰物流有限公司",
        )
        resp = DisambiguationResolveResponse(
            session_id="s1",
            status="resolved",
            selected=cand,
            original_question="查顺丰的运费",
        )
        assert resp.status == "resolved"
        assert resp.selected.candidate_id == "c1"
        assert resp.original_question == "查顺丰的运费"


# ==================== DisambiguationService 测试 ====================


class TestDisambiguationServiceGenerateFollowUp:
    """DisambiguationService.generate_follow_up 测试。"""

    @pytest.fixture
    def svc(self) -> DisambiguationService:
        """创建测试用的消歧服务实例。"""
        return DisambiguationService()

    @pytest.fixture
    def carrier_candidates(self) -> list[DisambiguationCandidate]:
        """承运商候选列表。"""
        return [
            DisambiguationCandidate(
                candidate_id="carrier_1",
                entity_type="carrier",
                entity_value="顺丰物流有限公司",
                display_label="顺丰物流有限公司",
            ),
            DisambiguationCandidate(
                candidate_id="carrier_2",
                entity_type="carrier",
                entity_value="德邦物流股份有限公司",
                display_label="德邦物流股份有限公司",
            ),
        ]

    @pytest.fixture
    def order_candidates(self) -> list[DisambiguationCandidate]:
        """订单候选列表。"""
        return [
            DisambiguationCandidate(
                candidate_id="order_1",
                entity_type="order_identity",
                entity_value="SO2025001",
                display_label="SO2025001 华为2025年光伏项目",
            ),
            DisambiguationCandidate(
                candidate_id="order_2",
                entity_type="order_identity",
                entity_value="SO2025002",
                display_label="SO2025002 中兴2025年光伏项目",
            ),
        ]

    def test_generate_follow_up_for_carrier(
        self, svc: DisambiguationService, carrier_candidates: list[DisambiguationCandidate]
    ) -> None:
        """承运商多候选时生成中文业务追问。"""
        follow_up = svc.generate_follow_up(
            question="查顺丰的运费",
            entity_type="carrier",
            candidates=carrier_candidates,
        )
        assert isinstance(follow_up, str)
        assert len(follow_up) > 0
        assert "承运商" in follow_up or "carrier" in follow_up.lower()

    def test_generate_follow_up_for_order(
        self, svc: DisambiguationService, order_candidates: list[DisambiguationCandidate]
    ) -> None:
        """订单多候选时生成中文业务追问。"""
        follow_up = svc.generate_follow_up(
            question="查SO2025的订单详情",
            entity_type="order_identity",
            candidates=order_candidates,
        )
        assert isinstance(follow_up, str)
        assert len(follow_up) > 0

    def test_generate_follow_up_for_customer_instance(
        self, svc: DisambiguationService
    ) -> None:
        """客户实例多候选时生成业务追问。"""
        candidates = [
            DisambiguationCandidate(
                candidate_id="cust_1",
                entity_type="customer_instance",
                entity_value="华为技术有限公司",
                display_label="华为技术有限公司",
            ),
            DisambiguationCandidate(
                candidate_id="cust_2",
                entity_type="customer_instance",
                entity_value="华为数字能源技术有限公司",
                display_label="华为数字能源技术有限公司",
            ),
        ]
        follow_up = svc.generate_follow_up(
            question="华为的订单",
            entity_type="customer_instance",
            candidates=candidates,
        )
        assert "客户" in follow_up or "华为" in follow_up

    def test_generate_follow_up_for_filename(
        self, svc: DisambiguationService
    ) -> None:
        """文件名多候选时生成业务追问。"""
        candidates = [
            DisambiguationCandidate(
                candidate_id="file_1",
                entity_type="filename",
                entity_value="GCL_2025_BOM_v2.xlsx",
                display_label="GCL_2025_BOM_v2.xlsx",
            ),
            DisambiguationCandidate(
                candidate_id="file_2",
                entity_type="filename",
                entity_value="GCL_2025_BOM_v3.xlsx",
                display_label="GCL_2025_BOM_v3.xlsx",
            ),
        ]
        follow_up = svc.generate_follow_up(
            question="查BOM文件",
            entity_type="filename",
            candidates=candidates,
        )
        assert "文件" in follow_up or "BOM" in follow_up

    def test_generate_follow_up_includes_candidate_count(
        self, svc: DisambiguationService, carrier_candidates: list[DisambiguationCandidate]
    ) -> None:
        """追问文本提及候选数量。"""
        follow_up = svc.generate_follow_up(
            question="查物流",
            entity_type="carrier",
            candidates=carrier_candidates,
        )
        # 追问应包含候选数量或选择提示
        assert "2" in follow_up or "两" in follow_up or "选择" in follow_up

    def test_generate_follow_up_unknown_entity_type(
        self, svc: DisambiguationService
    ) -> None:
        """未知实体类型时生成通用追问。"""
        candidates = [
            DisambiguationCandidate(
                candidate_id="x_1",
                entity_type="unknown_type",
                entity_value="值1",
                display_label="值1",
            ),
            DisambiguationCandidate(
                candidate_id="x_2",
                entity_type="unknown_type",
                entity_value="值2",
                display_label="值2",
            ),
        ]
        follow_up = svc.generate_follow_up(
            question="查询",
            entity_type="unknown_type",
            candidates=candidates,
        )
        assert isinstance(follow_up, str)
        assert len(follow_up) > 0

    def test_generate_follow_up_empty_candidates(
        self, svc: DisambiguationService
    ) -> None:
        """空候选列表返回空追问。"""
        follow_up = svc.generate_follow_up(
            question="查询",
            entity_type="carrier",
            candidates=[],
        )
        assert follow_up == ""


class TestDisambiguationServiceResolveSelection:
    """DisambiguationService.resolve_selection 测试。"""

    @pytest.fixture
    def svc(self) -> DisambiguationService:
        return DisambiguationService()

    @pytest.fixture
    def candidates(self) -> list[DisambiguationCandidate]:
        return [
            DisambiguationCandidate(
                candidate_id="c1",
                entity_type="carrier",
                entity_value="顺丰物流有限公司",
                display_label="顺丰物流有限公司",
            ),
            DisambiguationCandidate(
                candidate_id="c2",
                entity_type="carrier",
                entity_value="德邦物流股份有限公司",
                display_label="德邦物流股份有限公司",
            ),
            DisambiguationCandidate(
                candidate_id="c3",
                entity_type="carrier",
                entity_value="安能物流有限公司",
                display_label="安能物流有限公司",
            ),
        ]

    def test_resolve_selection_first_candidate(
        self, svc: DisambiguationService, candidates: list[DisambiguationCandidate]
    ) -> None:
        """选择第一个候选成功。"""
        result = svc.resolve_selection(candidates, "c1")
        assert result.candidate_id == "c1"
        assert result.entity_value == "顺丰物流有限公司"

    def test_resolve_selection_last_candidate(
        self, svc: DisambiguationService, candidates: list[DisambiguationCandidate]
    ) -> None:
        """选择最后一个候选成功。"""
        result = svc.resolve_selection(candidates, "c3")
        assert result.candidate_id == "c3"
        assert result.entity_value == "安能物流有限公司"

    def test_resolve_selection_unknown_id_raises(
        self, svc: DisambiguationService, candidates: list[DisambiguationCandidate]
    ) -> None:
        """选择不存在的 candidate_id 抛出 DisambiguationError。"""
        with pytest.raises(DisambiguationError, match="candidate_id"):
            svc.resolve_selection(candidates, "nonexistent")

    def test_resolve_selection_empty_candidates_raises(
        self, svc: DisambiguationService
    ) -> None:
        """空候选列表中做选择抛出错误。"""
        with pytest.raises(DisambiguationError):
            svc.resolve_selection([], "any_id")

    def test_resolve_selection_with_order_candidates(
        self, svc: DisambiguationService
    ) -> None:
        """订单候选选择成功。"""
        candidates = [
            DisambiguationCandidate(
                candidate_id="order_a",
                entity_type="order_identity",
                entity_value="SO2025001",
                display_label="SO2025001 华为2025年光伏项目",
            ),
            DisambiguationCandidate(
                candidate_id="order_b",
                entity_type="order_identity",
                entity_value="SO2025002",
                display_label="SO2025002 中兴2025年光伏项目",
            ),
        ]
        result = svc.resolve_selection(candidates, "order_b")
        assert result.candidate_id == "order_b"
        assert result.entity_type == "order_identity"


class TestDisambiguationServiceFullFlow:
    """完整消歧流程测试。"""

    @pytest.fixture
    def svc(self) -> DisambiguationService:
        return DisambiguationService()

    def test_full_flow_generate_and_resolve(self, svc: DisambiguationService) -> None:
        """完整流程：生成追问 → 用户选择 → 消歧完成。"""
        candidates = [
            DisambiguationCandidate(
                candidate_id="c_a", entity_type="carrier",
                entity_value="顺丰物流", display_label="顺丰物流有限公司",
            ),
            DisambiguationCandidate(
                candidate_id="c_b", entity_type="carrier",
                entity_value="德邦物流", display_label="德邦物流股份有限公司",
            ),
        ]

        # 第一步：生成追问
        follow_up = svc.generate_follow_up(
            question="顺丰的运费是多少",
            entity_type="carrier",
            candidates=candidates,
        )
        assert len(follow_up) > 0
        assert "选择" in follow_up or "请" in follow_up

        # 第二步：用户选择
        resolved = svc.resolve_selection(candidates, "c_a")
        assert resolved.candidate_id == "c_a"
        assert "顺丰" in resolved.display_label

        # 第三步：验证选择后候选包含原问题上下文
        assert resolved.entity_type == "carrier"


# ==================== 业务关键验收测试 ====================


class TestDisambiguationBusinessRules:
    """业务规则验收：多候选时不确定不执行查询，用户选择后正确路由。"""

    def test_multi_candidate_must_not_auto_execute(self) -> None:
        """
        多候选时不确定不执行查询——由前端根据 needs_selection 状态控流。
        
        后端只负责生成候选列表和追问，不直接路由到查询执行器。
        """
        candidates = [
            DisambiguationCandidate(
                candidate_id="c1", entity_type="carrier",
                entity_value="顺丰", display_label="顺丰物流",
            ),
            DisambiguationCandidate(
                candidate_id="c2", entity_type="carrier",
                entity_value="德邦", display_label="德邦物流",
            ),
        ]
        resp = DisambiguationResponse(
            session_id="s1",
            status="needs_selection",
            question="查顺丰的运费",
            domain="logistics",
            entity_type="carrier",
            candidates=candidates,
            follow_up_question="找到多个匹配的承运商",
        )
        # needs_selection 状态表示前端应显示候选列表供用户选择
        assert resp.status == "needs_selection"
        # 此时不应有 resolved_candidate
        assert resp.resolved_candidate is None

    def test_user_selection_leads_to_resolved_state(self) -> None:
        """用户选择后状态变为 resolved，可路由到领域服务。"""
        selected = DisambiguationCandidate(
            candidate_id="c1", entity_type="carrier",
            entity_value="顺丰物流有限公司", display_label="顺丰物流有限公司",
        )
        resp = DisambiguationResponse(
            session_id="s1",
            status="resolved",
            question="查顺丰的运费",
            domain="logistics",
            entity_type="carrier",
            candidates=[selected],
            follow_up_question="已选择：顺丰物流有限公司",
            resolved_candidate=selected,
        )
        assert resp.status == "resolved"
        assert resp.resolved_candidate is not None
        # 消歧完成后，调用方可从 resolved_candidate 获取确定的实体值
        assert resp.resolved_candidate.entity_value == "顺丰物流有限公司"


# ==================== API 请求完整性测试 ====================


class TestDisambiguationResolveRequestCandidates:
    """验证 DisambiguationResolveRequest 可携带候选列表传递给 API 端点。"""

    def test_resolve_request_with_candidates(self) -> None:
        """消歧确认请求可携带候选列表。"""
        candidates = [
            DisambiguationCandidate(
                candidate_id="c1", entity_type="carrier",
                entity_value="顺丰物流", display_label="顺丰物流有限公司",
            ),
            DisambiguationCandidate(
                candidate_id="c2", entity_type="carrier",
                entity_value="德邦物流", display_label="德邦物流股份有限公司",
            ),
        ]
        req = DisambiguationResolveRequest(
            session_id="s1",
            selected_candidate_id="c1",
            original_question="查顺丰的运费",
            candidates=candidates,
        )
        assert req.session_id == "s1"
        assert req.selected_candidate_id == "c1"
        assert len(req.candidates) == 2
        assert req.candidates[0].candidate_id == "c1"

    def test_resolve_request_without_candidates_still_valid(self) -> None:
        """不带候选列表的消歧确认请求也可构造（兼容旧调用方）。"""
        req = DisambiguationResolveRequest(
            session_id="s1",
            selected_candidate_id="c1",
        )
        assert req.candidates == []
        # 不带候选列表时 resolve 应抛 DisambiguationError
        svc = DisambiguationService()
        with pytest.raises(DisambiguationError):
            svc.resolve_selection([], "c1")

    def test_resolve_request_candidates_flow(self) -> None:
        """完整的消歧确认请求流程：携带候选 + 服务层解析。"""
        candidates = [
            DisambiguationCandidate(
                candidate_id="c_a", entity_type="carrier",
                entity_value="顺丰物流", display_label="顺丰物流有限公司",
            ),
            DisambiguationCandidate(
                candidate_id="c_b", entity_type="carrier",
                entity_value="德邦物流", display_label="德邦物流股份有限公司",
            ),
        ]
        req = DisambiguationResolveRequest(
            session_id="s1",
            selected_candidate_id="c_a",
            original_question="查顺丰运费",
            candidates=candidates,
        )
        svc = DisambiguationService()
        resolved = svc.resolve_selection(req.candidates, req.selected_candidate_id)
        assert resolved.candidate_id == "c_a"
        assert "顺丰" in resolved.display_label
