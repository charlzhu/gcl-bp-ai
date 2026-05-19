from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field


DEFAULT_CATALOG_DIR = Path(__file__).resolve().parents[2] / "config" / "nl2sql_catalog"
LOGISTICS_NL2SQL_ALLOWED_READ_TABLES = (
    "dws_logistics_detail_union",
    "dws_logistics_monthly_metric",
    "dwd_logistics_hist_shipment_detail",
    "dwd_logistics_ship_task",
    "dwd_logistics_assign_task",
    "dwd_logistics_assign_detail",
    "dwd_logistics_ship_product",
    "dm_logistics_company_month_rank",
)


class LogisticsCatalogColumn(BaseModel):
    """Semantic Catalog 中的字段声明。

    参数：
        name: 数据库字段名。
        data_type: 字段类型，来自中间库或人工 catalog。
        business_name: 面向业务的字段名称。
        semantic_role: 字段在 NL2SQL 中的语义角色，例如 metric、dimension、time、trace。
        nullable: 字段是否允许为空。
    返回：
        Pydantic 字段声明对象。
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    data_type: str = "unknown"
    business_name: str | None = None
    semantic_role: str | None = None
    nullable: bool = True


class LogisticsCatalogTable(BaseModel):
    """Semantic Catalog 中的白名单表声明。

    参数：
        table_name: 智能助手中间库表名。
        display_name: 业务展示名称。
        domain: 业务域，M1 只允许 logistics。
        source_system: 数据来源标记，M1 必须是 middle_db。
        allowed_read: 是否允许后续 NL2SQL SELECT/EXPLAIN 使用。
        grain: 表粒度说明。
        columns: 表字段白名单。
    返回：
        可供 catalog loader 与 SQLPlan validator 使用的表声明。
    """

    model_config = ConfigDict(extra="forbid")

    table_name: str
    display_name: str
    domain: str = "logistics"
    source_system: str = "middle_db"
    allowed_read: bool = True
    grain: str | None = None
    columns: list[LogisticsCatalogColumn] = Field(default_factory=list)


class LogisticsCatalogMetric(BaseModel):
    """Semantic Catalog 中的指标声明。

    参数：
        metric_id: 受控指标 ID。
        display_name: 业务展示名称。
        aliases: 用户可能使用的同义词。
        sql_expression: 后续 SQLPlan/SQL 渲染使用的确定性表达式。
        unit: 业务单位。
        aggregation: 聚合方式。
        table: 默认来源表。
        source_columns: 表达式依赖字段。
        sort_expression: 排名类指标使用的排序表达式。
        business_note: 业务口径说明。
    返回：
        指标 catalog 条目。
    """

    model_config = ConfigDict(extra="forbid")

    metric_id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    sql_expression: str
    unit: str | None = None
    aggregation: str | None = None
    table: str | None = None
    source_columns: list[str] = Field(default_factory=list)
    sort_expression: str | None = None
    business_note: str | None = None


class LogisticsCatalogDimension(BaseModel):
    """Semantic Catalog 中的维度声明。"""

    model_config = ConfigDict(extra="forbid")

    dimension_id: str
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    column: str
    table: str | None = None
    business_note: str | None = None


class LogisticsCatalogJoin(BaseModel):
    """Semantic Catalog 中的 Join 声明。"""

    model_config = ConfigDict(extra="forbid")

    join_id: str
    left_table: str
    right_table: str
    join_type: str = "left"
    on: list[str] = Field(default_factory=list)
    business_note: str | None = None


class LogisticsCatalogRule(BaseModel):
    """Semantic Catalog 中的业务规则声明。

    参数：
        rule_id: 规则 ID。
        display_name: 业务展示名称。
        rule_type: 规则类型，例如 time_default、unsupported_metric。
        aliases: 可触发该规则的自然语言同义词。
        action: 后续规划动作，例如 reject、default_years、allow。
        value: 规则值，例如默认年份列表。
        relax_filters: 空结果策略是否允许放宽过滤条件。
        business_message: 面向业务的提示文案。
    返回：
        业务规则 catalog 条目。
    """

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    display_name: str
    rule_type: str
    aliases: list[str] = Field(default_factory=list)
    action: str
    value: Any | None = None
    relax_filters: bool | None = None
    business_message: str | None = None


class LogisticsCatalogExample(BaseModel):
    """Semantic Catalog 中的自然语言到 SQLPlan 形状示例。

    业务逻辑：
        examples 只给 M9 LLM SQLPlan Generator 提供受控结构参考；不得保存 raw SQL、
        SQL 片段、连接信息或执行结果。后续 validator 仍只信 catalog_id 并回查 canonical catalog。
    """

    model_config = ConfigDict(extra="forbid")

    example_id: str
    display_name: str
    domain: str = "logistics"
    question: str
    query_type: str
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    catalog_refs: list[str] = Field(default_factory=list)
    notes: str | None = None
    sql: str | None = None
    raw_sql: str | None = None


class LogisticsSemanticCatalog(BaseModel):
    """物流 NL2SQL Semantic Catalog 聚合对象。"""

    model_config = ConfigDict(extra="forbid")

    catalog_version: str
    domain: str = "logistics"
    tables: list[LogisticsCatalogTable] = Field(default_factory=list)
    metrics: list[LogisticsCatalogMetric] = Field(default_factory=list)
    dimensions: list[LogisticsCatalogDimension] = Field(default_factory=list)
    joins: list[LogisticsCatalogJoin] = Field(default_factory=list)
    rules: list[LogisticsCatalogRule] = Field(default_factory=list)
    examples: list[LogisticsCatalogExample] = Field(default_factory=list)

    def get_metric(self, metric_id: str) -> LogisticsCatalogMetric:
        """按指标 ID 获取指标；不存在则抛出 KeyError。"""

        for metric in self.metrics:
            if metric.metric_id == metric_id:
                return metric
        raise KeyError(f"metric_not_found::{metric_id}")

    def resolve_metric_alias(self, alias: str) -> LogisticsCatalogMetric:
        """按用户口语同义词解析受控指标。"""

        normalized = self._normalize_text(alias)
        for metric in self.metrics:
            candidates = [metric.metric_id, metric.display_name, *metric.aliases]
            if normalized in {self._normalize_text(candidate) for candidate in candidates}:
                return metric
        raise KeyError(f"metric_alias_not_found::{alias}")

    def get_rule(self, rule_id: str) -> LogisticsCatalogRule:
        """按规则 ID 获取业务规则；不存在则抛出 KeyError。"""

        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        raise KeyError(f"rule_not_found::{rule_id}")

    def resolve_rule_alias(self, alias: str) -> LogisticsCatalogRule:
        """按用户口语同义词解析业务规则。"""

        normalized = self._normalize_text(alias)
        for rule in self.rules:
            candidates = [rule.rule_id, rule.display_name, *rule.aliases]
            if normalized in {self._normalize_text(candidate) for candidate in candidates}:
                return rule
        raise KeyError(f"rule_alias_not_found::{alias}")

    def allowed_tables(self) -> list[LogisticsCatalogTable]:
        """返回允许后续 NL2SQL 读取的表。"""

        return [table for table in self.tables if table.allowed_read]

    def allowed_table_names(self) -> set[str]:
        """返回允许后续 SQLPlan 引用的表名集合。"""

        return {table.table_name for table in self.allowed_tables()}

    @staticmethod
    def _normalize_text(value: str) -> str:
        """统一去空白并小写，避免中文/英文同义词匹配受格式影响。"""

        return "".join(str(value).strip().lower().split())


class LogisticsSemanticCatalogLoader:
    """物流 NL2SQL Semantic Catalog YAML 加载器。

    业务逻辑：
        1. 只从仓库内 `config/nl2sql_catalog` 读取人工审计后的 catalog；
        2. M1 不连接生产库、不读取 SAP MID、不生成 SQL；
        3. 返回强 schema 对象，后续 SQLPlan validator 可直接复用。
    """

    FILE_NAMES = ("tables.yaml", "metrics.yaml", "dimensions.yaml", "joins.yaml", "rules.yaml", "examples.yaml")

    def __init__(self, catalog_dir: str | Path | None = None) -> None:
        """初始化加载器。

        参数：
            catalog_dir: 可选 catalog 目录，测试可传临时目录；默认使用物流域配置目录。
        返回：
            无。
        """

        self.catalog_dir = Path(catalog_dir) if catalog_dir else DEFAULT_CATALOG_DIR

    def load(self) -> LogisticsSemanticCatalog:
        """加载并合并 M1 Semantic Catalog。"""

        raw_files = {name: self._read_yaml(name) for name in self.FILE_NAMES}
        catalog_version = (
            self._first_non_empty(raw_files, "catalog_version") or "logistics_nl2sql_catalog.v1"
        )
        domain = self._first_non_empty(raw_files, "domain") or "logistics"
        payload = {
            "catalog_version": catalog_version,
            "domain": domain,
            "tables": raw_files["tables.yaml"].get("tables", []),
            "metrics": raw_files["metrics.yaml"].get("metrics", []),
            "dimensions": raw_files["dimensions.yaml"].get("dimensions", []),
            "joins": raw_files["joins.yaml"].get("joins", []),
            "rules": raw_files["rules.yaml"].get("rules", []),
            "examples": raw_files["examples.yaml"].get("examples", []),
        }
        catalog = LogisticsSemanticCatalog.model_validate(payload)
        self._validate_catalog(catalog)
        return catalog

    def _validate_catalog(self, catalog: LogisticsSemanticCatalog) -> None:
        """对 catalog 做 fail-closed 安全校验。

        参数：
            catalog: 已通过 Pydantic schema 校验的 catalog。
        返回：
            无；若发现非物流域、非中间库或非白名单表，直接抛出 ValueError。
        业务逻辑：
            M1 只允许后续 NL2SQL 读取智能助手中间库物流业务表；SAP MID、ODS 源表、
            查询日志等审计表均不得进入 `allowed_read` 表集合。
        """

        if catalog.domain != "logistics":
            raise ValueError(f"catalog_domain_invalid::{catalog.domain}")
        allowed = set(LOGISTICS_NL2SQL_ALLOWED_READ_TABLES)
        seen_tables: set[str] = set()
        for table in catalog.tables:
            if table.table_name in seen_tables:
                raise ValueError(f"catalog_table_duplicate::{table.table_name}")
            seen_tables.add(table.table_name)
            if table.table_name not in allowed:
                raise ValueError(f"catalog_table_not_allowed::{table.table_name}")
            if table.source_system != "middle_db":
                raise ValueError(
                    f"catalog_table_source_system_invalid::{table.table_name}::{table.source_system}"
                )
            if table.domain != "logistics":
                raise ValueError(f"catalog_table_domain_invalid::{table.table_name}::{table.domain}")

        allowed_names = catalog.allowed_table_names()
        column_index = self._allowed_column_index(catalog)
        for join in catalog.joins:
            if join.left_table not in allowed_names:
                raise ValueError(f"catalog_join_table_not_allowed::{join.join_id}::{join.left_table}")
            if join.right_table not in allowed_names:
                raise ValueError(f"catalog_join_table_not_allowed::{join.join_id}::{join.right_table}")
            if join.left_table == join.right_table:
                raise ValueError(f"catalog_join_same_table_not_allowed::{join.join_id}::{join.left_table}")
            self._validate_join_columns(join, column_index)
        for metric in catalog.metrics:
            if metric.table and metric.table not in allowed_names:
                raise ValueError(f"catalog_metric_table_not_allowed::{metric.metric_id}::{metric.table}")
            self._validate_metric_columns(metric, column_index)
        for dimension in catalog.dimensions:
            if dimension.table and dimension.table not in allowed_names:
                raise ValueError(f"catalog_dimension_table_not_allowed::{dimension.dimension_id}::{dimension.table}")
            self._validate_dimension_column(dimension, column_index)
        allowed_catalog_refs = self._allowed_catalog_ref_ids(catalog)
        for example in catalog.examples:
            self._validate_example(example, allowed_catalog_refs)

    @staticmethod
    def _allowed_column_index(catalog: LogisticsSemanticCatalog) -> dict[str, set[str]]:
        """构造可读表字段索引。

        参数：
            catalog: 已通过表级白名单校验的 catalog。
        返回：
            表名到字段名集合的映射。
        业务逻辑：
            后续 SQL 生成只能引用人工审计过的字段；字段未声明时必须 fail-closed。
        """

        return {table.table_name: {column.name for column in table.columns} for table in catalog.allowed_tables()}

    @staticmethod
    def _validate_metric_columns(metric: LogisticsCatalogMetric, column_index: dict[str, set[str]]) -> None:
        """校验指标依赖字段必须属于指标来源表。

        参数：
            metric: 指标 catalog 条目。
            column_index: 可读表字段索引。
        返回：
            无；字段缺失时抛出 ValueError。
        """

        if metric.source_columns and not metric.table:
            raise ValueError(f"catalog_metric_table_required::{metric.metric_id}")
        if not metric.table:
            return
        available_columns = column_index.get(metric.table, set())
        for column in metric.source_columns:
            if column not in available_columns:
                raise ValueError(f"catalog_metric_column_not_allowed::{metric.metric_id}::{metric.table}.{column}")

    @staticmethod
    def _validate_dimension_column(dimension: LogisticsCatalogDimension, column_index: dict[str, set[str]]) -> None:
        """校验维度字段必须属于维度来源表。

        参数：
            dimension: 维度 catalog 条目。
            column_index: 可读表字段索引。
        返回：
            无；字段缺失时抛出 ValueError。
        """

        if not dimension.table:
            raise ValueError(f"catalog_dimension_table_required::{dimension.dimension_id}")
        available_columns = column_index.get(dimension.table, set())
        if dimension.column not in available_columns:
            raise ValueError(
                f"catalog_dimension_column_not_allowed::{dimension.dimension_id}::{dimension.table}.{dimension.column}"
            )

    @classmethod
    def _validate_join_columns(cls, join: LogisticsCatalogJoin, column_index: dict[str, set[str]]) -> None:
        """校验 Join on 表达式只能是单个受控等值字段引用。

        参数：
            join: Join catalog 条目。
            column_index: 可读表字段索引。
        返回：
            无；表达式夹带 SQL 片段、未引用两侧表或字段不存在时抛出 ValueError。
        业务逻辑：
            M1 只支持人工审计的 `表.字段 = 表.字段` 形态；任何 AND/OR、函数、子查询、
            常量条件或第三张表都在 catalog 加载期 fail-closed，避免 SQLPlan 渲染阶段被污染。
        """

        join_tables = {join.left_table, join.right_table}
        if len(join.on) != 1:
            raise ValueError(f"catalog_join_on_expression_invalid::{join.join_id}::{join.on}")
        for expression in join.on:
            refs = cls._parse_join_on_refs(expression, join_id=join.join_id)
            referenced_tables = {table_name for table_name, _ in refs}
            for table_name, column_name in refs:
                if table_name not in join_tables:
                    raise ValueError(f"catalog_join_on_table_not_in_join::{join.join_id}::{table_name}")
                if column_name not in column_index.get(table_name, set()):
                    raise ValueError(f"catalog_join_column_not_allowed::{join.join_id}::{table_name}.{column_name}")
            if referenced_tables != join_tables:
                raise ValueError(f"catalog_join_on_missing_join_side::{join.join_id}::{expression}")

    @staticmethod
    def _parse_join_on_refs(expression: str, *, join_id: str) -> list[tuple[str, str]]:
        """解析严格 join.on 表达式并返回左右两侧字段引用。

        参数：
            expression: catalog 中配置的 join.on 单条表达式。
            join_id: 当前 Join ID，用于生成确定性错误码。
        返回：
            左右两侧 `(table_name, column_name)` 引用列表。
        业务逻辑：
            必须完整匹配 `table.column = table.column`；用 fullmatch 阻断 `OR 1=1`、函数、
            子查询等额外 SQL 片段，而不是只提取其中看起来合法的字段 token。
        """

        match = re.fullmatch(
            r"\s*([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
            r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\s*",
            expression,
        )
        if not match:
            raise ValueError(f"catalog_join_on_expression_invalid::{join_id}::{expression}")
        left_table, left_column, right_table, right_column = match.groups()
        return [(left_table, left_column), (right_table, right_column)]

    @staticmethod
    def _allowed_catalog_ref_ids(catalog: LogisticsSemanticCatalog) -> set[str]:
        """构造 examples 可引用的受控 catalog ID 集合。"""

        ids: set[str] = set()
        ids.update(f"table:{table.table_name}" for table in catalog.allowed_tables())
        ids.update(f"metric:{metric.metric_id}" for metric in catalog.metrics)
        ids.update(f"dimension:{dimension.dimension_id}" for dimension in catalog.dimensions)
        ids.update(f"join:{join.join_id}" for join in catalog.joins)
        ids.update(f"rule:{rule.rule_id}" for rule in catalog.rules)
        return ids

    @staticmethod
    def _validate_example(example: LogisticsCatalogExample, allowed_catalog_refs: set[str]) -> None:
        """校验 examples 只描述受控 SQLPlan 形状，不携带 raw SQL。"""

        if example.domain != "logistics":
            raise ValueError(f"catalog_example_domain_invalid::{example.example_id}::{example.domain}")
        if example.sql is not None or example.raw_sql is not None:
            raise ValueError(f"catalog_example_sql_not_allowed::{example.example_id}")
        for ref in example.catalog_refs:
            if ref not in allowed_catalog_refs:
                raise ValueError(f"catalog_example_ref_not_allowed::{example.example_id}::{ref}")

    def _read_yaml(self, file_name: str) -> dict[str, Any]:
        """读取单个 YAML 文件，缺失文件按空配置处理。"""

        path = self.catalog_dir / file_name
        if not path.exists():
            return {}
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"catalog_yaml_must_be_mapping::{path}")
        return data

    @staticmethod
    def _first_non_empty(raw_files: dict[str, dict[str, Any]], key: str) -> Any | None:
        """从多个 YAML 顶层配置中读取第一个非空元数据值。"""

        for data in raw_files.values():
            if data.get(key):
                return data[key]
        return None


__all__ = [
    "DEFAULT_CATALOG_DIR",
    "LOGISTICS_NL2SQL_ALLOWED_READ_TABLES",
    "LogisticsCatalogColumn",
    "LogisticsCatalogDimension",
    "LogisticsCatalogJoin",
    "LogisticsCatalogMetric",
    "LogisticsCatalogExample",
    "LogisticsCatalogRule",
    "LogisticsCatalogTable",
    "LogisticsSemanticCatalog",
    "LogisticsSemanticCatalogLoader",
]
