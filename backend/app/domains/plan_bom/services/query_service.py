from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import cmp_to_key
from typing import Literal

from sqlalchemy.exc import SQLAlchemyError

from backend.app.core.exceptions import AppException
from backend.app.domains.plan_bom.constants import (
    CANDIDATE_SCOPE_FILE_INSTANCE,
    CANDIDATE_SCOPE_ORDER_IDENTITY,
    CANDIDATE_SCOPE_VERSION,
    CORE_MATERIAL_CATEGORIES,
    DOMAIN_PLAN_BOM,
    EXECUTION_MODE_DIRECT,
    MATERIAL_CATEGORY_LABELS,
    PLAN_BOM_NOISE_DESCRIPTION_KEYWORDS,
    PLAN_BOM_NOISE_NAME_KEYWORDS,
    PLAN_BOM_NOISE_SAP_CODE_KEYWORDS,
    PLAN_BOM_COMPARE_ROUTE_TYPE,
    PLAN_BOM_COMPARE_SNAPSHOT_CANDIDATE_LIMIT,
    PLAN_BOM_COMPARE_SNAPSHOT_DIFF_LIMIT,
    PLAN_BOM_COMPARE_SNAPSHOT_SAME_LIMIT,
    QUERY_TYPE_PLAN_BOM_CANDIDATE_LIST,
    QUERY_TYPE_PLAN_BOM_COMPARE,
    QUERY_TYPE_PLAN_BOM_DETAIL,
    SOURCE_TYPE_EXCEL,
    SOURCE_TYPE_SAP,
    STATUS_CODE_CANDIDATE_REQUIRED,
    STATUS_CODE_EMPTY_RESULT,
    STATUS_CODE_OK,
    STATUS_CODE_VERSION_NEED_CONFIRM,
)
from backend.app.domains.plan_bom.identity import build_order_display_label, normalize_identity_text
from backend.app.domains.plan_bom.models import PlanBomHeader, PlanBomMaterialLine
from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
from backend.app.domains.plan_bom.schemas.query import (
    PlanBomCandidate,
    PlanBomCompareChangedItem,
    PlanBomCompareDiffSummary,
    PlanBomCompareQueryRequest,
    PlanBomCompareResponse,
    PlanBomCompareSideContext,
    PlanBomCompareSideRequest,
    PlanBomCompareSingleSideItem,
    PlanBomCompareSummaryByCategory,
    PlanBomDetailQueryRequest,
    PlanBomDetailQueryResponse,
    PlanBomMaterialItem,
    PlanBomSelectedVersion,
    PlanBomStatus,
)


@dataclass(frozen=True)
class _LocatedHeaders:
    """订单定位结果。

    参数：
        headers: 已按业务版本去重后的 BOM 头；
        match_reasons: 每个 BOM 头对应的命中原因；
        search_text: 实际用于定位的输入文本。
    """

    headers: list[PlanBomHeader]
    match_reasons: dict[tuple[str, str, str, str], str]
    search_text: str


@dataclass(frozen=True)
class _SelectedVersion:
    """当前版本判定结果。"""

    header: PlanBomHeader | None
    need_confirm: bool = False


@dataclass(frozen=True)
class _CompareSideResolution:
    """compare 单侧解析结果。

    参数：
        header: 当前单侧已明确的最终 BOM 头；
        response: 如果当前单侧需要先返回候选或空结果，则直接返回 compare 响应；
    """

    header: PlanBomHeader | None = None
    response: PlanBomCompareResponse | None = None


@dataclass(frozen=True)
class _CompareComputation:
    """compare 差异计算结果。

    参数：
        only_left/only_right: 仅出现在单侧的材料项；
        changed: 左右两侧都存在但字段有变化的材料项；
        same: 左右两侧完全一致的材料项；
        diff_summary: 汇总统计。
    """

    only_left: list[PlanBomCompareSingleSideItem]
    only_right: list[PlanBomCompareSingleSideItem]
    changed: list[PlanBomCompareChangedItem]
    same: list[PlanBomCompareChangedItem]
    diff_summary: PlanBomCompareDiffSummary


