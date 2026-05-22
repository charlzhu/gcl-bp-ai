"""
统一语义资产 Catalog Schema 定义。

业务逻辑：
    本模块定义跨业务域的统一语义资产数据结构标准。
    包括指标（SemanticMetric）、维度（SemanticDimension）、实体（SemanticEntity）
    和可插拔的业务值解析器协议（BusinessValueResolverProtocol）。

    这些 Schema 是 NL2SQL / QueryPlanningV2 的辅助能力层，
    不是替代现有领域 catalog 的新核心。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class SemanticMetric(BaseModel):
    """统一语义指标定义。

    参数：
        metric_id: 统一指标 ID，如 shipment_mw、total_fee。
        display_name: 业务展示名称，如"发货量"、"总费用"。
        domain: 所属业务域，如 logistics、plan_bom、business_analysis。
        aliases: 用户口语同义词列表，如["件数", "发运量"]。
        unit: 业务单位，如"MW"、"元"。
        description: 业务口径说明，供 LLM 辅助理解。

    返回：
        业务域无关的统一指标条目。
    """

    model_config = ConfigDict(extra="forbid")

    metric_id: str = Field(..., description="统一指标 ID")
    display_name: str = Field(..., description="业务展示名称")
    domain: str = Field(..., description="所属业务域")
    aliases: list[str] = Field(default_factory=list, description="用户口语同义词")
    unit: str | None = Field(default=None, description="业务单位")
    description: str | None = Field(default=None, description="业务口径说明")


class SemanticDimension(BaseModel):
    """统一语义维度定义。

    参数：
        dimension_id: 统一维度 ID，如 material_category、version_no。
        display_name: 业务展示名称，如"物料类别"、"版本号"。
        domain: 所属业务域，如 logistics、plan_bom。
        aliases: 用户口语同义词列表。
        description: 业务口径说明。

    返回：
        业务域无关的统一维度条目。
    """

    model_config = ConfigDict(extra="forbid")

    dimension_id: str = Field(..., description="统一维度 ID")
    display_name: str = Field(..., description="业务展示名称")
    domain: str = Field(..., description="所属业务域")
    aliases: list[str] = Field(default_factory=list, description="用户口语同义词")
    description: str | None = Field(default=None, description="业务口径说明")


class SemanticEntity(BaseModel):
    """统一语义实体定义。

    参数：
        entity_id: 统一实体 ID，如 carrier、material。
        display_name: 业务展示名称，如"承运商"、"物料"。
        domain: 所属业务域。
        entity_type: 实体类型分类，如 carrier、customer、material。
        aliases: 用户口语同义词列表。
        description: 业务口径说明。

    返回：
        业务域无关的统一实体条目。
    """

    model_config = ConfigDict(extra="forbid")

    entity_id: str = Field(..., description="统一实体 ID")
    display_name: str = Field(..., description="业务展示名称")
    domain: str = Field(..., description="所属业务域")
    entity_type: str = Field(..., description="实体类型分类")
    aliases: list[str] = Field(default_factory=list, description="用户口语同义词")
    description: str | None = Field(default=None, description="业务口径说明")


class SemanticCapability(BaseModel):
    """统一语义能力定义 — 业务域的查询能力、意图分类或域能力。

    业务逻辑：
        每个业务域下存在多种"能力"（如物流的 query_key、计划 BOM 的 intent、
        计划功率的 domain capability），本模型统一描述这些能力。

        与 SemanticMetric/SemanticDimension 的关系：
        - 能力是"能做什么"（如 hist_carrier_kpi_by_year 可按承运商查 KPI）。
        - 指标/维度是"能查什么"（如 shipment_mw、carrier）。
        - 一个能力可以关联多个指标和维度。

    参数：
        capability_id: 统一能力 ID（即 query_key、intent 或 capability 编码）。
        display_name: 业务展示名称，如"承运商 KPI 年度查询"。
        domain: 所属业务域，如 logistics、plan_bom。
        capability_type: 能力类型：
            - "query_key"：物流域的传统 query_key 能力。
            - "intent"：计划 BOM 域的意图分类能力。
            - "domain_capability"：计划功率域的域级能力。
        related_metrics: 关联的业务指标 ID 列表（可选，供下游系统引用）。
        related_dimensions: 关联的业务维度 ID 列表（可选，供下游系统引用）。
        aliases: 用户口语同义词列表。
        description: 业务口径说明。

    返回：
        业务域无关的统一能力条目。

    约束：
        不暴露 SQL、表名、字段名、query_key 等内部技术内容。
    """

    model_config = ConfigDict(extra="forbid")

    capability_id: str = Field(..., description="统一能力 ID")
    display_name: str = Field(..., description="业务展示名称")
    domain: str = Field(..., description="所属业务域")
    capability_type: str = Field(..., description="能力类型：query_key / intent / domain_capability")
    related_metrics: list[str] = Field(default_factory=list, description="关联的业务指标 ID")
    related_dimensions: list[str] = Field(default_factory=list, description="关联的业务维度 ID")
    aliases: list[str] = Field(default_factory=list, description="用户口语同义词")
    description: str | None = Field(default=None, description="业务口径说明")


@runtime_checkable
class BusinessValueResolverProtocol(Protocol):
    """业务值解析器协议（可插拔）。

    业务逻辑：
        不同业务域的实体值解析逻辑可以不同（例如物流承运商从中间库查、
        计划 BOM 物料从 Excel 查），但都必须实现统一的 resolve/register 接口。
        这样可以支持后续的 ES 全文搜索、向量检索或其他解析器接入，
        而不修改统一 catalog 核心。

    Protocol 方法：
        resolve(domain, entity_type, user_input) → list[dict]:
            根据用户输入解析实体值候选列表。
            返回列表包含 dict，至少包含 id 和 label 字段。

        register(domain, entity_type, values):
            注册一批实体值供后续 resolve 使用。
    """

    def resolve(self, domain: str, entity_type: str, user_input: str) -> list[dict[str, str]]:
        """解析用户输入为实体值候选列表。

        参数：
            domain: 业务域，如 logistics、plan_bom。
            entity_type: 实体类型，如 carrier、material。
            user_input: 用户输入的实体名称或关键词。

        返回：
            候选实体值列表，每项 dict 至少包含 id 和 label。
        """
        ...

    def register(self, domain: str, entity_type: str, values: list[dict[str, str]]) -> None:
        """注册一批实体值。

        参数：
            domain: 业务域。
            entity_type: 实体类型。
            values: 实体值列表，每项 dict 至少包含 id 和 label。
        """
        ...


__all__ = [
    "SemanticMetric",
    "SemanticDimension",
    "SemanticEntity",
    "SemanticCapability",
    "BusinessValueResolverProtocol",
]
