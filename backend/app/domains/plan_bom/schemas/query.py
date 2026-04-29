from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from backend.app.domains.plan_bom.constants import CORE_MATERIAL_CATEGORIES

PlanBomMaterialCategory = Literal["glass", "gap_film", "interconnect_bar", "busbar", "junction_box"]


class PlanBomDetailQueryRequest(BaseModel):
    """计划 BOM 基础材料查询请求。

    参数说明：
    - order_identity_key: Excel 开发期内部实例键，只在候选已返回后用于精确选择，不替代业务主键；
    - file_instance_key: Excel 开发期文件实例键，只在文件实例候选已返回后用于精确选择；
    - order_no: 订单号或短订单号片段，优先级高于评审号；
    - order_name: 订单名称片段，用于按名称模糊定位；
    - review_no: 评审号别名，实际按订单号 / 订单名称 / 原始文件名归一化匹配；
    - version_no: 可选指定版本，为空时自动判定当前版本；
    - material_categories: 需要查询的核心材料类别，默认查询 5 类核心材料；
    - candidate_limit: 多命中候选列表最大返回条数。
    """

    order_identity_key: str | None = Field(default=None, description="Excel 开发期内部实例键")
    file_instance_key: str | None = Field(default=None, description="Excel 开发期文件实例键")
    order_no: str | None = Field(default=None, description="订单号或短订单号片段")
    order_name: str | None = Field(default=None, description="订单名称片段")
    review_no: str | None = Field(default=None, description="评审号别名，实际查询订单号")
    version_no: str | None = Field(default=None, description="指定 BOM 版本号")
    material_categories: list[PlanBomMaterialCategory] = Field(
        default_factory=lambda: list(CORE_MATERIAL_CATEGORIES),
        description="核心材料类别，默认查询 5 类核心材料",
    )
    candidate_limit: int = Field(default=20, ge=1, le=50, description="候选列表最大返回条数")

    @model_validator(mode="after")
    def validate_query_condition(self) -> "PlanBomDetailQueryRequest":
        """校验至少提供一个订单定位条件，并补齐默认材料范围。"""
        if not self.order_identity_key and not self.file_instance_key and not self.order_no and not self.order_name and not self.review_no:
            raise ValueError("order_no、order_name、review_no、file_instance_key 至少需要提供一个")
        if not self.material_categories:
            self.material_categories = list(CORE_MATERIAL_CATEGORIES)
        return self


class PlanBomCompareSideRequest(BaseModel):
    """计划 BOM compare 单侧查询条件。

    参数说明：
    - order_identity_key: 开发期内部业务实例键，仅用于 `00106` 这类多业务实例候选后的精确定位；
    - file_instance_key: 开发期内部文件实例键，仅用于 `00120` 这类文件实例候选后的精确定位；
    - order_no: 订单号或短订单号片段；
    - order_name: 订单名称片段；
    - review_no: 评审号别名；
    - version_no: 可选指定版本，不传时按当前版本规则处理。
    """

    order_identity_key: str | None = Field(default=None, description="Excel 开发期内部业务实例键")
    file_instance_key: str | None = Field(default=None, description="Excel 开发期内部文件实例键")
    order_no: str | None = Field(default=None, description="订单号或短订单号片段")
    order_name: str | None = Field(default=None, description="订单名称片段")
    review_no: str | None = Field(default=None, description="评审号别名")
    version_no: str | None = Field(default=None, description="指定 BOM 版本号")

    @model_validator(mode="after")
    def validate_compare_side(self) -> "PlanBomCompareSideRequest":
        """校验 compare 单侧至少给出一个定位条件。"""
        if (
            not self.order_identity_key
            and not self.file_instance_key
            and not self.order_no
            and not self.order_name
            and not self.review_no
        ):
            raise ValueError("compare 左右两侧都至少需要提供一个订单定位条件")
        return self


