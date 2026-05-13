from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.app.domains.logistics.repositories.query_repository import LogisticsQueryRepository
from backend.app.domains.logistics.repositories.data_qa_repository import LogisticsDataQaRepository
from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaPlan,
    LogisticsDataQaQueryRequest,
    LogisticsDataQaResult,
    LogisticsDataQaStatus,
    LogisticsDataQaTable,
)
from backend.app.domains.logistics.services.error_code_registry import LogisticsErrorCodeRegistry
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.llm_clarification_assist_service import LogisticsLlmClarificationAssistService
from backend.app.domains.logistics.services.llm_answer_presentation_service import LogisticsLlmAnswerPresentationService
from backend.app.domains.logistics.services.llm_unsupported_assist_service import LogisticsLlmUnsupportedAssistService
from backend.app.domains.logistics.services.llm_understanding_guardrail_service import LogisticsLlmUnderstandingGuardrailService
from backend.app.domains.logistics.schemas.llm_understanding import (
    LogisticsLlmGuardrailDecision,
    LogisticsLlmUnderstandingResult,
)
from backend.app.domains.query_planning.services.shadow_snapshot_builder import QueryPlanningV2ShadowSnapshotBuilder
from backend.app.services.qa_trace import QaTraceRecorder

logger = logging.getLogger(__name__)


