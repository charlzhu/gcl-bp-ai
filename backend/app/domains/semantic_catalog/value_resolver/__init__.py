"""
统一业务值解析器（Value Resolver）模块。

业务定位：
    本模块提供各业务域的实体值解析器实现，复用现有 MySQL 中间库
    和 Milvus 向量库做真实值解析。不同业务域（物流、计划 BOM）的
    解析逻辑各自封装。

模块组成：
    - base: 抽象基类 BusinessValueResolver
    - logistics_resolver: 物流域实体解析器（承运商、客户、区域等）
    - plan_bom_resolver: 计划 BOM 域实体解析器（订单、文件名等）

约束：
    - 不引入 ES。
    - 解析结果不暴露 SQL/表名/字段名。
    - 误匹配时返回多候选而非硬路由。
"""
from backend.app.domains.semantic_catalog.value_resolver.base import BusinessValueResolver

__all__ = [
    "BusinessValueResolver",
]
