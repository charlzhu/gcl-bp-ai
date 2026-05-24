from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, TypeVar

import yaml
from sqlalchemy.orm import Session

from backend.app.models.nqe_metadata import (
    NqeBusinessRule,
    NqeColumnInfo,
    NqeDataSource,
    NqeDimensionInfo,
    NqeDomain,
    NqeMetadataVersion,
    NqeMetricInfo,
    NqeQualityGate,
    NqeRetrievalChunk,
    NqeTableInfo,
)


# 中文注释：默认 catalog 根目录必须基于当前模块定位，避免服务进程 cwd 不是仓库根时物流自动召回失效。
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CATALOG_ROOT = PROJECT_ROOT / "backend/app/domains/logistics/config/nl2sql_catalog"
CATALOG_FILES = ("tables.yaml", "metrics.yaml", "dimensions.yaml", "rules.yaml")
SENSITIVE_REF_PATTERN = re.compile(
    "|".join(
        [
            "ho" + "st",
            "us" + "er",
            "pass" + "word",
            "pass" + "wd",
            "p" + "wd",
            "d" + "sn",
            "tok" + "en",
            "api[_ -]?" + "key",
            "sec" + "ret",
            "connection\\s*string",
        ]
    ),
    re.IGNORECASE,
)
ModelT = TypeVar("ModelT")


@dataclass
class NqeMetadataSyncBundle:
    """NQE 元数据同步的内存包。

    参数：
        domains: 业务域元数据列表。
        data_sources: 中间库数据源白名单列表。
        tables: 表资产列表。
        columns: 字段资产列表。
        metrics: 指标资产列表。
        dimensions: 维度资产列表。
        business_rules: 业务规则资产列表。
        retrieval_chunks: 召回文本块列表。
        metadata_versions: 元数据版本记录列表。
        quality_gates: 质量门禁记录列表。
        warnings: 构建过程中的非阻塞告警。
    返回：
        可 dry-run 输出，也可传入 upsert 函数落库的标准化 bundle。
    """

    domains: list[dict[str, Any]] = field(default_factory=list)
    data_sources: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    columns: list[dict[str, Any]] = field(default_factory=list)
    metrics: list[dict[str, Any]] = field(default_factory=list)
    dimensions: list[dict[str, Any]] = field(default_factory=list)
    business_rules: list[dict[str, Any]] = field(default_factory=list)
    retrieval_chunks: list[dict[str, Any]] = field(default_factory=list)
    metadata_versions: list[dict[str, Any]] = field(default_factory=list)
    quality_gates: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_summary(self) -> dict[str, Any]:
        """生成 dry-run 摘要。

        返回：
            包含资产数量、业务域、版本、门禁状态和告警列表的 JSON 友好字典。
        """

        counts = {
            "domains": len(self.domains),
            "data_sources": len(self.data_sources),
            "tables": len(self.tables),
            "columns": len(self.columns),
            "metrics": len(self.metrics),
            "dimensions": len(self.dimensions),
            "business_rules": len(self.business_rules),
            "retrieval_chunks": len(self.retrieval_chunks),
            "metadata_versions": len(self.metadata_versions),
            "quality_gates": len(self.quality_gates),
        }
        gate_statuses = {gate["gate_status"] for gate in self.quality_gates}
        quality_gate_status = "warn" if "warn" in gate_statuses else "passed"
        if "failed" in gate_statuses:
            quality_gate_status = "failed"
        return {
            "counts": counts,
            "domains": [domain["domain_code"] for domain in self.domains],
            "metadata_version": self.metadata_versions[0]["metadata_version"] if self.metadata_versions else None,
            "quality_gate_status": quality_gate_status,
            "warnings": list(self.warnings),
        }

    def to_dict(self) -> dict[str, Any]:
        """返回完整 bundle 字典，便于测试和本地排查。"""

        return asdict(self)


