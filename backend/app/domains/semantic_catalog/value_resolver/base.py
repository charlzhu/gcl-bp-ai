"""
统一业务值解析器抽象基类。

业务逻辑：
    本模块定义所有业务域值解析器的统一抽象接口。
    每个业务域子类只需继承 BusinessValueResolver 并实现
    resolve() 和 candidates() 两个抽象方法。

    设计原则：
        1. 基类不耦合具体数据源（MySQL/Milvus/ES）。
        2. 返回结构统一为包含 entity_type/value/label 的 dict。
        3. resolve_multi 提供默认批量实现，子类可覆盖。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class BusinessValueResolver(ABC):
    """统一业务值解析器抽象基类。

    业务逻辑：
        提供跨业务域的实体值解析能力。每个业务域子类
        （如物流、计划 BOM）自行实现数据源查询逻辑。

    抽象方法：
        resolve(entity_type, user_input) → list[dict]:
            根据用户输入解析匹配的实体值候选列表。
            返回的每个 dict 包含 entity_type、value、label。

        candidates(entity_type, limit) → list[dict]:
            获取指定实体类型下所有可能的值候选（不限制用户输入）。

    默认实现：
        resolve_multi(queries) → list[dict]:
            对每个 (entity_type, user_input) 调用 resolve 并汇总。
    """

    # 子类可选覆盖的 domain 标识
    domain: str = ""

    @abstractmethod
    def resolve(self, entity_type: str, user_input: str) -> list[dict]:
        """按用户输入解析实体值候选。

        参数：
            entity_type: 实体类型，如 carrier、customer、order_identity。
            user_input: 用户输入的实体名或关键词。

        返回：
            候选实体值列表，每项 dict 包含 entity_type、value、label。
            匹配不到时返回空列表；模糊匹配置信度不够时返回多个候选。
        """
        ...

    @abstractmethod
    def candidates(self, entity_type: str, limit: int = 20) -> list[dict]:
        """获取指定实体类型的候选值列表（不限定用户输入）。

        参数：
            entity_type: 实体类型。
            limit: 最大返回数量，防止数据量过大。

        返回：
            候选值列表，每项 dict 包含 entity_type、value、label。
        """
        ...

    def resolve_multi(self, queries: list[tuple[str, str]]) -> list[dict]:
        """批量解析多个实体查询。

        参数：
            queries: [(entity_type, user_input), ...] 查询对列表。

        返回：
            解析结果列表，每个元素是 resolve 的单次结果展平。

        业务逻辑：
            默认实现按顺序调用 resolve，子类可覆盖为并发或批量查询。
        """
        results: list[dict] = []
        for entity_type, user_input in queries:
            results.extend(self.resolve(entity_type, user_input))
        return results


__all__ = ["BusinessValueResolver"]
