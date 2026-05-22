"""
多候选消歧统一交互 — 服务层。

业务逻辑：
    本模块提供统一的消歧服务 DisambiguationService。当业务值解析器
    返回多个候选时，消歧服务负责：
    1. 根据候选列表和实体类型生成业务化追问文本。
    2. 根据用户选择的 candidate_id 解析对应候选。
    3. 未知 candidate_id 或空候选列表时明确报错。

    追问文本是中文业务语言，不包含 SQL、表名、字段名等内部技术内容。
    不同的实体类型（承运商、客户、订单等）有对应的追问模板。

设计原则：
    1. 消歧服务不耦合具体数据源——只操作已解析出的候选列表。
    2. 追问文本使用预定义模板 + 回退逻辑，不依赖 LLM。
    3. 解析选择时 fail-closed：未知 candidate_id 必须抛异常，不能返回任意候选。
"""
from __future__ import annotations

from backend.app.domains.semantic_catalog.disambiguation.schema import (
    DisambiguationCandidate,
)


class DisambiguationError(Exception):
    """消歧服务异常。

    参数：
        message: 错误描述。

    业务逻辑：
        消歧过程中遇到非法状态（如空候选列表、未知 candidate_id）时抛出。
        调用方应捕获此异常并返回合适的用户提示。
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# ── 实体类型 → 追问模板映射 ──

# 各实体类型对应的业务中文名称，用于追问文本
_ENTITY_LABELS: dict[str, str] = {
    "carrier": "承运商",
    "customer": "客户",
    "order_identity": "订单",
    "filename": "BOM 文件",
    "customer_instance": "客户实例",
    "version": "版本",
    "region": "区域",
    "route": "物流线路",
    "address": "收货地址",
}


def _entity_label(entity_type: str) -> str:
    """获取实体类型的业务中文名称。

    参数：
        entity_type: 实体类型标识。

    返回：
        中文业务名称；未知类型返回实体类型本身。
    """
    return _ENTITY_LABELS.get(entity_type, entity_type)


class DisambiguationService:
    """统一多候选消歧服务。

    业务逻辑：
        不依赖数据库、LLM 或任何外部系统——只基于已解析的候选列表
        生成追问文本和解析用户选择。
    """

    def generate_follow_up(
        self,
        question: str,
        entity_type: str,
        candidates: list[DisambiguationCandidate],
    ) -> str:
        """根据候选列表生成业务化追问文本。

        参数：
            question: 原始用户问题（当前版本未直接用于追问生成，
                但保留参数以便后续增强）。
            entity_type: 实体类型。
            candidates: 消歧候选列表。

        返回：
            中文业务追问文本。空候选时返回空字符串。

        业务逻辑：
            1. 候选数量为 0 时返回空字符串——不应生成追问。
            2. 候选数量为 1 时返回确认式追问。
            3. 候选数量 >= 2 时返回标准多候选追问，包含可选实体值列表。
            4. 未知实体类型使用通用追问模板。
        """
        count = len(candidates)
        label = _entity_label(entity_type)

        if count == 0:
            return ""
        if count == 1:
            return f"找到 1 个匹配的{label}：{candidates[0].display_label}。是否确认使用该{label}？"

        # count >= 2：生成带候选列表的业务追问
        option_text = "、".join(
            f"{c.display_label}" for c in candidates[:5]
        )
        if count > 5:
            option_text += f" 等共 {count} 个"

        return f"找到 {count} 个匹配的{label}：{option_text}。请选择一个{label}。"

    def resolve_selection(
        self,
        candidates: list[DisambiguationCandidate],
        selected_id: str,
    ) -> DisambiguationCandidate:
        """根据用户选择的 candidate_id 解析对应候选。

        参数：
            candidates: 消歧候选列表。
            selected_id: 用户选择的 candidate_id。

        返回：
            匹配的 DisambiguationCandidate。

        异常：
            DisambiguationError：候选列表为空或 candidate_id 不存在时抛出。

        业务逻辑：
            fail-closed——unknown ID 或空列表必须抛异常，
            不可返回任意候选或 None。
        """
        if not candidates:
            raise DisambiguationError(
                "候选列表为空，无法进行消歧。请先通过实体解析器获取候选列表。"
            )

        for c in candidates:
            if c.candidate_id == selected_id:
                return c

        # 未找到匹配的 candidate_id
        known_ids = ", ".join(c.candidate_id for c in candidates)
        raise DisambiguationError(
            f"未找到 candidate_id='{selected_id}' 对应的候选。"
            f"可用的候选 ID：{known_ids}。"
        )


__all__ = ["DisambiguationService", "DisambiguationError"]
