"""
多候选消歧统一交互（Disambiguation）模块。

业务定位：
    当业务值解析器（BusinessValueResolver）返回多个候选时，
    本模块提供统一的消歧流程——生成业务化追问文本、管理候选列表、
    根据用户选择解析最终实体值。前端复用 BusinessChatPage 的对话式体验，
    不新增独立弹出式选择器。

模块组成：
    - schema: 消歧数据结构（DisambiguationCandidate、Request、Response 等）
    - service: 消歧服务（DisambiguationService）

使用方式：
    # 1. 从值解析器获取候选
    candidates = resolver.resolve("carrier", "顺丰")
    # 2. 如果返回多个候选，进入消歧流程
    if len(candidates) > 1:
        svc = DisambiguationService()
        follow_up = svc.generate_follow_up(question, entity_type, candidates)
        # 返回 needs_selection 状态给前端
    # 3. 用户选择后
    resolved = svc.resolve_selection(candidates, selected_id)

约束：
    - 不做物管/SAP MID M2。
    - 不引入 ES。
    - 不替代 NL2SQL。
    - 消歧服务不耦合具体数据源。
    - 追问文本不暴露 SQL、表名、字段名、query_key 等技术信息。
"""
from __future__ import annotations

from backend.app.domains.semantic_catalog.disambiguation.schema import (
    DisambiguationCandidate,
    DisambiguationRequest,
    DisambiguationResponse,
    DisambiguationResolveRequest,
    DisambiguationResolveResponse,
)
from backend.app.domains.semantic_catalog.disambiguation.service import (
    DisambiguationService,
    DisambiguationError,
)

__all__ = [
    "DisambiguationCandidate",
    "DisambiguationRequest",
    "DisambiguationResponse",
    "DisambiguationResolveRequest",
    "DisambiguationResolveResponse",
    "DisambiguationService",
    "DisambiguationError",
]
