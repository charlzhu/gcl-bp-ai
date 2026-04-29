from __future__ import annotations

import logging
from typing import Any

from backend.app.domains.plan_bom.constants import CORE_MATERIAL_CATEGORIES, MATERIAL_CATEGORY_LABELS
from backend.app.domains.plan_bom.models import PlanBomHeader, PlanBomMaterialLine
from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate, PlanBomQaResponse, PlanBomQaStatus, PlanBomTableSpec
from backend.app.domains.plan_bom.schemas.query import (
    PlanBomCompareQueryRequest,
    PlanBomCompareSideRequest,
    PlanBomDetailQueryRequest,
)
from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
from backend.app.domains.plan_bom.services.nlu_center_service import PlanBomNluCenterService
from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService
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
    ) -> None:
        """初始化 BOM QA 服务。

        参数：
            repository: BOM 查询仓储；
            query_service: 已有 detail / compare 查询服务；
            nlu_service: BOM NLU Center；
            presentation_service: BOM 答案表达层。

        返回：
            无返回值。
        """

        self.repository = repository
        self.query_service = query_service
        self.nlu_service = nlu_service
        self.presentation_service = presentation_service

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
        result = self.query_service.compare(
            PlanBomCompareQueryRequest(left=left, right=right, material_categories=categories, candidate_limit=20)
        )
        if result.status.code != "OK" or not result.compare_ready:
            return self._non_ok_query_response(question=question, nlu=nlu, raw=result.model_dump(mode="json"))
        rows: list[dict[str, Any]] = []
        for item in result.changed:
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
                    f"{'、'.join(labels)}。当前计划 BOM QA detail/compare 主链路支持玻璃、间隙贴膜、焊带/互联条、汇流条、接线盒五类材料；"
                    "请确认是否改问核心五类材料，或需要后续扩展非核心材料查询口径。"
                ),
                warnings=["非核心材料已被 Guardrail 拦截，未进入核心五类查询 schema。"],
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
        return self._with_presentation(
            PlanBomQaResponse(
                question=question,
                classification="B",
                status=PlanBomQaStatus(code="CLARIFICATION_REQUIRED", message="需要补充关键信息后继续查询", severity="warning"),
                nlu=nlu,
                answer_summary=f"当前问题缺少或存在歧义的槽位：{', '.join(missing)}。请补充订单、版本、材料或查询范围。",
                raw_result=raw or {},
            )
        )

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
        """补齐 BOM QA 响应的明细节点。

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
        logger.info(
            "plan_bom_qa_completed trace_id=%s classification=%s status=%s rows=%s",
            trace_recorder.trace_id,
            response.classification,
            response.status.code,
            len(response.result_table.rows),
        )
        return response

    @staticmethod
    def _default_columns() -> list[str]:
        """返回材料明细默认列。

        返回：
            列名列表。
        """

        return ["order_no", "order_name", "version_no", "material_category", "material_name", "description", "sap_code", "standard_usage", "unit", "source_file"]

    @staticmethod
    def _compare_columns() -> list[str]:
        """返回对比表默认列。

        返回：
            列名列表。
        """

        return ["diff_type", "material_category", "left_order", "left_description", "right_order", "right_description", "changed_fields"]

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
