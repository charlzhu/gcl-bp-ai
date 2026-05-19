from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from typing import Any

from backend.app.domains.logistics.repositories.query_repository import LogisticsQueryRepository
from backend.app.domains.plan_bom.constants import CANDIDATE_SCOPE_ORDER_IDENTITY, CORE_MATERIAL_CATEGORIES, MATERIAL_CATEGORY_LABELS
from backend.app.domains.plan_bom.models import PlanBomHeader, PlanBomMaterialLine, PlanPowerFactorOption, PlanPowerModelSheet, PlanPowerModelVersion
from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate, PlanBomQaResponse, PlanBomQaStatus, PlanBomTableSpec
from backend.app.domains.plan_bom.schemas.query import (
    PlanBomCandidate,
    PlanBomCompareQueryRequest,
    PlanBomCompareResponse,
    PlanBomCompareSideContext,
    PlanBomCompareSideRequest,
    PlanBomDetailQueryRequest,
)
from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
from backend.app.domains.plan_bom.services.nlu_center_service import PlanBomNluCenterService
from backend.app.domains.plan_bom.services.power_config_resolver_service import (
    CANDIDATE_REQUIRED_STATUS,
    NO_ACTIVE_MODEL_STATUS,
    NOT_FOUND_STATUS,
    PARTIAL_STATUS,
    RESOLVED_STATUS,
    PlanBomPowerConfigResolverService,
)
from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine, PowerPredictionError, PowerPredictionResult
from backend.app.domains.plan_bom.services.power_recommendation_service import PowerRecommendationService, PowerRecommendationResult
from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService
from backend.app.domains.query_planning.services.shadow_snapshot_builder import QueryPlanningV2ShadowSnapshotBuilder
from backend.app.services.qa_trace import QaTraceRecorder


logger = logging.getLogger(__name__)


