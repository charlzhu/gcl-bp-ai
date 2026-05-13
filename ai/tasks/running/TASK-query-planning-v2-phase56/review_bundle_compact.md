# Compact Review Bundle

Review only the excerpts below. They are from the scoped diff for Query Planning V2 Phase 5.6 and Plan BOM multi-candidate compare fix.

Final verification after reviewer suggestions: scoped focused subset had 3 unrelated failures in untracked test_business_chat_answer_format_preference.py due parallel dirty stream task; tracked tests plus scoped new tests passed 185 passed, 2 warnings. Previously all-files full tests passed 246 passed, 2 warnings before that untracked parallel file changed. Compile/pyflakes/static scan PASS; ruff skipped (not installed).

Reviewer suggestions addressed: app_env is normalized and production alias is fail-closed; left-side candidate expansion now uses candidate_result.right resolved context.


## backend/app/domains/query_planning/services/response_meta_exposure_service.py:1-210
```python
   1|from __future__ import annotations
   2|
   3|import logging
   4|from typing import Any
   5|
   6|from backend.app.core.config import settings
   7|from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaResult
   8|from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision
   9|from backend.app.domains.plan_bom.schemas.qa import PlanBomQaResponse
  10|from backend.app.domains.query_planning.services.shadow_snapshot_builder import QueryPlanningV2ShadowSnapshotBuilder
  11|
  12|logger = logging.getLogger(__name__)
  13|
  14|
  15|class QueryPlanningV2ResponseMetaExposureService:
  16|    """构建可选暴露到正式响应中的 Query Planning V2 轻量 meta。
  17|
  18|    说明：
  19|        1. 本服务只在请求显式开启、feature flag 开启且非生产环境时返回 meta；
  20|        2. 生产环境在正式用户权限模块接入前一律 fail-closed；
  21|        3. meta 只包含 strategy / query_key / comparison / risk_tags 等审计摘要；
  22|        4. 不暴露原始问题、完整 trace、request_payload、query_result、raw_result 或完整 query_plan_v2_shadow。
  23|    """
  24|
  25|    SAFE_COMPARISON_KEYS = (
  26|        "schema_version",
  27|        "domain",
  28|        "formal_status",
  29|        "formal_intent",
  30|        "formal_query_key",
  31|        "formal_result_count",
  32|        "shadow_strategy",
  33|        "shadow_query_key",
  34|        "query_key_matched",
  35|        "matched",
  36|        "risk_tags",
  37|        "guardrail_status",
  38|        "shadow_only",
  39|        "llm_can_execute",
  40|        "sql_generation_allowed",
  41|    )
  42|
  43|    def __init__(self, builder: QueryPlanningV2ShadowSnapshotBuilder | None = None) -> None:
  44|        """初始化响应 meta 暴露服务。
  45|
  46|        参数：
  47|            builder: shadow 快照构建器，测试可注入。
  48|        返回：无返回值。
  49|        """
  50|
  51|        self.builder = builder or QueryPlanningV2ShadowSnapshotBuilder()
  52|
  53|    def should_expose(self, *, requested: bool) -> bool:
  54|        """判断当前请求是否允许暴露 Query Planning V2 meta。
  55|
  56|        参数：
  57|            requested: 请求体中是否显式要求返回 meta。
  58|        返回：
  59|            True 表示允许返回轻量 meta；False 表示必须隐藏。
  60|        业务逻辑：生产环境未接入正式权限模块前 fail-closed，避免用临时 header/token 绕过。
  61|        """
  62|
  63|        if not requested:
  64|            return False
  65|        if not bool(getattr(settings, "query_planning_v2_response_meta_enabled", False)):
  66|            return False
  67|        app_env = str(getattr(settings, "app_env", "local") or "local").strip().lower()
  68|        return app_env not in {"prod", "production"}
  69|
  70|    def build_logistics_meta(
  71|        self,
  72|        *,
  73|        requested: bool,
  74|        question: str,
  75|        result: LogisticsDataQaResult,
  76|        trace_id: str | None = None,
  77|        guardrail_decision: LogisticsLlmGuardrailDecision | None = None,
  78|    ) -> dict[str, Any] | None:
  79|        """为物流正式响应构建可选 Query Planning V2 meta。
  80|
  81|        参数：
  82|            requested: 请求体是否显式开启 meta。
  83|            question: 用户原始问题，仅用于构建 shadow 快照，最终不会暴露。
  84|            result: 已完成的物流正式响应。
  85|            trace_id: 请求追踪号。
  86|            guardrail_decision: 可选 Guardrail 决策，通常正式 API 响应阶段为空。
  87|        返回：
  88|            允许暴露时返回安全 meta；否则返回 None。
  89|        """
  90|
  91|        if not self.should_expose(requested=requested):
  92|            return None
  93|        try:
  94|            snapshot = self.builder.build_logistics_snapshot(
  95|                question=question,
  96|                result=result,
  97|                trace_id=trace_id,
  98|                guardrail_decision=guardrail_decision,
  99|            )
 100|            return self.build_from_shadow_snapshot(
 101|                snapshot=snapshot,
 102|                trace_id=trace_id,
 103|                history_log_id=result.history_log_id,
 104|            )
 105|        except Exception as exc:  # noqa: BLE001
 106|            logger.warning("build logistics query_plan_v2 response meta failed: %s", exc)
 107|            return None
 108|
 109|    def build_plan_bom_meta(
 110|        self,
 111|        *,
 112|        requested: bool,
 113|        question: str,
 114|        response: PlanBomQaResponse,
 115|        trace_id: str | None = None,
 116|    ) -> dict[str, Any] | None:
 117|        """为计划 BOM 正式响应构建可选 Query Planning V2 meta。
 118|
 119|        参数：
 120|            requested: 请求体是否显式开启 meta。
 121|            question: 用户原始问题，仅用于构建 shadow 快照，最终不会暴露。
 122|            response: 已完成的 BOM 正式响应。
 123|            trace_id: 请求追踪号。
 124|        返回：
 125|            允许暴露时返回安全 meta；否则返回 None。
 126|        """
 127|
 128|        if not self.should_expose(requested=requested):
 129|            return None
 130|        try:
 131|            snapshot = self.builder.build_plan_bom_snapshot(
 132|                question=question,
 133|                response=response,
 134|                trace_id=trace_id,
 135|            )
 136|            return self.build_from_shadow_snapshot(snapshot=snapshot, trace_id=trace_id)
 137|        except Exception as exc:  # noqa: BLE001
 138|            logger.warning("build plan bom query_plan_v2 response meta failed: %s", exc)
 139|            return None
 140|
 141|    @classmethod
 142|    def build_from_shadow_snapshot(
 143|        cls,
 144|        *,
 145|        snapshot: dict[str, Any],
 146|        trace_id: str | None = None,
 147|        history_log_id: int | None = None,
 148|    ) -> dict[str, Any]:
 149|        """从完整 shadow 快照中提取可暴露的轻量 meta。
 150|
 151|        参数：
 152|            snapshot: 完整 query_plan_v2_shadow 快照。
 153|            trace_id: 请求追踪号。
 154|            history_log_id: 可选查询历史 ID。
 155|        返回：
 156|            可放入正式响应 `query_plan_v2_meta` 的安全摘要。
 157|        """
 158|
 159|        comparison = snapshot.get("comparison") if isinstance(snapshot.get("comparison"), dict) else {}
 160|        safe_comparison = {key: comparison.get(key) for key in cls.SAFE_COMPARISON_KEYS if key in comparison}
 161|        risk_tags = cls._safe_list(snapshot.get("risk_tags") or safe_comparison.get("risk_tags"))
 162|        policy = snapshot.get("execution_policy") if isinstance(snapshot.get("execution_policy"), dict) else {}
 163|        return {
 164|            "schema_version": "query_plan_v2.response_meta.v1",
 165|            "enabled": True,
 166|            "domain": snapshot.get("domain") or safe_comparison.get("domain"),
 167|            "trace_id": trace_id,
 168|            "history_log_id": history_log_id,
 169|            "strategy": snapshot.get("strategy") or safe_comparison.get("shadow_strategy"),
 170|            "query_key": snapshot.get("query_key") or safe_comparison.get("shadow_query_key"),
 171|            "intent": snapshot.get("intent"),
 172|            "matched": safe_comparison.get("matched"),
 173|            "risk_tags": risk_tags,
 174|            "comparison": safe_comparison,
 175|            "shadow_only": policy.get("shadow_only", safe_comparison.get("shadow_only", True)),
 176|            "llm_can_execute": policy.get("llm_can_execute", safe_comparison.get("llm_can_execute", False)),
 177|            "sql_generation_allowed": policy.get(
 178|                "sql_generation_allowed",
 179|                safe_comparison.get("sql_generation_allowed", False),
 180|            ),
 181|        }
 182|
 183|    @staticmethod
 184|    def _safe_list(value: Any) -> list[str]:
 185|        """把风险标签转换为字符串列表。"""
 186|
 187|        if not isinstance(value, list):
 188|            return []
 189|        return [str(item) for item in value if str(item)]
 190|
 191|
 192|__all__ = ["QueryPlanningV2ResponseMetaExposureService"]
```


