from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BusinessQaDomainId = Literal["logistics", "plan_bom", "unknown"]
BusinessQaRoutableDomainId = Literal["logistics", "plan_bom"]
BusinessQaNormalizedDomainHint = Literal["auto", "logistics", "plan_bom", "unknown"]
BusinessQaDomainRouteStatus = Literal["ROUTED", "CLARIFY"]
BusinessQaCapabilityId = Literal[
    "logistics_data_qa",
    "plan_bom_qa",
    "plan_power_prediction",
    "plan_power_supplier_recommendation",
    "plan_power_factor_effect_compare",
    # NQE-S1 新增：物流 NL2SQL SQLPlan shadow 能力
    # 该能力仅用于 Graph shadow 记录，不改变现有 NL2SQL-A/B/C/D 执行链路
    "logistics_nl2sql_shadow",
    # NQE-S2 新增：物流复合问题分解能力
    # 使 Graph 能统一拆解对比/趋势/综合型复杂问法，通过 NL2SQL 子计划执行
    "logistics_composite_decomposition",
]
BusinessQaCapabilityRiskLevel = Literal["read_only_data_qa", "deterministic_calculation"]


class BusinessQaCapabilityDefinition(BaseModel):
    """统一业务问数 capability 定义。

    参数：
        capability: 稳定 capability 标识。
        domain: capability 所属业务域。
        label: 内部审计用中文名称。
        description: capability 覆盖的业务边界说明。
        risk_level: 风险等级；当前仅允许只读问数或确定性计算。
        executable_service: 后续 adapter 可调用的既有受控服务名称。
    返回：
        capability registry 中的单条能力定义。
    业务逻辑：
        registry 只声明受控能力，不包含 SQL、表名、字段名或可执行工具参数。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: BusinessQaCapabilityId
    domain: BusinessQaRoutableDomainId
    label: str
    description: str
    risk_level: BusinessQaCapabilityRiskLevel
    executable_service: str


class BusinessQaDomainDefinition(BaseModel):
    """统一业务问数业务域定义。

    参数：
        domain: 业务域稳定标识。
        label: 内部审计用中文名称。
        description: 业务域覆盖范围说明。
        capabilities: 该域可暴露给 Graph 的受控 capability 白名单。
    返回：
        domain registry 中的单条业务域定义。
    业务逻辑：
        LQG-2 只开放 logistics 与 plan_bom；功率能力作为 plan_bom 子能力，不新增 power 域。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: BusinessQaRoutableDomainId
    label: str
    description: str
    capabilities: tuple[BusinessQaCapabilityId, ...]


class BusinessQaDomainRouteCandidate(BaseModel):
    """无法明确识别时返回的澄清候选。

    参数：
        domain: 候选业务域。
        label: 候选业务域中文名称。
        capabilities: 候选域可处理的 capability 列表。
        reason: 该候选适合处理的问题类型摘要。
    返回：
        可供后续澄清节点或前端展示的候选项。
    业务逻辑：
        候选只来自 registry 白名单，避免未知问题误落旧域或未启用业务域。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: BusinessQaRoutableDomainId
    label: str
    capabilities: tuple[BusinessQaCapabilityId, ...]
    reason: str


class BusinessQaDomainRouteResult(BaseModel):
    """统一业务问数领域路由结果。

    参数：
        status: ROUTED 表示已确定领域，CLARIFY 表示需要澄清。
        requested_domain: 调用方原始 domain_hint。
        normalized_domain_hint: 归一后的 domain_hint。
        domain: 已确定领域；无法确定时为 unknown。
        confidence: 路由置信度，unknown 时为 0。
        capabilities: 本轮可进入的 capability 白名单。
        capability_domain: capability 所属域；unknown 表示未选中 capability。
        reason: 内部审计说明，不直接作为用户最终回答。
        clarify_candidates: 需要澄清时可选候选。
    返回：
        domain_route_node 写入 state 与 response 的稳定结构。
    业务逻辑：
        该结果只做外层路由和 capability 标记，不查数、不计算、不执行自由 SQL。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: BusinessQaDomainRouteStatus
    requested_domain: str | None = None
    normalized_domain_hint: BusinessQaNormalizedDomainHint = "auto"
    domain: BusinessQaDomainId
    confidence: float = Field(ge=0.0, le=1.0)
    capabilities: tuple[BusinessQaCapabilityId, ...] = ()
    capability_domain: BusinessQaDomainId = "unknown"
    reason: str
    clarify_candidates: tuple[BusinessQaDomainRouteCandidate, ...] = ()