class PlanBomQueryService:
    """计划 BOM 基础查询服务。

    职责边界：
    1. 支持订单号、订单名称、评审号别名定位；
    2. 支持多命中候选列表；
    3. 支持当前版本自动判定；
    4. 支持 5 类核心材料查询；
    5. 支持 compare 里程碑 2 的骨架、候选链路和核心差异计算；
    6. 支持 compare 里程碑 3 的最小历史 / 快照 / 回放；
    7. 不实现 compare 运行态抽验、导出、前端或 SAP 接入。
    """

    SOURCE_PRIORITY = {SOURCE_TYPE_SAP: 0, SOURCE_TYPE_EXCEL: 1}
    NOISE_NAME_KEYWORDS = PLAN_BOM_NOISE_NAME_KEYWORDS
    NOISE_DESCRIPTION_KEYWORDS = PLAN_BOM_NOISE_DESCRIPTION_KEYWORDS
    NOISE_SAP_CODE_KEYWORDS = PLAN_BOM_NOISE_SAP_CODE_KEYWORDS

    def __init__(self, repository: PlanBomQueryRepository) -> None:
        self.repository = repository

    def detail(self, payload: PlanBomDetailQueryRequest) -> PlanBomDetailQueryResponse:
        """执行计划 BOM 基础材料查询。

        参数：
            payload: 基础查询请求。

        返回：
            统一结构的 BOM 查询响应。
        """
        located = self._locate_headers(payload)
        if not located.headers:
            return self._empty_response(
                summary="未找到匹配的 BOM 订单。",
                reason="订单号、评审号或订单名称没有命中有效 BOM 头。",
                payload=payload,
            )

        distinct_identity_keys = {header.order_identity_key for header in located.headers}
        if len(distinct_identity_keys) > 1:
            return self._candidate_response(
                headers=located.headers,
                match_reasons=located.match_reasons,
                payload=payload,
                message="命中多个订单，请选择后继续查询。",
                candidate_scope=CANDIDATE_SCOPE_ORDER_IDENTITY,
            )

        selected = self._select_current_version(located.headers, payload.version_no)
        if selected.need_confirm:
            return self._candidate_response(
                headers=located.headers,
                match_reasons=located.match_reasons,
                payload=payload,
                message="当前版本无法自动判定，请选择版本后继续查询。",
                status_code=STATUS_CODE_VERSION_NEED_CONFIRM,
                candidate_scope=CANDIDATE_SCOPE_ORDER_IDENTITY,
            )
        if not selected.header:
            return self._empty_response(
                summary="未找到匹配的 BOM 版本。",
                reason="订单存在，但指定版本不存在或没有有效版本。",
                payload=payload,
            )

        file_instance_headers = self._headers_for_selected_file_instances(
            headers=located.headers,
            selected_header=selected.header,
        )
        distinct_file_instance_keys = {header.file_instance_key for header in file_instance_headers}
        if not payload.file_instance_key and len(distinct_file_instance_keys) > 1:
            file_instance_reasons = {
                self._header_key(header): "file_instance_required" for header in file_instance_headers
            }
            return self._candidate_response(
                headers=file_instance_headers,
                match_reasons=file_instance_reasons,
                payload=payload,
                message="命中同一订单版本的多个文件实例，请选择文件后继续查询。",
                status_code=STATUS_CODE_CANDIDATE_REQUIRED,
                candidate_scope=CANDIDATE_SCOPE_FILE_INSTANCE,
                selected_header=selected.header,
            )

        material_lines = self.repository.list_material_lines(
            order_identity_key=selected.header.order_identity_key,
            file_instance_key=selected.header.file_instance_key,
            version_no=selected.header.version_no,
            source_type=selected.header.source_type,
            material_categories=payload.material_categories,
        )
        material_lines = [line for line in material_lines if not self._is_noise_material_line(line)]
        if not material_lines:
            return self._empty_response(
                summary="订单已定位，但当前版本没有命中材料行。",
                reason="当前版本下没有 5 类核心材料，或请求材料类别没有匹配记录。",
                payload=payload,
                selected_header=selected.header,
            )

        items = [self._material_item(line) for line in material_lines]
        selected_version = self._selected_version(selected.header)
        return PlanBomDetailQueryResponse(
            query_type=QUERY_TYPE_PLAN_BOM_DETAIL,
            domain=DOMAIN_PLAN_BOM,
            execution_mode=EXECUTION_MODE_DIRECT,
            status=PlanBomStatus(code=STATUS_CODE_OK, message="查询成功", success=True, severity="info"),
            result_explanation={
                "summary": f"已查询订单 {selected.header.order_no} 当前版本 {selected.header.version_no} 的核心材料。",
                "query_scope": {
                    "order_identity_key": selected.header.order_identity_key,
                    "file_instance_key": selected.header.file_instance_key,
                    "order_no": selected.header.order_no,
                    "version_no": selected.header.version_no,
                    "materials": payload.material_categories,
                },
                "data_source": {
                    "source_type": selected.header.source_type,
                    "source_tag": selected.header.source_tag,
                },
                "warnings": [],
            },
            response_meta=self._response_meta(
                query_type=QUERY_TYPE_PLAN_BOM_DETAIL,
                status_code=STATUS_CODE_OK,
                result_count=len(items),
                selected_header=selected.header,
            ),
            candidate_scope=None,
            selected_version=selected_version,
            items=items,
            total=len(items),
        )

    def compare(
        self,
        payload: PlanBomCompareQueryRequest,
        *,
        trace_id: str | None = None,
    ) -> PlanBomCompareResponse:
        """执行计划 BOM compare 骨架查询。

        说明：
        1. 当前里程碑实现 compare 候选链路和核心差异结果；
        2. 当前里程碑把 compare 最小快照写入 `sys_query_log`，供历史回放使用；
        3. 当前只比较 5 类核心材料，不扩到导出、前端或 SAP。
        """
        left_result = self._resolve_compare_side(payload.left, payload=payload, side="left")
        if left_result.response:
            return self._finalize_compare_response(payload=payload, response=left_result.response, trace_id=trace_id)

        right_result = self._resolve_compare_side(
            payload.right,
            payload=payload,
            side="right",
            left_header=left_result.header,
        )
        if right_result.response:
            return self._finalize_compare_response(payload=payload, response=right_result.response, trace_id=trace_id)

        assert left_result.header is not None
        assert right_result.header is not None
        computed = self._compute_compare_result(
            left_header=left_result.header,
            right_header=right_result.header,
            material_categories=payload.material_categories,
        )

        response = PlanBomCompareResponse(
            query_type=QUERY_TYPE_PLAN_BOM_COMPARE,
            domain=DOMAIN_PLAN_BOM,
            execution_mode=EXECUTION_MODE_DIRECT,
            status=PlanBomStatus(code=STATUS_CODE_OK, message="compare 查询成功", success=True, severity="info"),
            result_explanation={
                "summary": "compare 左右两侧已完成定位，并已输出核心材料差异结果。",
                "query_scope": {
                    "left": self._compare_side_scope(payload.left),
                    "right": self._compare_side_scope(payload.right),
                    "materials": payload.material_categories,
                },
                "warnings": [],
            },
            response_meta={
                "domain": DOMAIN_PLAN_BOM,
                "query_type": QUERY_TYPE_PLAN_BOM_COMPARE,
                "execution_mode": EXECUTION_MODE_DIRECT,
                "status_code": STATUS_CODE_OK,
                "candidate_scope": None,
                "candidate_side": None,
                "compare_ready": True,
                "left_order_identity_key": left_result.header.order_identity_key,
                "left_file_instance_key": left_result.header.file_instance_key,
                "left_order_no": left_result.header.order_no,
                "left_version_no": left_result.header.version_no,
                "right_order_identity_key": right_result.header.order_identity_key,
                "right_file_instance_key": right_result.header.file_instance_key,
                "right_order_no": right_result.header.order_no,
                "right_version_no": right_result.header.version_no,
                "only_left_count": len(computed.only_left),
                "only_right_count": len(computed.only_right),
                "changed_count": len(computed.changed),
                "same_count": len(computed.same),
            },
            candidate_scope=None,
            candidate_side=None,
            left=self._compare_side_context(left_result.header),
            right=self._compare_side_context(right_result.header),
            compare_ready=True,
            only_left=computed.only_left,
            only_right=computed.only_right,
            changed=computed.changed,
            same=computed.same,
            diff_summary=computed.diff_summary,
        )
        return self._finalize_compare_response(payload=payload, response=response, trace_id=trace_id)

    def compare_replay(self, *, log_id: int) -> PlanBomCompareResponse:
        """读取 compare 历史快照并回放。

        参数：
            log_id: `sys_query_log.id`。

        返回：
            受控快照对应的 compare 响应。
        """
        try:
            row = self.repository.get_query_log_detail(log_id=log_id)
        except SQLAlchemyError as exc:
            raise AppException("compare 历史暂时不可用，请检查 sys_query_log 是否正常。", code=5006, status_code=500) from exc

        if not row:
            raise AppException("compare 历史记录不存在", code=4043, status_code=404)
        if str(row.get("query_type") or "").lower() != QUERY_TYPE_PLAN_BOM_COMPARE:
            raise AppException("指定日志不是 compare 记录", code=4007, status_code=400)

        payload_json = self._parse_query_log_payload(row.get("request_payload"))
        query_result = payload_json.get("query_result") if isinstance(payload_json, dict) else None
        if not isinstance(query_result, dict):
            raise AppException("compare 历史快照缺失，无法回放。", code=5007, status_code=500)

        try:
            response = PlanBomCompareResponse.model_validate(query_result)
        except Exception as exc:  # noqa: BLE001
            raise AppException("compare 历史快照格式异常，无法回放。", code=5008, status_code=500) from exc

        response.response_meta = dict(response.response_meta or {})
        response.response_meta["query_log_id"] = log_id
        response.response_meta["replay_mode"] = True
        response.response_meta["snapshot_source"] = "sys_query_log"
        return response

    def _resolve_compare_side(
        self,
        side_payload: PlanBomCompareSideRequest,
        *,
        payload: PlanBomCompareQueryRequest,
        side: Literal["left", "right"],
        left_header: PlanBomHeader | None = None,
    ) -> _CompareSideResolution:
        """解析 compare 单侧定位结果，并在需要时返回候选态响应。"""
        located = self._locate_compare_headers(side_payload)
        if not located.headers:
            return _CompareSideResolution(
                response=self._compare_empty_response(
                    payload=payload,
                    side=side,
                    summary=f"{side} 侧未找到匹配的 BOM 订单。",
                    reason="订单号、评审号或订单名称没有命中有效 BOM 头。",
                    left_header=left_header,
                )
            )

        distinct_identity_keys = {header.order_identity_key for header in located.headers}
        if len(distinct_identity_keys) > 1:
            return _CompareSideResolution(
                response=self._compare_candidate_response(
                    headers=located.headers,
                    match_reasons=located.match_reasons,
                    payload=payload,
                    side=side,
                    message=f"{side} 侧命中多个业务实例，请先选择。",
                    candidate_scope=CANDIDATE_SCOPE_ORDER_IDENTITY,
                    left_header=left_header,
                )
            )

        selected = self._select_current_version(located.headers, side_payload.version_no)
        if selected.need_confirm:
            version_headers = self._sort_headers(self._dedupe_version_candidates(located.headers))
            version_reasons = {self._header_key(header): "version_required" for header in version_headers}
            return _CompareSideResolution(
                response=self._compare_candidate_response(
                    headers=version_headers,
                    match_reasons=version_reasons,
                    payload=payload,
                    side=side,
                    message=f"{side} 侧当前版本无法自动判定，请先选择版本。",
                    status_code=STATUS_CODE_VERSION_NEED_CONFIRM,
                    candidate_scope=CANDIDATE_SCOPE_VERSION,
                    left_header=left_header,
                )
            )
        if not selected.header:
            return _CompareSideResolution(
                response=self._compare_empty_response(
                    payload=payload,
                    side=side,
                    summary=f"{side} 侧未找到匹配的 BOM 版本。",
                    reason="订单存在，但指定版本不存在或没有有效版本。",
                    left_header=left_header,
                )
            )

        file_instance_headers = self._headers_for_selected_file_instances(
            headers=located.headers,
            selected_header=selected.header,
        )
        distinct_file_instance_keys = {header.file_instance_key for header in file_instance_headers}
        if not side_payload.file_instance_key and len(distinct_file_instance_keys) > 1:
            file_instance_reasons = {
                self._header_key(header): "file_instance_required" for header in file_instance_headers
            }
            return _CompareSideResolution(
                response=self._compare_candidate_response(
                    headers=file_instance_headers,
                    match_reasons=file_instance_reasons,
                    payload=payload,
                    side=side,
                    message=f"{side} 侧命中同一版本的多个文件实例，请先选择。",
                    candidate_scope=CANDIDATE_SCOPE_FILE_INSTANCE,
                    selected_header=selected.header,
                    left_header=left_header,
                )
            )

        return _CompareSideResolution(header=selected.header)

    def _locate_compare_headers(self, side_payload: PlanBomCompareSideRequest) -> _LocatedHeaders:
        """按 compare 单侧条件定位 BOM 头。"""
        order_identity_key = self._clean_text(side_payload.order_identity_key)
        file_instance_key = self._clean_text(side_payload.file_instance_key)
        order_no = self._clean_text(side_payload.order_no)
        review_no = self._clean_text(side_payload.review_no)
        order_name = self._clean_text(side_payload.order_name)

        if file_instance_key:
            return self._located(
                self.repository.list_compare_headers(file_instance_key=file_instance_key),
                "file_instance_key",
                file_instance_key,
            )
        if order_identity_key:
            return self._located(
                self.repository.list_compare_headers(order_identity_key=order_identity_key),
                "order_identity_key",
                order_identity_key,
            )
        if order_no:
            exact_headers = self.repository.list_compare_headers(order_no=order_no)
            if exact_headers:
                return self._located(exact_headers, "order_no_exact", order_no)
            return self._located(
                self.repository.list_compare_headers(order_no_like=order_no),
                "order_no_like",
                order_no,
            )
        if review_no:
            return self._located(self._filter_headers_by_review_alias(review_no), "review_no_like", review_no)
        if order_name:
            return self._located(
                self.repository.list_compare_headers(order_no_like=order_name, order_name_like=order_name),
                "order_name_like",
                order_name,
            )
        return _LocatedHeaders(headers=[], match_reasons={}, search_text="")

    def _compare_candidate_response(
        self,
        *,
        headers: list[PlanBomHeader],
        match_reasons: dict[tuple[str, str, str, str], str],
        payload: PlanBomCompareQueryRequest,
        side: Literal["left", "right"],
        message: str,
        candidate_scope: str,
        status_code: str = STATUS_CODE_CANDIDATE_REQUIRED,
        selected_header: PlanBomHeader | None = None,
        left_header: PlanBomHeader | None = None,
    ) -> PlanBomCompareResponse:
        """构造 compare 候选响应。"""
        sorted_headers = self._sort_headers(headers)
        total_hint = len(sorted_headers)
        truncated = total_hint > payload.candidate_limit
        candidates = [
            self._candidate(header, match_reasons.get(self._header_key(header), "unknown"))
            for header in sorted_headers[: payload.candidate_limit]
        ]
        resolved_left = left_header if side == "right" else selected_header
        return PlanBomCompareResponse(
            query_type=QUERY_TYPE_PLAN_BOM_CANDIDATE_LIST,
            domain=DOMAIN_PLAN_BOM,
            execution_mode=EXECUTION_MODE_DIRECT,
            status=PlanBomStatus(
                code=status_code,
                message=message,
                success=True,
                severity="warning",
                extras={"candidate_truncated": truncated},
            ),
            result_explanation={
                "summary": message,
                "query_scope": {
                    "left": self._compare_side_scope(payload.left),
                    "right": self._compare_side_scope(payload.right),
                    "materials": payload.material_categories,
                },
                "warnings": ["compare 候选态不会默认选择业务实例、文件实例或版本。"],
            },
            no_result_analysis={
                "reason": "当前 compare 条件命中多个候选，需要先确认左侧或右侧的比较基线。",
                "suggestion": "请选择候选项或补充更完整的订单号、版本号、业务实例或文件实例。",
            },
            response_meta={
                "domain": DOMAIN_PLAN_BOM,
                "query_type": QUERY_TYPE_PLAN_BOM_CANDIDATE_LIST,
                "execution_mode": EXECUTION_MODE_DIRECT,
                "status_code": status_code,
                "candidate_scope": candidate_scope,
                "candidate_side": side,
                "candidate_count": len(candidates),
                "candidate_total_hint": total_hint,
                "candidate_truncated": truncated,
                "compare_ready": False,
                "left_order_identity_key": resolved_left.order_identity_key if resolved_left else None,
                "left_file_instance_key": resolved_left.file_instance_key if resolved_left else None,
                "left_order_no": resolved_left.order_no if resolved_left else None,
                "left_version_no": resolved_left.version_no if resolved_left else None,
            },
            candidate_scope=candidate_scope,
            candidate_side=side,
            left=self._compare_side_context(resolved_left) if resolved_left else None,
            right=None,
            candidates=candidates,
            candidate_total_hint=total_hint,
            compare_ready=False,
            diff_summary=None,
        )

    def _compare_empty_response(
        self,
        *,
        payload: PlanBomCompareQueryRequest,
        side: Literal["left", "right"],
        summary: str,
        reason: str,
        left_header: PlanBomHeader | None = None,
    ) -> PlanBomCompareResponse:
        """构造 compare 空结果响应。"""
        return PlanBomCompareResponse(
            query_type=QUERY_TYPE_PLAN_BOM_COMPARE,
            domain=DOMAIN_PLAN_BOM,
            execution_mode=EXECUTION_MODE_DIRECT,
            status=PlanBomStatus(code=STATUS_CODE_EMPTY_RESULT, message=summary, success=True, severity="warning"),
            result_explanation={
                "summary": summary,
                "query_scope": {
                    "left": self._compare_side_scope(payload.left),
                    "right": self._compare_side_scope(payload.right),
                    "materials": payload.material_categories,
                },
                "warnings": [],
            },
            no_result_analysis={
                "reason": reason,
                "suggestion": "请确认 compare 左右两侧的订单号、版本号、业务实例或文件实例是否正确。",
            },
            response_meta={
                "domain": DOMAIN_PLAN_BOM,
                "query_type": QUERY_TYPE_PLAN_BOM_COMPARE,
                "execution_mode": EXECUTION_MODE_DIRECT,
                "status_code": STATUS_CODE_EMPTY_RESULT,
                "candidate_scope": None,
                "candidate_side": side,
                "compare_ready": False,
                "left_order_identity_key": left_header.order_identity_key if left_header else None,
                "left_file_instance_key": left_header.file_instance_key if left_header else None,
                "left_order_no": left_header.order_no if left_header else None,
                "left_version_no": left_header.version_no if left_header else None,
            },
            candidate_scope=None,
            candidate_side=side,
            left=self._compare_side_context(left_header) if left_header else None,
            right=None,
            compare_ready=False,
            diff_summary=None,
        )

    def _finalize_compare_response(
        self,
        *,
        payload: PlanBomCompareQueryRequest,
        response: PlanBomCompareResponse,
        trace_id: str | None,
    ) -> PlanBomCompareResponse:
        """在 compare 响应返回前补齐历史日志写入。

        说明：
        1. 当前 compare 候选态也写历史，但只写候选快照，不生成最终差异快照；
        2. 写日志失败不能阻断 compare 主链路，只在 `response_meta` 标记失败；
        3. 成功写入后会把 `query_log_id` 回填到响应元信息中。
        """
        response.response_meta = dict(response.response_meta or {})
        response.response_meta["history_ready"] = False
        response.response_meta["history_write_failed"] = False
        try:
            log_id = self._write_compare_query_log(payload=payload, response=response, trace_id=trace_id)
        except SQLAlchemyError:
            response.response_meta["history_write_failed"] = True
            response.response_meta["history_ready"] = False
            return response

        response.response_meta["query_log_id"] = log_id
        response.response_meta["history_ready"] = bool(log_id)
        return response

    def _write_compare_query_log(
        self,
        *,
        payload: PlanBomCompareQueryRequest,
        response: PlanBomCompareResponse,
        trace_id: str | None,
    ) -> int:
        """把 compare 请求写入 `sys_query_log`。

        说明：
        1. `sys_query_log.query_type` 固定写 compare，便于历史页统一筛选；
        2. `route_type` 记录当前响应形态，区分 compare / candidate_list；
        3. `request_payload` 中写入受控快照，避免无限制堆积全量明细。
        """
        payload_json = self._build_compare_history_payload(payload=payload, response=response)
        result_count = self._compare_log_result_count(response)
        question = self._build_compare_question(payload)
        return self.repository.write_query_log(
            {
                "trace_id": trace_id,
                "query_type": QUERY_TYPE_PLAN_BOM_COMPARE,
                "question_text": question,
                "request_payload": json.dumps(payload_json, ensure_ascii=False),
                "route_type": PLAN_BOM_COMPARE_ROUTE_TYPE,
                "metric_type": ",".join(payload.material_categories),
                "result_count": result_count,
                "status": response.status.code,
                "message": response.status.message,
            }
        )

    def _build_compare_history_payload(
        self,
        *,
        payload: PlanBomCompareQueryRequest,
        response: PlanBomCompareResponse,
    ) -> dict[str, object]:
        """构造 compare 历史快照。

        说明：
        1. 顶层同时写 `request`、`response_meta` 和 `query_result`；
        2. `query_result` 只保留受控预览，不写无限制全量差异明细；
        3. 候选态不会生成最终 compare 快照，只保留候选和左右侧上下文。
        """
        snapshot_response_meta = self._build_compare_snapshot_response_meta(response)
        snapshot_query_result = self._build_compare_snapshot_query_result(
            response=response,
            snapshot_response_meta=snapshot_response_meta,
        )
        return {
            "domain": DOMAIN_PLAN_BOM,
            "query_type": QUERY_TYPE_PLAN_BOM_COMPARE,
            "question": self._build_compare_question(payload),
            "request": payload.model_dump(mode="json"),
            "response_meta": snapshot_response_meta,
            "query_result": snapshot_query_result,
        }

    def _build_compare_snapshot_response_meta(self, response: PlanBomCompareResponse) -> dict[str, object]:
        """构造 compare 历史快照的 `response_meta`。"""
        response_meta = dict(response.response_meta or {})
        response_meta.pop("query_log_id", None)
        response_meta["snapshot_ready"] = bool(response.compare_ready)
        return response_meta

    def _build_compare_snapshot_query_result(
        self,
        *,
        response: PlanBomCompareResponse,
        snapshot_response_meta: dict[str, object],
    ) -> dict[str, object]:
        """构造 compare 历史回放所需的受控 `query_result` 快照。"""
        snapshot = response.model_dump(mode="json")
        snapshot["response_meta"] = snapshot_response_meta

        truncated: dict[str, bool] = {}
        if isinstance(snapshot.get("candidates"), list):
            original_candidates = list(snapshot["candidates"])
            snapshot["candidates"] = original_candidates[:PLAN_BOM_COMPARE_SNAPSHOT_CANDIDATE_LIMIT]
            truncated["candidates"] = len(original_candidates) > PLAN_BOM_COMPARE_SNAPSHOT_CANDIDATE_LIMIT

        for field_name, limit in {
            "only_left": PLAN_BOM_COMPARE_SNAPSHOT_DIFF_LIMIT,
            "only_right": PLAN_BOM_COMPARE_SNAPSHOT_DIFF_LIMIT,
            "changed": PLAN_BOM_COMPARE_SNAPSHOT_DIFF_LIMIT,
            "same": PLAN_BOM_COMPARE_SNAPSHOT_SAME_LIMIT,
        }.items():
            bucket = snapshot.get(field_name)
            if isinstance(bucket, list):
                original_bucket = list(bucket)
                snapshot[field_name] = original_bucket[:limit]
                truncated[field_name] = len(original_bucket) > limit

        snapshot["response_meta"]["snapshot_policy"] = {
            "candidate_limit": PLAN_BOM_COMPARE_SNAPSHOT_CANDIDATE_LIMIT,
            "diff_bucket_limit": PLAN_BOM_COMPARE_SNAPSHOT_DIFF_LIMIT,
            "same_bucket_limit": PLAN_BOM_COMPARE_SNAPSHOT_SAME_LIMIT,
            "truncated": truncated,
        }
        return snapshot

    @staticmethod
    def _compare_log_result_count(response: PlanBomCompareResponse) -> int:
        """计算 compare 日志的结果条数。"""
        if response.compare_ready and response.diff_summary:
            return (
                response.diff_summary.only_left
                + response.diff_summary.only_right
                + response.diff_summary.changed
                + response.diff_summary.same
            )
        return int(response.candidate_total_hint or 0)

    @staticmethod
    def _build_compare_question(payload: PlanBomCompareQueryRequest) -> str:
        """构造 compare 历史标题。"""
        return f"BOM compare：{PlanBomQueryService._compare_side_question_text(payload.left)} vs {PlanBomQueryService._compare_side_question_text(payload.right)}"

    @staticmethod
    def _compare_side_question_text(payload: PlanBomCompareSideRequest) -> str:
        """构造 compare 单侧的历史标题片段。"""
        for value in (
            payload.order_no,
            payload.order_name,
            payload.review_no,
            payload.file_instance_key,
            payload.order_identity_key,
        ):
            cleaned = PlanBomQueryService._clean_text(value)
            if cleaned:
                return cleaned
        return "未指定"

    @staticmethod
    def _parse_query_log_payload(raw_payload: object) -> object:
        """安全解析 `sys_query_log.request_payload`。"""
        if raw_payload is None:
            return None
        if isinstance(raw_payload, (dict, list)):
            return raw_payload
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode("utf-8", errors="ignore")
        if isinstance(raw_payload, str):
            try:
                return json.loads(raw_payload)
            except Exception:  # noqa: BLE001
                return {"raw_text": raw_payload}
        return raw_payload

    def _locate_headers(self, payload: PlanBomDetailQueryRequest) -> _LocatedHeaders:
        """按订单号、评审号别名或订单名称定位 BOM 头。"""
        order_identity_key = self._clean_text(payload.order_identity_key)
        file_instance_key = self._clean_text(payload.file_instance_key)
        order_no = self._clean_text(payload.order_no)
        review_no = self._clean_text(payload.review_no)
        order_name = self._clean_text(payload.order_name)

        if file_instance_key:
            return self._located(
                self.repository.list_active_headers(file_instance_key=file_instance_key),
                "file_instance_key",
                file_instance_key,
            )
        if order_identity_key:
            return self._located(
                self.repository.list_active_headers(order_identity_key=order_identity_key),
                "order_identity_key",
                order_identity_key,
            )
        if order_no:
            exact_headers = self.repository.list_active_headers(order_no=order_no)
            if exact_headers:
                return self._located(exact_headers, "order_no_exact", order_no)
            return self._located(self.repository.list_active_headers(order_no_like=order_no), "order_no_like", order_no)
        if review_no:
            return self._located(self._filter_headers_by_review_alias(review_no), "review_no_like", review_no)
        if order_name:
            return self._located(
                self.repository.list_active_headers(order_no_like=order_name, order_name_like=order_name),
                "order_name_like",
                order_name,
            )
        return _LocatedHeaders(headers=[], match_reasons={}, search_text="")

    def _located(self, headers: list[PlanBomHeader], match_reason: str, search_text: str) -> _LocatedHeaders:
        """构造订单定位结果，并按 SAP 优先原则去重。"""
        deduped_headers = self._dedupe_headers_by_source(headers)
        reasons = {self._header_key(header): match_reason for header in deduped_headers}
        return _LocatedHeaders(headers=self._sort_headers(deduped_headers), match_reasons=reasons, search_text=search_text)

    def _dedupe_headers_by_source(self, headers: list[PlanBomHeader]) -> list[PlanBomHeader]:
        """同一实例版本同时存在 SAP 和 Excel 时，仅保留来源优先级最高的记录。"""
        selected: dict[tuple[str, str, str], PlanBomHeader] = {}
        for header in headers:
            key = (header.order_identity_key, header.file_instance_key, header.version_no)
            current = selected.get(key)
            if current is None or self._source_priority(header.source_type) < self._source_priority(current.source_type):
                selected[key] = header
        return list(selected.values())

    def _filter_headers_by_review_alias(self, review_no: str) -> list[PlanBomHeader]:
        """按评审号别名过滤 BOM 头。

        说明：
        真实业务里评审号经常出现在订单名称或原始文件名中，不能只按标准订单号 LIKE。
        这里统一做归一化匹配，兼容空格、下划线、连字符和中英文括号差异。
        """
        normalized_review = self._normalize_match_text(review_no)
        if not normalized_review:
            return []

        headers = self.repository.list_active_headers()
        matched: list[PlanBomHeader] = []
        for header in headers:
            haystacks = [header.order_no, header.order_name, header.raw_file_name]
            if any(normalized_review in self._normalize_match_text(value) for value in haystacks if value):
                matched.append(header)
        return matched

    def _select_current_version(self, headers: list[PlanBomHeader], version_no: str | None) -> _SelectedVersion:
        """按业务规则选择当前版本。"""
        requested_version = self._clean_text(version_no)
        if requested_version:
            matched = [header for header in headers if header.version_no == requested_version]
            if not matched:
                return _SelectedVersion(header=None)
            return _SelectedVersion(header=self._sort_headers(self._dedupe_version_candidates(matched))[0])

        active_headers = self._dedupe_version_candidates([header for header in headers if header.is_active == 1])
        if not active_headers:
            return _SelectedVersion(header=None)

        with_date = [header for header in active_headers if header.effective_date]
        version_candidates = active_headers
        if with_date:
            latest_date = max(header.effective_date for header in with_date if header.effective_date)
            version_candidates = [header for header in with_date if header.effective_date == latest_date]

        sorted_candidates = self._sort_headers(version_candidates)
        if not sorted_candidates:
            return _SelectedVersion(header=None)
        if len(sorted_candidates) > 1 and self._compare_version(sorted_candidates[0].version_no, sorted_candidates[1].version_no) == 0:
            return _SelectedVersion(header=None, need_confirm=True)
        return _SelectedVersion(header=sorted_candidates[0])

    def _dedupe_version_candidates(self, headers: list[PlanBomHeader]) -> list[PlanBomHeader]:
        """按版本候选维度去重，避免同一版本下多个文件实例干扰当前版本判定。"""
        selected: dict[tuple[str, str], PlanBomHeader] = {}
        for header in headers:
            key = (header.version_no, header.source_type)
            current = selected.get(key)
            if current is None or self._compare_header(header, current) < 0:
                selected[key] = header
        return list(selected.values())

    def _headers_for_selected_file_instances(
        self,
        *,
        headers: list[PlanBomHeader],
        selected_header: PlanBomHeader,
    ) -> list[PlanBomHeader]:
        """筛出当前选中版本下的全部文件实例候选。"""
        candidates = [
            header
            for header in headers
            if header.order_identity_key == selected_header.order_identity_key
            and header.version_no == selected_header.version_no
            and header.source_type == selected_header.source_type
        ]
        return self._sort_headers(candidates)

    def _candidate_response(
        self,
        *,
        headers: list[PlanBomHeader],
        match_reasons: dict[tuple[str, str, str, str], str],
        payload: PlanBomDetailQueryRequest,
        message: str,
        status_code: str = STATUS_CODE_CANDIDATE_REQUIRED,
        candidate_scope: str = CANDIDATE_SCOPE_ORDER_IDENTITY,
        selected_header: PlanBomHeader | None = None,
    ) -> PlanBomDetailQueryResponse:
        """构造多命中候选列表响应。"""
        sorted_headers = self._sort_headers(headers)
        total_hint = len(sorted_headers)
        truncated = total_hint > payload.candidate_limit
        candidates = [
            self._candidate(header, match_reasons.get(self._header_key(header), "unknown"))
            for header in sorted_headers[: payload.candidate_limit]
        ]
        return PlanBomDetailQueryResponse(
            query_type=QUERY_TYPE_PLAN_BOM_CANDIDATE_LIST,
            domain=DOMAIN_PLAN_BOM,
            execution_mode=EXECUTION_MODE_DIRECT,
            status=PlanBomStatus(
                code=status_code,
                message=message,
                success=True,
                severity="warning",
                extras={"candidate_truncated": truncated},
            ),
            result_explanation={
                "summary": message,
                "query_scope": {
                    "order_identity_key": payload.order_identity_key,
                    "file_instance_key": payload.file_instance_key,
                    "order_no": payload.order_no,
                    "order_name": payload.order_name,
                    "review_no": payload.review_no,
                    "version_no": payload.version_no,
                },
                "warnings": ["候选列表状态不会随机选择订单或版本。"],
            },
            no_result_analysis={
                "reason": "查询条件命中多个候选，需要业务确认后继续。",
                "suggestion": "请选择候选订单或补充更完整的订单号、订单名称。",
            },
            response_meta=self._response_meta(
                query_type=QUERY_TYPE_PLAN_BOM_CANDIDATE_LIST,
                status_code=status_code,
                result_count=0,
                selected_header=selected_header,
                candidate_count=len(candidates),
                candidate_total_hint=total_hint,
                candidate_truncated=truncated,
                candidate_scope=candidate_scope,
            ),
            candidate_scope=candidate_scope,
            candidates=candidates,
            candidate_total_hint=total_hint,
        )

    def _empty_response(
        self,
        *,
        summary: str,
        reason: str,
        payload: PlanBomDetailQueryRequest,
        selected_header: PlanBomHeader | None = None,
    ) -> PlanBomDetailQueryResponse:
        """构造空结果响应。"""
        return PlanBomDetailQueryResponse(
            query_type=QUERY_TYPE_PLAN_BOM_DETAIL,
            domain=DOMAIN_PLAN_BOM,
            execution_mode=EXECUTION_MODE_DIRECT,
            status=PlanBomStatus(code=STATUS_CODE_EMPTY_RESULT, message=summary, success=True, severity="warning"),
            result_explanation={
                "summary": summary,
                "query_scope": {
                    "order_no": payload.order_no,
                    "order_name": payload.order_name,
                    "review_no": payload.review_no,
                    "file_instance_key": payload.file_instance_key,
                    "version_no": payload.version_no,
                    "materials": payload.material_categories,
                },
                "warnings": [],
            },
            no_result_analysis={
                "reason": reason,
                "suggestion": "请确认订单号、评审号、订单名称、版本号或材料类别是否正确。",
            },
            response_meta=self._response_meta(
                query_type=QUERY_TYPE_PLAN_BOM_DETAIL,
                status_code=STATUS_CODE_EMPTY_RESULT,
                result_count=0,
                selected_header=selected_header,
            ),
            candidate_scope=None,
            selected_version=self._selected_version(selected_header) if selected_header else None,
            total=0,
        )

    def _candidate(self, header: PlanBomHeader, match_reason: str) -> PlanBomCandidate:
        """将 BOM 头转换为候选列表项。"""
        return PlanBomCandidate(
            order_identity_key=header.order_identity_key,
            file_instance_key=header.file_instance_key,
            order_no=header.order_no,
            order_display_label=build_order_display_label(header.order_name, header.raw_file_name, header.order_no),
            order_name=header.order_name,
            version_no=header.version_no,
            effective_date=self._date_text(header.effective_date),
            source_type=header.source_type,
            source_tag=header.source_tag,
            file_no=header.file_no,
            raw_file_name=header.raw_file_name,
            match_reason=match_reason,
        )

    def _selected_version(self, header: PlanBomHeader) -> PlanBomSelectedVersion:
        """将 BOM 头转换为已选版本信息。"""
        return PlanBomSelectedVersion(
            order_identity_key=header.order_identity_key,
            file_instance_key=header.file_instance_key,
            order_no=header.order_no,
            order_display_label=build_order_display_label(header.order_name, header.raw_file_name, header.order_no),
            order_name=header.order_name,
            version_no=header.version_no,
            effective_date=self._date_text(header.effective_date),
            source_type=header.source_type,
            source_tag=header.source_tag,
            file_no=header.file_no,
            raw_file_name=header.raw_file_name,
            import_batch_id=header.import_batch_id,
        )

    def _compare_side_context(self, header: PlanBomHeader) -> PlanBomCompareSideContext:
        """将 BOM 头转换为 compare 单侧上下文。

        说明：
        compare 里程碑 1 只需要把左右两侧已解析到的 BOM 头稳定返回给上层，
        以便前端或后续差异计算阶段明确当前 compare 基线。
        """
        return PlanBomCompareSideContext(
            order_identity_key=header.order_identity_key,
            file_instance_key=header.file_instance_key,
            order_no=header.order_no,
            order_display_label=build_order_display_label(header.order_name, header.raw_file_name, header.order_no),
            order_name=header.order_name,
            version_no=header.version_no,
            effective_date=self._date_text(header.effective_date),
            source_type=header.source_type,
            source_tag=header.source_tag,
            file_no=header.file_no,
            raw_file_name=header.raw_file_name,
            import_batch_id=header.import_batch_id,
        )

    @staticmethod
    def _compare_side_scope(payload: PlanBomCompareSideRequest) -> dict[str, object]:
        """提取 compare 单侧查询作用域。

        说明：
        候选态与空结果态都需要把左右两侧原始入参回传，便于前端继续补条件，
        同时避免 compare 入口在候选场景下丢失上下文。
        """
        return {
            "order_identity_key": payload.order_identity_key,
            "file_instance_key": payload.file_instance_key,
            "order_no": payload.order_no,
            "order_name": payload.order_name,
            "review_no": payload.review_no,
            "version_no": payload.version_no,
        }

    def _compute_compare_result(
        self,
        *,
        left_header: PlanBomHeader,
        right_header: PlanBomHeader,
        material_categories: list[str],
    ) -> _CompareComputation:
        """计算 compare 左右两侧核心材料差异结果。

        说明：
        1. 当前按底层材料行比较；
        2. 匹配键优先使用 `material_category + sap_code`；
        3. 当同一匹配键下字段完全一致时归入 `same`，否则归入 `changed`；
        4. 仅统计 5 类核心材料，不扩展到其它类别。
        """
        left_lines = self._load_compare_material_lines(left_header, material_categories)
        right_lines = self._load_compare_material_lines(right_header, material_categories)

        left_map = {self._compare_match_key(line): line for line in left_lines}
        right_map = {self._compare_match_key(line): line for line in right_lines}
        ordered_keys = sorted(set(left_map) | set(right_map))

        only_left: list[PlanBomCompareSingleSideItem] = []
        only_right: list[PlanBomCompareSingleSideItem] = []
        changed: list[PlanBomCompareChangedItem] = []
        same: list[PlanBomCompareChangedItem] = []
        category_summary = {
            category: PlanBomCompareSummaryByCategory(
                material_category=category,
                material_category_label=MATERIAL_CATEGORY_LABELS.get(category),
            )
            for category in CORE_MATERIAL_CATEGORIES
        }

        for match_key in ordered_keys:
            left_line = left_map.get(match_key)
            right_line = right_map.get(match_key)
            category = (
                (left_line.material_category if left_line else None)
                or (right_line.material_category if right_line else None)
                or ""
            )

            if left_line and not right_line:
                only_left.append(self._compare_single_side_item(match_key, left_line))
                if category in category_summary:
                    category_summary[category].only_left += 1
                continue
            if right_line and not left_line:
                only_right.append(self._compare_single_side_item(match_key, right_line))
                if category in category_summary:
                    category_summary[category].only_right += 1
                continue

            assert left_line is not None
            assert right_line is not None
            changed_fields = self._compare_changed_fields(left_line, right_line)
            diff_item = self._compare_changed_item(match_key, left_line, right_line, changed_fields)
            if changed_fields:
                changed.append(diff_item)
                if category in category_summary:
                    category_summary[category].changed += 1
            else:
                same.append(diff_item)
                if category in category_summary:
                    category_summary[category].same += 1

        summary = PlanBomCompareDiffSummary(
            total_left=len(left_lines),
            total_right=len(right_lines),
            only_left=len(only_left),
            only_right=len(only_right),
            changed=len(changed),
            same=len(same),
            categories=[
                item
                for item in category_summary.values()
                if item.only_left or item.only_right or item.changed or item.same
            ],
        )
        return _CompareComputation(
            only_left=only_left,
            only_right=only_right,
            changed=changed,
            same=same,
            diff_summary=summary,
        )

    def _load_compare_material_lines(
        self,
        header: PlanBomHeader,
        material_categories: list[str],
    ) -> list[PlanBomMaterialLine]:
        """加载 compare 单侧材料行，并应用与 detail 一致的噪音过滤。"""
        material_lines = self.repository.list_material_lines(
            order_identity_key=header.order_identity_key,
            file_instance_key=header.file_instance_key,
            version_no=header.version_no,
            source_type=header.source_type,
            material_categories=material_categories,
        )
        return [line for line in material_lines if not self._is_noise_material_line(line)]

    @staticmethod
    def _compare_match_key(line: PlanBomMaterialLine) -> str:
        """生成 compare 材料匹配键。

        说明：
        1. 一期优先按 `material_category + sap_code` 对齐底层物料行；
        2. 若 SAP 编码为空，则退化使用物料名称与描述做补位；
        3. 该键只用于 compare 内部比对，不作为业务主键。
        """
        material_category = line.material_category or "unknown"
        sap_code = (line.sap_code or "").strip()
        if sap_code:
            return f"{material_category}|{sap_code}"
        material_name = (line.material_name or "").strip()
        description = (line.description or "").strip()
        return f"{material_category}|{material_name}|{description}"

    def _compare_single_side_item(
        self,
        match_key: str,
        line: PlanBomMaterialLine,
    ) -> PlanBomCompareSingleSideItem:
        """构造 compare 单侧独有材料项。"""
        return PlanBomCompareSingleSideItem(
            match_key=match_key,
            material_category=line.material_category,
            material_category_label=MATERIAL_CATEGORY_LABELS.get(line.material_category or ""),
            item=self._material_item(line),
        )

    def _compare_changed_item(
        self,
        match_key: str,
        left_line: PlanBomMaterialLine,
        right_line: PlanBomMaterialLine,
        changed_fields: list[str],
    ) -> PlanBomCompareChangedItem:
        """构造 compare 变化或一致材料项。"""
        category = left_line.material_category or right_line.material_category
        return PlanBomCompareChangedItem(
            match_key=match_key,
            material_category=category,
            material_category_label=MATERIAL_CATEGORY_LABELS.get(category or ""),
            changed_fields=changed_fields,
            left=self._material_item(left_line),
            right=self._material_item(right_line),
        )

    @staticmethod
    def _compare_changed_fields(left_line: PlanBomMaterialLine, right_line: PlanBomMaterialLine) -> list[str]:
        """比较两条材料行的核心字段差异。

        说明：
        compare 里程碑 2 先按整行字段集合判断差异，不做更细的字段级结构化解释。
        """
        comparable_fields = {
            "material_name": (left_line.material_name or "", right_line.material_name or ""),
            "description": (left_line.description or "", right_line.description or ""),
            "standard_usage": (str(left_line.standard_usage or ""), str(right_line.standard_usage or "")),
            "unit": (left_line.unit or "", right_line.unit or ""),
            "production_loss": (left_line.production_loss or "", right_line.production_loss or ""),
            "remark": (left_line.remark or "", right_line.remark or ""),
            "replacement_marker": (left_line.replacement_marker or "", right_line.replacement_marker or ""),
        }
        return [field for field, values in comparable_fields.items() if values[0] != values[1]]

    def _material_item(self, line: PlanBomMaterialLine) -> PlanBomMaterialItem:
        """将材料 ORM 行转换为前端可消费的扁平结果行。"""
        return PlanBomMaterialItem(
            order_no=line.order_no,
            version_no=line.version_no,
            file_instance_key=line.file_instance_key,
            sap_code=line.sap_code,
            line_no=line.line_no,
            material_category=line.material_category,
            material_category_label=MATERIAL_CATEGORY_LABELS.get(line.material_category or ""),
            material_name=line.material_name,
            description=line.description,
            standard_usage=self._decimal_text(line.standard_usage),
            unit=line.unit,
            production_loss=line.production_loss,
            remark=line.remark,
            replacement_marker=line.replacement_marker,
            source_type=line.source_type,
            source_tag=line.source_tag,
            import_batch_id=line.import_batch_id,
            raw_row_no=line.raw_row_no,
        )

    def _response_meta(
        self,
        *,
        query_type: str,
        status_code: str,
        result_count: int,
        selected_header: PlanBomHeader | None = None,
        candidate_count: int = 0,
        candidate_total_hint: int = 0,
        candidate_truncated: bool = False,
        candidate_scope: str | None = None,
    ) -> dict[str, object]:
        """构造计划 BOM 查询响应元信息。"""
        return {
            "domain": DOMAIN_PLAN_BOM,
            "query_type": query_type,
            "execution_mode": EXECUTION_MODE_DIRECT,
            "status_code": status_code,
            "result_count": result_count,
            "candidate_count": candidate_count,
            "candidate_total_hint": candidate_total_hint,
            "candidate_truncated": candidate_truncated,
            "candidate_scope": candidate_scope,
            "selected_order_identity_key": selected_header.order_identity_key if selected_header else None,
            "selected_file_instance_key": selected_header.file_instance_key if selected_header else None,
            "selected_order_no": selected_header.order_no if selected_header else None,
            "selected_version_no": selected_header.version_no if selected_header else None,
            "source_type": selected_header.source_type if selected_header else None,
        }

    def _sort_headers(self, headers: list[PlanBomHeader]) -> list[PlanBomHeader]:
        """按来源、生效日期、自然序版本和订单号稳定排序。"""
        return sorted(headers, key=cmp_to_key(self._compare_header))

    def _compare_header(self, left: PlanBomHeader, right: PlanBomHeader) -> int:
        """比较两个 BOM 头的候选排序优先级。"""
        source_compare = self._source_priority(left.source_type) - self._source_priority(right.source_type)
        if source_compare:
            return source_compare

        date_compare = self._compare_date_desc(left.effective_date, right.effective_date)
        if date_compare:
            return date_compare

        version_compare = -self._compare_version(left.version_no, right.version_no)
        if version_compare:
            return version_compare

        return (left.order_no > right.order_no) - (left.order_no < right.order_no)

    @classmethod
    def _source_priority(cls, source_type: str | None) -> int:
        """返回来源优先级，SAP 高于 Excel，未知来源排最后。"""
        return cls.SOURCE_PRIORITY.get(source_type or "", 99)

    @staticmethod
    def _compare_date_desc(left: date | None, right: date | None) -> int:
        """按日期倒序比较，空日期排后。"""
        if left and right:
            return (right > left) - (right < left)
        if left and not right:
            return -1
        if right and not left:
            return 1
        return 0

    @staticmethod
    def _compare_version(left: str, right: str) -> int:
        """按自然序比较版本号，支持 A2 < A10。"""
        left_key = PlanBomQueryService._version_key(left)
        right_key = PlanBomQueryService._version_key(right)
        return (left_key > right_key) - (left_key < right_key)

    @staticmethod
    def _version_key(version_no: str) -> tuple[tuple[int, object], ...]:
        """将版本号拆成自然序可比较片段。"""
        parts = re.findall(r"\d+|\D+", version_no or "")
        key: list[tuple[int, object]] = []
        for part in parts:
            if part.isdigit():
                key.append((1, int(part)))
            else:
                key.append((0, part.lower()))
        return tuple(key)

    @staticmethod
    def _header_key(header: PlanBomHeader) -> tuple[str, str, str, str]:
        """生成候选命中原因映射键。"""
        return (header.order_identity_key, header.file_instance_key, header.version_no, header.source_type)

    @staticmethod
    def _clean_text(value: str | None) -> str | None:
        """清理请求文本。"""
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _date_text(value: date | None) -> str | None:
        """将日期转换为接口稳定字符串。"""
        return value.isoformat() if value else None

    @staticmethod
    def _decimal_text(value: Decimal | None) -> str | None:
        """将 Decimal 转换为字符串，避免 JSON 精度差异。"""
        return str(value) if value is not None else None

    @classmethod
    def _is_noise_material_line(cls, line: PlanBomMaterialLine) -> bool:
        """识别查询结果里的噪音行。

        说明：
        入库阶段会尽量把图纸、标签、虚拟件归到 other，但为了兼容旧数据和失败前残留样本，
        查询层仍需再做一次过滤，避免核心材料结果被噪音行污染。
        """
        material_name = line.material_name or ""
        description = line.description or ""
        sap_code = line.sap_code or ""
        if sap_code == "备注":
            return True
        if any(keyword in material_name for keyword in cls.NOISE_NAME_KEYWORDS):
            return True
        if any(keyword in description for keyword in cls.NOISE_DESCRIPTION_KEYWORDS):
            return True
        if any(keyword in sap_code for keyword in cls.NOISE_SAP_CODE_KEYWORDS) and any(
            keyword in description for keyword in cls.NOISE_DESCRIPTION_KEYWORDS
        ):
            return True
        return False

    @staticmethod
    def _normalize_match_text(value: str | None) -> str:
        """将查询值和候选文本归一化后再做别名匹配。"""
        return normalize_identity_text(value)


__all__ = ["PlanBomQueryService"]