class PlanBomCompareQueryRequest(BaseModel):
    """计划 BOM compare 请求。

    参数说明：
    - left/right: compare 左右两侧查询条件；
    - material_categories: 可选限制到 5 类核心材料；
    - candidate_limit: 候选列表最大返回条数。
    """

    left: PlanBomCompareSideRequest
    right: PlanBomCompareSideRequest
    material_categories: list[PlanBomMaterialCategory] = Field(
        default_factory=lambda: list(CORE_MATERIAL_CATEGORIES),
        description="核心材料类别，默认使用 5 类核心材料",
    )
    candidate_limit: int = Field(default=20, ge=1, le=50, description="候选列表最大返回条数")

    @model_validator(mode="after")
    def validate_compare_query(self) -> "PlanBomCompareQueryRequest":
        """补齐默认材料范围。"""
        if not self.material_categories:
            self.material_categories = list(CORE_MATERIAL_CATEGORIES)
        return self


class PlanBomStatus(BaseModel):
    """计划 BOM 查询状态。

    返回值说明：
    - success 表示接口主链路是否成功执行；
    - severity 用于前端区分普通信息、提示和错误；
    - extras 用于携带候选截断等轻量扩展信息。
    """

    code: str
    message: str
    success: bool = True
    severity: Literal["info", "warning", "error"] = "info"
    extras: dict[str, Any] = Field(default_factory=dict)


class PlanBomCandidate(BaseModel):
    """订单候选项，用于短订单号、评审号或订单名称多命中场景。"""

    order_identity_key: str
    file_instance_key: str | None = None
    order_no: str
    order_display_label: str | None = None
    order_name: str | None = None
    version_no: str
    effective_date: str | None = None
    source_type: str
    source_tag: str | None = None
    file_no: str | None = None
    raw_file_name: str | None = None
    match_reason: str


class PlanBomSelectedVersion(BaseModel):
    """已选中的 BOM 版本信息。"""

    order_identity_key: str
    file_instance_key: str | None = None
    order_no: str
    order_display_label: str | None = None
    order_name: str | None = None
    version_no: str
    effective_date: str | None = None
    source_type: str
    source_tag: str | None = None
    file_no: str | None = None
    raw_file_name: str | None = None
    import_batch_id: str | None = None


class PlanBomCompareSideContext(BaseModel):
    """compare 单侧已解析上下文。

    返回值说明：
    - candidate_side 处理完成后，left/right 都返回最终被 compare 的上下文；
    - compare 里程碑 1 仅要求返回定位结果，不输出差异明细。
    """

    order_identity_key: str
    file_instance_key: str | None = None
    order_no: str
    order_display_label: str | None = None
    order_name: str | None = None
    version_no: str
    effective_date: str | None = None
    source_type: str
    source_tag: str | None = None
    file_no: str | None = None
    raw_file_name: str | None = None
    import_batch_id: str | None = None


class PlanBomMaterialItem(BaseModel):
    """计划 BOM 材料查询结果行。

    返回值说明：
    - material_category 是系统归类编码；
    - material_category_label 是业务可读名称；
    - material_name 始终返回原始物料名称；
    - replacement_marker 仅展示明确替代标识，不做关系推断。
    """

    order_no: str
    version_no: str
    file_instance_key: str | None = None
    sap_code: str
    line_no: str | None = None
    material_category: str | None = None
    material_category_label: str | None = None
    material_name: str
    description: str | None = None
    standard_usage: str | None = None
    unit: str | None = None
    production_loss: str | None = None
    remark: str | None = None
    replacement_marker: str | None = None
    source_type: str
    source_tag: str | None = None
    import_batch_id: str | None = None
    raw_row_no: int | None = None


class PlanBomCompareSingleSideItem(BaseModel):
    """compare 单侧独有材料项。

    返回值说明：
    - match_key 是 compare 内部比对键，仅用于前端稳定渲染，不作为业务主键；
    - item 为当前单侧的完整材料行。
    """

    match_key: str
    material_category: str | None = None
    material_category_label: str | None = None
    item: PlanBomMaterialItem


