"""NL2SQL 多域路由——领域无关的抽象域路由。

职责：
1. 定义 Nl2SqlDomainRoute（域路由结果模型）
2. 定义 Nl2SqlDomainRouter（多域路由基类，通过 Nl2SqlDomainRegistry 判断域）
3. LogisticsNl2SqlDomainRouter 保持为子类兼容别名

设计原则：
- 不改文件路径，不拆包，不破坏现有 import
- LogisticsNl2SqlDomainRouter 作为子类保留在 m9_sqlplan_generation.py，不做迁移
- 新域通过 Nl2SqlDomainRegistry.register() 注册，无需修改路由逻辑
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class Nl2SqlDomainRoute(BaseModel):
    """NL2SQL 域路由结果。

    参数：
        should_process: 是否应由 NL2SQL shadow 处理该问题。
        domain: 命中的业务域（logistics / business_analysis / plan_bom / material_management）。
        source_system: 数据源系统，默认智能助手中间库（middle_db）。
        mode: 运行模式，当前只支持 shadow。
        reason_code: 路由决策的原因码，用于审计和脱敏日志。
    """

    model_config = ConfigDict(extra="forbid")

    should_process: bool
    domain: str
    source_system: str = "middle_db"
    mode: str = "shadow"
    reason_code: str | None = None


class Nl2SqlDomainRouter:
    """多域路由基类——通过 domain_registry 判断域。

    职责：
        1. 判断用户问题落在哪个已注册的业务域；
        2. 返回 Nl2SqlDomainRoute（包含 should_process、domain 等信息）；
        3. 已有 LogisticsNl2SqlDomainRouter 保留别名兼容（子类）。

    使用方式：
        router = Nl2SqlDomainRouter(registry)
        route = router.route(question)
    """

    def __init__(self, registry: Nl2SqlDomainRegistry | None = None) -> None:
        from backend.app.domains.logistics.services.nl2sql.domain_registry import (
            Nl2SqlDomainRegistry,
            create_default_registry,
        )

        self._registry = registry or create_default_registry()

    def route(
        self,
        question: str | Any,  # str or LogisticsNl2SqlQueryRewriteResult
    ) -> Nl2SqlDomainRoute:
        """根据问题文本识别域并返回路由结果。

        参数：
            question: 用户问题原文或 LogisticsNl2SqlQueryRewriteResult 对象。

        返回：
            Nl2SqlDomainRoute 路由结果。
        """
        # 兼容 LogisticsNl2SqlQueryRewriteResult 或其他含 normalized_question 的对象
        text = question.normalized_question if hasattr(question, "normalized_question") else str(question or "")

        identified = self._registry.identify(text)
        if identified is not None:
            domain, _priority = identified
            return Nl2SqlDomainRoute(
                should_process=True,
                domain=domain,
                source_system="middle_db",
                mode="shadow",
                reason_code=f"domain_identified::{domain}",
            )

        # 未识别出任何已注册域：默认不处理
        return Nl2SqlDomainRoute(
            should_process=False,
            domain="unknown",
            source_system="middle_db",
            reason_code="no_domain_identified",
        )


__all__ = [
    "Nl2SqlDomainRoute",
    "Nl2SqlDomainRouter",
]
