"""LQG-4 统一安全校验策略定义。

定义 PlanValidationResult、安全策略白名单、槽位策略、技术泄露检测规则。
本模块不查库、不执行 SQL、不调用 LLM，只提供确定性校验规则。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# =============================================================================
# 校验结果状态类型
# =============================================================================

PlanValidationResultStatus = Literal["ok", "clarify", "unsupported", "no_answer", "error"]
"""校验结果状态：
  - ok: 通过所有校验，可进入后续计划执行节点
  - clarify: 缺少必填信息，需业务化追问用户
  - unsupported: 问题不在受控能力范围 / 存在安全风险
  - no_answer: 查询可执行但结果为空
  - error: 系统内部异常，需安全降级
"""


class PlanValidationResult(BaseModel):
    """统一校验门输出结果。

    参数：
        validation_result: 校验路由状态，决定后续流向哪个终端节点。
        missing_slots: 缺少的必填槽位列表（clarify 时填充）。
        clarification_reason: 业务化追问说明，不暴露内部技术标识。
        unsupported_reason: 业务化拒答说明，不暴露 SQL/表名/字段名等。
        error_type: 异常类型（error 时填充），仅内部审计使用。
        error_message: 安全化后的错误描述，用于构造用户可见消息。
        tech_leak_blocked: 是否因技术泄露特征被阻断。
        safety_blocked: 是否因安全问题被阻断。
        blocked_details: 阻断详情，供审计日志使用。
    返回：
        供 plan_validate_node 写入 state.validation_details 的稳定结构。
    业务逻辑：
        用户可见字段（clarification_reason、unsupported_reason）不得包含 SQL/表名/
        字段名/query_key/planner/guardrail/schema/raw/debug/LLM 等内部标识。
    """

    model_config = ConfigDict(extra="forbid")

    validation_result: PlanValidationResultStatus
    """校验路由结果。"""

    missing_slots: list[str] = Field(default_factory=list)
    """缺少的必填槽位（clarify 时）—— 仅内部使用，不直接展示给用户。"""

    clarification_reason: str = ""
    """业务化追问原因，可由 clarify_node 直接用于用户可见消息。"""

    unsupported_reason: str = ""
    """业务化拒答原因，可由 unsupported_node 直接用于用户可见消息。"""

    error_type: str = ""
    """异常类型标识，仅内部审计。"""

    error_message: str = ""
    """安全化错误描述，已剥离内部堆栈/连接信息。"""

    tech_leak_blocked: bool = False
    """是否因技术泄露特征阻断。"""

    safety_blocked: bool = False
    """是否因安全问题阻断。"""

    blocked_details: dict = Field(default_factory=dict)
    """阻断详情，供审计日志。"""

    def is_blocked(self) -> bool:
        """是否被阻断（不能进入执行节点）。"""
        return self.validation_result != "ok"

    def is_ok(self) -> bool:
        """是否通过校验可继续。"""
        return self.validation_result == "ok"


# =============================================================================
# 安全策略常量（白名单与黑名单规则）
# =============================================================================

# 允许进入执行业务域的白名单
ALLOWED_DOMAINS: set[str] = {"logistics", "plan_bom"}
"""已注册可路由的业务域。unknown 不可进入后续执行。"""

# 允许进入执行业务 capability 的白名单
ALLOWED_CAPABILITIES: set[str] = {
    "logistics_data_qa",
    "plan_bom_qa",
    "plan_power_prediction",
    "plan_power_supplier_recommendation",
    "plan_power_factor_effect_compare",
}
"""已注册可执行的 capability 标识。"""

# 技术泄露特征关键字（用户问题或 shadow_plan 中出现即阻断）
TECH_LEAK_PATTERNS: tuple[str, ...] = (
    "SQL",
    "SELECT ",
    "DROP ",
    "INSERT ",
    "DELETE ",
    "UNION ",
    "TABLE ",
    "query_key",
    "SQLPlan",
    "guardrail",
    "schema",
    "planner",
    "rawResponse",
    "debug",
    "llm_prompt",
    "warehouse_",
    "ods_",
    "dwd_",
    # 中国語技术术语 / 内部表名引用
    "logistics_shipment",
    "logistics_carrier",
    "logistics_route",
)
"""触发技术泄露阻断的用户问题关键字/模式。
匹配规则：用户原始问题（大写）或 shadow_plan_raw 的序列化文本中包含任一模式时阻断。
"""

# 安全问题特征关键字（SQL 注入/危险操作）
SAFETY_DANGER_PATTERNS: tuple[str, ...] = (
    "1=1",
    "'; ",
    '"=',
    "OR 1=1",
    "UNION SELECT",
    "DROP TABLE",
    "DELETE FROM",
    "INSERT INTO",
    "UPDATE ",
    "ALTER ",
    "EXEC ",
    "EXECUTE ",
    "xp_",
    "sp_",
)
"""触发安全阻断的关键字/模式。
匹配规则：用户原始问题（大写）中包含任一模式时阻断，不进入后续执行。
"""

# 必填槽位表 —— 按意图分类
REQUIRED_SLOTS_BY_INTENT: dict[str, set[str]] = {
    # 物流意图：基本都需要时间范围
    "direct_retrieval": set(),  # 无强制槽位，由具体 query_key 决定
    "query_decomposition": set(),  # 无强制槽位
    # 计划 BOM 意图
    "single_order_material_specs": {"order_id"},  # 必须指定订单号
    "single_bom_file_material_specs": {"bom_file"},  # 必须指定 BOM 文件
    "power_prediction": {"order_id"},  # 功率预测需要订单号
}
"""必填槽位映射：intent -> 必须存在的 slot 名称集合。
若 shadow_plan 的 intent 在此表中且有缺失槽位，应返回 clarify。
"""


def is_domain_allowed(domain: str) -> bool:
    """检查业务域是否在注册白名单中。

    参数：
        domain: 业务域标识。
    返回：
        True 表示 domain 在白名单内。
    """
    return domain in ALLOWED_DOMAINS


def is_capability_allowed(capability: str) -> bool:
    """检查 capability 是否在注册白名单中。

    参数：
        capability: 业务能力标识。
    返回：
        True 表示 capability 在白名单内。
    """
    return capability in ALLOWED_CAPABILITIES


def detect_tech_leak(text: str) -> bool:
    """检测文本中是否包含技术泄露特征。

    参数：
        text: 待检测文本（用户问题或 shadow_plan_raw 序列化文本）。
    返回：
        True 表示检测到技术泄露特征，应阻断。
    业务逻辑：
        在文本大写形式中匹配 TECH_LEAK_PATTERNS 中的任一模式。
    """
    upper = text.upper()
    return any(pattern.upper() in upper for pattern in TECH_LEAK_PATTERNS)


def detect_safety_danger(text: str) -> bool:
    """检测文本中是否包含安全危险特征。

    参数：
        text: 待检测文本（用户问题）。
    返回：
        True 表示检测到安全危险特征（SQL 注入等），应阻断。
    """
    upper = text.upper()
    return any(pattern.upper() in upper for pattern in SAFETY_DANGER_PATTERNS)


def get_required_slots(intent: str) -> set[str]:
    """获取指定意图的必填槽位集合。

    参数：
        intent: NLU 识别出的意图名称。
    返回：
        必填 slot 名称集合；若 intent 不在表中则返回空集。
    """
    return REQUIRED_SLOTS_BY_INTENT.get(intent, set())


def check_missing_slots(intent: str, slots: dict) -> list[str]:
    """检查 shadow_plan 中是否缺少必填槽位。

    参数：
        intent: 意图名称。
        slots: shadow_plan 中已填充的槽位映射（key-value）。
    返回：
        缺失的 slot 名称列表。
    """
    required = get_required_slots(intent)
    if not required:
        return []
    return sorted(s for s in required if s not in slots or not slots[s])