class NqeMetadataSyncBuilder:
    """从受控 catalog 构建 NQE 元数据 bundle。

    参数：
        catalog_root: 物流 NL2SQL catalog 根目录，默认读取仓库内受控目录。
        metadata_version: 本次生成的元数据版本号。
    业务逻辑：
        只读取 YAML/Python catalog 静态资产，不连接业务库，不读取 .env，不执行 SQL。
    """

    def __init__(
        self,
        catalog_root: str | Path = DEFAULT_CATALOG_ROOT,
        *,
        metadata_version: str = "nqe_catalog_v1",
        include_domains: Iterable[str] | None = None,
        domain_codes: Iterable[str] | None = None,
    ) -> None:
        self.catalog_root = Path(catalog_root)
        self.metadata_version = metadata_version
        # 中文注释：include_domains/domain_codes 只作为受控白名单过滤，不改变默认全域构建行为。
        self._include_domain_codes = self._normalize_domain_filters(include_domains, domain_codes)
        self._warnings: list[str] = []

    def build(self) -> NqeMetadataSyncBundle:
        """构建标准化 NQE 元数据包。

        返回：
            包含业务域、表字段、指标、维度、规则、召回块、版本和门禁的 bundle。
        """

        bundle = NqeMetadataSyncBundle()
        domains = self._discover_catalog_domains()
        if not domains:
            self._warnings.append(f"未发现可读取的 catalog 目录：{self._safe_ref(self.catalog_root)}")

        matched_domain_codes: set[str] = set()
        for domain_dir in domains:
            raw_files = self._load_domain_catalog(domain_dir)
            domain_code = self._resolve_domain_code(domain_dir, raw_files)
            if self._include_domain_codes is not None and domain_code not in self._include_domain_codes:
                # 中文注释：单域同步时跳过未显式允许的 catalog，不落无关域资产。
                continue
            matched_domain_codes.add(domain_code)
            source_ref = self._domain_source_ref(domain_dir)
            data_source_code = self._stable_code("ds", domain_code, "middle_db")

            bundle.domains.append(
                {
                    "code": self._stable_code("domain", domain_code),
                    "domain_code": domain_code,
                    "name": domain_code,
                    "display_name": self._display_domain_name(domain_code),
                    "description": f"{domain_code} 受控 NL2SQL catalog 元数据",
                    "source_type": "catalog_yaml",
                    "source_ref": source_ref,
                    "version": self.metadata_version,
                    "status": "draft",
                    "is_active": 1,
                    "extra_json": self._json({"catalog_version": self._first_catalog_version(raw_files)}),
                }
            )
            bundle.data_sources.append(
                {
                    "code": data_source_code,
                    "domain_code": domain_code,
                    "name": f"{domain_code} middle_db",
                    "description": "智能助手中间库逻辑数据源，不保存真实连接信息",
                    "source_type": "catalog_yaml",
                    "source_ref": source_ref,
                    "source_kind": "middle_db",
                    "logical_name": "middle_db",
                    "readonly_required": 1,
                    "connection_ref": "logical_middle_db",
                    "allow_explain": 1,
                    "timeout_ms": 30000,
                    "max_rows": 1000,
                    "version": self.metadata_version,
                    "status": "draft",
                    "is_active": 1,
                    "extra_json": self._json({"domain_dir": source_ref}),
                }
            )
            self._append_tables(bundle, raw_files, domain_code, data_source_code, domain_dir)
            self._append_metrics(bundle, raw_files, domain_code, domain_dir)
            self._append_dimensions(bundle, raw_files, domain_code, domain_dir)
            self._append_rules(bundle, raw_files, domain_code, domain_dir)

        if self._include_domain_codes is not None:
            missing_domain_codes = sorted(self._include_domain_codes - matched_domain_codes)
            if missing_domain_codes:
                self._warnings.append(f"未匹配到 include_domains：{', '.join(missing_domain_codes)}")

        bundle.retrieval_chunks = self.build_retrieval_chunks(bundle)
        bundle.metadata_versions.append(self._metadata_version_record(bundle))
        bundle.warnings = list(self._warnings)
        bundle.quality_gates = self._quality_gates(bundle)
        return bundle

    def build_retrieval_chunks(self, bundle: NqeMetadataSyncBundle) -> list[dict[str, Any]]:
        """生成供后续向量索引用的召回 chunk。

        参数：
            bundle: 已构建的元数据资产包。
        返回：
            table/column/metric/dimension/rule 五类召回块列表。
        """

        chunks: list[dict[str, Any]] = []
        for table in bundle.tables:
            columns = [column for column in bundle.columns if column["table_code"] == table["code"]]
            column_summary = "、".join(column["business_name"] or column["name"] for column in columns[:12])
            text = (
                f"业务表：{table['business_name'] or table['name']}。"
                f"物理白名单表：{table['physical_table_name']}。"
                f"粒度：{table.get('grain') or '未声明'}。"
                f"字段摘要：{column_summary or '未声明'}。"
            )
            chunks.append(self._chunk("table", table["domain_code"], table["code"], table["name"], text, [table["name"], table["physical_table_name"]]))

        for column in bundle.columns:
            text = (
                f"字段：{column['business_name'] or column['name']}。"
                f"语义类型：{column.get('semantic_type') or '未声明'}。"
                f"可过滤：{self._yes_no(column.get('is_filterable'))}。"
                f"可分组：{self._yes_no(column.get('is_groupable'))}。"
                f"可聚合：{self._yes_no(column.get('is_aggregatable'))}。"
            )
            chunks.append(
                self._chunk(
                    "column",
                    column["domain_code"],
                    column["code"],
                    column["name"],
                    text,
                    [column["name"], column["column_code"], column.get("business_name")],
                )
            )

        for metric in bundle.metrics:
            extra = self._loads_json(metric.get("extra_json"))
            aliases = extra.get("aliases", [])
            text = (
                f"指标：{metric['business_name'] or metric['name']}。"
                f"同义词：{'、'.join(aliases[:10]) or '未声明'}。"
                f"公式/口径：{metric.get('formula_text') or metric.get('description') or '未声明'}。"
            )
            chunks.append(self._chunk("metric", metric["domain_code"], metric["code"], metric["name"], text, [metric["name"], metric["metric_code"], *aliases]))

        for dimension in bundle.dimensions:
            extra = self._loads_json(dimension.get("extra_json"))
            aliases = extra.get("aliases", [])
            examples = extra.get("field_value_examples", []) or extra.get("example_values", [])
            text = (
                f"维度：{dimension['business_name'] or dimension['name']}。"
                f"同义词：{'、'.join(aliases[:10]) or '未声明'}。"
                f"样例值：{'、'.join(str(item) for item in examples[:8]) or '未声明'}。"
            )
            chunks.append(
                self._chunk(
                    "dimension",
                    dimension["domain_code"],
                    dimension["code"],
                    dimension["name"],
                    text,
                    [dimension["name"], dimension["dimension_code"], *aliases],
                    aliases,
                )
            )

        for rule in bundle.business_rules:
            text = f"业务规则：{rule['title']}。正文摘要：{self._short_text(rule['rule_text'], 300)}"
            chunks.append(self._chunk("rule", rule["domain_code"], rule["code"], rule["name"], text, [rule["title"], rule["rule_code"]]))

        return chunks

    @classmethod
    def _normalize_domain_filters(cls, *groups: Iterable[str] | None) -> set[str] | None:
        """归一化调用方传入的业务域过滤白名单。

        参数：
            groups: include_domains/domain_codes 等可选业务域编码集合。
        返回：
            None 表示不过滤；set 表示只构建其中业务域。
        业务逻辑：
            中文注释：只接受非空业务域编码，统一走 slug 化，避免大小写或空格导致误同步。
        """

        filters: set[str] = set()
        for group in groups:
            if group is None:
                continue
            # 中文注释：兼容调用方误传单个字符串的情况，避免把 "logistics" 拆成字符过滤。
            items = (group,) if isinstance(group, str) else group
            for item in items:
                code = cls._slug(str(item))
                if code:
                    filters.add(code)
        return filters or None

    def _discover_catalog_domains(self) -> list[Path]:
        """发现 root、business_analysis、plan_bom 等 catalog 目录。"""

        if not self.catalog_root.exists():
            return []
        domains: list[Path] = []
        if any((self.catalog_root / name).exists() for name in CATALOG_FILES):
            domains.append(self.catalog_root)
        for child in sorted(path for path in self.catalog_root.iterdir() if path.is_dir()):
            if any((child / name).exists() for name in CATALOG_FILES):
                domains.append(child)
        return domains

    def _load_domain_catalog(self, domain_dir: Path) -> dict[str, dict[str, Any]]:
        """读取单个业务域目录中的 YAML 文件，缺失时记录 warn 并继续。"""

        raw_files: dict[str, dict[str, Any]] = {}
        for filename in CATALOG_FILES:
            path = domain_dir / filename
            ref = self._safe_ref(path)
            if not path.exists():
                self._warnings.append(f"catalog 文件缺失：{ref}")
                raw_files[filename] = {}
                continue
            try:
                raw_files[filename] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                self._warnings.append(f"catalog 文件解析失败：{ref}，原因：{exc.__class__.__name__}")
                raw_files[filename] = {}
        return raw_files

    def _append_tables(
        self,
        bundle: NqeMetadataSyncBundle,
        raw_files: dict[str, dict[str, Any]],
        domain_code: str,
        data_source_code: str,
        domain_dir: Path,
    ) -> None:
        """转换表和字段资产。"""

        tables = raw_files.get("tables.yaml", {}).get("tables", []) or []
        dimension_lookup = self._dimension_value_lookup(raw_files)
        if not tables:
            self._warnings.append(f"{domain_code} 缺少可同步表资产")
        for table in tables:
            table_name = str(table.get("table_name") or table.get("name") or "").strip()
            if not table_name:
                self._warnings.append(f"{domain_code} 存在缺少 table_name 的表资产，已跳过")
                continue
            table_code = self._stable_code("table", domain_code, table_name)
            table_role = self._resolve_table_role(table_name)
            source_ref = self._file_source_ref(domain_dir, "tables.yaml")
            columns = table.get("columns") or []
            bundle.tables.append(
                {
                    "code": table_code,
                    "domain_code": domain_code,
                    "data_source_code": data_source_code,
                    "name": table.get("display_name") or table_name,
                    "business_name": table.get("display_name") or table_name,
                    "description": table.get("description") or table.get("grain"),
                    "physical_table_name": table_name,
                    "table_role": table_role,
                    "grain": table.get("grain"),
                    "allow_select": 1 if table.get("allowed_read", True) else 0,
                    "allow_detail": 1 if table_role in {"ods", "dwd", "fact"} else 0,
                    "default_limit_rows": 100,
                    "max_limit_rows": 1000,
                    "sensitive_level": "normal",
                    "source_type": "catalog_yaml",
                    "source_ref": source_ref,
                    "version": self.metadata_version,
                    "status": "draft",
                    "is_active": 1,
                    "extra_json": self._json({k: v for k, v in table.items() if k != "columns"}),
                }
            )
            if not columns:
                self._warnings.append(f"{domain_code}.{table_name} 缺少字段资产")
            for column in columns:
                column_name = str(column.get("name") or "").strip()
                if not column_name:
                    self._warnings.append(f"{domain_code}.{table_name} 存在缺少 name 的字段资产，已跳过")
                    continue
                semantic_type = self._semantic_type(column.get("semantic_role"))
                column_code = self._stable_code("col_key", column_name)
                dimension_extra = dimension_lookup.get((table_name, column_name), {})
                sample_values = (
                    column.get("field_value_examples")
                    or column.get("sample_values")
                    or dimension_extra.get("field_value_examples")
                    or dimension_extra.get("sample_values")
                    or []
                )
                synonyms = column.get("aliases") or dimension_extra.get("aliases") or []
                bundle.columns.append(
                    {
                        "code": self._stable_code("column", domain_code, table_name, column_name),
                        "domain_code": domain_code,
                        "table_code": table_code,
                        "column_code": column_code,
                        "name": column.get("business_name") or column_name,
                        "business_name": column.get("business_name") or column_name,
                        "description": column.get("description") or column.get("business_note"),
                        "physical_column_name": column_name,
                        "data_type": column.get("data_type") or "unknown",
                        "semantic_type": semantic_type,
                        "is_filterable": 1 if semantic_type in {"time", "entity", "dimension", "status"} else 0,
                        "is_groupable": 1 if semantic_type in {"time", "entity", "dimension", "status"} else 0,
                        "is_aggregatable": 1 if semantic_type == "amount" else 0,
                        "allowed_aggregations": self._json(["sum", "avg", "min", "max"]) if semantic_type == "amount" else None,
                        "sensitive_level": "normal",
                        "sample_values_json": self._json(sample_values) if sample_values else None,
                        "value_index_enabled": 1 if self._value_index_enabled(column, semantic_type, sample_values) else 0,
                        "synonyms_json": self._json(synonyms) if synonyms else None,
                        "unit": column.get("unit") or dimension_extra.get("unit"),
                        "source_type": "catalog_yaml",
                        "source_ref": source_ref,
                        "version": self.metadata_version,
                        "status": "draft",
                        "is_active": 1,
                        "extra_json": self._json(column),
                    }
                )

    @staticmethod
    def _dimension_value_lookup(raw_files: dict[str, dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        """按表和字段汇总维度样例值。

        参数：
            raw_files: 当前业务域的 catalog 原始 YAML 内容。
        返回：
            {(table, column): dimension_dict} 映射，用于字段资产补齐安全样例值和同义词。
        """

        lookup: dict[tuple[str, str], dict[str, Any]] = {}
        for dimension in raw_files.get("dimensions.yaml", {}).get("dimensions", []) or []:
            table_name = str(dimension.get("table") or "").strip()
            column_name = str(dimension.get("column") or "").strip()
            if table_name and column_name:
                lookup[(table_name, column_name)] = dimension
        return lookup

    @staticmethod
    def _value_index_enabled(column: dict[str, Any], semantic_type: str | None, sample_values: list[Any]) -> bool:
        """判断字段是否默认允许构建取值索引。

        参数：
            column: tables.yaml 中的字段配置。
            semantic_type: 已归一化的字段语义类型。
            sample_values: 来自字段或维度 catalog 的安全样例值。
        返回：
            True 表示字段可进入 value index 白名单；False 表示默认跳过。
        业务逻辑：
            只有可过滤/可分组的低敏枚举、维度、实体、时间、状态字段才默认启用；
            trace、amount 等高基数或数值字段必须显式声明 value_index_enabled=true 才启用。
        """

        if "value_index_enabled" in column:
            return bool(column.get("value_index_enabled"))
        if semantic_type in {"entity", "dimension", "time", "status"}:
            return True
        return bool(sample_values and semantic_type not in {"amount", "trace"})

    def _append_metrics(self, bundle: NqeMetadataSyncBundle, raw_files: dict[str, dict[str, Any]], domain_code: str, domain_dir: Path) -> None:
        """转换指标资产。"""

        metrics = raw_files.get("metrics.yaml", {}).get("metrics", []) or []
        if not metrics:
            self._warnings.append(f"{domain_code} 缺少可同步指标资产")
        for metric in metrics:
            metric_id = str(metric.get("metric_id") or metric.get("metric_code") or "").strip()
            if not metric_id:
                self._warnings.append(f"{domain_code} 存在缺少 metric_id 的指标资产，已跳过")
                continue
            table_name = metric.get("table")
            bundle.metrics.append(
                {
                    "code": self._stable_code("metric", domain_code, metric_id),
                    "domain_code": domain_code,
                    "metric_code": self._stable_code("metric_key", domain_code, metric_id),
                    "name": metric.get("display_name") or metric_id,
                    "business_name": metric.get("display_name") or metric_id,
                    "description": metric.get("business_note") or metric.get("nl_description"),
                    "metric_type": self._metric_type(metric.get("aggregation")),
                    "default_aggregation": metric.get("aggregation"),
                    "formula_text": metric.get("calculation_formula") or metric.get("sql_expression"),
                    "sql_expression_template": metric.get("sql_expression"),
                    "base_table_code": self._stable_code("table", domain_code, table_name) if table_name else None,
                    "fallback_required": 0,
                    "source_type": "catalog_yaml",
                    "source_ref": self._file_source_ref(domain_dir, "metrics.yaml"),
                    "version": self.metadata_version,
                    "status": "draft",
                    "is_active": 1,
                    "extra_json": self._json(metric),
                }
            )

    def _append_dimensions(self, bundle: NqeMetadataSyncBundle, raw_files: dict[str, dict[str, Any]], domain_code: str, domain_dir: Path) -> None:
        """转换维度资产。"""

        dimensions = raw_files.get("dimensions.yaml", {}).get("dimensions", []) or []
        if not dimensions:
            self._warnings.append(f"{domain_code} 缺少可同步维度资产")
        for dimension in dimensions:
            dimension_id = str(dimension.get("dimension_id") or dimension.get("dimension_code") or "").strip()
            if not dimension_id:
                self._warnings.append(f"{domain_code} 存在缺少 dimension_id 的维度资产，已跳过")
                continue
            table_name = dimension.get("table")
            column_name = dimension.get("column")
            bundle.dimensions.append(
                {
                    "code": self._stable_code("dimension", domain_code, dimension_id),
                    "domain_code": domain_code,
                    "dimension_code": self._stable_code("dimension_key", domain_code, dimension_id),
                    "name": dimension.get("display_name") or dimension_id,
                    "business_name": dimension.get("display_name") or dimension_id,
                    "description": dimension.get("business_note") or dimension.get("nl_description"),
                    "dimension_type": self._dimension_type(dimension),
                    "table_code": self._stable_code("table", domain_code, table_name) if table_name else None,
                    "column_code": self._stable_code("col_key", column_name) if column_name else None,
                    "hierarchy_json": self._json(dimension.get("hierarchy") or []),
                    "source_type": "catalog_yaml",
                    "source_ref": self._file_source_ref(domain_dir, "dimensions.yaml"),
                    "version": self.metadata_version,
                    "status": "draft",
                    "is_active": 1,
                    "extra_json": self._json(dimension),
                }
            )

    def _append_rules(self, bundle: NqeMetadataSyncBundle, raw_files: dict[str, dict[str, Any]], domain_code: str, domain_dir: Path) -> None:
        """转换业务规则资产。"""

        rules = raw_files.get("rules.yaml", {}).get("rules", []) or []
        if not rules:
            self._warnings.append(f"{domain_code} 缺少可同步规则资产")
        for rule in rules:
            rule_id = str(rule.get("rule_id") or rule.get("rule_code") or "").strip()
            if not rule_id:
                self._warnings.append(f"{domain_code} 存在缺少 rule_id 的规则资产，已跳过")
                continue
            rule_text = rule.get("business_message") or rule.get("rule_text") or rule.get("description") or rule.get("display_name") or rule_id
            bundle.business_rules.append(
                {
                    "code": self._stable_code("rule", domain_code, rule_id),
                    "domain_code": domain_code,
                    "rule_code": self._stable_code("rule_key", domain_code, rule_id),
                    "rule_type": rule.get("rule_type") or "business",
                    "title": rule.get("display_name") or rule_id,
                    "name": rule.get("display_name") or rule_id,
                    "description": rule.get("business_message"),
                    "rule_text": rule_text,
                    "applies_to_json": self._json(rule.get("applies_to") or []),
                    "priority": int(rule.get("priority") or 100),
                    "requires_clarification": 1 if rule.get("action") == "clarify" else 0,
                    "fallback_required": 1 if rule.get("action") in {"reject", "fallback"} else 0,
                    "visible_to_user": 0,
                    "source_type": "catalog_yaml",
                    "source_ref": self._file_source_ref(domain_dir, "rules.yaml"),
                    "version": self.metadata_version,
                    "status": "draft",
                    "is_active": 1,
                    "extra_json": self._json(rule),
                }
            )

    def _metadata_version_record(self, bundle: NqeMetadataSyncBundle) -> dict[str, Any]:
        """生成元数据版本记录。"""

        return {
            "code": self._stable_code("metadata_version", self.metadata_version),
            "domain_code": None,
            "metadata_version": self.metadata_version,
            "name": self.metadata_version,
            "description": "由受控 catalog 生成的 NQE 元数据版本",
            "version_status": "draft",
            "change_note": self._json(bundle.to_summary()["counts"]),
            "source_type": "catalog_yaml",
            "source_ref": self._safe_ref(self.catalog_root),
            "version": self.metadata_version,
            "status": "draft",
            "is_active": 1,
            "extra_json": self._json({"warnings": self._warnings}),
        }

    def _quality_gates(self, bundle: NqeMetadataSyncBundle) -> list[dict[str, Any]]:
        """根据资产完整性和告警生成质量门禁记录。"""

        required_counts = {
            "domains": len(bundle.domains),
            "tables": len(bundle.tables),
            "columns": len(bundle.columns),
            "metrics": len(bundle.metrics),
            "dimensions": len(bundle.dimensions),
            "business_rules": len(bundle.business_rules),
            "retrieval_chunks": len(bundle.retrieval_chunks),
        }
        # 业务说明：catalog 某类 YAML 缺失属于可修复资产缺口，按 warn 记录；
        # 只有无法形成基本域、表、字段或召回块时，才阻断后续索引构建。
        critical_assets = {"domains", "tables", "columns", "retrieval_chunks"}
        failed = [name for name, count in required_counts.items() if count <= 0 and name in critical_assets]
        missing_optional = [name for name, count in required_counts.items() if count <= 0 and name not in critical_assets]
        status = "failed" if failed else "warn" if self._warnings else "passed"
        if missing_optional and status == "passed":
            status = "warn"
        return [
            {
                "code": self._stable_code("quality_gate", self.metadata_version, "catalog_completeness"),
                "domain_code": None,
                "gate_code": "catalog_completeness",
                "gate_type": "metadata",
                "metadata_version": self.metadata_version,
                "name": "catalog 完整性门禁",
                "description": "检查受控 catalog 是否生成 NQE 首批元数据资产",
                "gate_status": status,
                "passed_count": sum(1 for count in required_counts.values() if count > 0),
                "failed_count": len(failed),
                "report_ref": None,
                "error_message": self._json({"failed": failed, "missing_optional": missing_optional, "warnings": self._warnings})
                if failed or missing_optional or self._warnings
                else None,
                "source_type": "catalog_yaml",
                "source_ref": self._safe_ref(self.catalog_root),
                "version": self.metadata_version,
                "status": "draft",
                "is_active": 1,
                "extra_json": self._json(required_counts),
            }
        ]

    def _chunk(
        self,
        asset_type: str,
        domain_code: str,
        asset_code: str,
        name: str | None,
        chunk_text: str,
        keywords: Iterable[Any],
        synonyms: Iterable[Any] | None = None,
    ) -> dict[str, Any]:
        """生成单条召回块记录。"""

        chunk_code = self._stable_code("chunk", domain_code, asset_type, asset_code)
        return {
            "code": chunk_code,
            "domain_code": domain_code,
            "chunk_code": chunk_code,
            "asset_type": asset_type,
            "asset_id": None,
            "asset_code": asset_code,
            "name": name,
            "description": f"{asset_type} 元数据召回块",
            "chunk_text": chunk_text,
            "keywords_json": self._json([item for item in keywords if item]),
            "synonyms_json": self._json([item for item in (synonyms or []) if item]),
            "embedding_model": None,
            "embedding_hash": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
            "index_status": "pending",
            "source_type": "catalog_yaml",
            "source_ref": "retrieval_chunks",
            "version": self.metadata_version,
            "status": "draft",
            "is_active": 1,
            "extra_json": self._json({"asset_type": asset_type}),
        }

    def _resolve_domain_code(self, domain_dir: Path, raw_files: dict[str, dict[str, Any]]) -> str:
        """优先从 YAML 中解析业务域编码，缺省时用目录名。"""

        for raw in raw_files.values():
            domain = raw.get("domain")
            if domain:
                return self._slug(str(domain), fallback=domain_dir.name)
        return "logistics" if domain_dir == self.catalog_root else self._slug(domain_dir.name)

    @staticmethod
    def _display_domain_name(domain_code: str) -> str:
        """返回业务域展示名。"""

        return {"logistics": "物流", "plan_bom": "计划 BOM", "business_analysis": "经营分析"}.get(domain_code, domain_code)

    @staticmethod
    def _resolve_table_role(table_name: str) -> str:
        """根据表名前缀推断表角色。"""

        for prefix in ("ods", "dwd", "dws", "dm", "dim"):
            if table_name.startswith(f"{prefix}_"):
                return "dim" if prefix == "dim" else prefix
        if table_name.endswith("_fact"):
            return "fact"
        return "dwd"

    @staticmethod
    def _semantic_type(role: Any) -> str | None:
        """将现有 catalog semantic_role 映射到 NQE 字段语义类型。"""

        role_text = str(role or "").lower()
        mapping = {
            "time": "time",
            "dimension": "dimension",
            "metric": "amount",
            "rule_filter": "status",
            "trace": "trace",
        }
        return mapping.get(role_text, role_text or None)

    @staticmethod
    def _metric_type(aggregation: Any) -> str:
        """根据聚合方式推断指标类型。"""

        aggregation_text = str(aggregation or "").lower()
        if aggregation_text in {"ratio", "rate"}:
            return "ratio"
        if aggregation_text in {"value", "rank"}:
            return "derived"
        return "atomic"

    @staticmethod
    def _dimension_type(dimension: dict[str, Any]) -> str:
        """根据维度编码和字段名推断维度类型。"""

        text = f"{dimension.get('dimension_id', '')} {dimension.get('column', '')}".lower()
        if "year" in text or "month" in text or "date" in text or "period" in text:
            return "time"
        if "customer" in text:
            return "customer"
        if "product" in text or "model" in text or "material" in text:
            return "product"
        if "dept" in text or "base" in text or "factory" in text:
            return "org"
        return "entity"

    def _safe_ref(self, path: Path) -> str:
        """生成不含本机绝对路径和敏感连接信息的来源引用。"""

        try:
            ref = path.resolve().relative_to(self.catalog_root.resolve()).as_posix()
        except ValueError:
            ref = path.as_posix() if not path.is_absolute() else path.name
        if ref in {"", "."}:
            ref = self.catalog_root.as_posix() if not self.catalog_root.is_absolute() else self.catalog_root.name
        if SENSITIVE_REF_PATTERN.search(ref):
            return "redacted_source_ref"
        return ref

    def _file_source_ref(self, domain_dir: Path, filename: str) -> str:
        """返回单个 YAML 文件的相对来源引用。"""

        return self._safe_ref(domain_dir / filename)

    def _domain_source_ref(self, domain_dir: Path) -> str:
        """返回业务域目录的相对来源引用。"""

        return self._safe_ref(domain_dir)

    @staticmethod
    def _json(value: Any) -> str:
        """按 ensure_ascii=False 输出 JSON 字符串。"""

        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _loads_json(value: str | None) -> dict[str, Any]:
        """安全解析扩展 JSON，解析失败时返回空字典。"""

        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _yes_no(value: Any) -> str:
        """把 0/1 标记转成中文文本。"""

        return "是" if int(value or 0) else "否"

    @staticmethod
    def _short_text(value: Any, limit: int) -> str:
        """截断长文本，避免 chunk 过长。"""

        text = str(value or "")
        return text if len(text) <= limit else f"{text[:limit]}..."

    @staticmethod
    def _slug(value: str, *, fallback: str = "item") -> str:
        """生成稳定 ASCII 编码片段。"""

        slug = re.sub(r"[^a-zA-Z0-9_]+", "_", value.strip().lower()).strip("_")
        return slug or hashlib.sha256(value.encode("utf-8")).hexdigest()[:12] or fallback

    def _stable_code(self, prefix: str, *parts: Any, max_length: int = 128) -> str:
        """生成不超过模型字段限制的稳定 code。

        参数：
            prefix: 编码前缀。
            parts: 影响唯一性的业务键。
            max_length: 最大长度，默认 128。
        返回：
            稳定、幂等、长度受控的编码。
        """

        raw = "__".join(str(part) for part in (prefix, *parts) if part is not None)
        slug = "__".join(self._slug(str(part)) for part in (prefix, *parts) if part is not None)
        if len(slug) <= max_length:
            return slug
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"{slug[: max_length - 18]}__{digest}"

    @staticmethod
    def _first_catalog_version(raw_files: dict[str, dict[str, Any]]) -> str | None:
        """读取第一个可用 catalog_version。"""

        for raw in raw_files.values():
            version = raw.get("catalog_version")
            if version:
                return str(version)
        return None


def build_nqe_context_package_from_bundle(bundle: NqeMetadataSyncBundle, domain_code: str | None = None) -> dict[str, Any]:
    """从元数据 bundle 构造 NQE Graph 可直接使用的安全上下文包。

    参数：
        bundle: NqeMetadataSyncBuilder 生成的内存元数据包。
        domain_code: 可选业务域编码；不传时使用 bundle 中第一个业务域。
    返回：
        只包含 ready、domain_code、metadata_version、allowed_tables、table_columns、
        retrieval_assets 等非敏感字段的上下文包。
    业务逻辑：
        中文注释：本 helper 只汇总静态 catalog 资产，不读取 .env、不连接真实数据库，
        source_ref 仅保留 bundle 已脱敏的相对引用。
    """

    available_domains = [str(domain.get("domain_code") or "") for domain in bundle.domains if domain.get("domain_code")]
    selected_domain = domain_code or (available_domains[0] if available_domains else None)
    if not selected_domain:
        return {
            "ready": False,
            "domain_code": None,
            "metadata_version": bundle.metadata_versions[0]["metadata_version"] if bundle.metadata_versions else None,
            "allowed_tables": [],
            "table_columns": {},
            "columns_by_table": {},
            "retrieval_assets": {"summary": {"tables": 0, "columns": 0, "chunks": 0}, "chunks": []},
            "source_refs": [],
        }

    tables = [
        table
        for table in bundle.tables
        if table.get("domain_code") == selected_domain and int(table.get("allow_select") or 0) == 1 and table.get("physical_table_name")
    ]
    table_code_to_name = {str(table.get("code")): str(table.get("physical_table_name")) for table in tables}
    allowed_tables = sorted(set(table_code_to_name.values()))
    table_columns: dict[str, list[str]] = {table_name: [] for table_name in allowed_tables}
    for column in bundle.columns:
        table_name = table_code_to_name.get(str(column.get("table_code") or ""))
        column_name = str(column.get("physical_column_name") or "")
        if table_name and column_name:
            table_columns.setdefault(table_name, []).append(column_name)
    table_columns = {table: sorted(set(columns)) for table, columns in table_columns.items() if columns}

    chunks = [chunk for chunk in bundle.retrieval_chunks if chunk.get("domain_code") == selected_domain]
    retrieval_chunks = [
        {
            "asset_type": chunk.get("asset_type"),
            "asset_code": chunk.get("asset_code"),
            "name": chunk.get("name"),
            "chunk_text": chunk.get("chunk_text"),
        }
        for chunk in chunks[:20]
    ]
    source_refs = sorted(
        {
            str(row.get("source_ref"))
            for group in (bundle.domains, bundle.tables, bundle.columns, bundle.metrics, bundle.dimensions, bundle.business_rules)
            for row in group
            if row.get("domain_code") == selected_domain and row.get("source_ref")
        }
    )
    metadata_version = bundle.metadata_versions[0]["metadata_version"] if bundle.metadata_versions else None
    if metadata_version is None:
        metadata_version = next((row.get("version") for row in tables if row.get("version")), None)

    return {
        "ready": bool(allowed_tables and table_columns),
        "domain_code": selected_domain,
        "metadata_version": metadata_version,
        "allowed_tables": allowed_tables,
        "table_columns": table_columns,
        "columns_by_table": table_columns,
        "retrieval_assets": {
            "summary": {
                "domains": 1,
                "tables": len(allowed_tables),
                "columns": sum(len(columns) for columns in table_columns.values()),
                "chunks": len(chunks),
            },
            "chunks": retrieval_chunks,
        },
        "source_refs": source_refs,
    }


def upsert_nqe_metadata_bundle(session: Session, bundle: NqeMetadataSyncBundle) -> dict[str, int]:
    """将 NQE 元数据 bundle 幂等写入数据库。

    参数：
        session: 外部传入的 SQLAlchemy Session；测试可使用 SQLite 内存库。
        bundle: NqeMetadataSyncBuilder 生成的元数据包。
    返回：
        每类资产 upsert 的行数统计。
    业务逻辑：
        只按唯一业务键新增或更新，不执行删除，避免破坏旧版本数据。
    """

    stats = {
        "domains": _upsert_many(session, NqeDomain, "code", bundle.domains),
        "data_sources": _upsert_many(session, NqeDataSource, "code", bundle.data_sources),
        "tables": _upsert_many(session, NqeTableInfo, "code", bundle.tables),
        "columns": _upsert_many(session, NqeColumnInfo, "code", bundle.columns),
        "metrics": _upsert_many(session, NqeMetricInfo, "code", bundle.metrics),
        "dimensions": _upsert_many(session, NqeDimensionInfo, "code", bundle.dimensions),
        "business_rules": _upsert_many(session, NqeBusinessRule, "code", bundle.business_rules),
        "retrieval_chunks": _upsert_many(session, NqeRetrievalChunk, "code", bundle.retrieval_chunks),
        "metadata_versions": _upsert_many(session, NqeMetadataVersion, "code", bundle.metadata_versions),
        "quality_gates": _upsert_many(session, NqeQualityGate, "code", bundle.quality_gates),
    }
    session.commit()
    return stats


def _upsert_many(session: Session, model: type[ModelT], key: str, rows: list[dict[str, Any]]) -> int:
    """按指定唯一键批量 upsert。

    参数：
        session: SQLAlchemy Session。
        model: NQE SQLAlchemy 模型类。
        key: 唯一业务键字段名。
        rows: 待写入的标准化字典列表。
    返回：
        处理行数。
    """

    for row in rows:
        key_value = row[key]
        instance = session.query(model).filter(getattr(model, key) == key_value).one_or_none()
        if instance is None:
            session.add(model(**row))
            continue
        for column_name, value in row.items():
            if column_name == "id" or not hasattr(instance, column_name):
                continue
            setattr(instance, column_name, value)
    return len(rows)


__all__ = [
    "DEFAULT_CATALOG_ROOT",
    "NqeMetadataSyncBundle",
    "NqeMetadataSyncBuilder",
    "build_nqe_context_package_from_bundle",
    "upsert_nqe_metadata_bundle",
]
