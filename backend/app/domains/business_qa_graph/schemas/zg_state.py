"""
掌柜问数对齐版 Graph State 扩展。

在现有 BusinessQaGraphState 基础上增加掌柜问数 12 步工作流所需的字段：
keywords、retrieved_columns/metrics/values、table_infos、metric_infos、
date_info、db_info、sql、error 等。

参考掌柜问数 DataAgentState（data-agent/app/agent/state.py）。
"""

from __future__ import annotations

from typing import Any, TypedDict

from backend.app.domains.business_qa_graph.schemas.state import (
    BusinessQaGraphState,
    build_business_qa_initial_state,
)
from backend.app.domains.business_qa_graph.schemas.request import BusinessQaGraphRequest

# 掌柜问数 Graph 版本标识
ZG_BUSINESS_QA_GRAPH_VERSION = "zg_business_qa_graph.v1"


def build_zg_initial_state(request: BusinessQaGraphRequest) -> dict[str, Any]:
    """构建掌柜对齐版 Graph 初始 state。

    在现有 BusinessQaGraphState 基础上增加掌柜问数特有字段的初始值。

    参数：
        request: 已通过入口校验的 Graph 请求。
    返回：
        可直接传入 compiled graph.invoke 的初始 state 字典。
    """
    base = build_business_qa_initial_state(request)
    base.update({
        "graph_version": ZG_BUSINESS_QA_GRAPH_VERSION,
        # 掌柜问数特有字段
        "keywords": [],
        "retrieved_columns": [],
        "retrieved_values": [],
        "retrieved_metrics": [],
        "table_infos": [],
        "metric_infos": [],
        "date_info": {},
        "db_info": {},
        "sql": "",
        "error": None,
    })
    return base


# 以下定义掌柜问数对齐版 State 中的扩展类型，用于类型提示

class ZgRetrievedColumn(TypedDict, total=False):
    """召回的字段信息（掌柜问数 ColumnInfo 对齐）。
    
    参数：
        catalog_id: Milvus document catalog_id，如 dimension:base_name。
        name: 字段名。
        type: 字段类型，如 varchar、decimal。
        role: 字段角色，如 dimension、metric。
        examples: 取值示例列表。
        description: 字段业务说明。
        alias: 同义词列表。
        source_table: 所属表名。
    """
    catalog_id: str
    name: str
    type: str
    role: str
    examples: list[str]
    description: str
    alias: list[str]
    source_table: str


class ZgRetrievedMetric(TypedDict, total=False):
    """召回的指标信息（掌柜问数 MetricInfo 对齐）。
    
    参数：
        catalog_id: Milvus document catalog_id，如 metric:shipment_mw。
        name: 指标名称。
        description: 指标业务说明。
        relevant_columns: 相关字段列表。
        alias: 同义词列表。
        unit: 单位。
    """
    catalog_id: str
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]
    unit: str


class ZgRetrievedValue(TypedDict, total=False):
    """召回的维度取值信息（掌柜问数 ValueInfo 对齐）。
    
    参数：
        value_id: 唯一标识。
        column_id: 所属字段 catalog_id。
        column_name: 所属字段名。
        value: 维度取值，如 合肥。
        table_name: 所属表名。
    """
    value_id: str
    column_id: str
    column_name: str
    value: str
    table_name: str


class ZgTableInfo(TypedDict, total=False):
    """过滤后的表信息（掌柜问数 TableInfoState 对齐）。
    
    参数：
        name: 表名。
        role: 表角色，如 fact、dim。
        description: 表业务说明。
        columns: 表下字段列表。
    """
    name: str
    role: str
    description: str
    columns: list[dict[str, Any]]


class ZgMetricInfo(TypedDict, total=False):
    """过滤后的指标信息（掌柜问数 MetricInfoState 对齐）。
    
    参数：
        name: 指标名称。
        description: 指标说明。
        relevant_columns: 相关字段。
        alias: 同义词。
    """
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]