## backend/app/domains/plan_bom/services/qa_service.py:270-525
```python
 270|    def _compare_response(self, *, question: str, nlu: PlanBomNluCandidate) -> PlanBomQaResponse:
 271|        """处理跨订单或版本差异查询。
 272|
 273|        参数：
 274|            question: 原始问题；
 275|            nlu: NLU 候选。
 276|
 277|        返回：
 278|            QA 响应。
 279|        """
 280|
 281|        categories, non_core_response = self._resolve_core_material_categories(question=question, nlu=nlu)
 282|        if non_core_response:
 283|            return non_core_response
 284|        tails = nlu.slots.get("order_tail_no") or []
 285|        versions = nlu.slots.get("bom_version") or []
 286|        if nlu.intent == "bom_version_compare" and len(versions) >= 2 and tails:
 287|            left = PlanBomCompareSideRequest(order_no=tails[0], version_no=versions[0])
 288|            right = PlanBomCompareSideRequest(order_no=tails[0], version_no=versions[1])
 289|        elif len(tails) >= 2:
 290|            if tails[0] == tails[1]:
 291|                nlu.missing_slots = sorted(set([*(nlu.missing_slots or []), "compare_orders"]))
 292|                return self._clarification_response(question=question, nlu=nlu)
 293|            left = PlanBomCompareSideRequest(order_no=tails[0])
 294|            right = PlanBomCompareSideRequest(order_no=tails[1])
 295|        else:
 296|            return self._clarification_response(question=question, nlu=nlu)
 297|        compare_payload = PlanBomCompareQueryRequest(left=left, right=right, material_categories=categories, candidate_limit=20)
 298|        result = self.query_service.compare(compare_payload)
 299|        if result.status.code != "OK" or not result.compare_ready:
 300|            expanded_response = self._expanded_candidate_compare_response(
 301|                question=question,
 302|                nlu=nlu,
 303|                payload=compare_payload,
 304|                candidate_result=result,
 305|            )
 306|            if expanded_response:
 307|                return expanded_response
 308|            return self._non_ok_query_response(question=question, nlu=nlu, raw=result.model_dump(mode="json"))
 309|        rows: list[dict[str, Any]] = []
 310|        description_only = self._is_description_compare_question(question)
 311|        for item in result.changed:
 312|            if description_only and "description" not in item.changed_fields:
 313|                continue
 314|            rows.append(self._compare_changed_row(item.model_dump(mode="json")))
 315|        for item in result.only_left:
 316|            rows.append(self._compare_single_side_row(item.model_dump(mode="json"), side="仅左侧"))
 317|        for item in result.only_right:
 318|            rows.append(self._compare_single_side_row(item.model_dump(mode="json"), side="仅右侧"))
 319|        answer = f"已完成 BOM 差异对比，变化 {len(result.changed)} 条，仅左侧 {len(result.only_left)} 条，仅右侧 {len(result.only_right)} 条。"
 320|        return self._with_presentation(
 321|            PlanBomQaResponse(
 322|                question=question,
 323|                classification="A",
 324|                status=PlanBomQaStatus(code="OK", message="对比成功"),
 325|                nlu=nlu,
 326|                answer_summary=answer,
 327|                result_table=PlanBomTableSpec(columns=self._compare_columns(), rows=rows),
 328|                raw_result=result.model_dump(mode="json"),
 329|            )
 330|        )
 331|
 332|    def _expanded_candidate_compare_response(
 333|        self,
 334|        *,
 335|        question: str,
 336|        nlu: PlanBomNluCandidate,
 337|        payload: PlanBomCompareQueryRequest,
 338|        candidate_result: PlanBomCompareResponse,
 339|    ) -> PlanBomQaResponse | None:
 340|        """把跨订单 compare 的单侧多业务实例候选展开为多组确定性对比。
 341|
 342|        参数：
 343|            question: 原始问题；
 344|            nlu: 已完成槽位抽取的 NLU 候选；
 345|            payload: 初次 compare 请求；
 346|            candidate_result: 初次 compare 返回的候选态结果。
 347|
 348|        返回：
 349|            若可安全展开，则返回 A 类对比表；否则返回 None，继续沿用候选追问兜底。
 350|
 351|        业务逻辑：
 352|            用户明确要求“订单 A 和订单 B 的规格描述有什么不一样，并用表格统计”时，短订单号 B
 353|            可能对应多个真实业务实例。此时不能随机选择其中一个，也不应把内部 `order_identity`
 354|            暴露成泛化追问；安全做法是把多业务实例逐个与已确定的另一侧做确定性 compare，
 355|            在表格中保留左右实例名称和版本，业务员可直接看到每个候选实例的差异。
 356|        """
 357|
 358|        candidates = list(candidate_result.candidates or [])
 359|        if not self._can_expand_compare_candidates(nlu=nlu, candidate_result=candidate_result, candidates=candidates):
 360|            return None
 361|
 362|        pair_rows: list[dict[str, Any]] = []
 363|        compared_pairs: list[dict[str, Any]] = []
 364|        pair_summaries: list[dict[str, Any]] = []
 365|        warnings: list[str] = []
 366|        ambiguous_side = candidate_result.candidate_side
 367|        assert ambiguous_side in {"left", "right"}
 368|        description_only = self._is_description_compare_question(question)
 369|
 370|        for candidate in candidates:
 371|            expanded_payload = self._expanded_compare_payload_for_candidate(
 372|                original_payload=payload,
 373|                candidate_result=candidate_result,
 374|                candidate=candidate,
 375|            )
 376|            if expanded_payload is None:
 377|                return None
 378|            pair_result = self.query_service.compare(expanded_payload)
 379|            pair_summary = self._expanded_pair_summary(pair_result)
 380|            pair_summaries.append(pair_summary)
 381|            if pair_result.status.code != "OK" or not pair_result.compare_ready or not pair_result.left or not pair_result.right:
 382|                warnings.append(
 383|                    f"候选 {self._compare_side_label(candidate)} 未能完成对比：{pair_result.status.message}"
 384|                )
 385|                continue
 386|
 387|            left_label = self._compare_side_label(pair_result.left)
 388|            right_label = self._compare_side_label(pair_result.right)
 389|            pair_label = f"{left_label} ↔ {right_label}"
 390|            compared_pairs.append(
 391|                {
 392|                    "compare_pair": pair_label,
 393|                    "left_order_identity_key": pair_result.left.order_identity_key,
 394|                    "left_file_instance_key": pair_result.left.file_instance_key,
 395|                    "left_order_no": pair_result.left.order_no,
 396|                    "left_version_no": pair_result.left.version_no,
 397|                    "right_order_identity_key": pair_result.right.order_identity_key,
 398|                    "right_file_instance_key": pair_result.right.file_instance_key,
 399|                    "right_order_no": pair_result.right.order_no,
 400|                    "right_version_no": pair_result.right.version_no,
 401|                }
 402|            )
 403|            pair_rows.extend(
 404|                self._compare_rows_for_pair(
 405|                    pair_result=pair_result,
 406|                    pair_label=pair_label,
 407|                    left_label=left_label,
 408|                    right_label=right_label,
 409|                    description_only=description_only,
 410|                )
 411|            )
 412|
 413|        if not compared_pairs:
 414|            return None
 415|
 416|        left_count = len(candidates) if ambiguous_side == "left" else 1
 417|        right_count = len(candidates) if ambiguous_side == "right" else 1
 418|        answer = (
 419|            f"已展开{self._compare_side_name(ambiguous_side)}侧 {len(candidates)} 个业务实例并完成 "
 420|            f"{len(compared_pairs)} 组 BOM 核心材料规格差异对比，生成 {len(pair_rows)} 条差异记录。"
 421|        )
 422|        if warnings:
 423|            answer += f"其中 {len(warnings)} 个候选未完成对比，已在风险提示中列出。"
 424|        return self._with_presentation(
 425|            PlanBomQaResponse(
 426|                question=question,
 427|                classification="A",
 428|                status=PlanBomQaStatus(code="OK", message="对比成功"),
 429|                nlu=nlu,
 430|                answer_summary=answer,
 431|                result_table=PlanBomTableSpec(columns=self._expanded_compare_columns(), rows=pair_rows),
 432|                raw_result={
 433|                    "expanded_compare": True,
 434|                    "expanded_side": ambiguous_side,
 435|                    "left_candidate_count": left_count,
 436|                    "right_candidate_count": right_count,
 437|                    "compared_pairs": compared_pairs,
 438|                    "pair_summaries": pair_summaries,
 439|                    "source_candidate_result": candidate_result.model_dump(mode="json"),
 440|                },
 441|                warnings=warnings,
 442|            )
 443|        )
 444|
 445|    @staticmethod
 446|    def _can_expand_compare_candidates(
 447|        *,
 448|        nlu: PlanBomNluCandidate,
 449|        candidate_result: PlanBomCompareResponse,
 450|        candidates: list[PlanBomCandidate],
 451|    ) -> bool:
 452|        """判断 compare 候选态是否允许自动展开为多组对比。
 453|
 454|        只有跨订单材料对比、单侧业务实例候选且候选数受控时才展开；版本、文件实例或单订单查询
 455|        仍 fail closed，避免替业务员选择比较基线。
 456|        """
 457|
 458|        if nlu.intent != "cross_order_material_compare":
 459|            return False
 460|        if candidate_result.status.code != "CANDIDATE_REQUIRED":
 461|            return False
 462|        if candidate_result.candidate_scope != CANDIDATE_SCOPE_ORDER_IDENTITY:
 463|            return False
 464|        if candidate_result.candidate_side not in {"left", "right"}:
 465|            return False
 466|        candidate_truncated = bool(candidate_result.status.extras.get("candidate_truncated")) or bool(
 467|            (candidate_result.response_meta or {}).get("candidate_truncated")
 468|        )
 469|        if candidate_truncated or int(candidate_result.candidate_total_hint or 0) > len(candidates):
 470|            return False
 471|        if not candidates or len(candidates) > 20:
 472|            return False
 473|        return True
 474|
 475|    def _expanded_compare_payload_for_candidate(
 476|        self,
 477|        *,
 478|        original_payload: PlanBomCompareQueryRequest,
 479|        candidate_result: PlanBomCompareResponse,
 480|        candidate: PlanBomCandidate,
 481|    ) -> PlanBomCompareQueryRequest | None:
 482|        """构造单个候选实例对应的精确 compare 请求。"""
 483|
 484|        candidate_side = self._compare_side_request_from_candidate(candidate)
 485|        if candidate_result.candidate_side == "right":
 486|            if not candidate_result.left:
 487|                return None
 488|            left_side = self._compare_side_request_from_context(candidate_result.left)
 489|            right_side = candidate_side
 490|        else:
 491|            if not candidate_result.right:
 492|                return None
 493|            left_side = candidate_side
 494|            right_side = self._compare_side_request_from_context(candidate_result.right)
 495|        return PlanBomCompareQueryRequest(
 496|            left=left_side,
 497|            right=right_side,
 498|            material_categories=original_payload.material_categories,
 499|            candidate_limit=original_payload.candidate_limit,
 500|        )
 501|
 502|    @staticmethod
 503|    def _compare_side_request_from_candidate(candidate: PlanBomCandidate) -> PlanBomCompareSideRequest:
 504|        """从候选列表项生成精确 compare 单侧请求。"""
 505|
 506|        return PlanBomCompareSideRequest(
 507|            order_identity_key=candidate.order_identity_key,
 508|            file_instance_key=candidate.file_instance_key,
 509|            version_no=candidate.version_no,
 510|        )
 511|
 512|    @staticmethod
 513|    def _compare_side_request_from_context(context: PlanBomCompareSideContext) -> PlanBomCompareSideRequest:
 514|        """从已解析 compare 上下文生成精确 compare 单侧请求。"""
 515|
 516|        return PlanBomCompareSideRequest(
 517|            order_identity_key=context.order_identity_key,
 518|            file_instance_key=context.file_instance_key,
 519|            version_no=context.version_no,
 520|        )
 521|
 522|    @staticmethod
 523|    def _compare_side_label(side: PlanBomCandidate | PlanBomCompareSideContext) -> str:
 524|        """生成业务可读的 compare 单侧实例标签。"""
 525|
```


