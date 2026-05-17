from __future__ import annotations

import json

from backend.app.domains.logistics.services.query_planner_v2.capability_registry import (
    LogisticsQueryPlannerV2CapabilityRegistry,
)


class LogisticsQueryPlannerV2PromptBuilder:
    """构造物流 Query Planner V2 的受控 LLM prompt。

    业务逻辑：Prompt 只允许模型输出 JSON QueryPlan 候选，明确禁止 SQL、查库和最终数值计算。
    """

    FORBIDDEN_FIELDS = (
        "sql",
        "where",
        "where_clause",
        "database",
        "table_name",
        "answer",
        "computed_value",
        "python_code",
        "tool_call",
    )

    def build_system_prompt(
        self,
        registry: LogisticsQueryPlannerV2CapabilityRegistry,
        allowed_query_keys: list[str] | set[str] | None = None,
    ) -> str:
        """生成系统提示词。

        参数：
            registry: query_key 能力注册表。
            allowed_query_keys: 配置层允许进入 prompt 的 query_key 子集。
        返回：
            包含白名单和安全边界的中文系统提示词。
        """

        capabilities_json = json.dumps(registry.prompt_payload(allowed_query_keys), ensure_ascii=False, indent=2)
        forbidden = ", ".join(self.FORBIDDEN_FIELDS)
        lines = [
            "你是物流 QA 的查询规划器，不是数据查询器。",
            "你的唯一任务是把业务员自然语言问题理解成受控 JSON QueryPlan 候选。",
            "安全边界：",
            "1. 不能生成 SQL，不能输出 SQL 片段或 where 条件。",
            "2. 不能查数据库，不能调用任何工具，不能读取表。",
            "3. 不能计算业务数值，不能编造平均运费、总费用、车次数等答案。",
            "4. 只能从后端提供的 query_key 白名单中选择，不能发明 query_key。",
            "5. 槽位不足时必须输出 clarification_questions。",
            "6. 超出能力边界时必须输出 unsupported_reason。",
            "7. 输出必须是严格 JSON，不能有 markdown、解释文字或多余前后缀。",
            f"8. JSON 中禁止出现这些字段名：{forbidden}。一旦出现后端会 fail closed。",
            "可选 query_key 能力白名单：",
            capabilities_json,
            "输出 JSON 字段：intent, query_key, filters, metrics, dimensions, group_by, aggregations, compare_mode, time_range, confidence, clarification_questions, unsupported_reason, normalized_question。",
            "线路表达归一提示：合肥发/至/到/运到/往马鞍山发 都表示 origin_place=合肥, city=马鞍山；17米五车/17.5米车/17.5车 都表示 vehicle_type=17.5。",
        ]
        return "\n".join(lines)

    def build_user_prompt(self, question: str) -> str:
        """生成用户提示词。

        参数：
            question: 原始业务问题。
        返回：
            要求模型输出 JSON QueryPlan 的用户提示。
        """

        return f"原始问题：{question}\n请只返回一个严格 JSON QueryPlan 候选。"


__all__ = ["LogisticsQueryPlannerV2PromptBuilder"]