class PlanBomCompareChangedItem(BaseModel):
    """compare 变化材料项。

    返回值说明：
    - left/right 是同一比对键下左右两侧的材料行；
    - changed_fields 是当前差异命中的字段列表。
    """

    match_key: str
    material_category: str | None = None
    material_category_label: str | None = None
    changed_fields: list[str] = Field(default_factory=list)
    left: PlanBomMaterialItem
    right: PlanBomMaterialItem


class PlanBomCompareSummaryByCategory(BaseModel):
    """按材料类别统计 compare 差异分布。"""

    material_category: str
    material_category_label: str | None = None
    only_left: int = 0
    only_right: int = 0
    changed: int = 0
    same: int = 0


class PlanBomCompareDiffSummary(BaseModel):
    """compare 汇总统计。"""

    total_left: int = 0
    total_right: int = 0
    only_left: int = 0
    only_right: int = 0
    changed: int = 0
    same: int = 0
    categories: list[PlanBomCompareSummaryByCategory] = Field(default_factory=list)


class PlanBomDetailQueryResponse(BaseModel):
    """计划 BOM 基础材料查询响应。

    返回值说明：
    - query_type 为 detail 或 candidate_list；
    - candidates 只在多命中候选场景返回；
    - items 只在已定位到具体订单版本后返回；
    - 当前响应不包含两订单差异对比和导出任务信息。
    """

    query_type: str
    domain: str
    execution_mode: str
    status: PlanBomStatus
    result_explanation: dict[str, Any]
    no_result_analysis: dict[str, Any] | None = None
    response_meta: dict[str, Any]
    candidate_scope: str | None = None
    selected_version: PlanBomSelectedVersion | None = None
    candidates: list[PlanBomCandidate] = Field(default_factory=list)
    candidate_total_hint: int = 0
    items: list[PlanBomMaterialItem] = Field(default_factory=list)
    total: int = 0


class PlanBomCompareResponse(BaseModel):
    """计划 BOM compare 响应。

    返回值说明：
    - 里程碑 1 已补齐 compare 骨架与候选链路；
    - 里程碑 2 已补齐 `only_left / only_right / changed / same / diff_summary`；
    - 里程碑 3 会把该响应的受控快照写入 `sys_query_log`，供后续历史回放使用。
    """

    query_type: str
    domain: str
    execution_mode: str
    status: PlanBomStatus
    result_explanation: dict[str, Any]
    no_result_analysis: dict[str, Any] | None = None
    response_meta: dict[str, Any]
    candidate_scope: str | None = None
    candidate_side: Literal["left", "right"] | None = None
    left: PlanBomCompareSideContext | None = None
    right: PlanBomCompareSideContext | None = None
    candidates: list[PlanBomCandidate] = Field(default_factory=list)
    candidate_total_hint: int = 0
    compare_ready: bool = False
    only_left: list[PlanBomCompareSingleSideItem] = Field(default_factory=list)
    only_right: list[PlanBomCompareSingleSideItem] = Field(default_factory=list)
    changed: list[PlanBomCompareChangedItem] = Field(default_factory=list)
    same: list[PlanBomCompareChangedItem] = Field(default_factory=list)
    diff_summary: PlanBomCompareDiffSummary | None = None


__all__ = [
    "PlanBomCandidate",
    "PlanBomCompareQueryRequest",
    "PlanBomCompareResponse",
    "PlanBomCompareChangedItem",
    "PlanBomCompareDiffSummary",
    "PlanBomCompareSideContext",
    "PlanBomCompareSideRequest",
    "PlanBomCompareSingleSideItem",
    "PlanBomCompareSummaryByCategory",
    "PlanBomDetailQueryRequest",
    "PlanBomDetailQueryResponse",
    "PlanBomMaterialCategory",
    "PlanBomMaterialItem",
    "PlanBomSelectedVersion",
    "PlanBomStatus",
]