## backend/app/domains/plan_bom/api/endpoints/qa.py:1-160
```python
   1|from __future__ import annotations
   2|
   3|import re
   4|
   5|from fastapi import APIRouter, Depends, Request
   6|from fastapi.responses import StreamingResponse
   7|
   8|from backend.app.api.deps import get_plan_bom_qa_service
   9|from backend.app.domains.plan_bom.schemas.qa import PlanBomQaRequest
  10|from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
  11|from backend.app.domains.query_planning.services.response_meta_exposure_service import QueryPlanningV2ResponseMetaExposureService
  12|from backend.app.schemas.common import ApiResponse
  13|from backend.app.services.business_answer_stream_service import BusinessAnswerStreamService, build_json_line_event
  14|
  15|router = APIRouter()
  16|
  17|
  18|def _plan_bom_fallback_has_technical_leak(answer: str) -> bool:
  19|    """检查计划 BOM 流式兜底候选是否包含前端不可见的技术痕迹。"""
  20|
  21|    patterns = (
  22|        r"槽位",
  23|        r"字段",
  24|        r"表定义",
  25|        r"库定义",
  26|        r"数据库",
  27|        r"\bSQL\b",
  28|        r"\bquery(?:[-_ ]?(?:plan|key)|_key)?\b",
  29|        r"\bqueryKey\b",
  30|        r"\bplanner\b",
  31|        r"\bguard\s*rail\b",
  32|        r"\bguardrail\b",
  33|        r"\braw_result\b",
  34|        r"\bschema\b",
  35|        r"\bLLM\b",
  36|        r"\b[a-z]+_[a-z0-9_]+\b",
  37|    )
  38|    return any(re.search(pattern, answer or "", flags=re.I) for pattern in patterns)
  39|
  40|
  41|def _resolve_plan_bom_stream_fallback_answer(result_payload: dict) -> str:
  42|    """解析 Plan BOM 流式回答的确定性兜底文案。
  43|
  44|    参数：
  45|        result_payload: `PlanBomQaResponse.model_dump` 后的确定性响应快照。
  46|
  47|    返回：
  48|        可直接流式输出给业务员的安全兜底文本。
  49|
  50|    业务逻辑：
  51|        Plan BOM 的 `answer_summary` 可能携带槽位名等内部口径；若展示层已经生成
  52|        `presentation.answer`，流式降级应优先使用业务化表达，避免前端看到内部术语。
  53|    """
  54|
  55|    presentation = result_payload.get("presentation") if isinstance(result_payload, dict) else None
  56|    candidates: list[str] = []
  57|    if isinstance(presentation, dict) and presentation.get("answer"):
  58|        candidates.append(str(presentation["answer"]))
  59|    if isinstance(result_payload, dict) and result_payload.get("answer_summary"):
  60|        candidates.append(str(result_payload["answer_summary"]))
  61|    status = result_payload.get("status") if isinstance(result_payload, dict) else None
  62|    if isinstance(status, dict) and status.get("message"):
  63|        candidates.append(str(status["message"]))
  64|    for candidate in candidates:
  65|        if candidate and not _plan_bom_fallback_has_technical_leak(candidate):
  66|            return candidate
  67|    return "当前计划 BOM 查询已完成，我会基于已导入的数据整理结论；请查看下方数据依据。"
  68|
  69|
  70|@router.post("/ask", response_model=ApiResponse)
  71|def ask_plan_bom(
  72|    payload: PlanBomQaRequest,
  73|    request: Request,
  74|    service: PlanBomQaService = Depends(get_plan_bom_qa_service),
  75|) -> ApiResponse:
  76|    """计划 BOM 自然语言问答入口。
  77|
  78|    说明：
  79|        1. 接收用户自然语言问题；
  80|        2. 先执行 BOM NLU Center，再复用已有 detail / compare 查询服务；
  81|        3. 最终返回受控 QA 响应和 presentation；
  82|        4. LLM 只做理解候选与表达优化，不直接生成 BOM 事实。
  83|    """
  84|
  85|    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", payload.trace_id or ""))
  86|    try:
  87|        result = service.ask(payload.question, use_llm=True, trace_id=trace_id)
  88|        result_payload = result.model_dump(mode="json")
  89|        query_plan_v2_meta = QueryPlanningV2ResponseMetaExposureService().build_plan_bom_meta(
  90|            requested=payload.include_query_plan_v2_meta,
  91|            question=payload.question,
  92|            response=result,
  93|            trace_id=trace_id,
  94|        )
  95|        if query_plan_v2_meta:
  96|            result_payload["query_plan_v2_meta"] = query_plan_v2_meta
  97|        return ApiResponse.success(result_payload, trace_id=trace_id)
  98|    except Exception as exc:  # noqa: BLE001
  99|        # 计划 BOM 问答与物流问答使用同一张 sys_query_log；异常也要留存，便于业务回看失败问题。
 100|        service.write_error_log(question=payload.question, trace_id=trace_id, message=str(exc))
 101|        raise
 102|
 103|
 104|@router.post("/ask/stream")
 105|def ask_plan_bom_stream(
 106|    payload: PlanBomQaRequest,
 107|    request: Request,
 108|    service: PlanBomQaService = Depends(get_plan_bom_qa_service),
 109|) -> StreamingResponse:
 110|    """计划 BOM 自然语言问答流式入口。
 111|
 112|    说明：
 113|        1. 确定性 BOM/NLU/功率模型链路先执行，保证事实和数值可追溯；
 114|        2. 把用户原问题和确定性响应快照交给 LLM，只生成更自然的答案表达；
 115|        3. done 事件返回完整结构化结果，表格和状态不由 LLM 改写。
 116|    """
 117|
 118|    trace_id = getattr(request.state, "trace_id", getattr(request.state, "request_id", payload.trace_id or ""))
 119|    stream_service = BusinessAnswerStreamService()
 120|
 121|    def iter_events():
 122|        """逐行输出 NDJSON 事件，供前端 fetch 流式消费。"""
 123|
 124|        yield build_json_line_event("meta", {"trace_id": trace_id, "domain": "plan_bom", "stage": "received"})
 125|        try:
 126|            result = service.ask(payload.question, use_llm=True, trace_id=trace_id)
 127|            result_payload = result.model_dump(mode="json")
 128|            yield build_json_line_event(
 129|                "meta",
 130|                {
 131|                    "trace_id": trace_id,
 132|                    "domain": "plan_bom",
 133|                    "stage": "deterministic_result_ready",
 134|                    "status_code": (result_payload.get("status") or {}).get("code"),
 135|                },
 136|            )
 137|            chunks: list[str] = []
 138|            fallback_answer = _resolve_plan_bom_stream_fallback_answer(result_payload)
 139|            for chunk in stream_service.stream_answer(
 140|                domain="plan_bom",
 141|                question=payload.question,
 142|                deterministic_payload=result_payload,
 143|                fallback_answer=fallback_answer,
 144|            ):
 145|                chunks.append(chunk)
 146|                yield build_json_line_event("delta", {"text": chunk})
 147|            final_answer = "".join(chunks).strip()
 148|            final_payload = stream_service.apply_streamed_answer(
 149|                domain="plan_bom",
 150|                deterministic_payload=result_payload,
 151|                streamed_answer=final_answer,
 152|            )
 153|            query_plan_v2_meta = QueryPlanningV2ResponseMetaExposureService().build_plan_bom_meta(
 154|                requested=payload.include_query_plan_v2_meta,
 155|                question=payload.question,
 156|                response=result,
 157|                trace_id=trace_id,
 158|            )
 159|            if query_plan_v2_meta:
 160|                final_payload["query_plan_v2_meta"] = query_plan_v2_meta
```