class LogisticsDataQaService:
    """物流数据问答服务。

    目标：
        1. 把自然语言问题转换成受控查询计划；
        2. 基于真实结构化数据执行白名单查询；
        3. 返回摘要、表格、口径说明、数据范围和 warning。
    """

    def __init__(
        self,
        *,
        db: Session,
        repository: LogisticsDataQaRepository | None = None,
        planner: LogisticsDataQaPlanner | None = None,
        query_log_repository: LogisticsQueryRepository | None = None,
        guardrail_service: LogisticsLlmUnderstandingGuardrailService | None = None,
        clarification_assist_service: LogisticsLlmClarificationAssistService | None = None,
        unsupported_assist_service: LogisticsLlmUnsupportedAssistService | None = None,
        answer_presentation_service: LogisticsLlmAnswerPresentationService | None = None,
    ) -> None:
        self.db = db
        self.repository = repository or LogisticsDataQaRepository(db)
        self.planner = planner or LogisticsDataQaPlanner()
        self.query_log_repository = query_log_repository or LogisticsQueryRepository()
        self.guardrail_service = guardrail_service or LogisticsLlmUnderstandingGuardrailService()
        self.clarification_assist_service = clarification_assist_service or LogisticsLlmClarificationAssistService()
        self.unsupported_assist_service = unsupported_assist_service or LogisticsLlmUnsupportedAssistService()
        self.answer_presentation_service = answer_presentation_service or LogisticsLlmAnswerPresentationService()
        self.query_plan_shadow_builder = QueryPlanningV2ShadowSnapshotBuilder()

    def query(
        self,
        payload: LogisticsDataQaQueryRequest,
        *,
        trace_id: str | None = None,
    ) -> LogisticsDataQaResult:
        """执行物流数据问答。

        参数：
            payload: 当前自然语言问题。
            trace_id: 当前请求 trace_id，用于把 data-qa 结果写入统一查询历史。
        """
        trace_recorder = QaTraceRecorder(domain="logistics", trace_id=trace_id, question=payload.question)
        trace_recorder.add(
            "input_received",
            "收到物流问答用户问题。",
            {"question": payload.question},
        )
        rule_plan = self.planner.build_plan(payload.question)
        trace_recorder.add(
            "rule_plan_built",
            "规则 planner 已生成受控查询计划。",
            self._plan_trace_payload(rule_plan),
        )
        plan, guardrail_decision = self._resolve_plan_with_guardrail(
            question=payload.question,
            rule_plan=rule_plan,
            trace_id=trace_id,
        )
        trace_recorder.add(
            "guardrail_checked",
            "LLM 候选理解和 Guardrail 校验已完成。",
            {
                "final_plan": self._plan_trace_payload(plan),
                "guardrail": self._guardrail_trace_payload(guardrail_decision),
            },
        )
        if plan.intent == "unsupported":
            trace_recorder.add(
                "branch_selected",
                "问题进入 C 类受控拒答分支。",
                {"intent": plan.intent, "unsupported_category": plan.unsupported_category},
            )
            plan = self._resolve_unsupported_with_assist(
                question=payload.question,
                plan=plan,
                trace_id=trace_id,
            )
            unsupported_summary = self._build_unsupported_answer_summary(plan)
            result = LogisticsDataQaResult(
                answer_summary=unsupported_summary,
                result_table=LogisticsDataQaTable(),
                calculation_logic=[
                    "当前问题没有进入受控 query_key 白名单或超出现有结构化统计边界。",
                    "系统不会为预测、开放讨论、复杂推理或未固化口径的问题编造结果。",
                ],
                data_scope={
                    "question": payload.question,
                    "unsupported": {
                        "category": plan.unsupported_category,
                        "reason": plan.unsupported_reason,
                        "template": plan.unsupported_template,
                        "suggestions": plan.unsupported_suggestions,
                        "assist_used": plan.unsupported_assist_used,
                        "assist_provider_mode": plan.unsupported_assist_provider_mode,
                    },
                },
                query_plan=plan,
                warnings=self._build_unsupported_warnings(plan),
                supported=False,
                status=LogisticsDataQaStatus(
                    **LogisticsErrorCodeRegistry.build_status(
                        code=LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION,
                        message=unsupported_summary,
                        success=False,
                        severity="info",
                    )
                ),
            )
            return self._finalize_result(
                question=payload.question,
                trace_id=trace_id,
                result=result,
                guardrail_decision=guardrail_decision,
                trace_recorder=trace_recorder,
            )
        if plan.needs_clarification:
            trace_recorder.add(
                "branch_selected",
                "问题进入 B 类追问分支。",
                {
                    "intent": plan.intent,
                    "missing_slots": plan.clarification_missing_slots,
                    "clarification_category": plan.clarification_category,
                },
            )
            plan, clarification_summary = self._resolve_clarification_with_assist(
                question=payload.question,
                plan=plan,
                trace_id=trace_id,
            )
            result = LogisticsDataQaResult(
                answer_summary=clarification_summary,
                result_table=LogisticsDataQaTable(),
                calculation_logic=["为避免误算，系统先返回澄清问题。"],
                data_scope={
                    "question": payload.question,
                    "clarification": {
                        "category": plan.clarification_category,
                        "reason": plan.clarification_reason,
                        "missing_slots": plan.clarification_missing_slots,
                        "template": plan.clarification_template,
                        "assist_used": plan.clarification_assist_used,
                        "assist_provider_mode": plan.clarification_assist_provider_mode,
                    },
                },
                query_plan=plan,
                warnings=["当前问题需要澄清后才能继续查询。"],
                needs_clarification=True,
                clarification_questions=plan.clarification_questions,
                supported=False,
                status=LogisticsDataQaStatus(
                    **LogisticsErrorCodeRegistry.build_status(
                        code=LogisticsErrorCodeRegistry.CLARIFICATION_REQUIRED,
                        message=clarification_summary,
                        success=False,
                        severity="warning",
                    )
                ),
            )
            return self._finalize_result(
                question=payload.question,
                trace_id=trace_id,
                result=result,
                guardrail_decision=guardrail_decision,
                trace_recorder=trace_recorder,
            )
        trace_recorder.add(
            "branch_selected",
            "问题进入 A 类或空结果确定性查询分支。",
            {"intent": plan.intent, "query_key": plan.query_key},
        )
        result = self._execute_plan(payload.question, plan)
        return self._finalize_result(
            question=payload.question,
            trace_id=trace_id,
            result=result,
            guardrail_decision=guardrail_decision,
            trace_recorder=trace_recorder,
        )

    def write_error_log(
        self,
        *,
        question: str,
        trace_id: str | None,
        message: str,
    ) -> None:
        """为 data-qa 接口异常写最小错误日志。

        说明：
            1. 当前只记录最小错误快照，便于查询历史页区分错误态；
            2. 这里不吞掉原始异常，endpoint 写完日志后仍会继续抛出；
            3. 如果日志写入本身失败，只记录 warning，不影响接口错误返回。
        """
        status_payload = LogisticsErrorCodeRegistry.build_status(
            code=LogisticsErrorCodeRegistry.EXECUTION_ERROR,
            message="当前查询执行失败，请稍后重试；如持续失败，请联系管理员。",
            success=False,
            severity="error",
        )
        payload_snapshot = {
            "question": question,
            "response_meta": {
                "question": question,
                "domain": "logistics",
                "mode": "data_qa",
                "source_scope": "logistics_ai",
                "status": status_payload,
                "trace_ready": bool(trace_id),
                "result_count": 0,
            },
            "query_result": {
                "answer_summary": "当前查询执行失败，请稍后重试；如持续失败，请联系管理员。",
                "result_table": {"columns": [], "rows": []},
                "calculation_logic": [],
                "data_scope": {"question": question},
                "query_plan": {"domain": "logistics", "intent": "error", "metrics": [], "dimensions": [], "filters": {}, "group_by": [], "sort": [], "needs_clarification": False, "clarification_questions": []},
                "warnings": [message],
                "needs_clarification": False,
                "clarification_questions": [],
                "supported": False,
                "status": status_payload,
                "query_type": "data_qa",
                "execution_mode": "data_qa",
                "item_count": 0,
            },
        }
        try:
            self.query_log_repository.write_query_log(
                self.db,
                {
                    "trace_id": trace_id or "local-dev",
                    "query_type": "DATA_QA",
                    "question_text": question,
                    "request_payload": json.dumps(payload_snapshot, ensure_ascii=False, default=str),
                    "route_type": "data_qa",
                    "metric_type": "data_qa",
                    "result_count": 0,
                    "status": "ERROR",
                    "message": "当前查询执行失败，请稍后重试；如持续失败，请联系管理员。",
                },
            )
            self.db.commit()
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.warning("write data qa error log failed: %s", exc)

    def verify_assets(self) -> dict[str, Any]:
        """输出数据资产核验结果。"""
        return self.repository.verify_assets()

    def _finalize_result(
        self,
        *,
        question: str,
        trace_id: str | None,
        result: LogisticsDataQaResult,
        guardrail_decision: LogisticsLlmGuardrailDecision | None = None,
        trace_recorder: QaTraceRecorder | None = None,
    ) -> LogisticsDataQaResult:
        """补齐状态并写入历史快照。

        说明：
            1. 统一在这里给结果补状态，避免各个 query_key 分支重复判断；
            2. 写入历史失败不会影响主查询返回，只会把 `history_ready` 置为 false；
            3. 回放优先使用写入 `sys_query_log` 的快照，而不是再次实时执行查询。
        """
        if result.status is None:
            result.status = self._resolve_status(result)
        if trace_recorder:
            trace_recorder.add(
                "query_result_ready",
                "确定性查询结果已生成。",
                {
                    "status": result.status.model_dump() if result.status else None,
                    "supported": result.supported,
                    "needs_clarification": result.needs_clarification,
                    "row_count": len(result.result_table.rows),
                    "answer_summary": result.answer_summary,
                    "warnings": result.warnings,
                },
            )
        result.presentation = self.answer_presentation_service.build_presentation(
            question=question,
            result=result,
            trace_id=trace_id,
        )
        if trace_recorder:
            trace_recorder.add(
                "presentation_ready",
                "答案展示内容已生成。",
                {
                    "display_type": result.presentation.display_type if result.presentation else None,
                    "title": result.presentation.title if result.presentation else "",
                    "answer": result.presentation.answer if result.presentation else "",
                },
            )
            trace_recorder.add(
                "history_snapshot_writing",
                "准备写入统一查询历史快照。",
                {"trace_id": trace_id, "row_count": len(result.result_table.rows)},
            )
            result.trace_events = trace_recorder.events
        log_id = self._write_history_snapshot(
            question=question,
            trace_id=trace_id,
            result=result,
            guardrail_decision=guardrail_decision,
        )
        result.history_log_id = log_id or None
        result.history_ready = bool(log_id)
        if trace_recorder:
            trace_recorder.add(
                "history_snapshot_written",
                "统一查询历史快照写入完成。",
                {"history_log_id": result.history_log_id, "history_ready": result.history_ready},
            )
            result.trace_events = trace_recorder.events
        return result

    def _resolve_plan_with_guardrail(
        self,
        *,
        question: str,
        rule_plan: LogisticsDataQaPlan,
        trace_id: str | None,
    ) -> tuple[LogisticsDataQaPlan, LogisticsLlmGuardrailDecision | None]:
        """在正式主链路里受控接入 Guardrail。

        说明：
            1. 正式规则 planner 永远先跑，Guardrail 只是候选增强层；
            2. 只有规则层落入“通用兜底澄清”且满足白名单条件时，才允许尝试恢复 A 类 query_key；
            3. 一旦 assist 计划回构失败，必须无条件退回原始规则结果。
        """
        decision = self.guardrail_service.evaluate(
            question=question,
            rule_plan=rule_plan,
            trace_id=trace_id,
            write_audit=False,
        )
        if not decision.assist_applied or not decision.final_query_key:
            self.guardrail_service.write_audit_log(trace_id=trace_id, decision=decision)
            return rule_plan, decision

        llm_result = LogisticsLlmUnderstandingResult(
            normalized_question=question.strip(),
            intent=decision.llm_intent,
            filters=decision.llm_filters,
            time_range=decision.llm_time_range,
            candidate_query_keys=decision.llm_candidate_query_keys,
            normalized_terms=decision.llm_normalized_terms,
            confidence=decision.llm_confidence,
            provider_mode=decision.llm_provider_mode,
        )
        assisted_plan = self.planner.build_plan_from_guardrail_candidate(
            question,
            candidate_query_key=decision.final_query_key,
            llm_result=llm_result,
        )
        if assisted_plan is None:
            decision.assist_applied = False
            decision.final_source = "rule"
            decision.final_intent = rule_plan.intent
            decision.final_query_key = rule_plan.query_key
            decision.final_needs_clarification = rule_plan.needs_clarification
            decision.final_supported = rule_plan.intent not in {"clarification", "unsupported"}
            decision.blocked_reason = "assist_plan_build_failed"
            decision.rollback_reason = "assist_plan_build_failed"
            self.guardrail_service.write_audit_log(trace_id=trace_id, decision=decision)
            return rule_plan, decision
        self.guardrail_service.write_audit_log(trace_id=trace_id, decision=decision)
        return assisted_plan, decision

    def _resolve_status(self, result: LogisticsDataQaResult) -> LogisticsDataQaStatus:
        """按当前 data-qa 结果统一生成状态。"""
        if result.needs_clarification:
            return LogisticsDataQaStatus(
                **LogisticsErrorCodeRegistry.build_status(
                    code=LogisticsErrorCodeRegistry.CLARIFICATION_REQUIRED,
                    message="当前问题还不够明确，需先补充口径。",
                    success=False,
                    severity="warning",
                )
            )
        if not result.supported:
            return LogisticsDataQaStatus(
                **LogisticsErrorCodeRegistry.build_status(
                    code=LogisticsErrorCodeRegistry.UNSUPPORTED_QUESTION,
                    message=result.answer_summary or "当前问题暂不支持。",
                    success=False,
                    severity="info",
                )
            )
        if not result.result_table.rows:
            return LogisticsDataQaStatus(
                **LogisticsErrorCodeRegistry.build_status(
                    code=LogisticsErrorCodeRegistry.EMPTY_RESULT,
                    message=result.answer_summary or "当前未查到结果。",
                    success=True,
                    severity="warning",
                )
            )
        return LogisticsDataQaStatus(
            **LogisticsErrorCodeRegistry.build_status(
                code=LogisticsErrorCodeRegistry.OK,
                message=result.answer_summary,
                success=True,
                severity="info",
            )
        )

    @staticmethod
    def _plan_trace_payload(plan: LogisticsDataQaPlan) -> dict[str, Any]:
        """抽取查询计划中适合写入明细日志的字段。

        参数：
            plan: 当前受控查询计划。

        返回：
            可安全记录的计划摘要。
        """

        return {
            "intent": plan.intent,
            "query_key": plan.query_key,
            "metrics": plan.metrics,
            "dimensions": plan.dimensions,
            "filters": plan.filters,
            "group_by": plan.group_by,
            "limit": plan.limit,
            "needs_clarification": plan.needs_clarification,
            "clarification_missing_slots": plan.clarification_missing_slots,
            "unsupported_category": plan.unsupported_category,
        }

    @staticmethod
    def _guardrail_trace_payload(decision: LogisticsLlmGuardrailDecision | None) -> dict[str, Any] | None:
        """抽取 Guardrail 决策摘要。

        参数：
            decision: LLM 候选理解的 Guardrail 裁决。

        返回：
            Guardrail 摘要；无决策时返回 None。
        """

        if decision is None:
            return None
        return {
            "assist_applied": decision.assist_applied,
            "final_source": decision.final_source,
            "final_intent": decision.final_intent,
            "final_query_key": decision.final_query_key,
            "final_supported": decision.final_supported,
            "final_needs_clarification": decision.final_needs_clarification,
            "blocked_reason": decision.blocked_reason,
            "rollback_reason": decision.rollback_reason,
            "llm_provider_mode": decision.llm_provider_mode,
            "llm_confidence": decision.llm_confidence,
        }

    def _write_history_snapshot(
        self,
        *,
        question: str,
        trace_id: str | None,
        result: LogisticsDataQaResult,
        guardrail_decision: LogisticsLlmGuardrailDecision | None = None,
    ) -> int:
        """把 data-qa 当前结果快照写入统一查询历史。"""
        try:
            query_result_snapshot = result.model_dump(mode="json")
            query_result_snapshot["query_type"] = "data_qa"
            query_result_snapshot["execution_mode"] = "data_qa"
            query_result_snapshot["item_count"] = len(result.result_table.rows)
            query_plan_v2_shadow = self.query_plan_shadow_builder.build_logistics_snapshot(
                question=question,
                result=result,
                trace_id=trace_id,
                guardrail_decision=guardrail_decision,
            )
            payload_snapshot = {
                "question": question,
                "request_payload": {"question": question},
                "response_meta": {
                    "question": question,
                    "domain": "logistics",
                    "mode": "data_qa",
                    "metric_type": result.query_plan.query_key or (result.query_plan.metrics[0] if result.query_plan.metrics else "data_qa"),
                    "source_scope": "logistics_ai",
                    "status": result.status.model_dump() if result.status else {},
                    "trace_ready": bool(trace_id),
                    "result_count": len(result.result_table.rows),
                    "guardrail": guardrail_decision.model_dump(mode="json") if guardrail_decision else None,
                    "query_plan_v2_strategy": query_plan_v2_shadow.get("strategy"),
                    "query_plan_v2_query_key": query_plan_v2_shadow.get("query_key"),
                    "query_plan_v2_shadow_ready": True,
                },
                "query_plan_v2_shadow": query_plan_v2_shadow,
                "query_result": query_result_snapshot,
            }
            log_id = self.query_log_repository.write_query_log(
                self.db,
                {
                    "trace_id": trace_id or "local-dev",
                    "query_type": "DATA_QA",
                    "question_text": question,
                    "request_payload": json.dumps(payload_snapshot, ensure_ascii=False, default=str),
                    "route_type": "data_qa",
                    "metric_type": result.query_plan.query_key or (result.query_plan.metrics[0] if result.query_plan.metrics else "data_qa"),
                    "result_count": len(result.result_table.rows),
                    "status": self._resolve_history_row_status(result),
                    "message": result.answer_summary,
                },
            )
            self.db.commit()
            return log_id
        except Exception as exc:  # noqa: BLE001
            self.db.rollback()
            logger.warning("write data qa history snapshot failed: %s", exc)
            return 0

    @staticmethod
    def _resolve_history_row_status(result: LogisticsDataQaResult) -> str:
        """生成历史列表级状态标签。"""
        if result.status and result.status.code == LogisticsErrorCodeRegistry.EXECUTION_ERROR:
            return "ERROR"
        if result.needs_clarification:
            return "CLARIFICATION"
        if not result.supported:
            return "UNSUPPORTED"
        if not result.result_table.rows:
            return "EMPTY_RESULT"
        return "SUCCESS"

    def _execute_plan(self, question: str, plan: LogisticsDataQaPlan) -> LogisticsDataQaResult:
        """执行受控查询计划。"""
        warnings: list[str] = []
        filters = plan.filters

        if plan.query_key == "composite_decomposed":
            return self._execute_composite_decomposed_plan(question, plan)

        if plan.query_key == "hist_total_fee_city_rank":
            data = self.repository.hist_total_fee_city_rank(
                year=filters["year"],
                province=filters["province"],
                top_n=plan.limit or 5,
            )
            summary = f"{filters['year']}年{filters['province']}总运费为{int(data['total_fee'] or 0)}元。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["city", "total_fee"],
                table_rows=data["items"],
                calculation_logic=[
                    "历史口径按 dwd_logistics_hist_shipment_detail.total_fee 汇总。",
                    "省份字段使用历史明细表 province，城市字段使用 city。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", "year": filters["year"], "province": filters["province"]},
                warnings=warnings,
            )

        if plan.query_key == "hist_avg_fee_by_month":
            data = self.repository.hist_avg_fee_by_month(
                year=filters["year"],
                origin_place=filters["origin_place"],
                province=filters["province"],
                vehicle_type=filters["vehicle_type"],
            )
            summary = (
                f"{filters['year']}年{filters['origin_place']}基地发往{filters['province']}的{filters['vehicle_type']}车，"
                f"整体样本平均运费约为{int(data['overall_avg_fee'] or 0):,}元，"
                f"月均值再平均约为{int(data['avg_of_monthly_avgs'] or 0):,}元。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["biz_month", "avg_fee"],
                table_rows=data["items"],
                calculation_logic=[
                    "平均运费按历史明细 total_fee 做 AVG 计算。",
                    "整体样本平均直接对全部命中明细做 AVG(total_fee)。",
                    "月均值再平均先按月份计算 AVG(total_fee)，再对月份结果做一次 AVG。",
                    "车型按 required_vehicle_type 模糊匹配，例如 17.5。"
                ],
                data_scope={
                    "table": "dwd_logistics_hist_shipment_detail",
                    "year": filters["year"],
                    "origin_place": filters["origin_place"],
                    "province": filters["province"],
                    "vehicle_type": filters["vehicle_type"],
                },
                warnings=warnings,
            )

        if plan.query_key == "hist_avg_fee_per_watt_by_transport":
            data = self.repository.hist_avg_fee_per_watt_by_transport(region_name=filters["region_name"])
            summary = (
                f"{filters['region_name']}区域各运输方式的平均元/瓦已按成本从低到高排序。"
                if data else f"{filters['region_name']}区域未找到可计算元/瓦的数据。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["transport_mode", "avg_fee_per_watt"],
                table_rows=data,
                calculation_logic=[
                    "平均元/瓦按 SUM(total_fee) / SUM(actual_watt) 加权计算，仅纳入 actual_watt 大于 0 的历史明细。",
                    "运输方式口径中，汽运与公路统一归并到公路。"
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", "region_name": filters["region_name"]},
                warnings=warnings,
            )

        if plan.query_key == "hist_extra_fee_ratio_peak_month":
            data = self.repository.hist_extra_fee_ratio_peak_month(year=filters["year"])
            if not data:
                warnings.append("当前年份没有可用的额外费用数据。")
            summary = (
                f"{filters['year']}年额外费用占比最高的是{data['biz_month']}月，额外费用{int(data['extra_fee_amount'] or 0):,}元，"
                f"占总费用{data['extra_fee_ratio']}%。"
                if data else f"{filters['year']}年未找到额外费用占比数据。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["biz_month", "extra_fee_amount", "total_fee_amount", "extra_fee_ratio"],
                table_rows=[data] if data else [],
                calculation_logic=[
                    "额外费用总额使用 extra_fee 汇总。",
                    "占比 = SUM(extra_fee) / SUM(total_fee)。"
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", "year": filters["year"]},
                warnings=warnings,
            )

        if plan.query_key == "hist_total_fee_by_origin_and_carrier":
            data = self.repository.hist_total_fee_by_origin_and_carrier(
                year=filters["year"],
                origin_place=filters["origin_place"],
                carrier_name=filters["carrier_name"],
            )
            summary = f"{filters['year']}年{filters['origin_place']}基地、承运商{filters['carrier_name']}的总运费为{int(data['total_fee'] or 0):,}元。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["total_fee"],
                table_rows=[data],
                calculation_logic=["总运费使用历史明细 total_fee 汇总。"],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_top_customers_fee_and_mw_by_province":
            top_n = filters.get("top_n", plan.limit or 5)
            data = self.repository.hist_top_customers_fee_and_mw_by_province(
                year=filters["year"],
                province=filters["province"],
                top_n=top_n,
            )
            scope_text = (
                f"{filters['year']}年{filters['province']}"
                if filters.get("year")
                else f"{filters['province']}历史累计"
            )
            summary = (
                f"{scope_text}发运记录中，按客户名称统计的前{top_n}名客户"
                "总费用和总发运量已返回。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["customer_name", "total_fee", "shipment_mw"],
                table_rows=data,
                calculation_logic=[
                    "客户排名按历史台账 total_fee 汇总降序排序。",
                    "发运量口径按 actual_watt 汇总后折算为 MW。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_customer_mw_ranking":
            top_n = filters.get("top_n", plan.limit or 10)
            data = self.repository.hist_customer_mw_ranking(
                year=filters.get("year"),
                top_n=top_n,
            )
            summary = f"{data['scope_label']}总发运瓦数最高的前{top_n}个客户已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["customer_name", "shipment_mw"],
                table_rows=data["items"],
                calculation_logic=[
                    "历史客户排行按 actual_watt 汇总后折算为 MW。",
                    "未给年份时默认按 2023–2025 历史台账累计统计。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters, "scope_label": data["scope_label"]},
                warnings=warnings,
            )

        if plan.query_key == "hist_total_fee_by_province":
            data = self.repository.hist_total_fee_by_province(
                province=filters["province"],
                year=filters.get("year"),
                years=filters.get("years"),
            )
            summary = f"{data['scope_label']}{filters['province']}省总费用为{int(data.get('total_fee') or 0):,}元。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["scope_label", "province", "total_fee", "shipment_mw", "row_count"],
                table_rows=[{**data, "province": filters["province"]}],
                calculation_logic=[
                    "历史总费用按 dwd_logistics_hist_shipment_detail.total_fee 汇总。",
                    "未给年份时默认按 2023–2025 历史台账累计统计。",
                    "同时返回发运量 MW 和命中行数，便于复核统计范围。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "mixed_total_fee_summary_2023_2026":
            data = self.repository.mixed_total_fee_summary_2023_2026(
                months=filters.get("months"),
                region_name=filters.get("region_name"),
                transport_mode=filters.get("transport_mode"),
                carrier_name=filters.get("carrier_name"),
                customer_name=filters.get("customer_name"),
            )
            scope_parts = [data["scope_label"]]
            if filters.get("region_name"):
                scope_parts.append(f"{filters['region_name']}区域")
            if filters.get("transport_mode"):
                scope_parts.append(f"{filters['transport_mode']}运输")
            if filters.get("carrier_name"):
                scope_parts.append(f"承运商{filters['carrier_name']}")
            if filters.get("customer_name"):
                scope_parts.append(f"客户{filters['customer_name']}")
            scope_text = "".join(scope_parts)
            summary = f"{scope_text}总运费为{int(data.get('total_fee') or 0):,}元。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=[
                    "scope_label",
                    "total_fee",
                    "hist_total_fee",
                    "sys_2026_total_fee",
                    "shipment_mw",
                    "hist_row_count",
                    "sys_2026_task_count",
                ],
                table_rows=[data],
                calculation_logic=[
                    "未给年月日时，默认查询 2023-2026 全时间范围。",
                    "2023-2025 使用历史物流台账 total_fee 汇总，2026 使用正式系统费用口径汇总。",
                    "如限定区域、运输方式、承运商或客户，会在历史侧和 2026 系统侧分别应用可映射过滤条件。",
                ],
                data_scope={"table": "mixed:hist_2023_2025 + sys_2026", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_total_fee_summary":
            data = self.repository.hist_total_fee_summary(
                year=filters["year"],
                months=filters.get("months"),
                region_name=filters.get("region_name"),
                transport_mode=filters.get("transport_mode"),
                carrier_name=filters.get("carrier_name"),
                customer_name=filters.get("customer_name"),
            )
            scope_parts = [data["scope_label"]]
            if filters.get("region_name"):
                scope_parts.append(f"{filters['region_name']}区域")
            if filters.get("transport_mode"):
                scope_parts.append(f"{filters['transport_mode']}运输")
            if filters.get("carrier_name"):
                scope_parts.append(f"承运商{filters['carrier_name']}")
            if filters.get("customer_name"):
                scope_parts.append(f"客户{filters['customer_name']}")
            scope_text = "".join(scope_parts)
            if filters.get("include_share"):
                summary = (
                    f"{scope_text}总运费为{int(data.get('total_fee') or 0):,}元，"
                    f"占同口径总运费比例为{data.get('total_fee_share_pct') or 0}%。"
                )
            else:
                if plan.metrics == ["shipment_trip_count"]:
                    summary = f"{scope_text}承运车次为{int(data.get('shipment_trip_count') or 0):,}车次。"
                else:
                    summary = f"{scope_text}总运费为{int(data.get('total_fee') or 0):,}元。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=[
                    "scope_label",
                    "total_fee",
                    "shipment_mw",
                    "shipment_trip_count",
                    "row_count",
                    "denominator_total_fee",
                    "total_fee_share_pct",
                ],
                table_rows=[data],
                calculation_logic=[
                    "历史总运费按 dwd_logistics_hist_shipment_detail.total_fee 汇总。",
                    "发运量 MW 使用 actual_watt 汇总后除以 1,000,000，作为统计范围复核字段。",
                    "如问题包含承运商或客户占比，占比 = 当前过滤条件总运费 / 同年份同月份同区域同运输方式总运费。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_product_spec_mw_summary":
            data = self.repository.hist_product_spec_mw_summary(product_spec=filters["product_spec"])
            summary = (
                f"2023-2025历史台账中，规格{filters['product_spec']}的总发运瓦数为"
                f"{int(data.get('shipment_watt') or 0):,}W，折合{data.get('shipment_mw') or 0}MW。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["shipment_watt", "shipment_mw", "row_count", "matched_spec_count"],
                table_rows=[data],
                calculation_logic=[
                    "历史规格总瓦数按 dwd_logistics_hist_shipment_detail.actual_watt 汇总。",
                    "历史范围锁定 2023-2025 年台账，规格按 product_spec 模糊匹配。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_transport_mode_record_summary":
            data = self.repository.hist_transport_mode_record_summary(
                transport_mode=filters["transport_mode"],
                years=filters.get("years"),
            )
            scope_text = "、".join(f"{year}年" for year in data["years"])
            summary = (
                f"{scope_text}历史台账中，{filters['transport_mode']}口径发运记录数为"
                f"{int(data.get('record_count') or 0):,}条，占全部历史记录{data.get('record_share_pct') or 0}%。"
            )
            rows = [
                {
                    "category": "总体",
                    "item": f"{data['transport_mode']}记录",
                    "record_count": data["record_count"],
                    "record_share_pct": data["record_share_pct"],
                }
            ]
            rows.extend(
                {
                    "category": "省份",
                    "item": row.get("province"),
                    "record_count": row.get("record_count"),
                    "record_share_pct": None,
                }
                for row in data.get("top_provinces", [])
                if row.get("province")
            )
            rows.extend(
                {
                    "category": "月份",
                    "item": row.get("biz_month"),
                    "record_count": row.get("record_count"),
                    "record_share_pct": None,
                }
                for row in data.get("top_months", [])
                if row.get("biz_month") is not None
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["category", "item", "record_count", "record_share_pct"],
                table_rows=rows,
                calculation_logic=[
                    "发运记录数按历史台账行数 COUNT(*) 统计。",
                    "公路口径合并“公路/汽运”，铁路口径合并“铁路/铁运”。",
                    "同时在结果附带省份和月份集中分布，供业务解释使用。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_remark_keyword_amount_summary":
            data = self.repository.hist_remark_keyword_amount_summary(
                year=int(filters["year"]),
                keywords=filters["keywords"],
            )
            keywords_text = "/".join(filters["keywords"])
            summary = (
                f"{int(filters['year'])}年历史台账备注包含{keywords_text}的记录数量为"
                f"{int(data.get('keyword_record_count') or 0):,}条，费用金额为"
                f"{int(data.get('keyword_total_fee') or 0):,}元。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["year", "keywords", "keyword_record_count", "keyword_total_fee", "total_record_count"],
                table_rows=[data],
                calculation_logic=[
                    "按 dwd_logistics_hist_shipment_detail.biz_year 限定历史年份。",
                    "在 remark 字段中按关键词 OR 匹配，命中记录只计数一次。",
                    "费用金额按命中记录的 total_fee 汇总。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_remark_keyword_fee_ratio":
            data = self.repository.hist_remark_keyword_fee_ratio(keywords=filters["keywords"])
            summary = (
                f"2023-2025历史台账备注包含{'/'.join(filters['keywords'])}的记录总费用为"
                f"{int(data.get('keyword_total_fee') or 0):,}元，占历史总费用{data.get('fee_share_pct') or 0}%。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["keywords", "keyword_total_fee", "total_fee", "keyword_record_count", "total_record_count", "fee_share_pct"],
                table_rows=[data],
                calculation_logic=[
                    "先在 remark 字段中匹配倒运/中转关键词，再汇总命中记录 total_fee。",
                    "占比 = 命中关键词记录总费用 / 2023-2025 历史台账总费用。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_high_fee_addresses_by_customer":
            data = self.repository.hist_high_fee_addresses_by_customer(
                year=filters["year"],
                customer_name=filters["customer_name"],
                threshold_fee=filters["threshold_fee"],
            )
            rows = data or [
                {
                    "address": "无",
                    "province": None,
                    "city": None,
                    "total_fee": 0,
                    "shipment_mw": 0,
                    "row_count": 0,
                }
            ]
            summary = (
                f"{filters['year']}年客户{filters['customer_name']}发货项目地中，"
                f"运费超过{int(filters['threshold_fee']):,}元的收货地址共{len(data)}个。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["address", "province", "city", "total_fee", "shipment_mw", "row_count"],
                table_rows=rows,
                calculation_logic=[
                    "按客户名前缀过滤历史台账，再按收货地址汇总 total_fee。",
                    "只返回汇总运费超过阈值的地址，默认阈值为 20 万元。",
                    "如果没有超过阈值的地址，返回零值行，避免把“没有命中”误判为系统不可答。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_quarter_region_metric":
            data = self.repository.hist_quarter_region_metric(
                year=filters["year"],
                quarter=filters["quarter"],
                metric=filters["metric"],
            )
            metric_label = {
                "shipment_mw": "发运量",
                "unit_fee_per_watt": "单瓦运输成本",
                "total_fee": "运费",
            }.get(filters["metric"], "指标")
            summary = f"{filters['year']}年{filters['quarter']}各区域{metric_label}已按区域排序返回。"
            table_columns = (
                ["region_name", "shipment_mw", "row_count"]
                if filters["metric"] == "shipment_mw"
                else ["region_name", filters["metric"], "shipment_mw", "row_count"]
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=table_columns,
                table_rows=data,
                calculation_logic=[
                    "季度口径按发货日期月份映射 Q1-Q4。",
                    "运费按 total_fee 汇总；单瓦运输成本按 SUM(total_fee) / SUM(actual_watt) 计算。",
                    "结果按指标从高到低排序。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_carrier_kpi_by_year":
            # 城市是本 query_key 的可选筛选条件；只有用户明确给出城市时才下推，
            # 这样既避免丢失用户给出的城市范围，也兼容只支持 region_name 的既有测试替身。
            carrier_kpi_kwargs: dict[str, Any] = {
                "year": filters["year"],
                "region_name": filters.get("region_name"),
            }
            if filters.get("city"):
                carrier_kpi_kwargs["city"] = filters["city"]
            data = self.repository.hist_carrier_kpi_by_year(**carrier_kpi_kwargs)
            view_mode = filters.get("view_mode", "full_kpi")
            scope_parts = []
            if filters.get("region_name"):
                scope_parts.append(f"{filters['region_name']}区域")
            if filters.get("city"):
                scope_parts.append(f"{filters['city']}城市")
            scope_text = "".join(scope_parts)
            if view_mode == "fee_only":
                summary = f"{filters['year']}年{scope_text}各物流承运商年度运输费用已汇总返回。"
            else:
                summary = (
                    f"{filters['year']}年{scope_text}各物流承运商的发运量、占比和运费总额已汇总返回。"
                )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["carrier_name", "shipment_mw", "shipment_share_pct", "total_fee"],
                table_rows=data["items"],
                calculation_logic=[
                    "承运量默认按历史 actual_watt 汇总后折算为 MW。",
                    "承运量占比 = 当前承运商 shipment_mw / 当前查询范围内全部承运商 shipment_mw。",
                    "运费总额按历史 total_fee 汇总。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "mixed_mw_by_all_regions_2023_2026":
            data = self.repository.mixed_mw_by_all_regions_2023_2026(
                months=filters.get("months"),
                transport_mode=filters.get("transport_mode"),
            )
            summary = "2023-2026年各区域发运量汇总已按区域拆分返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["region_name", "shipment_mw", "hist_shipment_mw", "sys_2026_shipment_mw"],
                table_rows=data,
                calculation_logic=[
                    "未给年月日时，默认查询 2023-2026 全时间范围。",
                    "2023-2025 与 2026 数据分别按统一发运量口径折算为 MW 后合并。",
                    "本次按区域分组展示，不把各区域相加成单行总和。",
                ],
                data_scope={"business_scope": "2023-2026年物流发运量", **filters},
                warnings=warnings,
            )

        if plan.query_key == "mixed_mw_summary_2023_2026":
            data = self.repository.mixed_mw_summary_2023_2026(
                months=filters.get("months"),
                region_name=filters.get("region_name"),
                transport_mode=filters.get("transport_mode"),
            )
            scope_parts = [data["scope_label"]]
            if filters.get("region_name"):
                scope_parts.append(f"{filters['region_name']}区域")
            if filters.get("transport_mode"):
                scope_parts.append(f"{filters['transport_mode']}运输")
            scope_text = "".join(scope_parts)
            summary = f"{scope_text}总发运量为{data.get('shipment_mw') or 0}MW。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=[
                    "scope_label",
                    "shipment_mw",
                    "hist_shipment_mw",
                    "sys_2026_shipment_mw",
                    "hist_row_count",
                    "sys_2026_task_count",
                ],
                table_rows=[data],
                calculation_logic=[
                    "未给年月日时，默认查询 2023-2026 全时间范围。",
                    "2023-2025 使用历史台账 actual_watt 汇总后折算 MW，2026 使用正式系统 power × quantity 折算 MW。",
                    "如限定区域或运输方式，会在历史侧和 2026 系统侧分别应用可映射过滤条件。",
                ],
                data_scope={"table": "mixed:hist_2023_2025 + sys_2026", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_mw_summary":
            data = self.repository.hist_mw_summary(
                year=filters["year"],
                months=filters.get("months"),
                customer_name=filters.get("customer_name"),
                region_name=filters.get("region_name"),
                origin_place=filters.get("origin_place"),
                carrier_name=filters.get("carrier_name"),
                transport_mode=filters.get("transport_mode"),
            )
            month_text = ""
            if filters.get("months"):
                month_text = "".join(f"{month}月" for month in filters["months"])
            scope_parts = [f"{filters['year']}年"]
            if month_text:
                scope_parts.append(month_text)
            if filters.get("region_name"):
                scope_parts.append(f"{filters['region_name']}区域")
            if filters.get("customer_name"):
                scope_parts.append(filters["customer_name"])
            if filters.get("origin_place"):
                scope_parts.append(f"{filters['origin_place']}基地")
            if filters.get("carrier_name"):
                scope_parts.append(filters["carrier_name"])
            if filters.get("transport_mode"):
                scope_parts.append(f"{filters['transport_mode']}运输")
            scope_text = "".join(scope_parts)
            summary = f"{scope_text}总发运量为{data['shipment_mw'] or 0}MW。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["shipment_mw"],
                table_rows=[data],
                calculation_logic=["历史发运量 MW 使用 actual_watt 汇总后除以 1,000,000。"],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_mw_by_origin_and_carrier":
            data = self.repository.hist_mw_by_origin_and_carrier(
                year=filters["year"],
                origin_place=filters["origin_place"],
                carrier_name=filters["carrier_name"],
            )
            summary = (
                f"{filters['year']}年{filters['origin_place']}基地、承运商{filters['carrier_name']}的总发运量为"
                f"{data['shipment_mw'] or 0}MW。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["shipment_mw"],
                table_rows=[data],
                calculation_logic=["历史发运量 MW 使用 actual_watt 汇总后除以 1,000,000。"],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_mw_by_region_province":
            data = self.repository.hist_mw_by_region_province(
                year=filters["year"],
                region_name=filters["region_name"],
                provinces=filters.get("provinces"),
            )
            summary = f"{filters['year']}年{filters['region_name']}区域各省发运量已拆分返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["province", "shipment_mw"],
                table_rows=data,
                calculation_logic=["历史发运量 MW 使用 actual_watt 汇总后除以 1,000,000，并按省份分组。"],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_mw_by_all_regions":
            data = self.repository.hist_mw_by_all_regions(
                year=filters["year"],
                carrier_name=filters.get("carrier_name"),
                regions=filters.get("regions"),
            )
            scope_parts = [f"{filters['year']}年"]
            if filters.get("carrier_name"):
                scope_parts.append(str(filters["carrier_name"]))
            if filters.get("regions"):
                scope_parts.append("、".join(str(item) for item in filters["regions"]))
            else:
                scope_parts.append("各区域")
            summary = f"{''.join(scope_parts)}发运量汇总已按区域拆分返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["region_name", "shipment_mw"],
                table_rows=data,
                calculation_logic=["历史发运量按已入库的实际发运瓦数汇总后折算为 MW，并按区域分组。"],
                data_scope={"business_scope": "历史物流发运量", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_monthly_total_fee_by_year":
            years = filters.get("years") or ([filters["year"]] if filters.get("year") else [])
            if not years:
                warnings.append("缺少年份过滤条件，无法执行历史月度总费用查询。")
                return self._build_result(
                    answer_summary="请补充需要查询的历史年份，例如 2025 年或 2023–2025 年。",
                    plan=plan,
                    table_columns=["biz_month", "total_fee"],
                    table_rows=[],
                    calculation_logic=["历史月度总费用查询必须先明确 2023–2025 范围内的年份。"],
                    data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                    warnings=warnings,
                )
            data = self.repository.hist_monthly_total_fee_by_year(years=years)
            scope_label = f"{min(years)}–{max(years)}年" if len(years) > 1 else f"{years[0]}年"
            calculation_logic = ["月度运费按历史台账 total_fee 汇总，并按 YYYY-MM 升序返回。"]
            if len(years) > 1:
                calculation_logic.append("跨年度问题保留 year-month 粒度，不把不同年份的同月份合并。")
            summary = f"{scope_label}各月物流总费用已按 year-month 月份粒度返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["biz_month", "total_fee"],
                table_rows=data,
                calculation_logic=calculation_logic,
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_monthly_metric_by_filters":
            data = self.repository.hist_monthly_metric_by_filters(
                years=filters["years"],
                region_name=filters.get("region_name"),
                province=filters.get("province"),
            )
            scope_parts = [f"{min(filters['years'])}-{max(filters['years'])}年"]
            if filters.get("region_name"):
                scope_parts.append(f"{filters['region_name']}区域")
            if filters.get("province"):
                scope_parts.append(f"{filters['province']}省")
            summary = f"{''.join(scope_parts)}按月份汇总的发运量和总费用已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["biz_month", "shipment_mw", "total_fee", "row_count"],
                table_rows=data,
                calculation_logic=[
                    "月份按发货日期月份 MONTH(biz_date) 统计，跨年题按同月份合并汇总。",
                    "发运量按 SUM(actual_watt) / 1,000,000 计算；总费用按 SUM(total_fee) 计算。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_unit_fee_per_watt":
            data = self.repository.hist_unit_fee_per_watt(
                year=filters["year"],
                province=filters.get("province"),
                months=filters.get("months"),
                include_extra_fee=filters.get("include_extra_fee", False),
                transport_mode=filters.get("transport_mode"),
                carrier_name=filters.get("carrier_name"),
                monthly_breakdown=bool(filters.get("monthly_breakdown")),
            )
            scope_label = filters.get("province") or filters.get("transport_mode") or filters.get("carrier_name") or ""
            if filters.get("monthly_breakdown"):
                # 用户明确要求 1-12 月或按月展示时，保留月份粒度，避免服务层把已下推的 monthly_breakdown 压平成总计行。
                monthly_rows = data if isinstance(data, list) else data.get("monthly_rows", [])
                summary = f"{filters['year']}年{scope_label}按月单瓦运输成本已返回。"
                return self._build_result(
                    answer_summary=summary,
                    plan=plan,
                    table_columns=["biz_month", "total_fee_amount", "extra_fee_amount", "shipment_mw", "unit_fee_per_watt"],
                    table_rows=monthly_rows,
                    calculation_logic=[
                        "月度单瓦价默认按当月 total_fee / actual_watt。",
                        "当问题明确要求“运费+额外费用”时，再把当月 extra_fee 一并纳入分子。",
                        "月份粒度按历史台账 biz_date 对应 YYYY-MM 返回。",
                    ],
                    data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                    warnings=warnings,
                )
            summary = (
                f"{filters['year']}年{scope_label}单瓦运输成本为"
                f"{data.get('unit_fee_per_watt') or 0}元/瓦。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["unit_fee_per_watt", "total_fee_amount", "extra_fee_amount", "shipment_mw"],
                table_rows=[data],
                calculation_logic=[
                    "单瓦价默认按 total_fee / actual_watt。",
                    "当问题明确要求“运费+额外费用”时，再把 extra_fee 一并纳入分子。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_city_mw_rank":
            data = self.repository.hist_city_mw_rank(
                year=filters["year"],
                top_n=int(filters.get("top_n") or plan.limit or 10),
                region_name=filters.get("region_name"),
                province=filters.get("province"),
            )
            scope_label = data.get("scope_label") or f"{filters['year']}年"
            summary = f"{scope_label}城市发运量前{int(filters.get('top_n') or plan.limit or 10)}名已按 MW 返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["city", "shipment_mw"],
                table_rows=data.get("items") or [],
                calculation_logic=[
                    "历史城市发运量按 actual_watt 汇总后除以 1,000,000 折算为 MW。",
                    "当问题给出区域或省份时，先下推对应过滤条件，再按城市分组排序。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_route_pricing_analysis":
            data = self.repository.hist_route_pricing_analysis(
                years=filters["years"],
                vehicle_type=filters["vehicle_type"],
                view_mode=filters["view_mode"],
                origin_place=filters.get("origin_place"),
                province=filters.get("province"),
                city=filters.get("city"),
                price_metric=filters.get("price_metric", "total_fee"),
            )
            view_mode = filters["view_mode"]
            price_metric = filters.get("price_metric", "total_fee")
            price_metric_label = "单价/车" if price_metric == "unit_price_per_vehicle" else "总费用"
            price_summary_label = "报价" if price_metric == "unit_price_per_vehicle" else "运费"
            if filters.get("default_year_scope_label"):
                scope_parts = [filters["default_year_scope_label"]]
                warnings.append(
                    f"当前题目未明确统计年份与指标口径，系统默认按{filters['default_year_scope_label']}平均运费返回。"
                )
            elif view_mode == "year_compare":
                ordered_years = sorted({int(year) for year in filters["years"]})
                scope_parts = ["与".join(f"{year}年" for year in ordered_years)]
            else:
                scope_parts = [f"{year}年" for year in filters["years"]]
            if filters.get("origin_place"):
                scope_parts.append(f"{filters['origin_place']}发")
            if filters.get("province"):
                scope_parts.append(filters["province"])
            if filters.get("city"):
                scope_parts.append(filters["city"])
            scope_parts.append(f"{filters['vehicle_type']}车")
            scope_text = "".join(scope_parts)
            if view_mode == "monthly_avg":
                summary = f"{scope_text}每月平均{price_summary_label}已按月份返回。"
                table_columns = ["biz_month", "avg_fee", "row_count"]
            elif view_mode == "year_compare":
                missing_years = [int(year) for year in data.get("missing_years") or []]
                summary = f"{scope_text}{price_summary_label}对比已按年份返回。"
                if missing_years:
                    missing_year_text = "、".join(f"{year}年" for year in missing_years)
                    summary = f"{summary}其中{missing_year_text}无匹配记录。"
                    warnings.append(
                        f"{scope_text}在{missing_year_text}无匹配记录，已保留空值行，避免显式年份被静默遗漏。"
                    )
                table_columns = ["biz_year", "avg_fee", "row_count"]
            elif view_mode == "fee_extremes":
                summary_row = data["summary_row"] or {}
                summary = (
                    f"{scope_text}最高{price_summary_label}为{int(summary_row.get('max_fee') or 0):,}元，"
                    f"最低{price_summary_label}为{int(summary_row.get('min_fee') or 0):,}元。"
                )
                table_columns = ["min_fee", "max_fee", "avg_fee", "row_count"]
            else:
                summary_row = data["summary_row"] or {}
                summary = f"{scope_text}平均{price_summary_label}为{int(summary_row.get('avg_fee') or 0):,}元。"
                table_columns = ["avg_fee", "row_count"]
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=table_columns,
                table_rows=data["items"],
                calculation_logic=[
                    f"历史线路{price_summary_label}按 dwd_logistics_hist_shipment_detail.{price_metric}（{price_metric_label}）统计。",
                    "当问题指定城市时优先按 city 模糊过滤，兼容广州/广州市等同一城市写法；否则按 province 过滤。",
                    "车型口径通过 required_vehicle_type 模糊匹配实现。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_route_aggregate_summary":
            data = self.repository.hist_route_aggregate_summary(
                year=filters["year"],
                origin_place=filters["origin_place"],
                metric=filters["metric"],
                province=filters.get("province"),
                city=filters.get("city"),
            )
            destination_text = filters.get("city") or filters.get("province") or ""
            if filters["metric"] == "shipment_mw":
                summary = (
                    f"{filters['year']}年{filters['origin_place']}基地发往{destination_text}"
                    f"总发运量为{data.get('shipment_mw') or 0}MW。"
                )
            elif filters["metric"] == "avg_fee_per_trip":
                summary = (
                    f"{filters['year']}年{filters['origin_place']}基地发往{destination_text}"
                    f"平均每车运费为{int(data.get('avg_fee_per_trip') or 0):,}元。"
                )
            else:
                summary = (
                    f"{filters['year']}年{filters['origin_place']}基地发往{destination_text}"
                    f"平均运费为{int(data.get('avg_fee') or 0):,}元。"
                )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["metric", "avg_fee", "avg_fee_per_trip", "shipment_mw", "row_count"],
                table_rows=[data],
                calculation_logic=[
                    "历史始发-目的线路汇总使用 dwd_logistics_hist_shipment_detail。",
                    "平均运费按 AVG(total_fee) 计算。",
                    "平均每车运费按 SUM(total_fee) / SUM(shipment_trip_count) 计算。",
                    "发运量 MW 使用 actual_watt 汇总后除以 1,000,000。",
                    "当问题指定城市时优先按 city 模糊过滤；否则按 province 过滤。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_origin_vehicle_metric_summary":
            data = self.repository.hist_origin_vehicle_metric_summary(
                year=filters["year"],
                origin_place=filters["origin_place"],
                vehicle_type=filters["vehicle_type"],
                metric=filters["metric"],
            )
            if filters["metric"] == "unit_fee_per_watt":
                summary = (
                    f"{filters['year']}年{filters['origin_place']}基地{filters['vehicle_type']}车"
                    f"平均单瓦价为{data.get('unit_fee_per_watt') or 0}元/瓦。"
                )
            else:
                summary = (
                    f"{filters['year']}年{filters['origin_place']}基地{filters['vehicle_type']}车"
                    f"平均单车运费为{float(data.get('avg_fee_per_trip') or 0):,.2f}元/车。"
                )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=[
                    "metric",
                    "avg_fee_per_trip",
                    "unit_fee_per_watt",
                    "total_fee",
                    "shipment_mw",
                    "shipment_trip_count",
                    "row_count",
                ],
                table_rows=[data],
                calculation_logic=[
                    "平均单车运费 = SUM(total_fee) / SUM(shipment_trip_count)。",
                    "平均单瓦价 = SUM(total_fee) / SUM(actual_watt)。",
                    "车型按 required_vehicle_type 模糊匹配，例如 17.5、13、9.6。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_origin_vehicle_breakdown_summary":
            rows = self.repository.hist_origin_vehicle_breakdown_summary(
                year=filters.get("year"),
                years=filters.get("years"),
                origin_place=filters.get("origin_place"),
                include_origin_dimension=bool(filters.get("include_origin_dimension")),
            )
            table_rows: list[dict[str, Any]] = []
            for row in rows:
                item: dict[str, Any] = {}
                if filters.get("include_origin_dimension"):
                    item["始发地"] = row.get("origin_place") or "未填始发地"
                item.update(
                    {
                        "车型": row.get("required_vehicle_type") or "未填车型",
                        "发运车次": int(float(row.get("shipment_trip_count") or 0)),
                        "发运件数": int(float(row.get("shipment_count") or 0)),
                        "总运费": float(row.get("total_fee") or 0),
                        "平均单车费用": float(row.get("avg_fee_per_trip") or 0),
                        "平均每车装载托数": float(row.get("avg_pallet_per_vehicle") or 0),
                        "有效托数记录数": int(row.get("valid_pallet_record_count") or 0),
                        "缺失托数记录数": int(row.get("missing_pallet_record_count") or 0),
                        "记录数": int(row.get("row_count") or 0),
                    }
                )
                table_rows.append(item)
            scope_text = f"{filters['origin_place']}始发" if filters.get("origin_place") else "按始发地"
            if filters.get("year"):
                time_text = f"{filters['year']}年"
            else:
                time_text = "2023-2025年历史台账"
                warnings.append("平均每车装载托数字段当前仅在历史台账可审计，2026 正式系统侧暂无 pallet_per_vehicle 字段，本汇总未伪造 2026 装载托数。")
            summary = f"{time_text}{scope_text}不同车型的发运车次、发运件数、总运费和平均每车装载托数已汇总。"
            columns = ["车型", "发运车次", "发运件数", "总运费", "平均单车费用", "平均每车装载托数", "有效托数记录数", "缺失托数记录数", "记录数"]
            if filters.get("include_origin_dimension"):
                columns = ["始发地", *columns]
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=columns,
                table_rows=table_rows,
                calculation_logic=[
                    "发运车次按 dwd_logistics_hist_shipment_detail.shipment_trip_count 汇总。",
                    "发运件数按 dwd_logistics_hist_shipment_detail.actual_qty 汇总。",
                    "总运费按 dwd_logistics_hist_shipment_detail.total_fee 汇总。",
                    "平均单车费用 = SUM(total_fee) / SUM(shipment_trip_count)。",
                    "平均每车装载托数 = AVG(pallet_per_vehicle)，只统计非空记录，空值不按 0 处理。",
                    "车型按 required_vehicle_type 分组；无法安全识别始发地时保留真实始发地分组，不编造过滤条件。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_monthly_trip_count_summary":
            data = self.repository.hist_monthly_trip_count_summary(
                year=filters["year"],
                months=filters["months"],
            )
            month_text = "、".join(f"{month}月" for month in filters["months"])
            summary = f"{filters['year']}年{month_text}总车次为{int(data.get('shipment_trip_count') or 0):,}车次。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["shipment_trip_count", "row_count"],
                table_rows=[data],
                calculation_logic=[
                    "历史月度总车次按 dwd_logistics_hist_shipment_detail.shipment_trip_count 汇总。",
                    "月份过滤使用历史台账 biz_month 字段。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_trip_count_by_region":
            data = self.repository.hist_trip_count_by_region(year=filters["year"], region_name=filters["region_name"])
            summary = f"{filters['year']}年{filters['region_name']}区域合计发运{int(data['shipment_trip_count'] or 0):,}车次。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["shipment_trip_count"],
                table_rows=[data],
                calculation_logic=["历史车次口径直接使用 dwd_logistics_hist_shipment_detail.shipment_trip_count 汇总。"],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_quantity_by_region":
            data = self.repository.hist_quantity_by_region(
                region_name=filters["region_name"],
                year=filters.get("year"),
                transport_mode=filters.get("transport_mode"),
            )
            year_text = f"{filters['year']}年" if filters.get("year") else ""
            transport_text = f"通过{filters['transport_mode']}" if filters.get("transport_mode") else ""
            summary = f"{year_text}{filters['region_name']}区域{transport_text}总发运件数为{int(data['shipment_count'] or 0):,}件。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["shipment_count"],
                table_rows=[data],
                calculation_logic=["历史发运件数口径使用 dwd_logistics_hist_shipment_detail.actual_qty 汇总。"],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_customer_mw":
            data = self.repository.hist_customer_mw(
                year=filters.get("year"),
                customer_name=filters["customer_name"],
                months=filters.get("months"),
            )
            matched_names = data.get("matched_customer_names", [])
            if len(matched_names) > 1:
                warnings.append(f"当前按客户名前缀归并，命中了 {len(matched_names)} 个客户名变体。")
            summary = f"{data['scope_label']}{filters['customer_name']}总发运量为{data['shipment_mw'] or 0}MW。"
            calculation_logic = [
                "历史发运量 MW 使用 actual_watt 汇总后除以 1,000,000。",
                "客户名按业务问法做前缀归并，以兼容同一项目的名称变体。",
            ]
            if filters.get("year") is None:
                # 只有用户确实未给年份时，才展示历史累计默认口径；避免明确年月问题出现误导性风险提示。
                calculation_logic.append("未给年份时默认按 2023–2025 历史台账累计统计。")
            elif filters.get("months"):
                calculation_logic.append("已按用户给出的年份和月份过滤统计。")
            else:
                calculation_logic.append("已按用户给出的年份过滤统计。")
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["scope_label", "shipment_mw"],
                table_rows=[data],
                calculation_logic=calculation_logic,
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_city_carrier_avg_fee_per_trip":
            data = self.repository.hist_city_carrier_avg_fee_per_trip(
                city=filters["city"],
                year=filters.get("year"),
            )
            summary = f"{data['scope_label']}{filters['city']}城市发运中，不同物流公司的平均单价/车已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["carrier_name", "avg_fee_per_trip", "total_fee", "shipment_trip_count"],
                table_rows=data["items"],
                calculation_logic=[
                    "平均单价/车口径 = SUM(total_fee) / SUM(shipment_trip_count)。",
                    "按城市和承运商分组统计，shipment_trip_count 为 0 的承运商不纳入均价计算。",
                    "未给年份时默认按 2023–2025 历史台账累计统计。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters, "scope_label": data["scope_label"]},
                warnings=warnings,
            )

        if plan.query_key == "hist_avg_pallet_per_vehicle":
            data = self.repository.hist_avg_pallet_per_vehicle(
                year=filters["year"],
                months=filters["months"],
                origin_place=filters["origin_place"],
            )
            if data.get("missing_record_count"):
                warnings.append(f"共有 {int(data['missing_record_count'] or 0):,} 条记录的每车装载托数为空，未参与平均值计算。")
            month_text = "、".join(f"{month}月" for month in filters["months"])
            summary = (
                f"{filters['year']}年{month_text}{filters['origin_place']}始发订单的"
                f"平均每车装载托数为{data.get('avg_pallet_per_vehicle') or 0}托。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["avg_pallet_per_vehicle", "valid_record_count", "total_record_count", "missing_record_count"],
                table_rows=[data],
                calculation_logic=[
                    "平均每车装载托数 = AVG(pallet_per_vehicle)。",
                    "只统计 pallet_per_vehicle 非空记录；空值不按 0 处理，避免拉低平均值。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_vehicle_type_trip_count":
            data = self.repository.hist_vehicle_type_trip_count(
                year=filters["year"],
                vehicle_type=filters["vehicle_type"],
                origin_place=filters.get("origin_place"),
            )
            # 用户指定始发基地时，业务摘要同步展示基地范围，避免“合肥基地”问题返回全车型口径。
            scope_text = f"{filters['year']}年"
            if filters.get("origin_place"):
                scope_text += f"{filters['origin_place']}基地"
            scope_text += f"{filters['vehicle_type']}车"
            summary = f"{scope_text}合计发运{int(data['shipment_trip_count'] or 0):,}车次。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["shipment_trip_count"],
                table_rows=[data],
                calculation_logic=["历史车型口径使用 required_vehicle_type 过滤；如指定始发基地，则同步按 origin_place 过滤，再汇总 shipment_trip_count。"],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "carrier_metric_ranking":
            ranking_metric = filters["ranking_metric"]
            top_n = filters.get("top_n", plan.limit or 10)
            if filters["year"] == 2026:
                data = self.repository.sys_carrier_ranking(
                    year=filters["year"],
                    months=filters["months"],
                    ranking_metric=ranking_metric,
                    top_n=top_n,
                )
            else:
                data = self.repository.hist_carrier_ranking(
                    year=filters["year"],
                    ranking_metric=ranking_metric,
                    top_n=top_n,
                )
            month_text = ""
            if filters.get("months"):
                month_text = "、".join(f"{month}月" for month in filters["months"])
            metric_text = "单瓦成本" if ranking_metric == "unit_fee_per_watt" else "总运费"
            summary = f"{filters['year']}年{month_text}各承运商按{metric_text}排名前{top_n}结果已返回。"
            table_columns = (
                ["carrier_name", "unit_fee_per_watt", "total_fee", "shipment_mw", "task_count"]
                if ranking_metric == "unit_fee_per_watt"
                else ["carrier_name", "total_fee", "shipment_mw", "task_count"]
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=table_columns,
                table_rows=data,
                calculation_logic=[
                    "历史口径下总运费按 total_fee 汇总，单瓦成本按 total_fee / actual_watt 计算。",
                    "2026 系统口径下总运费沿用正式 price × 解析总车数，单瓦成本 = 系统总运费 / 总发运瓦数。",
                    f"排名统一按指标降序返回前{top_n}名。",
                ],
                data_scope={"tables": ["dwd_logistics_hist_shipment_detail", "dwd_logistics_ship_task", "dwd_logistics_ship_product"], **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_multi_origin_customers":
            data = self.repository.hist_multi_origin_customers(year=filters["year"])
            summary = f"{filters['year']}年同一客户由多个始发地发货的客户共有{int(data['customer_count'] or 0):,}个。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["customer_name", "origin_place_count"],
                table_rows=data["items"],
                calculation_logic=[
                    "客户口径严格使用原始台账字段“客户名称（标准名称；最终客户）”。",
                    "按最终客户分组，统计 origin_place 去重数大于 1 的客户。",
                ],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "hist_plan_actual_deviation":
            data = self.repository.hist_plan_actual_deviation(year=filters["year"], region_name=filters["region_name"])
            summary = (
                f"{filters['year']}年{filters['region_name']}区域实际发运件数较计划"
                f"{'提高' if (data.get('deviation_rate') or 0) >= 0 else '下降'}{abs(data.get('deviation_rate') or 0)}%。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["plan_qty_total", "actual_qty_total", "deviation_rate"],
                table_rows=[data],
                calculation_logic=["偏差率 = (SUM(actual_qty) - SUM(plan_qty)) / SUM(plan_qty)。"],
                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_mw_and_trip_count":
            data = self.repository.sys_mw_and_trip_count(
                year=filters["year"],
                months=filters["months"],
                transport_mode=filters.get("transport_mode"),
                base_code=filters.get("base_code"),
                special_scope=filters.get("special_scope"),
                monthly_breakdown=bool(filters.get("monthly_breakdown")),
            )
            if filters.get("default_ytd_scope"):
                warnings.append("当前题目未给具体月份，系统默认按 2026 年截至目前累计口径返回运量综合结果。")
            if data["power_missing_count"] > 0:
                warnings.append(f"共有 {data['power_missing_count']} 条 product 记录 power 缺失，未纳入 MW 统计。")
            if data["pickup_date_missing_count"] > 0:
                warnings.append(
                    f"当前 2026 年任务中有 {data['pickup_date_missing_count']} 条 pickup_date 缺失，"
                    "会影响按业务月份口径统计。"
                )
            warnings.append(
                "区域口径优先使用 delivery_area；为空时用 delivery_province 映射七大区域，异常值归入“其他”。"
            )
            warnings.append(
                "当前统计范围区域覆盖率："
                f"delivery_area 直接命中 {data['year_region_coverage']['direct_area_count']} 条，"
                f"省份兜底 {data['year_region_coverage']['province_fallback_count']} 条，"
                f"归入其他 {data['year_region_coverage']['other_count']} 条。"
            )
            month_text = "、".join(f"{month}月" for month in (filters.get("months") or []))
            base_text = filters.get("base_name") or ""
            special_text = {
                "planning": "经营计划用车",
                "sample": "辅料送样",
                "liujuan": "刘娟用车",
            }.get(filters.get("special_scope"), "")
            transport_text = f"{filters['transport_mode']}方式" if filters.get("transport_mode") else ""
            scope_label = month_text or "截至目前累计"
            scope_prefix = f"{filters['year']}年{base_text}{special_text}"
            if data["strict_scope_task_count"] == 0 and data["year_task_count"] > 0:
                summary = (
                    f"{scope_prefix}{scope_label}{transport_text}的系统任务尚未同步 pickup_date，"
                    "暂无法按已锁定业务时间口径计算发运量和车次。"
                )
                return self._build_result(
                    answer_summary=summary,
                    plan=plan,
                    table_columns=[
                        "shipment_mw",
                        "shipment_trip_count",
                        "power_missing_count",
                        "pickup_date_missing_count",
                        "strict_scope_task_count",
                        "year_task_count",
                        "pickup_date_available_count",
                    ],
                    table_rows=[data],
                    calculation_logic=[
                        "MW = SUM(ship_product.power * ship_product.quantity) / 1,000,000。",
                        "power 缺失记录不纳入 MW 统计。",
                        "车次 = COUNT(assign_task.task_id)，且仅统计 ENTER / LEAVE。",
                        "2026 月份统计必须使用 pickup_date，不能再退回 biz_date。",
                    ],
                    data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product", "dwd_logistics_assign_task"], **filters},
                    warnings=warnings,
                    supported=False,
                )
            metrics = plan.metrics or ["shipment_mw", "shipment_trip_count"]
            if filters.get("monthly_breakdown") and data.get("monthly_rows"):
                if metrics == ["shipment_mw"]:
                    monthly_rows = [
                        {"biz_month": row.get("biz_month"), "shipment_mw": row.get("shipment_mw")}
                        for row in data["monthly_rows"]
                    ]
                    summary = (
                        f"{scope_prefix}{scope_label}{transport_text}发运量已按月返回，"
                        f"合计发运量为{data['shipment_mw'] or 0}MW。"
                    )
                    table_columns = ["biz_month", "shipment_mw"]
                else:
                    monthly_rows = list(data["monthly_rows"])
                    summary = (
                        f"{scope_prefix}{scope_label}{transport_text}运量和车次已按月返回，"
                        f"合计发运量为{data['shipment_mw'] or 0}MW，"
                        f"合计车次为{int(data['shipment_trip_count'] or 0):,}。"
                    )
                    table_columns = ["biz_month", "shipment_mw", "shipment_trip_count"]
                return self._build_result(
                    answer_summary=summary,
                    plan=plan,
                    table_columns=table_columns,
                    table_rows=monthly_rows,
                    calculation_logic=[
                        "MW = SUM(ship_product.power * ship_product.quantity) / 1,000,000。",
                        "power 缺失记录不纳入 MW 统计。",
                        "车次 = COUNT(assign_task.task_id)，且仅统计 ENTER / LEAVE。",
                        "按月趋势使用 pickup_date 对应业务月份分组。",
                    ],
                    data_scope={
                        "tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product", "dwd_logistics_assign_task"],
                        **filters,
                    },
                    warnings=warnings,
                )
            if metrics == ["shipment_mw"]:
                summary = f"{scope_prefix}{scope_label}{transport_text}合计发运量为{data['shipment_mw'] or 0}MW。"
                table_columns = [
                    "shipment_mw",
                    "power_missing_count",
                    "pickup_date_missing_count",
                    "strict_scope_task_count",
                    "pickup_date_available_count",
                ]
            else:
                summary = (
                    f"{scope_prefix}{scope_label}{transport_text}合计发运量为{data['shipment_mw'] or 0}MW，"
                    f"合计车次为{int(data['shipment_trip_count'] or 0):,}。"
                )
                table_columns = [
                    "shipment_mw",
                    "shipment_trip_count",
                    "power_missing_count",
                    "pickup_date_missing_count",
                    "strict_scope_task_count",
                    "pickup_date_available_count",
                ]
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=table_columns,
                table_rows=[data],
                calculation_logic=[
                    "MW = SUM(ship_product.power * ship_product.quantity) / 1,000,000。",
                    "power 缺失记录不纳入 MW 统计。",
                    "车次 = COUNT(assign_task.task_id)，且仅统计 ENTER / LEAVE。",
                    "2026 月份统计必须使用 pickup_date。",
                    "如题目指定运输方式，则先按 transport_mode 过滤后再统计。",
                ],
                data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product", "dwd_logistics_assign_task"], **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_mw_by_procurement_type":
            data = self.repository.sys_mw_by_procurement_type(year=filters["year"])
            summary = f"{filters['year']}年招标、询比价等采购方式对应的发运量拆分已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["procurement_type", "shipment_mw", "task_count"],
                table_rows=data,
                calculation_logic=[
                    "采购方式拆分基于 dwd_logistics_ship_task.procurement_type。",
                    "发运量 MW 使用 ship_product.power × quantity 汇总后除以 1,000,000。",
                ],
                data_scope={
                    "tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product", "dwd_logistics_assign_detail"],
                    **filters,
                },
                warnings=warnings,
            )

        if plan.query_key == "sys_task_status_distribution":
            data = self.repository.sys_task_status_distribution(
                year=filters["year"],
                table_scope=filters.get("table_scope", "ship_task"),
            )
            rows = data["items"]
            if filters.get("status"):
                rows = [row for row in rows if row.get("status") == filters["status"]]
                if not rows:
                    rows = [{"status": filters["status"], "task_count": 0, "task_share_pct": 0}]
            scope_label = "主任务表" if data["table_scope"] == "ship_task" else "派车任务表"
            summary = f"{filters['year']}年{scope_label}状态分布已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["status", "task_count", "task_share_pct"],
                table_rows=rows,
                calculation_logic=[
                    "状态数量按对应系统任务表 status 字段分组计数。",
                    "占比 = 当前状态任务数 / 当前任务表全部有效状态任务数。",
                    "指定状态没有命中时返回零值行，表示该状态当前统计数为 0。",
                ],
                data_scope={"table_scope": data["table_scope"], **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_avg_loading_trucks_by_province":
            data = self.repository.sys_avg_loading_trucks_by_province(year=filters["year"], province=filters["province"])
            summary = (
                f"{filters['year']}年送达省份为{data['province']}的任务中，"
                f"平均装车数为{data.get('avg_loading_trucks') or 0}。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["province", "avg_loading_trucks", "task_count", "non_null_task_count"],
                table_rows=[data],
                calculation_logic=[
                    "平均装车数按 dwd_logistics_ship_task.loading_trucks 的 AVG 计算。",
                    "同时返回总任务数和 loading_trucks 非空任务数，便于判断数据填充情况。",
                ],
                data_scope={"table": "dwd_logistics_ship_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_task_status_province_ranking":
            data = self.repository.sys_task_status_province_ranking(
                year=filters["year"],
                status=filters["status"],
                top_n=filters.get("top_n", plan.limit or 10),
            )
            summary = f"{filters['year']}年{filters['status']}状态任务最多的送达省份已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["delivery_province", "task_count"],
                table_rows=data,
                calculation_logic=["先按主任务表 status 过滤，再按送达省份分组统计任务数量。"],
                data_scope={"table": "dwd_logistics_ship_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_reconciliation_fill_rate_by_month":
            data = self.repository.sys_reconciliation_fill_rate_by_month(year=filters["year"])
            summary = f"{filters['year']}年各月份 reconciliation_status 填充率已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["biz_month", "fill_rate", "task_count"],
                table_rows=data,
                calculation_logic=["填充率 = reconciliation_status 非空任务数 / 当月全部任务数。"],
                data_scope={"table": "dwd_logistics_ship_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_ship_product_detail_stats":
            data = self.repository.sys_ship_product_detail_stats(
                year=filters["year"],
                top_n=filters.get("top_n", plan.limit or 10),
            )
            rows = [{"task_id": "平均值", "project_name": None, "detail_count": data["avg_detail_count"]}] + data["items"]
            summary = (
                f"{filters['year']}年平均每个物流任务包含{data.get('avg_detail_count') or 0}条 ship_product 明细，"
                "明细数最高的任务已返回。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["task_id", "project_name", "detail_count"],
                table_rows=rows,
                calculation_logic=[
                    "先按 task_id 统计 ship_product 明细数，再计算任务级平均值。",
                    "明细数最高任务按 detail_count 降序返回。",
                ],
                data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product"], **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_driver_task_ranking":
            data = self.repository.sys_driver_task_ranking(
                year=filters["year"],
                top_n=filters.get("top_n", plan.limit or 20),
            )
            summary = f"{filters['year']}年派车任务量最高的司机排名已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["driver_name", "assign_task_count"],
                table_rows=data,
                calculation_logic=["派车任务量按 dwd_logistics_assign_task.driver_name 分组计数。"],
                data_scope={"table": "dwd_logistics_assign_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_driver_phone_name_consistency":
            data = self.repository.sys_driver_phone_name_consistency(
                year=filters["year"],
                top_n=filters.get("top_n", plan.limit or 50),
            )
            count = int(data.get("abnormal_group_count") or 0)
            task_count = int(data.get("abnormal_task_count") or 0)
            summary = f"{filters['year']}年存在{count}个同一手机号关联多个司机姓名的异常手机号，涉及{task_count}条派车任务。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["driver_phone", "driver_names", "driver_name_count", "assign_task_count", "distinct_task_count"],
                table_rows=data["items"],
                calculation_logic=[
                    "按 dwd_logistics_assign_task.driver_phone 分组，统计 DISTINCT driver_name。",
                    "仅统计手机号和司机姓名均非空的派车记录；driver_name_count > 1 判定为一号多人异常。",
                ],
                data_scope={"table": "dwd_logistics_assign_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_driver_id_phone_consistency":
            data = self.repository.sys_driver_id_phone_consistency(
                year=filters["year"],
                top_n=filters.get("top_n", plan.limit or 50),
            )
            count = int(data.get("abnormal_group_count") or 0)
            task_count = int(data.get("abnormal_task_count") or 0)
            summary = f"{filters['year']}年存在{count}个同一身份证号对应多个手机号的异常身份证号，涉及{task_count}条派车任务。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["driver_id_number", "driver_phones", "driver_phone_count", "assign_task_count", "distinct_task_count"],
                table_rows=data["items"],
                calculation_logic=[
                    "按 dwd_logistics_assign_task.driver_id_number 分组，统计 DISTINCT driver_phone。",
                    "仅统计身份证号和手机号均非空的派车记录；driver_phone_count > 1 判定为一人多号异常。",
                ],
                data_scope={"table": "dwd_logistics_assign_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_delivery_note_parse_status_distribution":
            data = self.repository.sys_delivery_note_parse_status_distribution(year=filters["year"])
            summary = f"{filters['year']}年派车任务回单解析状态分布已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["delivery_note_parse_status", "record_count", "record_share_pct"],
                table_rows=data["items"],
                calculation_logic=["回单解析状态按 dwd_logistics_assign_task.delivery_note_parse_status 分组计数。"],
                data_scope={"table": "dwd_logistics_assign_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_procurement_task_distribution":
            data = self.repository.sys_procurement_task_distribution(year=filters["year"])
            summary = f"{filters['year']}年有采购方式标记的任务中，各采购方式任务量与占比已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["procurement_type", "task_count", "task_share_pct"],
                table_rows=data["items"],
                calculation_logic=["采购方式任务量按 procurement_type 分组计数，占比基于有采购方式标记的任务。"],
                data_scope={"table": "dwd_logistics_ship_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_procurement_avg_loading_trucks":
            data = self.repository.sys_procurement_avg_loading_trucks(year=filters["year"])
            summary = f"{filters['year']}年招标与询比价等采购方式的平均装车数已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["procurement_type", "avg_loading_trucks", "task_count", "non_null_task_count"],
                table_rows=data,
                calculation_logic=["按采购方式分组后，对 loading_trucks 求平均。"],
                data_scope={"table": "dwd_logistics_ship_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_extra_fee_summary":
            if filters.get("detail_warning") == "extra_fee_project_reason_unfixed":
                warnings.append("额外费用项目/原因明细口径尚未固化，本次先返回可审计的额外费用总额。")
            data = self.repository.sys_extra_fee_summary(
                year=filters["year"],
                months=filters.get("months"),
                base_code=filters.get("base_code"),
            )
            month_text = "、".join(f"{month}月" for month in (filters.get("months") or []))
            base_text = filters.get("base_name") or ""
            summary = f"{filters['year']}年{month_text}{base_text}额外费用总额为{float(data.get('extra_fee_amount') or 0):,.2f}元。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["extra_fee_amount", "task_count", "detail_count"],
                table_rows=[data],
                calculation_logic=["额外费用按 dwd_logistics_assign_detail.extra_cost 汇总，并按主任务年月和基地过滤。"],
                data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_assign_detail"], **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_total_fee_by_filters":
            data = self.repository.sys_total_fee_by_filters(
                year=filters["year"],
                months=filters.get("months"),
                company_name=filters.get("company_name"),
                customer_name=filters.get("customer_name"),
                transport_mode=filters.get("transport_mode"),
                special_scope=filters.get("special_scope"),
                base_code=filters.get("base_code"),
                procurement_type=filters.get("procurement_type"),
                expand_dept=filters.get("expand_dept"),
                entrusted_person=filters.get("entrusted_person"),
                monthly_breakdown=bool(filters.get("monthly_breakdown")),
            )
            if data.get("parse_fail_count"):
                warnings.append(
                    f"共有 {int(data['parse_fail_count'])} 条任务的 project_name 无法解析总车数，未纳入总运费统计。"
                )
            if data.get("price_missing_count"):
                warnings.append(
                    f"共有 {int(data['price_missing_count'])} 条任务缺少 ship_product.price，未纳入总运费统计。"
                )
            scope_parts = [f"{filters['year']}年"]
            if filters.get("months"):
                scope_parts.append("、".join(f"{month}月" for month in filters["months"]))
            if filters.get("base_name"):
                scope_parts.append(filters["base_name"])
            if filters.get("expand_dept"):
                scope_parts.append(f"扩充部门={filters['expand_dept']}")
            if filters.get("entrusted_person"):
                scope_parts.append(f"委托人={filters['entrusted_person']}")
            if filters.get("customer_name"):
                scope_parts.append(f"客户{filters['customer_name']}")
            if filters.get("company_name"):
                scope_parts.append(f"承运商{filters['company_name']}")
            if filters.get("transport_mode"):
                scope_parts.append(f"{filters['transport_mode']}运输")
            if filters.get("procurement_type"):
                scope_parts.append(f"{filters['procurement_type']}采购方式")
            scope_text = "".join(scope_parts)
            if filters.get("monthly_breakdown") and data.get("monthly_rows"):
                calculation_logic = [
                    "系统总运费口径沿用当前正式系统计算方式：ship_product.price × project_name 解析总车数。",
                    "按月拆分使用 pickup_date；pickup_date 缺失时按 biz_date 归属月份。",
                    "按月返回只改变展示颗粒度，不改变总费用计算口径。",
                ]
                if filters.get("expand_dept") or filters.get("entrusted_person"):
                    calculation_logic.append("业务范围词已按受控字段下推过滤：扩充部门使用 expand_dept，委托人使用 entrusted_person。")
                monthly_rows = list(data["monthly_rows"])
                summary = (
                    f"{scope_text}总运费已按月返回，"
                    f"合计总运费为{float(data.get('total_fee') or 0):,.2f}元。"
                )
                return self._build_result(
                    answer_summary=summary,
                    plan=plan,
                    table_columns=["biz_month", "total_fee", "task_count", "parse_fail_count", "price_missing_count"],
                    table_rows=monthly_rows,
                    calculation_logic=calculation_logic,
                    data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product"], **filters},
                    warnings=warnings,
                )
            summary = f"{scope_text}按当前系统口径统计的总运费为{float(data.get('total_fee') or 0):,.2f}元。"
            calculation_logic = [
                "系统总运费口径沿用当前正式系统计算方式：ship_product.price × project_name 解析总车数。",
                "月份过滤优先使用 pickup_date，缺失时退回 biz_date。",
                "客户过滤当前按 project_name 模糊命中，不额外承诺独立 customer 字段。",
                "运输方式过滤仅在用户明确指定公路、铁路等运输方式时下推。",
                "采购方式过滤仅在用户明确指定招标、询比价等系统字段时下推。",
            ]
            if filters.get("expand_dept") or filters.get("entrusted_person"):
                calculation_logic.append("业务范围词已按受控字段下推过滤：扩充部门使用 expand_dept，委托人使用 entrusted_person。")
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["total_fee", "task_count", "parse_fail_count", "price_missing_count"],
                table_rows=[data],
                calculation_logic=calculation_logic,
                data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product"], **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_task_count_ranking":
            data = self.repository.sys_task_count_ranking(
                year=filters["year"],
                dimension=filters["dimension"],
                top_n=filters.get("top_n", plan.limit or 10),
            )
            dimension_label = "送达城市" if filters["dimension"] == "delivery_city" else "项目"
            summary = f"{filters['year']}年按{dimension_label}统计的任务量排名结果已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["dimension_value", "task_count"],
                table_rows=data,
                calculation_logic=[
                    "任务量直接按 dwd_logistics_ship_task 计数。",
                    "当前不区分主任务/派车任务，统一按 ship_task 口径统计。",
                ],
                data_scope={"table": "dwd_logistics_ship_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_delivery_distance_fill_rate_by_province":
            top_n = filters.get("top_n", plan.limit or 10)
            data = self.repository.sys_delivery_distance_fill_rate_by_province(
                year=filters["year"],
                top_n=top_n,
            )
            summary = f"{filters['year']}年各送达省份 delivery_distance 填充率已返回，最低前{top_n}省份已排序。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["delivery_province", "fill_rate", "task_count"],
                table_rows=data,
                calculation_logic=[
                    "填充率 = delivery_distance 非空任务数 / 该送达省份全部任务数。",
                    f"当前结果按填充率升序输出，便于直接查看最低前{top_n}省份。",
                ],
                data_scope={"table": "dwd_logistics_ship_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_parse_success_rate_by_carrier":
            top_n = filters.get("top_n", plan.limit or 10)
            data = self.repository.sys_parse_success_rate_by_carrier(
                year=filters["year"],
                top_n=top_n,
            )
            rows = [
                {"bucket": f"top{top_n}", **row} for row in data["top_rows"]
            ] + [
                {"bucket": f"bottom{top_n}", **row} for row in data["bottom_rows"]
            ]
            summary = f"{filters['year']}年按承运商统计的送货单解析成功率前{top_n}和后{top_n}结果已返回。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["bucket", "company_name", "parse_success_rate", "task_count"],
                table_rows=rows,
                calculation_logic=[
                    "解析成功率 = project_name 能按当前正式规则解析总车数的任务数 / 全部任务数。",
                    f"同一承运商分别给出解析成功率前{top_n}和后{top_n}结果，便于同时看最佳与最差。",
                ],
                data_scope={"table": "dwd_logistics_ship_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_company_mapping_gap":
            data = self.repository.sys_company_mapping_gap(
                year=filters["year"],
                limit=filters.get("limit", plan.limit or 20),
            )
            summary = (
                f"{filters['year']}年存在{int(data['missing_task_count'] or 0)}条任务的 company_id 找不到承运商主数据映射。"
                if data["missing_task_count"]
                else f"{filters['year']}年未发现 company_id 找不到承运商主数据映射的任务。"
            )
            table_rows = data["items"] or [{"task_id": None, "company_id": None, "company_name": None, "missing_task_count": data["missing_task_count"]}]
            table_columns = ["task_id", "company_id", "company_name", "missing_task_count"]
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=table_columns,
                table_rows=table_rows,
                calculation_logic=[
                    "先以 ship_task.company_id 对承运商主数据做左连接，再统计无法映射的任务。",
                    "即使当前没有缺口，也会返回汇总行，避免误判成空结果。",
                ],
                data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_company"], **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_extra_cost_audited_concentration":
            data = self.repository.sys_extra_cost_audited_concentration(
                year=filters["year"],
                top_n=filters.get("top_n", plan.limit or 10),
            )
            rows = [
                {"bucket": "carrier", **row} for row in data["top_carriers"]
            ] + [
                {"bucket": "province", **row} for row in data["top_provinces"]
            ]
            if not rows:
                rows = [{"bucket": "summary", "company_name": None, "delivery_province": None, "task_count": data["audited_task_count"]}]
            summary = (
                f"{filters['year']}年 extra_cost_audited=1 的主任务共有{int(data['audited_task_count'] or 0)}条，"
                "主要集中承运商和省份已返回。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["bucket", "company_name", "delivery_province", "task_count"],
                table_rows=rows,
                calculation_logic=[
                    "先筛选 extra_cost_audited=1 的主任务，再分别按承运商和送达省份聚合。",
                    "当前结果用于识别额外费用审核任务的集中分布，不做离群判定。",
                ],
                data_scope={"table": "dwd_logistics_ship_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_unit_fee_per_watt":
            data = self.repository.sys_unit_fee_per_watt(
                year=filters["year"],
                months=filters["months"],
                company_name=filters.get("company_name"),
                include_extra_cost=filters.get("include_extra_cost", False),
            )
            if filters.get("default_year_scope"):
                warnings.append(
                    f"当前题目未给统计年份，系统默认按{filters.get('default_year_scope_label') or '2026正式系统'}月份口径计算。"
                )
            if data.get("parse_fail_count"):
                warnings.append(
                    f"共有 {int(data['parse_fail_count'])} 条任务的 project_name 无法解析总车数，未纳入总运费统计。"
                )
            if data.get("price_missing_count"):
                warnings.append(
                    f"共有 {int(data['price_missing_count'])} 条任务缺少 ship_product.price，未纳入总运费统计。"
                )
            if data.get("power_missing_count"):
                warnings.append(
                    f"共有 {int(data['power_missing_count'])} 条 product 记录 power 缺失，未纳入单瓦成本统计。"
                )
            scope_parts = [f"{filters['year']}年", "、".join(f"{month}月" for month in filters["months"])]
            if filters.get("company_name"):
                scope_parts.append(f"承运商{filters['company_name']}")
            if filters.get("include_extra_cost"):
                summary = (
                    f"{''.join(scope_parts)}按（总运费+额外费用）/总发运瓦数口径统计的单瓦运输成本为"
                    f"{data.get('unit_fee_per_watt') or 0}元/瓦。"
                )
            else:
                summary = f"{''.join(scope_parts)}按当前系统口径统计的单瓦运输成本为{data.get('unit_fee_per_watt') or 0}元/瓦。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=[
                    "unit_fee_per_watt",
                    "total_fee",
                    "extra_fee_amount",
                    "shipment_mw",
                    "task_count",
                    "parse_fail_count",
                    "price_missing_count",
                    "power_missing_count",
                ],
                table_rows=[data],
                calculation_logic=[
                    "系统单瓦运输成本 = 分子 / 总发运瓦数。",
                    "默认分子为当前系统总运费：price × project_name 解析总车数。",
                    "当问题显式给出“运费+额外费用”公式时，分子改为 总运费 + extra_cost。",
                    "总发运瓦数 = SUM(ship_product.power × quantity)。",
                ],
                data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product"], **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_special_total_fee":
            data = self.repository.sys_special_total_fee(year=filters["year"], special_scope=filters["special_scope"])
            if data.get("parse_fail_count"):
                warnings.append(
                    f"共有 {int(data['parse_fail_count'])} 条任务的 project_name 无法按“-”分段规则解析总车数，未纳入总运费统计。"
                )
            if data.get("price_missing_count"):
                warnings.append(
                    f"共有 {int(data['price_missing_count'])} 条任务缺少 ship_product.price，未纳入总运费统计。"
                )
            scope_label = {
                "planning": "经营计划用车",
                "sample": "辅料送样",
                "liujuan": "刘娟用车",
            }[filters["special_scope"]]
            summary = f"{filters['year']}年{scope_label}按锁定口径统计的总运费为{float(data.get('total_fee') or 0):,.2f}元。"
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["total_fee", "parse_fail_count", "price_missing_count"],
                table_rows=[data],
                calculation_logic=[
                    "总运费 = ship_product.price × project_name 解析出的总车数。",
                    "project_name 解析规则：按“-”分隔，取第 3 段作为总车数。",
                    "解析失败和 price 缺失记录都不允许静默吞错，必须单独计数提醒。",
                ],
                data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product"], **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_signedfor_rate_by_carrier":
            top_n = filters.get("top_n", plan.limit or 10)
            data = self.repository.sys_signedfor_rate_by_carrier(year=filters["year"], top_n=top_n)
            summary = f"{filters['year']}年承运商 SIGNEDFOR 签收率已返回前{top_n}和后{top_n}结果。"
            rows = [
                {"bucket": f"top{top_n}", **row} for row in data["top_rows"]
            ] + [
                {"bucket": f"bottom{top_n}", **row} for row in data["bottom_rows"]
            ]
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["bucket", "company_name", "signedfor_rate", "task_count"],
                table_rows=rows,
                calculation_logic=["签收率 = SIGNEDFOR 状态任务数 / 全部任务数。"],
                data_scope={"table": "dwd_logistics_ship_task", **filters},
                warnings=warnings,
            )

        if plan.query_key == "sys_companies_without_tasks":
            data = self.repository.sys_companies_without_tasks(year=filters["year"])
            summary = (
                f"存在{int(data['company_count'] or 0)}家物流公司已建档但{filters['year']}年无任务记录。"
                if data["company_count"] else f"{filters['year']}年所有已建档物流公司均有任务记录。"
            )
            return self._build_result(
                answer_summary=summary,
                plan=plan,
                table_columns=["company_name"],
                table_rows=data["items"],
                calculation_logic=["以 dwd_logistics_company 为主表，左连接 dwd_logistics_ship_task 判断当年是否存在任务。"],
                data_scope={"tables": ["dwd_logistics_company", "dwd_logistics_ship_task"], **filters},
                warnings=warnings,
            )

        return LogisticsDataQaResult(
            answer_summary="当前问题暂未落到受控查询实现。",
            result_table=LogisticsDataQaTable(),
            calculation_logic=["当前 query_key 尚未实现。"],
            data_scope={"question": question},
            query_plan=plan,
            warnings=["当前问题尚未实现。"],
            supported=False,
        )

    def _resolve_clarification_with_assist(
        self,
        *,
        question: str,
        plan: LogisticsDataQaPlan,
        trace_id: str | None,
    ) -> tuple[LogisticsDataQaPlan, str]:
        """用受控 LLM 辅助优化澄清问题。

        说明：
            1. 规则层已经明确判定必须澄清，当前方法不允许把结果改成 success / unsupported；
            2. LLM 只补充缺口径识别和业务化追问候选，最终仍返回 clarification；
            3. 若 LLM 不可用、置信度不足或类别不在白名单内，统一回退到规则模板。
        """

        return self.clarification_assist_service.apply(
            question=question,
            plan=plan,
            trace_id=trace_id,
        )

    def _resolve_unsupported_with_assist(
        self,
        *,
        question: str,
        plan: LogisticsDataQaPlan,
        trace_id: str | None,
    ) -> LogisticsDataQaPlan:
        """用受控 LLM 辅助优化 C 类拒答解释。

        说明：
            1. 规则层已经明确判定 unsupported，当前方法不允许把结果改成 success / clarification；
            2. LLM 只补充业务可理解原因和可改问方向，最终仍返回 unsupported；
            3. 若 LLM 不可用、置信度不足或类别不在白名单内，统一回退到规则拒答模板。

        返回：
            可能被增强过解释文本的 unsupported plan。
        """

        return self.unsupported_assist_service.apply(
            question=question,
            plan=plan,
            trace_id=trace_id,
        )

    def _build_unsupported_answer_summary(self, plan: LogisticsDataQaPlan) -> str:
        """生成 C 类不支持问题的业务化摘要。

        参数：
            plan: 当前受控查询计划，包含 unsupported_* 边界信息。

        返回：
            适合前端直接展示的拒答摘要，包含原因和可改问方向。
        """

        reason = plan.unsupported_reason or "当前问题暂不支持。"
        if not plan.unsupported_suggestions:
            return reason
        suggestions = "；".join(plan.unsupported_suggestions[:2])
        return f"{reason} 可改问方向：{suggestions}"

    def _build_unsupported_warnings(self, plan: LogisticsDataQaPlan) -> list[str]:
        """生成 C 类不支持问题的 warning 列表。

        参数：
            plan: 当前受控查询计划。

        返回：
            第一条为拒答原因，后续为可替代问法建议，便于前端分开展示。
        """

        warnings: list[str] = []
        if plan.unsupported_reason:
            warnings.append(plan.unsupported_reason)
        warnings.extend(plan.unsupported_suggestions)
        return warnings

    def _execute_composite_decomposed_plan(self, question: str, plan: LogisticsDataQaPlan) -> LogisticsDataQaResult:
        """执行复合问题拆分计划，并把多个子查询结果合并成一个前端响应。

        参数：
            question: 原始用户问题，用于结果审计和 data_scope 追溯。
            plan: composite_decomposed 总计划，filters.sub_plans 内保存受控子计划。
        返回值：
            合并后的物流问答结果；如果任一子计划越界，则保守返回不支持。
        """

        sub_plan_payloads = plan.filters.get("sub_plans") or []
        sub_results: list[dict[str, Any]] = []
        merged_rows: list[dict[str, Any]] = []
        merged_columns: list[str] = ["section"]
        decomposition_source = str(plan.filters.get("decomposition_source") or "rule_guardrail")
        calculation_logic = [
            "由 LLM 先识别顶层并列子问题，规则层再把每个子问题映射到既有受控 query_key。",
            "每个子查询独立执行仓储层确定性统计，最终仅在表达层合并结果，不做跨来源二次推理。",
        ]
        warnings = [
            f"已基于 {decomposition_source} 拆成 {len(sub_plan_payloads)} 个可独立审计的子问题分别查询后合并返回。",
            "历史高运费地址使用 2023-2025 历史台账口径；2026 系统侧采购方式发运量使用正式系统采购方式字段，两者不做跨源混算。",
        ]
        answer_parts: list[str] = []

        for raw_sub_plan in sub_plan_payloads:
            # section_label 只用于合并展示，不属于 LogisticsDataQaPlan schema；构造前先移除。
            sub_plan_dict = dict(raw_sub_plan)
            section_label = str(sub_plan_dict.pop("section_label", "子查询"))
            sub_plan = LogisticsDataQaPlan(**sub_plan_dict)
            sub_result = self._execute_plan(question, sub_plan)
            sub_results.append(
                {
                    "section": section_label,
                    "query_key": sub_plan.query_key,
                    "filters": sub_plan.filters,
                    "row_count": len(sub_result.result_table.rows),
                    "answer_summary": sub_result.answer_summary,
                    "supported": sub_result.supported,
                    "needs_clarification": sub_result.needs_clarification,
                    "data_scope": sub_result.data_scope,
                }
            )
            if sub_result.needs_clarification or not sub_result.supported:
                return self._build_result(
                    answer_summary=f"复合问题中的“{section_label}”子问题暂不能直接回答，请先补充口径或拆开单独提问。",
                    plan=plan,
                    table_columns=[],
                    table_rows=[],
                    calculation_logic=calculation_logic,
                    data_scope={"question": question, "composite": {"sub_results": sub_results}},
                    warnings=warnings + sub_result.warnings,
                    supported=False,
                )
            answer_parts.append(sub_result.answer_summary)
            calculation_logic.extend([f"【{section_label}】{item}" for item in sub_result.calculation_logic])
            warnings.extend(sub_result.warnings)
            for column in sub_result.result_table.columns:
                if column not in merged_columns:
                    merged_columns.append(column)
            for row in sub_result.result_table.rows:
                merged_rows.append({"section": section_label, **row})

        summary = f"已将问题拆成 {len(sub_results)} 个子问题分别查询：" + "；".join(answer_parts)
        return self._build_result(
            answer_summary=summary,
            plan=plan,
            table_columns=merged_columns,
            table_rows=merged_rows,
            calculation_logic=calculation_logic,
            data_scope={
                "question": question,
                "composite": {
                    "strategy": plan.filters.get("decomposition_strategy"),
                    "sub_result_count": len(sub_results),
                    "sub_results": sub_results,
                },
            },
            warnings=warnings,
        )

    def _build_result(
        self,
        *,
        answer_summary: str,
        plan: LogisticsDataQaPlan,
        table_columns: list[str],
        table_rows: list[dict[str, Any]],
        calculation_logic: list[str],
        data_scope: dict[str, Any],
        warnings: list[str],
        supported: bool = True,
    ) -> LogisticsDataQaResult:
        """统一组装结果。"""
        return LogisticsDataQaResult(
            answer_summary=answer_summary,
            result_table=LogisticsDataQaTable(columns=table_columns, rows=table_rows),
            calculation_logic=calculation_logic,
            data_scope=data_scope,
            query_plan=plan,
            warnings=warnings,
            needs_clarification=plan.needs_clarification,
            clarification_questions=plan.clarification_questions,
            supported=supported,
            status=None,
        )
