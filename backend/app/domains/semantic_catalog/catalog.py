"""
统一语义资产注册表（BusinessSemanticCatalog）。

业务逻辑：
    提供按业务域（domain）和 capability 查询、注册统一语义资产的能力。
    注册表是 NL2SQL/QueryPlanningV2 的辅助能力——它保存"哪些指标/维度/实体可用"，
    但不替代现有领域 catalog 的 SQLPlan 校验、表白名单、Join 规则等内部实现。

使用方式：
    catalog = BusinessSemanticCatalog()
    catalog.register_metric(SemanticMetric(metric_id="shipment_mw", ...))
    found = catalog.get_metric("logistics", "shipment_mw")
"""

from __future__ import annotations

from collections import OrderedDict

from backend.app.domains.semantic_catalog.schema import (
    SemanticMetric,
    SemanticDimension,
    SemanticEntity,
    SemanticCapability,
)


class BusinessSemanticCatalog:
    """统一语义资产注册表。

    支持按 domain 和 ID 查询已注册的指标、维度和实体。
    注册表本身无状态依赖——所有资产通过 register_* 方法注入，
    也可以从 YAML 文件或现有领域 catalog 桥接填充。

    参数：
        无（初始化为空注册表）。

    返回：
        可注册、查询的统一语义资产容器。
    """

    def __init__(self) -> None:
        """初始化空注册表。

        业务逻辑：
            使用 OrderedDict 保证注册顺序可预测，方便测试和调试。
            内部按 domain 组织数据：_metrics[domain][metric_id] = SemanticMetric。
        """
        # 指标注册表：_metrics[domain] = OrderedDict[metric_id → SemanticMetric]
        self._metrics: dict[str, OrderedDict[str, SemanticMetric]] = {}
        # 维度注册表：_dimensions[domain] = OrderedDict[dimension_id → SemanticDimension]
        self._dimensions: dict[str, OrderedDict[str, SemanticDimension]] = {}
        # 实体注册表：_entities[domain] = OrderedDict[entity_id → SemanticEntity]
        self._entities: dict[str, OrderedDict[str, SemanticEntity]] = {}
        # 能力注册表：_capabilities[domain] = OrderedDict[capability_id → SemanticCapability]
        self._capabilities: dict[str, OrderedDict[str, SemanticCapability]] = {}

    # ── 指标操作 ──

    def register_metric(self, metric: SemanticMetric) -> None:
        """注册一个统一指标。

        参数：
            metric: 统一语义指标对象。

        业务逻辑：
            同一 domain + metric_id 重复注册时会覆盖旧值。
        """
        domain = metric.domain
        if domain not in self._metrics:
            self._metrics[domain] = OrderedDict()
        self._metrics[domain][metric.metric_id] = metric

    def get_metrics(self, domain: str) -> list[SemanticMetric]:
        """获取指定域的全部已注册指标。

        参数：
            domain: 业务域。

        返回：
            指标列表（按注册顺序排列）。
        """
        return list(self._metrics.get(domain, {}).values())

    def get_metric(self, domain: str, metric_id: str) -> SemanticMetric | None:
        """按域和 ID 获取单个指标。

        参数：
            domain: 业务域。
            metric_id: 指标 ID。

        返回：
            匹配的指标；不存在则返回 None。
        """
        return self._metrics.get(domain, {}).get(metric_id)

    def resolve_metric_alias(self, domain: str, alias: str) -> SemanticMetric | None:
        """按用户口语同义词解析受控指标。

        参数：
            domain: 业务域。
            alias: 用户输入的同义词或指标名称。

        返回：
            匹配指标；不匹配则返回 None。

        业务逻辑：
            归一化匹配 metric_id、display_name 和 aliases。
        """
        normalized = self._normalize_text(alias)
        for metric in self.get_metrics(domain):
            candidates = [metric.metric_id, metric.display_name, *metric.aliases]
            for candidate in candidates:
                if normalized == self._normalize_text(candidate):
                    return metric
        return None

    # ── 维度操作 ──

    def register_dimension(self, dimension: SemanticDimension) -> None:
        """注册一个统一维度。

        参数：
            dimension: 统一语义维度对象。
        """
        domain = dimension.domain
        if domain not in self._dimensions:
            self._dimensions[domain] = OrderedDict()
        self._dimensions[domain][dimension.dimension_id] = dimension

    def get_dimensions(self, domain: str) -> list[SemanticDimension]:
        """获取指定域的全部已注册维度。

        参数：
            domain: 业务域。

        返回：
            维度列表（按注册顺序排列）。
        """
        return list(self._dimensions.get(domain, {}).values())

    def get_dimension(self, domain: str, dimension_id: str) -> SemanticDimension | None:
        """按域和 ID 获取单个维度。

        参数：
            domain: 业务域。
            dimension_id: 维度 ID。

        返回：
            匹配的维度；不存在则返回 None。
        """
        return self._dimensions.get(domain, {}).get(dimension_id)

    # ── 实体操作 ──

    def register_entity(self, entity: SemanticEntity) -> None:
        """注册一个统一实体。

        参数：
            entity: 统一语义实体对象。
        """
        domain = entity.domain
        if domain not in self._entities:
            self._entities[domain] = OrderedDict()
        self._entities[domain][entity.entity_id] = entity

    def get_entities(self, domain: str, entity_type: str | None = None) -> list[SemanticEntity]:
        """获取指定域的已注册实体，可按类型过滤。

        参数：
            domain: 业务域。
            entity_type: 可选实体类型过滤。

        返回：
            实体列表。
        """
        entities = list(self._entities.get(domain, {}).values())
        if entity_type is not None:
            entities = [e for e in entities if e.entity_type == entity_type]
        return entities

    # ── 能力操作 ──

    def register_capability(self, capability: SemanticCapability) -> None:
        """注册一个统一能力。

        参数：
            capability: 统一语义能力对象。

        业务逻辑：
            同一 domain + capability_id 重复注册时会覆盖旧值。
            能力类型（query_key / intent / domain_capability）区分不同来源的能力。
        """
        domain = capability.domain
        if domain not in self._capabilities:
            self._capabilities[domain] = OrderedDict()
        self._capabilities[domain][capability.capability_id] = capability

    def get_capabilities(
        self, domain: str, capability_type: str | None = None
    ) -> list[SemanticCapability]:
        """获取指定域的全部已注册能力，可按类型过滤。

        参数：
            domain: 业务域。
            capability_type: 可选能力类型过滤（query_key / intent / domain_capability）。

        返回：
            能力列表（按注册顺序排列）。
        """
        caps = list(self._capabilities.get(domain, {}).values())
        if capability_type is not None:
            caps = [c for c in caps if c.capability_type == capability_type]
        return caps

    def get_capability(self, domain: str, capability_id: str) -> SemanticCapability | None:
        """按域和 ID 获取单个能力。

        参数：
            domain: 业务域。
            capability_id: 能力 ID。

        返回：
            匹配的能力；不存在则返回 None。
        """
        return self._capabilities.get(domain, {}).get(capability_id)

    # ── 域查询 ──

    def domains(self) -> list[str]:
        """返回所有已注册域名的有序列表。

        返回：
            域名列表（按首次注册顺序排列）。
        """
        seen: dict[str, bool] = {}
        ordered: list[str] = []
        for source in (self._metrics, self._dimensions, self._entities, self._capabilities):
            for domain in source:
                if domain not in seen:
                    seen[domain] = True
                    ordered.append(domain)
        return ordered

    # ── 辅助方法 ──

    @staticmethod
    def _normalize_text(value: str) -> str:
        """统一去空白并小写，避免中文/英文同义词匹配受格式影响。

        参数：
            value: 待归一化的文本。

        返回：
            归一化后的文本。
        """
        return "".join(str(value).strip().lower().split())


__all__ = ["BusinessSemanticCatalog"]