## backend/app/domains/plan_bom/services/answer_presentation_service.py:420-670
```python
 420|            if response.nlu.intent == "plan_power_supplier_recommendation":
 421|                return "计划 BOM 供应商功率推荐结果"
 422|            return "计划 BOM 查询结果"
 423|        if response.classification == "B":
 424|            return "需要补充条件后继续查询"
 425|        if response.classification == "C":
 426|            return "当前 BOM 数据暂不能直接回答"
 427|        return "计划 BOM 问题待确认"
 428|
 429|    def _build_highlights(self, response: PlanBomQaResponse) -> list[str]:
 430|        """生成关键结论。
 431|
 432|        参数：
 433|            response: QA 响应。
 434|
 435|        返回：
 436|            关键结论列表。
 437|        """
 438|
 439|        highlights = []
 440|        status_message = self._safe_business_text(response.status.message)
 441|        if status_message:
 442|            highlights.append(status_message)
 443|        if response.result_table.rows:
 444|            highlights.append(f"命中 {len(response.result_table.rows)} 条 BOM 记录。")
 445|        material_values = response.nlu.slots.get("material_category")
 446|        if material_values:
 447|            material_labels = [self._business_value(item) for item in material_values]
 448|            highlights.append(f"材料范围：{', '.join(material_labels)}")
 449|        if response.nlu.intent in {"plan_power_prediction", "plan_power_supplier_recommendation"}:
 450|            model_code = response.raw_result.get("bom_config_resolution", {}).get("model_code")
 451|            if model_code:
 452|                highlights.append(f"功率版型：{model_code}")
 453|            if response.raw_result.get("power_prediction", {}).get("supplier_name"):
 454|                highlights.append(f"供应商：{response.raw_result['power_prediction']['supplier_name']}")
 455|            if response.raw_result.get("power_recommendation", {}).get("recommendations"):
 456|                highlights.append(f"推荐供应商数：{len(response.raw_result['power_recommendation']['recommendations'])}")
 457|        return [item for item in highlights if not self._visible_text_has_technical_leak(item)]
 458|
 459|    @staticmethod
 460|    def _build_follow_up_examples(response: PlanBomQaResponse) -> list[str]:
 461|        """生成补槽示例。
 462|
 463|        参数：
 464|            response: QA 响应。
 465|
 466|        返回：
 467|            可点击或可复制的示例问法。
 468|        """
 469|
 470|        if "order_id" in response.nlu.missing_slots:
 471|            if response.nlu.intent in {"plan_power_prediction", "plan_power_supplier_recommendation"}:
 472|                return ["请补充订单号，例如：订单00104做功率预测。"]
 473|            return ["请补充订单号，例如：订单00104的接线盒规格是什么？"]
 474|        if "target_power_ratio" in response.nlu.missing_slots:
 475|            return ["请补充目标功率比例，例如：订单00104目标620W 50%，625W 50%，推荐供应商。"]
 476|        if "power_configuration" in response.nlu.missing_slots:
 477|            return ["请确认未识别的功率配置，例如玻璃、接线盒线径、标板基准或供应商。"]
 478|        if "compare_orders" in response.nlu.missing_slots:
 479|            return ["请补充两个订单号，例如：订单00067和00106的接线盒有什么不一样？"]
 480|        return ["请补充订单、版本、材料类别或查询范围后继续。"]
 481|
 482|    def _request_llm(self, response: PlanBomQaResponse, fallback: PlanBomPresentation) -> tuple[dict[str, Any] | None, str | None]:
 483|        """请求 LLM 表达优化。
 484|
 485|        参数：
 486|            response: 确定性 QA 响应；
 487|            fallback: 确定性展示，用于限定字段。
 488|
 489|        返回：
 490|            二元组：(LLM JSON, 错误信息)。
 491|        """
 492|
 493|        try:
 494|            client = self._client or OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=15, max_retries=0)
 495|            completion = client.chat.completions.create(
 496|                model=self.model,
 497|                temperature=0,
 498|                messages=[
 499|                    {"role": "system", "content": self._build_system_prompt()},
 500|                    {"role": "user", "content": self._build_user_prompt(response, fallback)},
 501|                ],
 502|            )
 503|            content = completion.choices[0].message.content or "{}"
 504|            return self._extract_json(content), None
 505|        except Exception as exc:  # noqa: BLE001
 506|            return None, str(exc)
 507|
 508|    def _normalize_and_validate(
 509|        self,
 510|        response: PlanBomQaResponse,
 511|        fallback: PlanBomPresentation,
 512|        payload: dict[str, Any] | None,
 513|    ) -> tuple[PlanBomPresentation | None, str | None]:
 514|        """归一并校验 LLM 表达结果。
 515|
 516|        参数：
 517|            response: 确定性 QA 响应；
 518|            fallback: 确定性展示；
 519|            payload: LLM 返回 JSON。
 520|
 521|        返回：
 522|            二元组：(presentation, 校验错误)。错误为空表示可采用。
 523|        """
 524|
 525|        if not isinstance(payload, dict):
 526|            return None, "llm_payload_not_object"
 527|        display_type = str(payload.get("display_type") or fallback.display_type)
 528|        if display_type not in self.DISPLAY_TYPES:
 529|            return None, "llm_display_type_invalid"
 530|        if display_type != fallback.display_type:
 531|            # 展示形式由确定性层根据用户显式意图裁决，LLM 只优化文字，不能主动加表格或取消用户要求的表格。
 532|            return None, "llm_display_type_changed"
 533|        table_payload = payload.get("table_spec")
 534|        table_spec = fallback.table_spec
 535|        if table_payload is not None:
 536|            try:
 537|                candidate = PlanBomTableSpec.model_validate(table_payload)
 538|            except Exception:  # noqa: BLE001
 539|                return None, "llm_table_schema_invalid"
 540|            if candidate.model_dump(mode="json") != (fallback.table_spec.model_dump(mode="json") if fallback.table_spec else None):
 541|                return None, "llm_table_changed"
 542|            table_spec = candidate
 543|        answer = str(payload.get("answer") or fallback.answer)
 544|        title = str(payload.get("title") or fallback.title)
 545|        highlights = [str(item) for item in payload.get("highlights") or fallback.highlights]
 546|        caveats = [str(item) for item in payload.get("caveats") or fallback.caveats]
 547|        visible_text = "\n".join([title, answer, *highlights, *caveats])
 548|        if self._visible_text_has_technical_leak(visible_text):
 549|            return None, "llm_visible_technical_leak"
 550|        if not self._answer_mentions_only_existing_values(answer, response):
 551|            return None, "llm_answer_contains_unverified_value"
 552|        return (
 553|            PlanBomPresentation(
 554|                display_type=display_type,
 555|                title=title,
 556|                answer=answer,
 557|                highlights=highlights,
 558|                table_spec=table_spec,
 559|                caveats=caveats,
 560|                follow_up=fallback.follow_up,
 561|                unsupported_explanation=fallback.unsupported_explanation,
 562|                debug=dict(fallback.debug),
 563|            ),
 564|            None,
 565|        )
 566|
 567|    @staticmethod
 568|    def _answer_mentions_only_existing_values(answer: str, response: PlanBomQaResponse) -> bool:
 569|        """校验回答文本是否只引用可追溯事实。
 570|
 571|        参数：
 572|            answer: LLM 回答文本；
 573|            response: 确定性 QA 响应。
 574|
 575|        返回：
 576|            当前采用保守策略：只要没有明显新增订单号格式即可通过。
 577|        """
 578|
 579|        known_text = json.dumps(response.model_dump(mode="json"), ensure_ascii=False)
 580|        for order in re.findall(r"20\d{2}-\d{5}|\b\d{5}\b", answer):
 581|            if order not in known_text:
 582|                return False
 583|        return True
 584|
 585|    def _is_llm_available(self) -> bool:
 586|        """判断 LLM 是否可用。
 587|
 588|        返回：
 589|            配置齐全时返回 True。
 590|        """
 591|
 592|        return bool(self.base_url and self.api_key and self.model)
 593|
 594|    @staticmethod
 595|    def _extract_json(content: str) -> dict[str, Any]:
 596|        """从 LLM 文本中提取 JSON。
 597|
 598|        参数：
 599|            content: LLM 返回文本。
 600|
 601|        返回：
 602|            JSON 对象。
 603|        """
 604|
 605|        stripped = content.strip()
 606|        if stripped.startswith("```"):
 607|            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
 608|            stripped = re.sub(r"\s*```$", "", stripped)
 609|        match = re.search(r"\{.*\}", stripped, flags=re.S)
 610|        parsed = json.loads(match.group(0) if match else stripped)
 611|        return parsed if isinstance(parsed, dict) else {}
 612|
 613|    @staticmethod
 614|    def _build_system_prompt() -> str:
 615|        """构造表达层系统提示词。
 616|
 617|        返回：
 618|            约束 LLM 只做表达的提示词。
 619|        """
 620|
 621|        return (
 622|            "你是计划 BOM 问答的答案表达层，只能优化文字和展示编排。\n"
 623|            "不能新增订单、物料、版本、规格、用量或供应商；不能把追问/拒答包装成可答。\n"
 624|            "面向业务员的可见回答中，禁止出现槽位、字段、表名、库名、SQL、query、schema、guardrail、debug、LLM 或英文蛇形命名等技术词。\n"
 625|            "未明确要求表格/明细/清单/导出时，display_type 必须保持 narrative，table_spec 必须为空；不要固定展示明细数据。\n"
 626|            "answer 可以使用清晰 Markdown 段落、加粗和列表，语气要专业、温馨、清晰，先给结论，再说明查询思路和依据。\n"
 627|            "输出单个 JSON，字段可包含 display_type,title,answer,highlights,table_spec,caveats。"
 628|        )
 629|
 630|    def _build_user_prompt(self, response: PlanBomQaResponse, fallback: PlanBomPresentation) -> str:
 631|        """构造表达层用户提示词。
 632|
 633|        参数：
 634|            response: 确定性 QA 响应；
 635|            fallback: 确定性展示。
 636|
 637|        返回：
 638|            JSON 上下文文本。
 639|        """
 640|
 641|        public_context = {
 642|            "用户原问题": response.question,
 643|            "状态": response.status.message,
 644|            "业务结论草稿": fallback.answer,
 645|            "展示形式": fallback.display_type,
 646|            "关键结论": fallback.highlights,
 647|            "数据口径": fallback.caveats,
 648|            "结果表": {
 649|                "columns": [self._business_column_label(column) for column in response.result_table.columns],
 650|                "rows": [
 651|                    {
 652|                        self._business_column_label(str(key)): self._business_value(value)
 653|                        for key, value in row.items()
 654|                        if self._business_column_label(str(key)) and value is not None and value != ""
 655|                    }
 656|                    for row in response.result_table.rows[:30]
 657|                ],
 658|                "total_rows": len(response.result_table.rows),
 659|            },
 660|            "表达要求": [
 661|                "先给结论，再说明你按什么业务顺序核对。",
 662|                "只能使用这里给出的事实，不补充外部信息。",
 663|                "不要出现槽位、字段、表名、库名或英文蛇形命名。",
 664|            ],
 665|        }
 666|        return json.dumps(public_context, ensure_ascii=False, default=str)
 667|
 668|
 669|__all__ = ["PlanBomAnswerPresentationService"]