class PlanBomQaService:
    """计划 BOM 自然语言问答主服务。

    说明：
        1. 本服务不重建查询引擎，复用既有 `PlanBomQueryService.detail/compare`；
        2. NLU 只负责受控意图和槽位抽取，订单、材料、版本都要回到 BOM 索引校验；
        3. 事实性结果只来自数据库中的 BOM 头和材料行；
        4. LLM 只允许做理解候选和表达优化，不能生成业务事实。
    """

    def __init__(
        self,
        *,
        repository: PlanBomQueryRepository,
        query_service: PlanBomQueryService,
        nlu_service: PlanBomNluCenterService,
        presentation_service: PlanBomAnswerPresentationService,
        power_config_resolver: PlanBomPowerConfigResolverService | None = None,
        power_prediction_engine: PowerPredictionEngine | None = None,
        power_recommendation_service: PowerRecommendationService | None = None,
        query_log_repository: LogisticsQueryRepository | None = None,
    ) -> None:
        """初始化 BOM QA 服务。

        参数：
            repository: BOM 查询仓储；
            query_service: 已有 detail / compare 查询服务；
            nlu_service: BOM NLU Center；
            presentation_service: BOM 答案表达层。
            power_config_resolver: M4 BOM 配置自动映射服务，未注入时按 repository 所在 DB 懒创建。
            power_prediction_engine: M3 单供应商功率预测引擎，未注入时懒创建。
            power_recommendation_service: M3 供应商推荐服务，未注入时懒创建。
            query_log_repository: 统一查询历史写入仓储，复用 sys_query_log。

        返回：
            无返回值。
        """

        self.repository = repository
        self.query_service = query_service
        self.nlu_service = nlu_service
        self.presentation_service = presentation_service
        self.power_config_resolver = power_config_resolver or PlanBomPowerConfigResolverService(repository.db, repository=repository)
        self.power_prediction_engine = power_prediction_engine or PowerPredictionEngine(repository.db)
        self.power_recommendation_service = power_recommendation_service or PowerRecommendationService(
            repository.db,
            engine=self.power_prediction_engine,
        )
        self.query_log_repository = query_log_repository or LogisticsQueryRepository()
        self.query_plan_shadow_builder = QueryPlanningV2ShadowSnapshotBuilder()

    def ask(self, question: str, *, use_llm: bool = True, trace_id: str | None = None) -> PlanBomQaResponse:
        """回答计划 BOM 自然语言问题。

        参数：
            question: 用户自然语言问题；
            use_llm: 是否允许 LLM 候选理解；
            trace_id: 请求追踪号，当前仅写入 presentation debug。

        返回：
            统一 BOM QA 响应。
        """

        trace_recorder = QaTraceRecorder(
            domain="plan_bom",
            trace_id=trace_id,
            question=question,
            logger_name=__name__,
        )
        trace_recorder.add(
            "input_received",
            "收到计划 BOM 问答用户问题。",
            {"question": question, "use_llm": use_llm},
        )
        nlu = self.nlu_service.understand(question, use_llm=use_llm)
        trace_recorder.add(
            "nlu_completed",
            "BOM NLU Center 已完成意图和槽位理解。",
            {
                "intent": nlu.intent,
                "slots": nlu.slots,
                "missing_slots": nlu.missing_slots,
                "confidence": nlu.confidence,
                "provider_mode": nlu.provider_mode,
                "guardrail_notes": nlu.guardrail_notes,
            },
        )
        if nlu.intent == "power_cell_requirement":
            trace_recorder.add(
                "branch_selected",
                "问题进入 C 类拒答分支：当前 BOM 数据不支持功率倒推。",
                {"intent": nlu.intent},
            )
            response = self._with_presentation(
                PlanBomQaResponse(
                    question=question,
                    classification="C",
                    status=PlanBomQaStatus(
                        code="UNSUPPORTED_QUESTION",
                        message="当前 BOM 数据不能直接支撑功率倒推电池方案。",
                        severity="warning",
                    ),
                    nlu=nlu,
                    answer_summary="当前结构化 BOM 只包含订单、版本、材料和规格等事实数据，缺少功率预测模型、电池片功率档位规则、组件版型约束和业务选型规则，不能据此倒推“需要什么样的电池”。",
                    warnings=["该类问题需补充功率预测规则、电池片选型规则和组件功率约束后才能进入可答范围。"],
                )
            )
        elif nlu.missing_slots:
            trace_recorder.add(
                "branch_selected",
                "问题进入 B 类追问分支：仍缺少关键槽位。",
                {"missing_slots": nlu.missing_slots},
            )
            response = self._clarification_response(question=question, nlu=nlu)
        elif nlu.intent in {"plan_power_prediction", "plan_power_supplier_recommendation"}:
            trace_recorder.add(
                "branch_selected",
                "问题进入计划 BOM 功率预测 / 供应商推荐分支。",
                {"intent": nlu.intent, "slots": nlu.slots},
            )
            response = self._power_response(question=question, nlu=nlu)
        elif nlu.intent == "plan_power_factor_effect_compare":
            trace_recorder.add(
                "branch_selected",
                "问题进入功率模型配置影响值对比分支。",
                {"intent": nlu.intent, "slots": nlu.slots},
            )
            response = self._power_factor_effect_compare_response(question=question, nlu=nlu)
        elif nlu.intent in {"single_order_material_specs", "specific_material_query"}:
            trace_recorder.add(
                "branch_selected",
                "问题进入单订单或指定材料查询分支。",
                {"intent": nlu.intent, "slots": nlu.slots},
            )
            response = self._single_order_response(question=question, nlu=nlu)
        elif nlu.intent in {"multi_order_material_table", "scope_material_list", "batch_export_table"}:
            trace_recorder.add(
                "branch_selected",
                "问题进入多订单或范围清单查询分支。",
                {"intent": nlu.intent, "slots": nlu.slots},
            )
            response = self._multi_or_scope_response(question=question, nlu=nlu)
        elif nlu.intent in {"cross_order_material_compare", "bom_version_compare", "material_consistency_check"}:
            trace_recorder.add(
                "branch_selected",
                "问题进入跨订单或版本对比查询分支。",
                {"intent": nlu.intent, "slots": nlu.slots},
            )
            response = self._compare_response(question=question, nlu=nlu)
        elif nlu.intent == "material_presence_check":
            trace_recorder.add(
                "branch_selected",
                "问题进入物料存在性检查分支。",
                {"intent": nlu.intent, "slots": nlu.slots},
            )
            response = self._presence_response(question=question, nlu=nlu)
        else:
            trace_recorder.add(
                "branch_selected",
                "问题未命中可直接执行分支，进入受控追问。",
                {"intent": nlu.intent, "slots": nlu.slots},
            )
            response = self._clarification_response(question=question, nlu=nlu)
        return self._complete_traced_response(response=response, trace_recorder=trace_recorder)

    def _single_order_response(self, *, question: str, nlu: PlanBomNluCandidate) -> PlanBomQaResponse:
        """处理单订单材料规格查询。

        参数：
            question: 原始问题；
            nlu: NLU 候选。

        返回：
            QA 响应。
        """

        tail = (nlu.slots.get("order_tail_no") or [None])[0]
        categories, non_core_response = self._resolve_core_material_categories(question=question, nlu=nlu)
        if non_core_response:
            return non_core_response
        result = self.query_service.detail(
            PlanBomDetailQueryRequest(order_no=tail, material_categories=categories, candidate_limit=20)
        )
        if result.status.code != "OK":
            return self._non_ok_query_response(question=question, nlu=nlu, raw=result.model_dump(mode="json"))
        rows = [self._item_row(item.model_dump(mode="json")) for item in result.items]
        selected = result.selected_version
        answer = f"已查询订单 {selected.order_display_label or selected.order_no if selected else tail} 的 {len(rows)} 条 BOM 材料规格。"
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="A",
                status=PlanBomQaStatus(code="OK", message="查询成功"),
                nlu=nlu,
                answer_summary=answer,
                result_table=PlanBomTableSpec(columns=self._default_columns(), rows=rows),
                raw_result=result.model_dump(mode="json"),
            )
        )

    def _multi_or_scope_response(self, *, question: str, nlu: PlanBomNluCandidate) -> PlanBomQaResponse:
        """处理多订单或范围清单查询。

        参数：
            question: 原始问题；
            nlu: NLU 候选。

        返回：
            QA 响应。
        """

        categories, non_core_response = self._resolve_core_material_categories(question=question, nlu=nlu)
        if non_core_response:
            return non_core_response
        tails = nlu.slots.get("order_tail_no") or []
        headers = self._headers_from_tails_or_scope(tails=tails, nlu=nlu)
        if not headers:
            return self._empty_response(question=question, nlu=nlu, reason="未找到匹配订单范围。")
        rows: list[dict[str, Any]] = []
        for header in self._select_current_headers(headers):
            for line in self.repository.list_material_lines_for_header(header=header, material_categories=categories):
                rows.append(self._line_row(header, line))
        if not rows:
            return self._empty_response(question=question, nlu=nlu, reason="已定位订单，但没有命中请求材料。")
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="A",
                status=PlanBomQaStatus(code="OK", message="清单生成成功"),
                nlu=nlu,
                answer_summary=f"已按当前条件生成 {len(rows)} 条计划 BOM 材料清单。",
                result_table=PlanBomTableSpec(columns=self._default_columns(), rows=rows),
                raw_result={"headers_count": len(headers), "selected_headers_count": len(self._select_current_headers(headers))},
            )
        )

    def _compare_response(self, *, question: str, nlu: PlanBomNluCandidate) -> PlanBomQaResponse:
        """处理跨订单或版本差异查询。

        参数：
            question: 原始问题；
            nlu: NLU 候选。

        返回：
            QA 响应。
        """

        categories, non_core_response = self._resolve_core_material_categories(question=question, nlu=nlu)
        if non_core_response:
            return non_core_response
        tails = nlu.slots.get("order_tail_no") or []
        versions = nlu.slots.get("bom_version") or []
        if nlu.intent == "bom_version_compare" and len(versions) >= 2 and tails:
            left = PlanBomCompareSideRequest(order_no=tails[0], version_no=versions[0])
            right = PlanBomCompareSideRequest(order_no=tails[0], version_no=versions[1])
        elif len(tails) >= 2:
            if tails[0] == tails[1]:
                nlu.missing_slots = sorted(set([*(nlu.missing_slots or []), "compare_orders"]))
                return self._clarification_response(question=question, nlu=nlu)
            left = PlanBomCompareSideRequest(order_no=tails[0])
            right = PlanBomCompareSideRequest(order_no=tails[1])
        else:
            return self._clarification_response(question=question, nlu=nlu)
        compare_payload = PlanBomCompareQueryRequest(left=left, right=right, material_categories=categories, candidate_limit=20)
        result = self.query_service.compare(compare_payload)
        if result.status.code != "OK" or not result.compare_ready:
            expanded_response = self._expanded_candidate_compare_response(
                question=question,
                nlu=nlu,
                payload=compare_payload,
                candidate_result=result,
            )
            if expanded_response:
                return expanded_response
            return self._non_ok_query_response(question=question, nlu=nlu, raw=result.model_dump(mode="json"))
        rows: list[dict[str, Any]] = []
        description_only = self._is_description_compare_question(question)
        for item in result.changed:
            if description_only and "description" not in item.changed_fields:
                continue
            rows.append(self._compare_changed_row(item.model_dump(mode="json")))
        for item in result.only_left:
            rows.append(self._compare_single_side_row(item.model_dump(mode="json"), side="仅左侧"))
        for item in result.only_right:
            rows.append(self._compare_single_side_row(item.model_dump(mode="json"), side="仅右侧"))
        answer = f"已完成 BOM 差异对比，变化 {len(result.changed)} 条，仅左侧 {len(result.only_left)} 条，仅右侧 {len(result.only_right)} 条。"
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="A",
                status=PlanBomQaStatus(code="OK", message="对比成功"),
                nlu=nlu,
                answer_summary=answer,
                result_table=PlanBomTableSpec(columns=self._compare_columns(), rows=rows),
                raw_result=result.model_dump(mode="json"),
            )
        )

    def _expanded_candidate_compare_response(
        self,
        *,
        question: str,
        nlu: PlanBomNluCandidate,
        payload: PlanBomCompareQueryRequest,
        candidate_result: PlanBomCompareResponse,
    ) -> PlanBomQaResponse | None:
        """把跨订单 compare 的单侧多业务实例候选展开为多组确定性对比。

        参数：
            question: 原始问题；
            nlu: 已完成槽位抽取的 NLU 候选；
            payload: 初次 compare 请求；
            candidate_result: 初次 compare 返回的候选态结果。

        返回：
            若可安全展开，则返回 A 类对比表；否则返回 None，继续沿用候选追问兜底。

        业务逻辑：
            用户明确要求“订单 A 和订单 B 的规格描述有什么不一样，并用表格统计”时，短订单号 B
            可能对应多个真实业务实例。此时不能随机选择其中一个，也不应把内部 `order_identity`
            暴露成泛化追问；安全做法是把多业务实例逐个与已确定的另一侧做确定性 compare，
            在表格中保留左右实例名称和版本，业务员可直接看到每个候选实例的差异。
        """

        candidates = list(candidate_result.candidates or [])
        if not self._can_expand_compare_candidates(nlu=nlu, candidate_result=candidate_result, candidates=candidates):
            return None

        pair_rows: list[dict[str, Any]] = []
        compared_pairs: list[dict[str, Any]] = []
        pair_summaries: list[dict[str, Any]] = []
        warnings: list[str] = []
        ambiguous_side = candidate_result.candidate_side
        assert ambiguous_side in {"left", "right"}
        description_only = self._is_description_compare_question(question)

        for candidate in candidates:
            expanded_payload = self._expanded_compare_payload_for_candidate(
                original_payload=payload,
                candidate_result=candidate_result,
                candidate=candidate,
            )
            if expanded_payload is None:
                return None
            pair_result = self.query_service.compare(expanded_payload)
            pair_summary = self._expanded_pair_summary(pair_result)
            pair_summaries.append(pair_summary)
            if pair_result.status.code != "OK" or not pair_result.compare_ready or not pair_result.left or not pair_result.right:
                warnings.append(
                    f"候选 {self._compare_side_label(candidate)} 未能完成对比：{pair_result.status.message}"
                )
                continue

            left_label = self._compare_side_label(pair_result.left)
            right_label = self._compare_side_label(pair_result.right)
            pair_label = f"{left_label} ↔ {right_label}"
            compared_pairs.append(
                {
                    "compare_pair": pair_label,
                    "left_order_identity_key": pair_result.left.order_identity_key,
                    "left_file_instance_key": pair_result.left.file_instance_key,
                    "left_order_no": pair_result.left.order_no,
                    "left_version_no": pair_result.left.version_no,
                    "right_order_identity_key": pair_result.right.order_identity_key,
                    "right_file_instance_key": pair_result.right.file_instance_key,
                    "right_order_no": pair_result.right.order_no,
                    "right_version_no": pair_result.right.version_no,
                }
            )
            pair_rows.extend(
                self._compare_rows_for_pair(
                    pair_result=pair_result,
                    pair_label=pair_label,
                    left_label=left_label,
                    right_label=right_label,
                    description_only=description_only,
                )
            )

        if not compared_pairs:
            return None

        left_count = len(candidates) if ambiguous_side == "left" else 1
        right_count = len(candidates) if ambiguous_side == "right" else 1
        answer = (
            f"已展开{self._compare_side_name(ambiguous_side)}侧 {len(candidates)} 个业务实例并完成 "
            f"{len(compared_pairs)} 组 BOM 核心材料规格差异对比，生成 {len(pair_rows)} 条差异记录。"
        )
        if warnings:
            answer += f"其中 {len(warnings)} 个候选未完成对比，已在风险提示中列出。"
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="A",
                status=PlanBomQaStatus(code="OK", message="对比成功"),
                nlu=nlu,
                answer_summary=answer,
                result_table=PlanBomTableSpec(columns=self._expanded_compare_columns(), rows=pair_rows),
                raw_result={
                    "expanded_compare": True,
                    "expanded_side": ambiguous_side,
                    "left_candidate_count": left_count,
                    "right_candidate_count": right_count,
                    "compared_pairs": compared_pairs,
                    "pair_summaries": pair_summaries,
                    "source_candidate_result": candidate_result.model_dump(mode="json"),
                },
                warnings=warnings,
            )
        )

    @staticmethod
    def _can_expand_compare_candidates(
        *,
        nlu: PlanBomNluCandidate,
        candidate_result: PlanBomCompareResponse,
        candidates: list[PlanBomCandidate],
    ) -> bool:
        """判断 compare 候选态是否允许自动展开为多组对比。

        只有跨订单材料对比、单侧业务实例候选且候选数受控时才展开；版本、文件实例或单订单查询
        仍 fail closed，避免替业务员选择比较基线。
        """

        if nlu.intent != "cross_order_material_compare":
            return False
        if candidate_result.status.code != "CANDIDATE_REQUIRED":
            return False
        if candidate_result.candidate_scope != CANDIDATE_SCOPE_ORDER_IDENTITY:
            return False
        if candidate_result.candidate_side not in {"left", "right"}:
            return False
        candidate_truncated = bool(candidate_result.status.extras.get("candidate_truncated")) or bool(
            (candidate_result.response_meta or {}).get("candidate_truncated")
        )
        if candidate_truncated or int(candidate_result.candidate_total_hint or 0) > len(candidates):
            return False
        if not candidates or len(candidates) > 20:
            return False
        return True

    def _expanded_compare_payload_for_candidate(
        self,
        *,
        original_payload: PlanBomCompareQueryRequest,
        candidate_result: PlanBomCompareResponse,
        candidate: PlanBomCandidate,
    ) -> PlanBomCompareQueryRequest | None:
        """构造单个候选实例对应的精确 compare 请求。"""

        candidate_side = self._compare_side_request_from_candidate(candidate)
        if candidate_result.candidate_side == "right":
            if not candidate_result.left:
                return None
            left_side = self._compare_side_request_from_context(candidate_result.left)
            right_side = candidate_side
        else:
            if not candidate_result.right:
                return None
            left_side = candidate_side
            right_side = self._compare_side_request_from_context(candidate_result.right)
        return PlanBomCompareQueryRequest(
            left=left_side,
            right=right_side,
            material_categories=original_payload.material_categories,
            candidate_limit=original_payload.candidate_limit,
        )

    @staticmethod
    def _compare_side_request_from_candidate(candidate: PlanBomCandidate) -> PlanBomCompareSideRequest:
        """从候选列表项生成精确 compare 单侧请求。"""

        return PlanBomCompareSideRequest(
            order_identity_key=candidate.order_identity_key,
            file_instance_key=candidate.file_instance_key,
            version_no=candidate.version_no,
        )

    @staticmethod
    def _compare_side_request_from_context(context: PlanBomCompareSideContext) -> PlanBomCompareSideRequest:
        """从已解析 compare 上下文生成精确 compare 单侧请求。"""

        return PlanBomCompareSideRequest(
            order_identity_key=context.order_identity_key,
            file_instance_key=context.file_instance_key,
            version_no=context.version_no,
        )

    @staticmethod
    def _compare_side_label(side: PlanBomCandidate | PlanBomCompareSideContext) -> str:
        """生成业务可读的 compare 单侧实例标签。"""

        display = side.order_display_label or side.order_name or side.order_no
        if side.version_no:
            return f"{display}（版本 {side.version_no}）"
        return display

    @staticmethod
    def _compare_side_name(side: str) -> str:
        """把 compare 内部侧别转换为中文说明。"""

        return "左" if side == "left" else "右"

    @staticmethod
    def _is_description_compare_question(question: str) -> bool:
        """判断用户是否明确只关注规格描述差异。

        参数：
            question: 原始问题文本。

        返回：
            命中“规格描述/描述”时返回 True，用于避免把用量、备注等非描述字段变化混入描述差异表。
        """

        text = question or ""
        return "规格描述" in text or "描述" in text

    def _compare_rows_for_pair(
        self,
        *,
        pair_result: PlanBomCompareResponse,
        pair_label: str,
        left_label: str,
        right_label: str,
        description_only: bool = False,
    ) -> list[dict[str, Any]]:
        """把单组 compare 结果转换为带实例信息的表格行。"""

        rows: list[dict[str, Any]] = []
        for item in pair_result.changed:
            if description_only and "description" not in item.changed_fields:
                continue
            rows.append(
                self._compare_pair_row(
                    self._compare_changed_row(item.model_dump(mode="json")),
                    pair_label=pair_label,
                    left_label=left_label,
                    right_label=right_label,
                )
            )
        for item in pair_result.only_left:
            rows.append(
                self._compare_pair_row(
                    self._compare_single_side_row(item.model_dump(mode="json"), side="仅左侧"),
                    pair_label=pair_label,
                    left_label=left_label,
                    right_label=right_label,
                )
            )
        for item in pair_result.only_right:
            rows.append(
                self._compare_pair_row(
                    self._compare_single_side_row(item.model_dump(mode="json"), side="仅右侧"),
                    pair_label=pair_label,
                    left_label=left_label,
                    right_label=right_label,
                )
            )
        return rows

    @staticmethod
    def _compare_pair_row(
        row: dict[str, Any],
        *,
        pair_label: str,
        left_label: str,
        right_label: str,
    ) -> dict[str, Any]:
        """为差异行补充比较组和左右业务实例信息。"""

        return {
            "compare_pair": pair_label,
            "diff_type": row.get("diff_type"),
            "material_category": row.get("material_category"),
            "left_instance": left_label,
            "left_order": row.get("left_order"),
            "left_description": row.get("left_description"),
            "right_instance": right_label,
            "right_order": row.get("right_order"),
            "right_description": row.get("right_description"),
            "changed_fields": row.get("changed_fields"),
        }

    @staticmethod
    def _expanded_pair_summary(pair_result: PlanBomCompareResponse) -> dict[str, Any]:
        """生成单组 compare 的轻量追溯摘要，避免 raw_result 写入过大的明细快照。"""

        return {
            "status_code": pair_result.status.code,
            "status_message": pair_result.status.message,
            "compare_ready": pair_result.compare_ready,
            "left_order_no": pair_result.left.order_no if pair_result.left else None,
            "left_version_no": pair_result.left.version_no if pair_result.left else None,
            "right_order_no": pair_result.right.order_no if pair_result.right else None,
            "right_version_no": pair_result.right.version_no if pair_result.right else None,
            "changed_count": len(pair_result.changed),
            "only_left_count": len(pair_result.only_left),
            "only_right_count": len(pair_result.only_right),
            "same_count": len(pair_result.same),
        }

    def _presence_response(self, *, question: str, nlu: PlanBomNluCandidate) -> PlanBomQaResponse:
        """处理某类物料是否存在或缺失查询。

        参数：
            question: 原始问题；
            nlu: NLU 候选。

        返回：
            QA 响应。
        """

        categories, non_core_response = self._resolve_core_material_categories(question=question, nlu=nlu, default_categories=["junction_box"])
        if non_core_response:
            return non_core_response
        headers = self._select_current_headers(self.repository.list_all_active_headers(limit=500))
        rows: list[dict[str, Any]] = []
        for header in headers:
            lines = self.repository.list_material_lines_for_header(header=header, material_categories=categories)
            if "没有" in question and lines:
                continue
            if "没有" not in question and not lines:
                continue
            rows.append(
                {
                    "order_no": header.order_no,
                    "order_name": header.order_name,
                    "version_no": header.version_no,
                    "material_category": ",".join(categories),
                    "status": "缺失" if not lines else "存在",
                    "source_file": header.raw_file_name,
                }
            )
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="A",
                status=PlanBomQaStatus(code="OK", message="物料存在性检查完成"),
                nlu=nlu,
                answer_summary=f"已完成 {len(headers)} 个当前 BOM 版本的物料存在性检查，返回 {len(rows)} 条匹配记录。",
                result_table=PlanBomTableSpec(
                    columns=["order_no", "order_name", "version_no", "material_category", "status", "source_file"],
                    rows=rows,
                ),
                raw_result={"checked_orders": len(headers), "matched_rows": len(rows)},
            )
        )

    @staticmethod
    def _infer_single_model_code_from_power_candidates(candidates: list[Any]) -> str | None:
        """从未确认订单候选中提取唯一版型编码。

        参数：
            candidates: M4 返回的候选订单列表，元素可以是 dataclass、Pydantic 或字典。
        返回：
            当所有可识别候选只指向同一个 `NTxx-xxGDF` 版型时返回该版型；否则返回 None。
        业务逻辑：显式配置 no-BOM 评估只可借用“唯一一致的版型线索”，不能在多版型候选中替业务员硬选订单。
        """

        model_codes: set[str] = set()
        for candidate in candidates or []:
            if isinstance(candidate, dict):
                raw_values = [candidate.get("order_name"), candidate.get("raw_file_name")]
            else:
                raw_values = [getattr(candidate, "order_name", None), getattr(candidate, "raw_file_name", None)]
            for raw_value in raw_values:
                text = str(raw_value or "")
                match = re.search(r"NT[0-9A-Z]+[-/][0-9A-Z]+GDF", text, flags=re.IGNORECASE)
                if match:
                    model_codes.add(match.group(0).upper().replace("/", "-"))
        return next(iter(model_codes)) if len(model_codes) == 1 else None

    def _power_response(self, *, question: str, nlu: PlanBomNluCandidate) -> PlanBomQaResponse:
        """处理计划 BOM 功率预测 / 供应商推荐问答。

        参数：
            question: 原始问题；
            nlu: 已完成规则和可选 LLM guardrail 的 NLU 候选。

        返回：
            QA 响应。所有配置解析来自 M4，所有数值计算来自 M3，LLM 不参与计算。
        """

        tail = (nlu.slots.get("order_tail_no") or [None])[0]
        bom_version = (nlu.slots.get("bom_version") or [None])[0]
        order_name_hint = nlu.slots.get("order_name_hint")
        benchmark = nlu.slots.get("benchmark")
        explicit_configuration = dict(nlu.slots.get("explicit_power_configuration") or {})
        if benchmark and "benchmark" not in explicit_configuration:
            explicit_configuration["benchmark"] = benchmark
        if nlu.slots.get("supplier_name") and "supplier" not in explicit_configuration:
            explicit_configuration["supplier"] = nlu.slots.get("supplier_name")
        if tail:
            resolution = self.power_config_resolver.resolve(
                order_no=tail,
                order_name=order_name_hint,
                version_no=bom_version,
                benchmark=benchmark,
                explicit_configuration=explicit_configuration,
            )
            fallback_model_code = nlu.slots.get("model") or self._infer_single_model_code_from_power_candidates(
                getattr(resolution, "candidates", [])
            )
            if resolution.status == CANDIDATE_REQUIRED_STATUS and explicit_configuration and fallback_model_code:
                # 业务员有时会把不可靠短尾号和完整计划搭配一起写入问题。
                # 若订单候选未确认，但显式配置 + 版型已经足够让 M4/M3 做 no-BOM 评估，
                # 则转为“显式输入配置”路径，避免把可安全计算的问题降级为候选追问。
                explicit_resolution = self.power_config_resolver.resolve_explicit_configuration(
                    model_code=fallback_model_code,
                    configuration=explicit_configuration,
                )
                if explicit_resolution.status != CANDIDATE_REQUIRED_STATUS:
                    explicit_resolution.warnings.append("已忽略未确认订单候选，按显式输入配置执行 no-BOM 功率推荐。")
                    resolution = explicit_resolution
        else:
            resolution = self.power_config_resolver.resolve_explicit_configuration(
                model_code=nlu.slots.get("model"),
                configuration=explicit_configuration,
            )
        resolution_payload = resolution.to_dict()
        if resolution.status in {CANDIDATE_REQUIRED_STATUS, PARTIAL_STATUS}:
            slot_name = "candidate" if resolution.status == CANDIDATE_REQUIRED_STATUS else "power_configuration"
            nlu.missing_slots = sorted(set([*(nlu.missing_slots or []), slot_name]))
            return self._with_presentation(
                PlanBomQaResponse(
                    question=question,
                    classification="B",
                    status=PlanBomQaStatus(
                        code="CLARIFICATION_REQUIRED",
                        message="功率预测配置仍需确认",
                        severity="warning",
                    ),
                    nlu=nlu,
                    answer_summary=self._power_resolution_clarification_summary(
                        resolution_payload,
                        question=question,
                    ),
                    raw_result={"bom_config_resolution": resolution_payload},
                    warnings=["M4 配置解析未完全 resolved，已停止调用 M3 计算，避免编造功率预测。"],
                )
            )
        if resolution.status in {NOT_FOUND_STATUS, NO_ACTIVE_MODEL_STATUS} or resolution.model_code is None:
            return self._empty_response(
                question=question,
                nlu=nlu,
                reason=resolution.message,
                raw={"bom_config_resolution": resolution_payload},
            )
        if resolution.status != RESOLVED_STATUS:
            return self._empty_response(
                question=question,
                nlu=nlu,
                reason=f"BOM 配置映射状态不可用于功率预测：{resolution.status}",
                raw={"bom_config_resolution": resolution_payload},
            )

        configuration = resolution.to_prediction_configuration()
        supplier_name = nlu.slots.get("supplier_name")
        if supplier_name:
            configuration["supplier"] = supplier_name
        try:
            if nlu.intent == "plan_power_supplier_recommendation":
                recommendation = self.power_recommendation_service.recommend(
                    model_code=resolution.model_code,
                    configuration=configuration,
                    target_power_ratio=nlu.slots.get("target_power_ratio"),
                    supplier_names=[supplier_name] if supplier_name else None,
                )
                return self._power_recommendation_response(
                    question=question,
                    nlu=nlu,
                    resolution_payload=resolution_payload,
                    recommendation=recommendation,
                )
            prediction = self.power_prediction_engine.predict(
                model_code=resolution.model_code,
                configuration=configuration,
                supplier_name=supplier_name,
            )
            return self._power_prediction_response(
                question=question,
                nlu=nlu,
                resolution_payload=resolution_payload,
                prediction=prediction,
            )
        except PowerPredictionError as exc:
            return self._empty_response(
                question=question,
                nlu=nlu,
                reason=str(exc),
                raw={"bom_config_resolution": resolution_payload, "power_error": str(exc)},
            )

    def _power_factor_effect_compare_response(self, *, question: str, nlu: PlanBomNluCandidate) -> PlanBomQaResponse:
        """处理功率模型配置影响值差异查询。

        参数：
            question: 用户原始问题。
            nlu: 已抽取版型、配置项和两个配置选项的 NLU 结果。

        返回：
            A 类配置影响值对比响应；若版型或选项无法在 active 功率模型中命中，则 fail-closed 追问。

        业务逻辑：
            这类问题问的是 Excel 功率模型中“某配置项两个选项的影响值相差多少”，
            不依赖具体订单/BOM 明细，因此不能因为缺少订单号而追问；但所有选项必须回到
            当前生效功率模型的真实 option 校验后才能返回差值，避免按文本硬算。
        """

        model_code = str(nlu.slots.get("model") or "").strip()
        factor_key = str(nlu.slots.get("power_factor_key") or "").strip()
        factor_options = nlu.slots.get("power_factor_options") or {}
        option_values = list(factor_options.get(factor_key) or [])
        if not model_code or not factor_key or len(option_values) != 2:
            nlu.missing_slots = sorted({str(slot) for slot in [*(nlu.missing_slots or []), "power_factor_options"]})
            return self._clarification_response(
                question=question,
                nlu=nlu,
                raw={"power_factor_effect_compare": {"model_code": model_code, "factor_key": factor_key, "options": option_values}},
            )

        version = self.repository.db.query(PlanPowerModelVersion).filter_by(is_active=1).first()
        if version is None:
            return self._empty_response(
                question=question,
                nlu=nlu,
                reason="当前没有生效的功率模型版本，无法查询配置影响值。",
                raw={"power_factor_effect_compare": {"model_code": model_code, "factor_key": factor_key}},
            )
        sheet = (
            self.repository.db.query(PlanPowerModelSheet)
            .filter_by(version_id=version.id, normalized_model_code=model_code)
            .first()
        )
        if sheet is None:
            return self._empty_response(
                question=question,
                nlu=nlu,
                reason=f"当前生效功率模型中没有版型 {model_code}。",
                raw={"power_factor_effect_compare": {"model_code": model_code, "factor_key": factor_key}},
            )

        options = (
            self.repository.db.query(PlanPowerFactorOption)
            .filter_by(sheet_id=sheet.id, factor_key=factor_key, is_valid=1)
            .order_by(PlanPowerFactorOption.id.asc())
            .all()
        )
        option_by_label = {self._normalize_power_factor_label(option.option_label): option for option in options}
        selected_options = [option_by_label.get(self._normalize_power_factor_label(value)) for value in option_values]
        if any(option is None or option.effect_value is None for option in selected_options):
            nlu.missing_slots = sorted({str(slot) for slot in [*(nlu.missing_slots or []), "power_factor_options"]})
            return self._with_presentation(
                PlanBomQaResponse(
                    question=question,
                    classification="B",
                    status=PlanBomQaStatus(code="CLARIFICATION_REQUIRED", message="需要确认功率配置选项", severity="warning"),
                    nlu=nlu,
                    answer_summary=(
                        f"已识别为 {model_code} 的{self._power_factor_label(factor_key)}影响值对比，"
                        "但至少有一个配置选项未命中当前生效功率模型。请从模型候选配置中确认后再比较。"
                    ),
                    raw_result={
                        "power_factor_effect_compare": {
                            "model_code": model_code,
                            "factor_key": factor_key,
                            "requested_options": option_values,
                            "candidate_options": [option.option_label for option in options[:20]],
                        }
                    },
                    warnings=["配置影响值对比未完全命中 active 模型 option，已停止计算差值。"],
                )
            )

        left_option, right_option = selected_options
        assert left_option is not None and right_option is not None
        assert left_option.effect_value is not None and right_option.effect_value is not None
        left_effect = self._decimal_to_float(left_option.effect_value)
        right_effect = self._decimal_to_float(right_option.effect_value)
        absolute_difference = round(abs(left_effect - right_effect), 6)
        factor_label = self._power_factor_label(factor_key)
        answer = (
            f"{model_code} 的{factor_label}功率影响值对比："
            f"{left_option.option_label} 为 {self._format_plain_number(left_effect)}W，"
            f"{right_option.option_label} 为 {self._format_plain_number(right_effect)}W，"
            f"二者相差 {self._format_plain_number(absolute_difference)}W。"
        )
        payload = {
            "model_code": model_code,
            "factor_key": factor_key,
            "factor_label": factor_label,
            "left": self._power_factor_option_payload(left_option),
            "right": self._power_factor_option_payload(right_option),
            "absolute_difference": absolute_difference,
        }
        rows = [
            {"配置项": factor_label, "选项": left_option.option_label, "功率影响值": left_effect},
            {"配置项": factor_label, "选项": right_option.option_label, "功率影响值": right_effect},
            {"配置项": factor_label, "选项": "差值", "功率影响值": absolute_difference},
        ]
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="A",
                status=PlanBomQaStatus(code="OK", message="配置影响值对比成功"),
                nlu=nlu,
                answer_summary=answer,
                result_table=PlanBomTableSpec(columns=["配置项", "选项", "功率影响值"], rows=rows),
                raw_result={"power_factor_effect_compare": payload},
            )
        )

    @staticmethod
    def _power_factor_label(factor_key: str) -> str:
        """把功率模型配置项 key 转为业务可读名称。"""
        labels = {
            "glass": "玻璃",
            "ribbon": "焊带",
            "busbar": "汇流条",
            "cable": "接线盒线缆",
            "supplier": "供应商",
            "cell_size": "电池尺寸",
            "benchmark": "标板基准",
        }
        return labels.get(factor_key, factor_key)

    @staticmethod
    def _normalize_power_factor_label(value: str | None) -> str:
        """归一化功率模型 option 标签，用于用户文本与 active 模型 option 的确定性匹配。"""
        text = str(value or "").strip()
        text = text.replace("＋", "+").replace("＊", "*").replace("×", "*").replace("X", "*").replace("x", "*")
        return re.sub(r"\s+", "", text)

    @staticmethod
    def _decimal_to_float(value: Decimal | int | float) -> float:
        """把数据库 Decimal 影响值转成前端和测试易消费的 float。"""
        return float(value)

    @staticmethod
    def _format_plain_number(value: float) -> str:
        """格式化普通数值，去掉无意义尾零。"""
        return f"{value:.6f}".rstrip("0").rstrip(".")

    @staticmethod
    def _power_factor_option_payload(option: PlanPowerFactorOption) -> dict[str, Any]:
        """输出配置 option 的审计载荷，所有数值来自 active 功率模型。"""
        return {
            "option_label": option.option_label,
            "effect_value": PlanBomQaService._decimal_to_float(option.effect_value or 0),
            "source_cell": option.source_cell_ref,
        }

    def _power_prediction_response(
        self,
        *,
        question: str,
        nlu: PlanBomNluCandidate,
        resolution_payload: dict[str, Any],
        prediction: PowerPredictionResult,
    ) -> PlanBomQaResponse:
        """构造单供应商功率预测 QA 响应。

        参数：
            question: 原始问题；
            nlu: NLU 候选；
            resolution_payload: M4 配置映射追溯；
            prediction: M3 确定性预测结果。

        返回：
            A 类预测响应。
        """

        rows = self._power_distribution_rows(prediction)
        configuration_text = self._power_configuration_text(resolution_payload)
        answer = (
            f"已完成订单 {resolution_payload.get('order_no')} 的功率预测：版型 {prediction.model_code}，"
            f"供应商 {prediction.supplier_name}，中心功率 {round(prediction.center_power, 4)}W。"
            f"配置来源：{configuration_text}。"
        )
        warnings = list(resolution_payload.get("warnings") or []) + list(prediction.warnings)
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="A",
                status=PlanBomQaStatus(code="OK", message="功率预测成功"),
                nlu=nlu,
                answer_summary=answer,
                result_table=PlanBomTableSpec(columns=["功率档", "预测比例", "累计比例", "中心功率", "供应商"], rows=rows),
                raw_result={
                    "bom_config_resolution": resolution_payload,
                    "power_prediction": prediction.to_dict(),
                },
                warnings=warnings,
            )
        )

    def _power_recommendation_response(
        self,
        *,
        question: str,
        nlu: PlanBomNluCandidate,
        resolution_payload: dict[str, Any],
        recommendation: PowerRecommendationResult,
    ) -> PlanBomQaResponse:
        """构造目标功率比例下的供应商推荐 QA 响应。

        参数：
            question: 原始问题；
            nlu: NLU 候选；
            resolution_payload: M4 配置映射追溯；
            recommendation: M3 推荐服务输出。

        返回：
            A 类推荐响应。
        """

        rows = self._power_recommendation_rows(recommendation)
        top_item = recommendation.recommendations[0] if recommendation.recommendations else None
        top_supplier = top_item.supplier_name if top_item else "无"
        source_label = f"订单 {resolution_payload.get('order_no')} 的 BOM 配置" if resolution_payload.get("order_no") else "显式输入配置"
        efficiency_label = self._format_suggested_efficiency_segments(top_item.suggested_efficiency_segments) if top_item else ""
        if efficiency_label:
            # 用户问“什么效率段投产”时，正文必须直接给出最低建议效率段；
            # 多个效率段仍保留在明细表中，避免只返回泛化的“推荐供应商”。
            first_efficiency = efficiency_label.split("、", 1)[0]
            answer = (
                f"已按{source_label}和目标功率比例完成供应商推荐，"
                f"{top_supplier}建议从 {first_efficiency} 效率段投产；可重点关注效率段：{efficiency_label}。"
            )
        else:
            answer = (
                f"已按{source_label}和目标功率比例完成供应商推荐，"
                f"当前最高匹配供应商为 {top_supplier}。"
            )
        warnings = list(resolution_payload.get("warnings") or []) + list(recommendation.warnings)
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="A",
                status=PlanBomQaStatus(code="OK", message="供应商功率推荐成功"),
                nlu=nlu,
                answer_summary=answer,
                result_table=PlanBomTableSpec(
                    columns=["供应商", "目标功率档", "目标比例", "预测比例", "CTM 值", "中心功率", "建议效率段", "落档比例预估"],
                    rows=rows,
                ),
                raw_result={
                    "bom_config_resolution": resolution_payload,
                    "power_recommendation": recommendation.to_dict(),
                },
                warnings=warnings,
            )
        )

    @staticmethod
    def _power_distribution_rows(prediction: PowerPredictionResult) -> list[dict[str, Any]]:
        """转换 M3 功率档分布为 QA 表格行。"""
        rows: list[dict[str, Any]] = []
        cumulative = 0.0
        for power_bin, ratio in prediction.weighted_distribution.items():
            cumulative += float(ratio)
            rows.append(
                {
                    "功率档": f"{power_bin}W",
                    "预测比例": round(float(ratio) * 100.0, 4),
                    "累计比例": round(cumulative * 100.0, 4),
                    "中心功率": round(prediction.center_power, 4),
                    "供应商": prediction.supplier_name,
                }
            )
        return rows

    @staticmethod
    def _power_recommendation_rows(recommendation: PowerRecommendationResult) -> list[dict[str, Any]]:
        """转换 M3 推荐结果为 QA 表格行。"""
        rows: list[dict[str, Any]] = []
        for item in recommendation.recommendations:
            efficiency_label = PlanBomQaService._format_suggested_efficiency_segments(item.suggested_efficiency_segments)
            bin_probability_label = PlanBomQaService._format_efficiency_bin_probability_estimate(
                item=item,
                target_bins=list(recommendation.target_power_ratio.keys()),
            )
            for power_bin, target_ratio in recommendation.target_power_ratio.items():
                rows.append(
                    {
                        "供应商": item.supplier_name,
                        "目标功率档": f"{power_bin}W",
                        "目标比例": round(float(target_ratio) * 100.0, 4),
                        "预测比例": round(float(item.predicted_target_ratio.get(power_bin, 0.0)) * 100.0, 4),
                        "CTM 值": PlanBomQaService._format_ctm_value(item.prediction),
                        "中心功率": round(item.prediction.center_power, 4),
                        "建议效率段": efficiency_label,
                        "落档比例预估": bin_probability_label,
                    }
                )
        return rows

    @staticmethod
    def _format_suggested_efficiency_segments(segments: list[dict[str, Any]]) -> str:
        """格式化 M3 推荐结果中的建议效率段。

        参数：
            segments: M3 `PowerRecommendationItem.suggested_efficiency_segments` 输出。

        返回：
            用于 QA 表格展示的效率段文本；无建议时返回空字符串。
        """
        labels: list[str] = []
        sorted_segments = sorted(
            segments,
            key=lambda item: float(item.get("efficiency_value") or item.get("efficiency_percent") or 0.0),
        )
        for segment in sorted_segments[:2]:
            percent = segment.get("efficiency_percent")
            if percent is None:
                continue
            labels.append(f"{PlanBomQaService._format_percent_number(float(percent), digits=3)}%")
        return "、".join(labels)

    @staticmethod
    def _format_ctm_value(prediction: PowerPredictionResult) -> str:
        """按业务口径格式化 CTM 值。

        参数：
            prediction: M3 确定性功率预测结果，包含中心功率、中心效率、面积和电池片数。

        返回：
            百分比展示文本；关键字段缺失或分母非法时返回空字符串，避免编造结果。
        """
        denominator = float(prediction.center_efficiency) * float(prediction.area) * float(prediction.cell_count) / 1000.0
        if denominator <= 0:
            return ""
        ctm_value = float(prediction.center_power) / denominator * 100.0
        return f"{ctm_value:.2f}%"

    @staticmethod
    def _format_efficiency_bin_probability_estimate(*, item: Any, target_bins: list[str]) -> str:
        """格式化建议效率段的落档比例预估。

        参数：
            item: `PowerRecommendationItem`，其中 `prediction.efficiency_rows[*].bin_probabilities`
                是唯一数据来源。
            target_bins: 用户关注的目标功率档列表。

        返回：
            形如 `25.5%→615W 12.98%\n25.6%→615W 82.08%` 的展示文本；没有可追溯效率行时返回空字符串。
        """
        segments = PlanBomQaService._select_display_efficiency_segments(item.suggested_efficiency_segments)
        if not segments:
            return ""

        labels: list[str] = []
        for segment in segments:
            row = PlanBomQaService._find_efficiency_row(item.prediction.efficiency_rows, segment)
            if row is None:
                continue
            bin_labels = PlanBomQaService._format_probability_bins(row.bin_probabilities, target_bins=target_bins)
            if not bin_labels:
                continue
            percent = segment.get("efficiency_percent")
            if percent is None:
                percent = float(row.efficiency_value) * 100.0
            labels.append(f"{PlanBomQaService._format_percent_number(float(percent), digits=3)}%→{'、'.join(bin_labels)}")
        return "\n".join(labels)

    @staticmethod
    def _select_display_efficiency_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """选择表格中展示的建议效率段。

        参数：
            segments: 推荐服务输出的候选效率段。

        返回：
            按效率从低到高排序后的前 2 个效率段，满足业务员“从最低效率开始展示”的要求。
        """
        return sorted(
            segments,
            key=lambda item: float(item.get("efficiency_value") or item.get("efficiency_percent") or 0.0),
        )[:2]

    @staticmethod
    def _find_efficiency_row(efficiency_rows: list[Any], segment: dict[str, Any]) -> Any | None:
        """从预测结果中查找建议效率段对应的效率行。

        参数：
            efficiency_rows: `PowerPredictionResult.efficiency_rows`。
            segment: 推荐服务输出的单个建议效率段。

        返回：
            匹配的效率行；找不到时返回 None，避免脱离模型明细编造落档比例。
        """
        raw_efficiency = segment.get("efficiency_value")
        if raw_efficiency is None and segment.get("efficiency_percent") is not None:
            raw_efficiency = float(segment["efficiency_percent"]) / 100.0
        if raw_efficiency is None:
            return None
        target_efficiency = float(raw_efficiency)
        for row in efficiency_rows:
            if abs(float(row.efficiency_value) - target_efficiency) <= 0.0000001:
                return row
        return None

    @staticmethod
    def _format_probability_bins(bin_probabilities: dict[str, float], *, target_bins: list[str]) -> list[str]:
        """格式化目标档和一个相邻档的落档概率。

        参数：
            bin_probabilities: 单个效率段的功率档概率，来源于后端正态落档计算。
            target_bins: 用户关注的目标功率档。

        返回：
            至少包含目标功率档的展示片段；若存在相邻档，则追加概率最高的相邻档。
        """
        ordered_keys = sorted(bin_probabilities.keys(), key=lambda value: float(value))
        selected_keys: list[str] = []
        for power_bin in target_bins:
            if power_bin in bin_probabilities and power_bin not in selected_keys:
                selected_keys.append(power_bin)

        adjacent_key = PlanBomQaService._highest_probability_adjacent_bin(
            ordered_keys=ordered_keys,
            target_bins=target_bins,
            bin_probabilities=bin_probabilities,
        )
        if adjacent_key and adjacent_key not in selected_keys:
            selected_keys.append(adjacent_key)

        return [f"{key}W {float(bin_probabilities.get(key, 0.0)) * 100.0:.2f}%" for key in selected_keys]

    @staticmethod
    def _highest_probability_adjacent_bin(
        *,
        ordered_keys: list[str],
        target_bins: list[str],
        bin_probabilities: dict[str, float],
    ) -> str | None:
        """选择目标档旁边概率最高的相邻功率档。

        参数：
            ordered_keys: 按功率升序排列的模型输出档位。
            target_bins: 用户关注的目标功率档。
            bin_probabilities: 单个效率段的功率档概率。

        返回：
            相邻档 key；没有可用相邻档时返回 None。
        """
        adjacent: set[str] = set()
        for target_bin in target_bins:
            if target_bin not in ordered_keys:
                continue
            index = ordered_keys.index(target_bin)
            if index > 0:
                adjacent.add(ordered_keys[index - 1])
            if index + 1 < len(ordered_keys):
                adjacent.add(ordered_keys[index + 1])
        if not adjacent:
            return None
        return max(adjacent, key=lambda key: float(bin_probabilities.get(key, 0.0)))

    @staticmethod
    def _format_percent_number(value: float, *, digits: int) -> str:
        """格式化百分比数字，去掉无意义的尾随 0。

        参数：
            value: 百分比数值。
            digits: 最多保留的小数位数。

        返回：
            去尾零后的数字文本。
        """
        return f"{value:.{digits}f}".rstrip("0").rstrip(".")

    @staticmethod
    def _power_configuration_text(resolution_payload: dict[str, Any]) -> str:
        """汇总 M4 已解析配置，供 answer_summary 使用。"""
        resolved_config = resolution_payload.get("resolved_config") or {}
        pairs = []
        for key in ["glass", "ribbon", "busbar", "cable", "cell_size", "benchmark"]:
            item = resolved_config.get(key) or {}
            if item.get("value"):
                pairs.append(f"{key}={item['value']}")
        return "；".join(pairs) if pairs else "无可展示配置"

    @staticmethod
    def _power_resolution_clarification_summary(resolution_payload: dict[str, Any], *, question: str = "") -> str:
        """为 M4 candidate / partial 状态生成追问摘要。

        参数：
            resolution_payload: M4 配置解析追溯。
            question: 用户原始问题；用于提示候选名称与用户输入项目/客户名不一致。

        返回：
            面向业务用户的追问摘要，候选态会列出受控候选名称。
        """
        if resolution_payload.get("status") == CANDIDATE_REQUIRED_STATUS:
            candidates = resolution_payload.get("candidates") or []
            count = resolution_payload.get("candidate_total_count") or len(candidates)
            candidate_labels = []
            for index, candidate in enumerate(candidates[:5], start=1):
                order_name = candidate.get("order_name") or "未命名 BOM"
                order_no = candidate.get("order_no") or "未知订单号"
                version_no = candidate.get("version_no") or "未知版本"
                candidate_labels.append(f"{index}. {order_name}（{order_no}，版本 {version_no}）")
            candidate_text = "；".join(candidate_labels) if candidate_labels else "暂无可展示候选"
            mismatch_text = PlanBomQaService._candidate_name_mismatch_text(question, candidates)
            return (
                f"当前订单条件命中 {count} 个 BOM 候选，请先确认订单或文件实例后再做功率预测。"
                f"候选包括：{candidate_text}。{mismatch_text}"
            )
        unresolved = resolution_payload.get("unresolved_items") or []
        labels = [str(item.get("factor_key")) for item in unresolved if item.get("factor_key")]
        return f"当前 BOM 配置仍有未确认项：{', '.join(labels) if labels else '未知配置'}。请确认后再执行功率预测。"

    @staticmethod
    def _candidate_name_mismatch_text(question: str, candidates: list[dict[str, Any]]) -> str:
        """识别用户输入的订单前缀是否未出现在候选 BOM 名称中。"""
        if not question or not candidates:
            return ""
        # 业务常写“客户/项目—00106”；尾号候选过多时，将破折号前的项目词与候选名做只读比对。
        match = re.search(r"(?P<token>[\u4e00-\u9fa5A-Za-z0-9/\-]+)\s*[—-]\s*\d{5}", question)
        if not match:
            return ""
        token = match.group("token").strip()
        if not token or token.upper().startswith("GCL"):
            return ""
        candidate_text = " ".join(str(candidate.get("order_name") or "") + " " + str(candidate.get("order_no") or "") for candidate in candidates)
        if token in candidate_text:
            return ""
        return f"你输入的“{token}”未匹配当前候选名称，请确认是否为同一订单/项目。"

    def _resolve_core_material_categories(
        self,
        *,
        question: str,
        nlu: PlanBomNluCandidate,
        default_categories: list[str] | None = None,
    ) -> tuple[list[str], PlanBomQaResponse | None]:
        """解析可进入当前 detail/compare 主链路的核心材料类别。

        参数：
            question: 原始问题；
            nlu: NLU 候选；
            default_categories: 未显式指定材料时的默认核心材料范围。

        返回：
            二元组：(可安全传入 Pydantic 查询 schema 的核心材料列表, 非核心材料受控响应)。
        """

        requested = list(nlu.slots.get("material_category") or [])
        core_categories = [category for category in requested if category in CORE_MATERIAL_CATEGORIES]
        invalid_or_non_core = [category for category in requested if category not in CORE_MATERIAL_CATEGORIES]
        llm_non_core = list(nlu.slots.get("non_core_material_category") or [])
        non_core_categories: list[str] = []
        for category in [*invalid_or_non_core, *llm_non_core]:
            if category and category not in non_core_categories:
                non_core_categories.append(category)
        if non_core_categories and not self._question_mentions_core_material(question):
            return [], self._non_core_material_response(question=question, nlu=nlu, categories=non_core_categories)
        if non_core_categories and not core_categories:
            return [], self._non_core_material_response(question=question, nlu=nlu, categories=non_core_categories)
        if non_core_categories:
            nlu.guardrail_notes.append(
                f"已过滤当前核心五类查询不支持的非核心材料：{', '.join(non_core_categories)}。"
            )
        return core_categories or list(default_categories or CORE_MATERIAL_CATEGORIES), None

    @staticmethod
    def _question_mentions_core_material(question: str) -> bool:
        """判断问题原文是否显式包含核心五类材料表达。

        参数：
            question: 原始问题。

        返回：
            包含核心五类或五类集合表达时返回 True。
        """

        core_words = ("玻璃", "间隙贴膜", "间隙膜", "焊带", "互联条", "汇流条", "接线盒", "线盒", "五类", "关键材料", "核心材料", "核心辅材", "关键辅材")
        return any(word in question for word in core_words)

    def _non_core_material_response(
        self,
        *,
        question: str,
        nlu: PlanBomNluCandidate,
        categories: list[str],
    ) -> PlanBomQaResponse:
        """构造非核心材料的受控降级响应。

        参数：
            question: 原始问题；
            nlu: NLU 候选；
            categories: 已识别但当前主链路不支持的材料类别。

        返回：
            B 类追问响应，避免非核心材料触发 schema 校验异常。
        """

        labels = [MATERIAL_CATEGORY_LABELS.get(category, category) for category in categories]
        nlu.missing_slots = sorted(set([*(nlu.missing_slots or []), "supported_material_category"]))
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="B",
                status=PlanBomQaStatus(
                    code="CLARIFICATION_REQUIRED",
                    message="当前材料类别不在核心五类明细查询范围内",
                    severity="warning",
                ),
                nlu=nlu,
                answer_summary=(
                    "已识别到非核心材料："
                    f"{'、'.join(labels)}。当前计划 BOM 智能问答优先支持玻璃、间隙贴膜、焊带/互联条、汇流条、接线盒五类材料；"
                    "请确认是否改问这些核心材料，或说明你希望扩展到哪类非核心材料。"
                ),
                warnings=["当前材料不在已支持的核心材料范围内，暂不进入明细查询。"],
                raw_result={"non_core_material_category": categories, "supported_categories": list(CORE_MATERIAL_CATEGORIES)},
            )
        )

    def _headers_from_tails_or_scope(self, *, tails: list[str], nlu: PlanBomNluCandidate) -> list[PlanBomHeader]:
        """按尾号或范围定位 BOM 头。

        参数：
            tails: 订单尾号；
            nlu: NLU 候选。

        返回：
            BOM 头列表。
        """

        headers: list[PlanBomHeader] = []
        if tails:
            for tail in tails:
                headers.extend(self.repository.list_active_headers(order_no_like=tail, order_name_like=tail))
            return headers
        return self.repository.list_headers_by_scope(
            year=nlu.slots.get("year"),
            model=nlu.slots.get("model"),
            country=nlu.slots.get("country"),
            limit=200,
        )

    @staticmethod
    def _select_current_headers(headers: list[PlanBomHeader]) -> list[PlanBomHeader]:
        """按业务实例选择当前版本。

        参数：
            headers: 候选 BOM 头。

        返回：
            每个业务实例一条当前版本 BOM 头。
        """

        grouped: dict[str, list[PlanBomHeader]] = {}
        for header in headers:
            grouped.setdefault(header.order_identity_key, []).append(header)
        selected: list[PlanBomHeader] = []
        for bucket in grouped.values():
            selected.append(sorted(bucket, key=lambda h: ((h.effective_date is not None, h.effective_date), h.version_no), reverse=True)[0])
        return selected

    def _non_ok_query_response(self, *, question: str, nlu: PlanBomNluCandidate, raw: dict[str, Any]) -> PlanBomQaResponse:
        """把已有查询服务的非 OK 状态转换为 QA 状态。

        参数：
            question: 原始问题；
            nlu: NLU 候选；
            raw: 原始查询结果。

        返回：
            B 或空结果响应。
        """

        status_code = raw.get("status", {}).get("code")
        if status_code in {"CANDIDATE_REQUIRED", "VERSION_NEED_CONFIRM"}:
            nlu.missing_slots.append(raw.get("candidate_scope") or "candidate")
            return self._clarification_response(question=question, nlu=nlu, raw=raw)
        return self._empty_response(question=question, nlu=nlu, reason=raw.get("status", {}).get("message", "未命中结果"), raw=raw)

    def _clarification_response(self, *, question: str, nlu: PlanBomNluCandidate, raw: dict[str, Any] | None = None) -> PlanBomQaResponse:
        """构造 B 类追问响应。

        参数：
            question: 原始问题；
            nlu: NLU 候选；
            raw: 可选原始结果。

        返回：
            B 类 QA 响应。
        """

        missing = nlu.missing_slots or ["order_id", "material_category"]
        missing_text = "、".join(self._business_missing_slot_label(slot) for slot in missing)
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="B",
                status=PlanBomQaStatus(code="CLARIFICATION_REQUIRED", message="需要补充关键信息后继续查询", severity="warning"),
                nlu=nlu,
                answer_summary=(
                    "我理解你想查询计划 BOM 信息，但当前还缺少足够的业务条件。"
                    f"请补充：{missing_text}。补充后我会继续按订单、版本和材料范围整理结果。"
                ),
                raw_result=raw or {},
            )
        )

    @staticmethod
    def _business_missing_slot_label(slot: str) -> str:
        """把内部缺失项名称转换为业务可读说明。"""

        mapping = {
            "order_id": "订单号、订单尾号或订单范围",
            "order_tail_no": "订单尾号或更完整的订单号",
            "material_category": "材料范围，例如玻璃、焊带、汇流条或接线盒",
            "compare_orders": "需要对比的订单",
            "candidate": "更完整订单号或具体文件实例",
            "order_identity": "项目名、客户或文件名等订单识别信息",
            "bom_version": "BOM 版本",
            "target_power_ratio": "目标功率档比例",
            "power_configuration": "功率预测所需配置",
            "power_factor_options": "需要对比的两个功率模型配置选项",
            "supported_material_category": "当前要查询的核心材料范围",
        }
        return mapping.get(slot, "更明确的查询条件")

    def _empty_response(self, *, question: str, nlu: PlanBomNluCandidate, reason: str, raw: dict[str, Any] | None = None) -> PlanBomQaResponse:
        """构造空结果响应。

        参数：
            question: 原始问题；
            nlu: NLU 候选；
            reason: 空结果原因；
            raw: 可选原始结果。

        返回：
            空结果 QA 响应。
        """

        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="C",
                status=PlanBomQaStatus(code="EMPTY_RESULT", message=reason, severity="warning"),
                nlu=nlu,
                answer_summary=f"当前已导入 BOM 数据中没有找到可支撑该问题的结果。原因：{reason}",
                raw_result=raw or {},
            )
        )

    def _with_presentation(self, response: PlanBomQaResponse) -> PlanBomQaResponse:
        """为 QA 响应补充 presentation。

        参数：
            response: 未带 presentation 的响应。

        返回：
            已补 presentation 的响应。
        """

        response.presentation = self.presentation_service.build_presentation(response)
        return response

    def _complete_traced_response(
        self,
        *,
        response: PlanBomQaResponse,
        trace_recorder: QaTraceRecorder,
    ) -> PlanBomQaResponse:
        """补齐 BOM QA 响应的明细节点，并写入统一查询历史。

        参数：
            response: 已完成确定性查询和 presentation 的响应；
            trace_recorder: 当前请求的节点记录器。

        返回：
            带 trace_events 的响应。
        """

        trace_recorder.add(
            "qa_result_ready",
            "BOM 确定性问答结果已生成。",
            {
                "classification": response.classification,
                "status": response.status.model_dump(mode="json"),
                "row_count": len(response.result_table.rows),
                "answer_summary": response.answer_summary,
                "warnings": response.warnings,
                "guardrail_notes": response.nlu.guardrail_notes,
            },
        )
        trace_recorder.add(
            "presentation_ready",
            "BOM 答案展示内容已生成。",
            {
                "display_type": response.presentation.display_type if response.presentation else None,
                "title": response.presentation.title if response.presentation else "",
                "answer": response.presentation.answer if response.presentation else "",
            },
        )
        response.trace_events = trace_recorder.events
        history_log_id = self._write_history_snapshot(
            question=response.question,
            trace_id=trace_recorder.trace_id,
            response=response,
        )
        trace_recorder.add(
            "history_snapshot_written",
            "BOM QA 查询历史快照写入完成。",
            {"history_log_id": history_log_id, "history_ready": bool(history_log_id)},
        )
        response.trace_events = trace_recorder.events
        logger.info(
            "plan_bom_qa_completed trace_id=%s classification=%s status=%s rows=%s history_log_id=%s",
            trace_recorder.trace_id,
            response.classification,
            response.status.code,
            len(response.result_table.rows),
            history_log_id,
        )
        return response

    def write_error_log(self, *, question: str, trace_id: str | None, message: str) -> int:
        """把 BOM QA API 异常写入统一查询历史。

        参数：
            question: 用户原始问题；
            trace_id: 当前请求追踪号；
            message: 异常摘要，写入前会截断，避免日志过大。

        返回：
            新写入的 `sys_query_log.id`；写入失败时返回 0。
        """

        safe_message = self._safe_log_message(message)
        self._rollback_before_error_log()
        response = PlanBomQaResponse(
            question=question,
            classification="D",
            status=PlanBomQaStatus(
                code="EXECUTION_ERROR",
                message="计划 BOM 问答执行异常，已记录失败快照。",
                success=False,
                severity="error",
            ),
            nlu=PlanBomNluCandidate(
                question=question,
                intent="plan_bom_qa_error",
                slots={},
                missing_slots=[],
                confidence=0.0,
                provider_mode="error",
                guardrail_notes=[safe_message],
            ),
            answer_summary=f"计划 BOM 问答执行异常：{safe_message}",
            warnings=["该记录来自 API 异常兜底日志，业务结果未完成计算。"],
            raw_result={"error_message": safe_message},
        )
        return self._write_history_snapshot(question=question, trace_id=trace_id, response=response)

    def _write_history_snapshot(
        self,
        *,
        question: str,
        trace_id: str | None,
        response: PlanBomQaResponse,
    ) -> int:
        """把 BOM QA 当前响应快照写入 sys_query_log。

        参数：
            question: 用户原始问题；
            trace_id: 当前请求追踪号；
            response: 已生成的 BOM QA 响应或异常兜底响应。

        返回：
            新写入的日志 ID；任何日志异常都被吞掉并返回 0，不影响主问答链路。
        """

        try:
            result_count = len(response.result_table.rows)
            query_result_snapshot = response.model_dump(mode="json")
            query_result_snapshot["query_type"] = "plan_bom_qa"
            query_result_snapshot["execution_mode"] = "plan_bom_qa"
            query_result_snapshot["item_count"] = result_count
            status_payload = response.status.model_dump(mode="json")
            query_plan_v2_shadow = self.query_plan_shadow_builder.build_plan_bom_snapshot(
                question=question,
                response=response,
                trace_id=trace_id,
            )
            query_plan_v2_comparison = (
                query_plan_v2_shadow.get("comparison") if isinstance(query_plan_v2_shadow.get("comparison"), dict) else {}
            )
            payload_snapshot = {
                "question": question,
                "request_payload": {"question": question, "domain": "plan_bom"},
                "response_meta": {
                    "question": question,
                    "domain": "plan_bom",
                    "mode": "plan_bom_qa",
                    "metric_type": response.nlu.intent,
                    "source_scope": "plan_bom_ai",
                    "status": status_payload,
                    "trace_ready": bool(trace_id),
                    "classification": response.classification,
                    "result_count": result_count,
                    "query_plan_v2_strategy": query_plan_v2_shadow.get("strategy"),
                    "query_plan_v2_query_key": query_plan_v2_shadow.get("query_key"),
                    "query_plan_v2_shadow_ready": True,
                    "query_plan_v2_compare_matched": query_plan_v2_comparison.get("matched"),
                    "query_plan_v2_formal_query_key": query_plan_v2_comparison.get("formal_query_key"),
                    "query_plan_v2_shadow_query_key": query_plan_v2_comparison.get("shadow_query_key"),
                    "query_plan_v2_risk_tags": list(query_plan_v2_comparison.get("risk_tags") or []),
                },
                "query_plan_v2_shadow": query_plan_v2_shadow,
                "query_result": query_result_snapshot,
            }
            log_id = self.query_log_repository.write_query_log(
                self.repository.db,
                {
                    "trace_id": trace_id or "local-dev",
                    "query_type": "PLAN_BOM_QA",
                    "question_text": question,
                    "request_payload": json.dumps(payload_snapshot, ensure_ascii=False, default=str),
                    "route_type": "plan_bom_qa",
                    "metric_type": response.nlu.intent,
                    "result_count": result_count,
                    "status": self._resolve_history_row_status(response),
                    "message": response.answer_summary,
                },
            )
            self.repository.db.commit()
            return log_id
        except Exception as exc:  # noqa: BLE001
            try:
                self.repository.db.rollback()
            except Exception as rollback_exc:  # noqa: BLE001
                logger.warning("rollback plan bom qa history snapshot failed: %s", rollback_exc)
            logger.warning("write plan bom qa history snapshot failed: %s", exc)
            return 0

    @staticmethod
    def _resolve_history_row_status(response: PlanBomQaResponse) -> str:
        """把 BOM QA 响应状态转换成 sys_query_log 列表状态。"""
        if response.status.code == "EXECUTION_ERROR" or not response.status.success:
            return "ERROR"
        if response.classification == "B" or response.status.code == "CLARIFICATION_REQUIRED":
            return "CLARIFICATION"
        if response.status.code == "UNSUPPORTED_QUESTION":
            return "UNSUPPORTED"
        if response.status.code == "EMPTY_RESULT":
            return "EMPTY_RESULT"
        return "SUCCESS"

    @staticmethod
    def _safe_log_message(message: str) -> str:
        """返回已脱敏且长度受控的异常摘要。

        参数：
            message: 原始异常文本，可能包含下游 API key、Bearer token、密码或连接串。

        返回：
            可写入 sys_query_log 的安全摘要。
        """
        text = str(message or "")
        redaction_patterns = [
            # OpenAI/兼容模型常见 sk- 前缀密钥。
            (r"sk-[A-Za-z0-9_-]{8,}", "[REDACTED]"),
            # Authorization: Bearer xxx 或 Authorization=Bearer xxx。
            (r"(?i)(authorization\s*[:=]\s*bearer\s+)([^\s,;]+)", r"\1[REDACTED]"),
            # 某些 HTTP/SDK 异常只保留独立 Bearer xxx 片段，也必须脱敏。
            (r"(?i)(\bbearer\s+)([^\s,;]+)", r"\1[REDACTED]"),
            # JSON/字典字符串中的 "api_key":"xxx"、'password': 'xxx' 等键值形式。
            (
                r"(?i)((?:[\"']?)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password|passwd|token)(?:[\"']?)\s*[:=]\s*[\"']?)([^\"',\s&;}\]]+)",
                r"\1[REDACTED]",
            ),
            # api_key=xxx、password: xxx、access_token=xxx 等无引号键值形式。
            (
                r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|secret|password|passwd|token)\s*[:=]\s*)([^,\s&;]+)",
                r"\1[REDACTED]",
            ),
            # mysql://user:password@host/db 等 URL 连接串中的密码。
            (r"(://[^:/\s]+:)([^@\s/]+)(@)", r"\1[REDACTED]\3"),
        ]
        for pattern, replacement in redaction_patterns:
            text = re.sub(pattern, replacement, text)
        return text if len(text) <= 500 else f"{text[:500]}...已截断"

    def _rollback_before_error_log(self) -> None:
        """异常兜底写日志前先清理业务 Session 的失败事务状态。"""
        try:
            self.repository.db.rollback()
        except Exception as exc:  # noqa: BLE001
            logger.warning("rollback plan bom qa session before error log failed: %s", exc)

    @staticmethod
    def _default_columns() -> list[str]:
        """返回材料明细默认列。

        返回：
            列名列表。
        """

        return ["material_category", "material_name", "description", "standard_usage", "unit"]

    @staticmethod
    def _compare_columns() -> list[str]:
        """返回对比表默认列。

        返回：
            列名列表。
        """

        return ["diff_type", "material_category", "left_order", "left_description", "right_order", "right_description", "changed_fields"]

    @staticmethod
    def _expanded_compare_columns() -> list[str]:
        """返回多候选展开对比表列。

        返回：
            列名列表；相比普通 compare 多出比较组和左右业务实例，避免短订单号多实例时丢失上下文。
        """

        return [
            "compare_pair",
            "diff_type",
            "material_category",
            "left_instance",
            "left_order",
            "left_description",
            "right_instance",
            "right_order",
            "right_description",
            "changed_fields",
        ]

    @staticmethod
    def _item_row(item: dict[str, Any]) -> dict[str, Any]:
        """转换 detail item 为表格行。

        参数：
            item: detail item 字典。

        返回：
            表格行。
        """

        return {
            "order_no": item.get("order_no"),
            "order_name": None,
            "version_no": item.get("version_no"),
            "material_category": item.get("material_category_label") or MATERIAL_CATEGORY_LABELS.get(item.get("material_category")),
            "material_name": item.get("material_name"),
            "description": item.get("description"),
            "sap_code": item.get("sap_code"),
            "standard_usage": item.get("standard_usage"),
            "unit": item.get("unit"),
            "source_file": item.get("source_tag"),
        }

    @staticmethod
    def _line_row(header: PlanBomHeader, line: PlanBomMaterialLine) -> dict[str, Any]:
        """转换材料行为表格行。

        参数：
            header: BOM 头；
            line: 材料行。

        返回：
            表格行。
        """

        return {
            "order_no": header.order_no,
            "order_name": header.order_name,
            "version_no": header.version_no,
            "material_category": MATERIAL_CATEGORY_LABELS.get(line.material_category or "", line.material_category),
            "material_name": line.material_name,
            "description": line.description,
            "sap_code": line.sap_code,
            "standard_usage": str(line.standard_usage) if line.standard_usage is not None else None,
            "unit": line.unit,
            "source_file": header.raw_file_name,
        }

    @staticmethod
    def _compare_changed_row(item: dict[str, Any]) -> dict[str, Any]:
        """转换变化差异为对比表行。

        参数：
            item: compare changed item。

        返回：
            对比表行。
        """

        return {
            "diff_type": "字段变化",
            "material_category": item.get("material_category_label"),
            "left_order": item.get("left", {}).get("order_no"),
            "left_description": item.get("left", {}).get("description"),
            "right_order": item.get("right", {}).get("order_no"),
            "right_description": item.get("right", {}).get("description"),
            "changed_fields": ",".join(item.get("changed_fields") or []),
        }

    @staticmethod
    def _compare_single_side_row(item: dict[str, Any], *, side: str) -> dict[str, Any]:
        """转换单侧独有差异为对比表行。

        参数：
            item: compare single side item；
            side: 差异侧说明。

        返回：
            对比表行。
        """

        material = item.get("item", {})
        return {
            "diff_type": side,
            "material_category": item.get("material_category_label"),
            "left_order": material.get("order_no") if side == "仅左侧" else None,
            "left_description": material.get("description") if side == "仅左侧" else None,
            "right_order": material.get("order_no") if side == "仅右侧" else None,
            "right_description": material.get("description") if side == "仅右侧" else None,
            "changed_fields": "",
        }


__all__ = ["PlanBomQaService"]
