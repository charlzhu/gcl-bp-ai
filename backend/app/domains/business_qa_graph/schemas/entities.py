"""掌柜问数召回实体模型。

本文件只定义召回节点之间传递的强类型实体，不承载数据库访问、
向量检索或业务计算逻辑。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _RecallEntityBase(BaseModel):
    """召回实体基类，提供旧 dict 读取方式的兼容接口。

    业务逻辑：
        召回节点内部使用 Pydantic 模型获得字段约束；旧节点仍可能
        使用 ``item.get(...)`` 读取字段，因此这里保留轻量兼容能力。
    """

    model_config = ConfigDict(populate_by_name=True)

    def get(self, key: str, default: Any = None) -> Any:
        """按 dict 风格读取字段值。

        参数：
            key: 字段名；ColumnInfo 兼容历史 ``type`` 键。
            default: 字段不存在或值为 None 时返回的默认值。
        返回：
            字段值或默认值。
        """
        if key == "type" and hasattr(self, "data_type"):
            value = getattr(self, "data_type", None)
        else:
            value = getattr(self, key, None)
        return default if value is None else value


class ColumnInfo(_RecallEntityBase):
    """字段召回实体。

    参数：
        catalog_id: 语义目录中的字段唯一标识。
        name: 字段名。
        data_type: 字段数据类型。
        role: 字段角色，例如 dimension、metric。
        examples: 字段示例值。
        description: 字段业务说明。
        source_table: 字段来源表。
        alias: 字段别名或同义词。
    """

    catalog_id: str = ""
    name: str = ""
    data_type: str = Field(default="varchar", validation_alias="type")
    role: str = "dimension"
    examples: list[str] = Field(default_factory=list)
    description: str = ""
    source_table: str = ""
    alias: list[str] = Field(default_factory=list)

    def to_legacy_dict(self) -> dict[str, Any]:
        """输出旧节点兼容的 dict 结构。

        返回：
            包含历史 ``type`` 键的字段信息字典。
        """
        payload = self.model_dump(mode="json")
        payload["type"] = payload.pop("data_type", "varchar")
        return payload


class MetricInfo(_RecallEntityBase):
    """指标召回实体。

    参数：
        catalog_id: 语义目录中的指标唯一标识。
        name: 指标名称。
        description: 指标业务说明。
        relevant_columns: 指标相关字段 catalog_id 列表。
        alias: 指标别名或同义词。
        unit: 指标单位。
    """

    catalog_id: str = ""
    name: str = ""
    description: str = ""
    relevant_columns: list[str] = Field(default_factory=list)
    alias: list[str] = Field(default_factory=list)
    unit: str = ""


class ValueInfo(_RecallEntityBase):
    """维度值召回实体。

    参数：
        value_id: 维度值唯一标识。
        value: 维度取值。
        column_id: 所属字段 catalog_id。
        column_name: 所属字段名。
        table_name: 所属表名。
        match_score: 匹配分数；SQL 精确/LIKE 兜底默认 1.0，模糊匹配保留 rapidfuzz 分数。
    """

    value_id: str = ""
    value: str = ""
    column_id: str = ""
    column_name: str = ""
    table_name: str = ""
    match_score: float = 0.0