```


## tests/business_acceptance/test_plan_bom_qa_multi_candidate_compare.py:1-180
```python
   1|from __future__ import annotations
   2|
   3|import pytest
   4|
   5|from backend.app.db.session import SessionLocal
   6|from backend.app.domains.plan_bom.models import PlanBomHeader
   7|from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
   8|from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate
   9|from backend.app.domains.plan_bom.schemas.query import PlanBomCandidate, PlanBomCompareResponse, PlanBomStatus
  10|from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
  11|from backend.app.domains.plan_bom.services.nlu_center_service import PlanBomNluCenterService
  12|from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
  13|from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService
  14|
  15|
  16|@pytest.fixture()
  17|def live_db_session():
  18|    """连接当前项目真实 BOM 数据库，用真实订单尾号复现多候选 compare 问题。"""
  19|    session = SessionLocal()
  20|    try:
  21|        try:
  22|            session.query(PlanBomHeader).limit(1).all()
  23|        except Exception as exc:  # pragma: no cover - 本地无验收库时跳过。
  24|            pytest.skip(f"当前环境无法连接真实 BOM 数据库，跳过计划 BOM compare 验收：{exc}")
  25|        yield session
  26|    finally:
  27|        session.close()
  28|
  29|
  30|@pytest.fixture()
  31|def qa_service(live_db_session) -> PlanBomQaService:
  32|    """构造关闭 LLM 的计划 BOM QA 服务，只验证确定性 NLU + 查询链路。"""
  33|    repository = PlanBomQueryRepository(live_db_session)
  34|    return PlanBomQaService(
  35|        repository=repository,
  36|        query_service=PlanBomQueryService(repository=repository),
  37|        nlu_service=PlanBomNluCenterService(repository=repository, base_url="", api_key="", model=""),
  38|        presentation_service=PlanBomAnswerPresentationService(enabled=False, base_url="", api_key="", model=""),
  39|    )
  40|
  41|
  42|def _require_tail_headers(session, tail: str) -> list[PlanBomHeader]:
  43|    """读取真实库中包含指定尾号的有效 BOM 头；不存在时跳过而不是伪造数据。"""
  44|    headers = (
  45|        session.query(PlanBomHeader)
  46|        .filter(PlanBomHeader.is_active == 1, PlanBomHeader.order_no.contains(tail))
  47|        .order_by(PlanBomHeader.order_no.asc(), PlanBomHeader.order_name.asc(), PlanBomHeader.version_no.asc())
  48|        .all()
  49|    )
  50|    if not headers:
  51|        pytest.skip(f"当前真实 BOM 数据缺少订单尾号 {tail}，无法复现本次业务问题。")
  52|    return headers
  53|
  54|
  55|def test_table_compare_expands_multi_candidate_order_tail_without_clarification(live_db_session, qa_service) -> None:
  56|    """两个订单尾号做规格差异表时，多业务实例尾号应全部展开对比，而不是追问内部 order_identity。"""
  57|    _require_tail_headers(live_db_session, "00067")
  58|    right_headers = _require_tail_headers(live_db_session, "00106")
  59|    if len({header.order_identity_key for header in right_headers}) < 2:
  60|        pytest.skip("当前真实 BOM 数据中的 00106 未形成多业务实例候选，无法复现本次缺陷。")
  61|
  62|    response = qa_service.ask(
  63|        "订单00067和订单00106玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述有什么不一样，并用表格统计出来",
  64|        use_llm=False,
  65|    )
  66|
  67|    assert response.classification == "A"
  68|    assert response.status.code == "OK"
  69|    assert response.nlu.intent == "cross_order_material_compare"
  70|    assert "order_identity" not in response.nlu.missing_slots
  71|    assert response.result_table.rows
  72|    assert {"compare_pair", "left_instance", "right_instance", "left_description", "right_description"}.issubset(
  73|        set(response.result_table.columns)
  74|    )
  75|    assert response.raw_result.get("expanded_compare") is True
  76|    assert response.raw_result.get("right_candidate_count", 0) >= 2
  77|    assert len(response.raw_result.get("compared_pairs") or []) >= 2
  78|
  79|
  80|def test_single_ambiguous_order_tail_still_requires_business_instance_confirmation(qa_service, live_db_session) -> None:
  81|    """单订单查询没有对比展开语义时，仍需确认业务实例，避免静默选错候选。"""
  82|    right_headers = _require_tail_headers(live_db_session, "00106")
  83|    if len({header.order_identity_key for header in right_headers}) < 2:
  84|        pytest.skip("当前真实 BOM 数据中的 00106 未形成多业务实例候选，无法验证单订单保护。")
  85|
  86|    response = qa_service.ask("订单00106玻璃规格描述是什么", use_llm=False)
  87|
  88|    assert response.classification == "B"
  89|    assert response.status.code == "CLARIFICATION_REQUIRED"
  90|    assert response.result_table.rows == []
  91|    assert any(slot in response.nlu.missing_slots for slot in ("order_identity", "candidate"))
  92|
  93|
  94|def test_truncated_compare_candidate_list_is_not_partially_expanded() -> None:
  95|    """候选被截断时不能只展开前 N 个候选，否则会把不完整对比伪装成完整答案。"""
  96|    nlu = PlanBomNluCandidate(
  97|        question="订单A和订单B玻璃规格描述有什么不一样",
  98|        intent="cross_order_material_compare",
  99|        slots={"order_tail_no": ["00001", "00002"]},
 100|        missing_slots=[],
 101|        confidence=1.0,
 102|    )
 103|    candidate = PlanBomCandidate(
 104|        order_identity_key="identity-1",
 105|        file_instance_key="file-1",
 106|        order_no="GCL-TEST-00002",
 107|        order_display_label="测试客户-00002",
 108|        order_name="测试客户-00002",
 109|        version_no="A0",
 110|        effective_date="2026-01-01",
 111|        source_type="EXCEL",
 112|        source_tag="fixture",
 113|        match_reason="order_no_like",
 114|    )
 115|    candidate_result = PlanBomCompareResponse(
 116|        query_type="plan_bom_candidate_list",
 117|        domain="plan_bom",
 118|        execution_mode="direct",
 119|        status=PlanBomStatus(
 120|            code="CANDIDATE_REQUIRED",
 121|            message="right 侧命中多个业务实例，请先选择。",
 122|            severity="warning",
 123|            extras={"candidate_truncated": True},
 124|        ),
 125|        result_explanation={},
 126|        response_meta={"candidate_truncated": True},
 127|        candidate_scope="order_identity",
 128|        candidate_side="right",
 129|        candidates=[candidate],
 130|        candidate_total_hint=21,
 131|        compare_ready=False,
 132|    )
 133|
 134|    assert (
 135|        PlanBomQaService._can_expand_compare_candidates(
 136|            nlu=nlu,
 137|            candidate_result=candidate_result,
 138|            candidates=candidate_result.candidates,
 139|        )
 140|        is False
 141|    )
```


## tests/unit/query_planning/test_query_planning_phase56_response_meta.py:170-360
```python
 170|        "original_question",
 171|        "question",
 172|        "answer_summary",
 173|    }
 174|    assert forbidden_keys.isdisjoint(meta.keys())
 175|    assert forbidden_keys.isdisjoint(meta["comparison"].keys())
 176|
 177|
 178|def test_logistics_query_plan_v2_meta_is_hidden_by_default(monkeypatch) -> None:
 179|    """默认关闭时，正式物流响应不应暴露 query_plan_v2_meta。"""
 180|
 181|    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
 182|    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "local", raising=False)
 183|
 184|    api_response = logistics_data_qa_query(
 185|        LogisticsDataQaQueryRequest(question="2025年各承运商发运量是多少？"),
 186|        _FakeRequest(),
 187|        _FakeLogisticsQaService(_logistics_result()),
 188|    )
 189|
 190|    data = api_response.data
 191|    assert isinstance(data, dict)
 192|    assert "query_plan_v2_meta" not in data
 193|    assert data["answer_summary"] == "已统计 2025 年各承运商发运量。"
 194|    assert data["status"]["code"] == "OK"
 195|    assert data["result_table"]["rows"] == [{"承运商": "A", "发运量": 1}]
 196|
 197|
 198|def test_logistics_query_plan_v2_meta_can_be_exposed_when_flag_and_request_enabled(monkeypatch) -> None:
 199|    """非生产环境中，开关和请求参数同时开启时才暴露轻量 meta。"""
 200|
 201|    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
 202|    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "local", raising=False)
 203|
 204|    api_response = logistics_data_qa_query(
 205|        LogisticsDataQaQueryRequest(
 206|            question="2025年各承运商发运量是多少？",
 207|            include_query_plan_v2_meta=True,
 208|        ),
 209|        _FakeRequest("trace-p56-logistics"),
 210|        _FakeLogisticsQaService(_logistics_result()),
 211|    )
 212|
 213|    data = api_response.data
 214|    assert isinstance(data, dict)
 215|    meta = data["query_plan_v2_meta"]
 216|    _assert_safe_query_plan_meta(meta, domain="logistics")
 217|    assert meta["trace_id"] == "trace-p56-logistics"
 218|    assert meta["history_log_id"] == 8801
 219|    assert meta["strategy"] == "DIRECT_RETRIEVAL"
 220|    assert meta["comparison"]["formal_query_key"] == "hist_mw_by_carrier"
 221|    assert meta["comparison"]["shadow_query_key"] == "hist_mw_by_carrier"
 222|    assert meta["comparison"]["matched"] is True
 223|
 224|
 225|def test_query_plan_v2_meta_stays_hidden_when_feature_flag_is_off(monkeypatch) -> None:
 226|    """即使请求参数显式开启，只要 feature flag 关闭，正式响应也不能暴露 meta。"""
 227|
 228|    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", False, raising=False)
 229|    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "local", raising=False)
 230|
 231|    api_response = logistics_data_qa_query(
 232|        LogisticsDataQaQueryRequest(
 233|            question="2025年各承运商发运量是多少？",
 234|            include_query_plan_v2_meta=True,
 235|        ),
 236|        _FakeRequest("trace-p56-flag-off"),
 237|        _FakeLogisticsQaService(_logistics_result()),
 238|    )
 239|
 240|    assert isinstance(api_response.data, dict)
 241|    assert "query_plan_v2_meta" not in api_response.data
 242|
 243|
 244|def test_query_plan_v2_meta_hides_in_production_alias(monkeypatch) -> None:
 245|    """生产环境别名也必须 fail-closed，避免环境命名差异导致 meta 暴露。"""
 246|
 247|    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
 248|    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "Production", raising=False)
 249|
 250|    service = response_meta_exposure_service.QueryPlanningV2ResponseMetaExposureService()
 251|
 252|    assert service.should_expose(requested=True) is False
 253|
 254|
 255|def test_query_plan_v2_meta_build_failure_is_fail_soft(monkeypatch) -> None:
 256|    """shadow meta 构建异常时，正式响应仍成功且不附加 meta。"""
 257|
 258|    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
 259|    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "local", raising=False)
 260|    monkeypatch.setattr(
 261|        response_meta_exposure_service,
 262|        "QueryPlanningV2ShadowSnapshotBuilder",
 263|        lambda: _BrokenShadowSnapshotBuilder(),
 264|    )
 265|
 266|    api_response = logistics_data_qa_query(
 267|        LogisticsDataQaQueryRequest(
 268|            question="2025年各承运商发运量是多少？",
 269|            include_query_plan_v2_meta=True,
 270|        ),
 271|        _FakeRequest("trace-p56-fail-soft"),
 272|        _FakeLogisticsQaService(_logistics_result()),
 273|    )
 274|
 275|    assert isinstance(api_response.data, dict)
 276|    assert api_response.data["answer_summary"] == "已统计 2025 年各承运商发运量。"
 277|    assert api_response.data["status"]["code"] == "OK"
 278|    assert "query_plan_v2_meta" not in api_response.data
 279|
 280|
 281|def test_logistics_stream_done_payload_exposes_query_plan_v2_meta_when_enabled(monkeypatch) -> None:
 282|    """物流流式 done payload 与同步接口保持同样的可选 meta 语义。"""
 283|
 284|    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
 285|    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "local", raising=False)
 286|    monkeypatch.setattr(logistics_data_qa_endpoint, "BusinessAnswerStreamService", _FakeBusinessAnswerStreamService)
 287|
 288|    streaming_response = logistics_data_qa_endpoint.logistics_data_qa_query_stream(
 289|        LogisticsDataQaQueryRequest(
 290|            question="2025年各承运商发运量是多少？",
 291|            include_query_plan_v2_meta=True,
 292|        ),
 293|        _FakeRequest("trace-p56-logistics-stream"),
 294|        _FakeLogisticsQaService(_logistics_result()),
 295|    )
 296|    done = _done_event(asyncio.run(_collect_stream_events(streaming_response)))
 297|
 298|    meta = done["data"]["data"]["query_plan_v2_meta"]
 299|    _assert_safe_query_plan_meta(meta, domain="logistics")
 300|    assert meta["trace_id"] == "trace-p56-logistics-stream"
 301|    assert meta["comparison"]["matched"] is True
 302|
 303|
 304|def test_plan_bom_stream_done_payload_hides_query_plan_v2_meta_in_prod(monkeypatch) -> None:
 305|    """BOM 流式 done payload 在生产环境同样 fail-closed。"""
 306|
 307|    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
 308|    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "prod", raising=False)
 309|    monkeypatch.setattr(plan_bom_qa_endpoint, "BusinessAnswerStreamService", _FakeBusinessAnswerStreamService)
 310|
 311|    streaming_response = plan_bom_qa_endpoint.ask_plan_bom_stream(
 312|        PlanBomQaRequest(
 313|            question="订单 ABC 的玻璃是什么？",
 314|            include_query_plan_v2_meta=True,
 315|        ),
 316|        _FakeRequest("trace-p56-bom-stream-prod"),
 317|        _FakePlanBomQaService(_plan_bom_response()),
 318|    )
 319|    done = _done_event(asyncio.run(_collect_stream_events(streaming_response)))
 320|
 321|    assert "query_plan_v2_meta" not in done["data"]["data"]
 322|    assert done["data"]["data"]["status"]["code"] == "OK"
 323|
 324|
 325|def test_plan_bom_query_plan_v2_meta_can_be_exposed_without_raw_payload(monkeypatch) -> None:
 326|    """BOM 响应显式开启时也只暴露安全摘要，不泄露 raw_result/trace。"""
 327|
 328|    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
 329|    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "dev", raising=False)
 330|
 331|    api_response = ask_plan_bom(
 332|        PlanBomQaRequest(
 333|            question="订单 ABC 的玻璃是什么？",
 334|            include_query_plan_v2_meta=True,
 335|            trace_id="trace-p56-bom-request",
 336|        ),
 337|        _FakeRequest("trace-p56-bom"),
 338|        _FakePlanBomQaService(_plan_bom_response()),
 339|    )
 340|
 341|    data = api_response.data
 342|    assert isinstance(data, dict)
 343|    meta = data["query_plan_v2_meta"]
 344|    _assert_safe_query_plan_meta(meta, domain="plan_bom")
 345|    assert meta["trace_id"] == "trace-p56-bom"
 346|    assert meta["strategy"] == "DIRECT_RETRIEVAL"
 347|    assert meta["comparison"]["formal_query_key"] == "single_order_material_specs"
 348|    assert data["answer_summary"] == "已查询订单 ABC 的玻璃规格。"
 349|    assert data["status"]["code"] == "OK"
 350|
 351|
 352|def test_query_plan_v2_meta_is_fail_closed_in_prod_even_when_requested(monkeypatch) -> None:
 353|    """生产环境未接入正式权限模块前必须 fail-closed，不能因请求参数暴露 meta。"""
 354|
 355|    monkeypatch.setattr(response_meta_exposure_service.settings, "query_planning_v2_response_meta_enabled", True, raising=False)
 356|    monkeypatch.setattr(response_meta_exposure_service.settings, "app_env", "prod", raising=False)
 357|
 358|    logistics_response = logistics_data_qa_query(
 359|        LogisticsDataQaQueryRequest(
 360|            question="2025年各承运商发运量是多少？",
```
