from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.models.nqe_metadata import NqeColumnInfo, NqeTableInfo, NqeValueIndex, NqeValueInfo


SAFE_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SAFE_SENSITIVE_LEVELS = {"", "normal", "public", "low"}
INDEXABLE_SEMANTIC_TYPES = {"entity", "dimension", "status", "time"}


@dataclass(frozen=True)
class NqeValueIndexColumnSpec:
    """NQE 字段取值索引列白名单。

    参数：
        domain_code: 业务域编码。
        table_code: NQE 表编码。
        column_code: NQE 字段编码。
        physical_table_name: 物理表名，只能来自已校验元数据。
        physical_column_name: 物理字段名，只能来自已校验元数据。
        semantic_type: 字段语义类型。
        sensitive_level: 敏感等级。
        value_index_enabled: 是否允许构建 value index。
        max_values_per_column: 单字段最多读取或生成的取值数。
    返回：
        dataclass 实例，供 builder 生成 SQL 或 catalog 候选。
    """

    domain_code: str
    table_code: str
    column_code: str
    physical_table_name: str
    physical_column_name: str
    semantic_type: str | None = None
    sensitive_level: str = "normal"
    value_index_enabled: bool = False
    max_values_per_column: int = 100


@dataclass(frozen=True)
class NqeValueCandidate:
    """字段取值候选。

    参数：
        domain_code: 业务域编码。
        table_code: NQE 表编码。
        column_code: NQE 字段编码。
        raw_value: 原始值。
        normalized_value: 标准化值。
        display_value: 展示值。
        aliases: 值级别别名。
        freq: 频次，catalog 样例默认 1。
        source_type: 来源类型。
        source_snapshot: 来源摘要，不含真实连接信息。
        quality_score: 质量分，0 到 100。
    返回：
        dataclass 实例，供 upsert 与 recall 使用。
    """

    domain_code: str
    table_code: str
    column_code: str
    raw_value: str
    normalized_value: str
    display_value: str
    aliases: list[str] = field(default_factory=list)
    freq: int = 1
    source_type: str = "catalog_examples"
    source_snapshot: dict[str, Any] = field(default_factory=dict)
    quality_score: int = 100


@dataclass
class NqeValueIndexSummary:
    """字段取值索引构建摘要。

    参数：
        total_columns: 输入字段数。
        indexed_columns: 实际进入索引的字段数。
        skipped_columns: 跳过字段数。
        total_values: 生成或读取的候选值数量。
        dry_run: 是否 dry-run。
        warnings: 非阻断告警。
        errors: 阻断或局部错误。
        domain_counts: 按业务域统计的候选数量。
    返回：
        可直接 JSON 化的构建摘要。
    """

    total_columns: int = 0
    indexed_columns: int = 0
    skipped_columns: int = 0
    total_values: int = 0
    dry_run: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    domain_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """返回 JSON 友好的摘要字典。"""

        return asdict(self)


@dataclass(frozen=True)
class NqeValueRecallCandidate:
    """字段取值召回结果。

    参数：
        value: 标准化值。
        display_value: 展示值。
        domain_code: 业务域编码。
        table_code: 表编码。
        column_code: 字段编码。
        score: 综合分。
        score_breakdown: 分数来源拆解。
        matched_by: 命中方式。
        needs_disambiguation: 是否需要消歧。
    返回：
        dataclass 实例，可转 dict 给上游 trace 摘要。
    """

    value: str
    display_value: str
    domain_code: str
    table_code: str
    column_code: str
    score: float
    score_breakdown: dict[str, float]
    matched_by: str
    needs_disambiguation: bool = False

    def to_dict(self) -> dict[str, Any]:
        """返回 JSON 友好的召回结果。"""

        return asdict(self)


class NqeValueIndexBuilder:
    """NQE 字段取值索引构建服务。

    业务逻辑：
        只从 NQE 元数据白名单生成字段取值候选；默认 dry-run 不连接真实业务库。
        apply 模式也只允许对已校验表名、字段名执行带 LIMIT 的 distinct 查询。
    """

    def __init__(self) -> None:
        """初始化构建服务。"""

        self.warnings: list[str] = []

    def build_column_specs_from_metadata(
        self,
        tables: Iterable[NqeTableInfo | dict[str, Any]],
        columns: Iterable[NqeColumnInfo | dict[str, Any]],
        *,
        max_values_per_column: int = 100,
    ) -> tuple[list[NqeValueIndexColumnSpec], NqeValueIndexSummary]:
        """从 NQE 表/字段元数据构建字段白名单。

        参数：
            tables: NQE 表元数据，可传 ORM 或 bundle dict。
            columns: NQE 字段元数据，可传 ORM 或 bundle dict。
            max_values_per_column: 单字段最多取值数量。
        返回：
            (字段白名单, 构建摘要)。
        重要业务逻辑：
            只有 active、allow_select、可过滤或可分组、value_index_enabled、非敏感字段可以进入白名单。
        """

        warnings: list[str] = []
        table_map = {self._get(row, "code"): row for row in tables}
        specs: list[NqeValueIndexColumnSpec] = []
        total_columns = 0
        skipped_columns = 0

        for column in columns:
            total_columns += 1
            table_code = str(self._get(column, "table_code") or "")
            table = table_map.get(table_code)
            if not table:
                skipped_columns += 1
                warnings.append(f"字段缺少表元数据，已跳过：{table_code}")
                continue
            if not self._is_active(table) or not self._is_active(column):
                skipped_columns += 1
                continue
            if int(self._get(table, "allow_select") or 0) != 1:
                skipped_columns += 1
                continue
            if int(self._get(column, "value_index_enabled") or 0) != 1:
                skipped_columns += 1
                continue
            if int(self._get(column, "is_filterable") or 0) != 1 and int(self._get(column, "is_groupable") or 0) != 1:
                skipped_columns += 1
                continue
            sensitive_level = str(self._get(column, "sensitive_level") or "normal").lower()
            if sensitive_level not in SAFE_SENSITIVE_LEVELS:
                skipped_columns += 1
                warnings.append(f"敏感字段不构建取值索引：{table_code}.{self._get(column, 'column_code')}")
                continue

            physical_table_name = str(self._get(table, "physical_table_name") or "")
            physical_column_name = str(self._get(column, "physical_column_name") or "")
            if not self._is_safe_identifier(physical_table_name) or not self._is_safe_identifier(physical_column_name):
                skipped_columns += 1
                warnings.append(f"非法表名或字段名已跳过：{table_code}.{self._get(column, 'column_code')}")
                continue

            specs.append(
                NqeValueIndexColumnSpec(
                    domain_code=str(self._get(column, "domain_code") or self._get(table, "domain_code") or ""),
                    table_code=table_code,
                    column_code=str(self._get(column, "column_code") or ""),
                    physical_table_name=physical_table_name,
                    physical_column_name=physical_column_name,
                    semantic_type=self._get(column, "semantic_type"),
                    sensitive_level=sensitive_level,
                    value_index_enabled=True,
                    max_values_per_column=max(1, int(max_values_per_column)),
                )
            )

        summary = NqeValueIndexSummary(
            total_columns=total_columns,
            indexed_columns=len(specs),
            skipped_columns=skipped_columns,
            dry_run=True,
            warnings=warnings,
        )
        return specs, summary

    def build_from_catalog_examples(self, bundle: Any, *, max_values_per_column: int = 100) -> tuple[list[NqeValueCandidate], NqeValueIndexSummary]:
        """从受控 catalog 样例值构建静态候选。

        参数：
            bundle: NqeMetadataSyncBuilder 生成的 bundle。
            max_values_per_column: 单字段最多生成样例值数量。
        返回：
            (候选值列表, 构建摘要)。
        业务逻辑：
            只读取 bundle 内的 sample_values_json、field_value_examples、aliases，不访问业务库。
        """

        tables = list(getattr(bundle, "tables", []) or [])
        columns = list(getattr(bundle, "columns", []) or [])
        specs, spec_summary = self.build_column_specs_from_metadata(tables, columns, max_values_per_column=max_values_per_column)
        spec_keys = {(spec.table_code, spec.column_code): spec for spec in specs}
        candidates: list[NqeValueCandidate] = []
        warnings = list(spec_summary.warnings)
        seen: set[tuple[str, str, str]] = set()

        for column in columns:
            table_code = str(column.get("table_code") or "")
            column_code = str(column.get("column_code") or "")
            spec = spec_keys.get((table_code, column_code))
            if not spec:
                continue
            examples = self._json_list(column.get("sample_values_json"))
            aliases = self._json_list(column.get("synonyms_json"))
            for raw_value in examples[: spec.max_values_per_column]:
                normalized = self.normalize_value(raw_value)
                if not normalized:
                    continue
                key = (table_code, column_code, normalized)
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(
                    NqeValueCandidate(
                        domain_code=spec.domain_code,
                        table_code=table_code,
                        column_code=column_code,
                        raw_value=str(raw_value),
                        normalized_value=normalized,
                        display_value=str(raw_value).strip(),
                        aliases=[str(item).strip() for item in aliases if str(item).strip()],
                        freq=1,
                        source_type="catalog_examples",
                        source_snapshot={"source_ref": column.get("source_ref"), "metadata_version": column.get("version")},
                        quality_score=90,
                    )
                )

        domain_counts = self._domain_counts(candidates)
        summary = NqeValueIndexSummary(
            total_columns=spec_summary.total_columns,
            indexed_columns=spec_summary.indexed_columns,
            skipped_columns=spec_summary.skipped_columns,
            total_values=len(candidates),
            dry_run=True,
            warnings=warnings,
            domain_counts=domain_counts,
        )
        return candidates, summary

    def build_from_mysql(
        self,
        session: Session,
        column_specs: Iterable[NqeValueIndexColumnSpec],
        *,
        limit_per_column: int = 100,
        timeout_ms: int = 3000,
        dry_run: bool = True,
    ) -> tuple[list[NqeValueCandidate], NqeValueIndexSummary]:
        """从 MySQL 执行限量 distinct 查询构建候选。

        参数：
            session: 外部注入的 SQLAlchemy Session；本服务不创建连接、不读取 .env。
            column_specs: 已通过白名单校验的字段列表。
            limit_per_column: 单字段最多返回取值数。
            timeout_ms: SQL 最大执行时间提示，写入 MySQL optimizer hint。
            dry_run: True 时不执行任何 SQL。
        返回：
            (候选值列表, 构建摘要)。
        重要业务逻辑：
            SQL 只拼接已通过安全校验的表名/字段名，且强制 LIMIT，禁止无界 distinct 扫描。
        """

        specs = list(column_specs)
        warnings: list[str] = []
        errors: list[str] = []
        candidates: list[NqeValueCandidate] = []
        safe_specs: list[NqeValueIndexColumnSpec] = []
        effective_limit = max(1, min(int(limit_per_column), 1000))
        effective_timeout = max(1, min(int(timeout_ms), 30000))

        for spec in specs:
            if not self._is_safe_identifier(spec.physical_table_name) or not self._is_safe_identifier(spec.physical_column_name):
                warnings.append(f"非法表名或字段名已跳过：{spec.table_code}.{spec.column_code}")
                continue
            safe_specs.append(spec)

        if dry_run:
            return [], NqeValueIndexSummary(
                total_columns=len(specs),
                indexed_columns=len(safe_specs),
                skipped_columns=len(specs) - len(safe_specs),
                dry_run=True,
                warnings=warnings,
            )

        for spec in safe_specs:
            sql_text = self._distinct_sql(spec, limit_per_column=effective_limit, timeout_ms=effective_timeout)
            try:
                rows = session.execute(text(sql_text), {"limit": effective_limit}).mappings().all()
            except Exception as exc:  # pragma: no cover - 真实 DB 错误只记录脱敏类型
                errors.append(f"distinct 查询失败：{spec.table_code}.{spec.column_code}:{exc.__class__.__name__}")
                continue
            for row in rows:
                raw_value = row.get("raw_value")
                normalized = self.normalize_value(raw_value)
                if not normalized:
                    continue
                candidates.append(
                    NqeValueCandidate(
                        domain_code=spec.domain_code,
                        table_code=spec.table_code,
                        column_code=spec.column_code,
                        raw_value=str(raw_value).strip(),
                        normalized_value=normalized,
                        display_value=str(raw_value).strip(),
                        aliases=[],
                        freq=int(row.get("freq") or 1),
                        source_type="mysql_distinct",
                        source_snapshot={"limit_per_column": effective_limit, "timeout_ms": effective_timeout},
                        quality_score=80,
                    )
                )

        return candidates, NqeValueIndexSummary(
            total_columns=len(specs),
            indexed_columns=len({(item.table_code, item.column_code) for item in candidates}),
            skipped_columns=len(specs) - len(safe_specs),
            total_values=len(candidates),
            dry_run=False,
            warnings=warnings,
            errors=errors,
            domain_counts=self._domain_counts(candidates),
        )

    def upsert_value_candidates(self, session: Session, candidates: Iterable[NqeValueCandidate], *, metadata_version: str = "nqe_value_index_v1") -> dict[str, int]:
        """幂等写入取值资产表和索引表。

        参数：
            session: 外部注入的 SQLAlchemy Session。
            candidates: 待写入候选值。
            metadata_version: 本次索引版本标签。
        返回：
            写入统计，包含 value_info 和 value_index 处理数量。
        业务逻辑：
            按 table_code + column_code + normalized_value 与
            domain_code + table_code + column_code + normalized_value 做幂等更新，不重复插入。
        """

        info_count = 0
        index_count = 0
        for candidate in candidates:
            info_row = self._value_info_row(candidate, metadata_version=metadata_version)
            info = (
                session.query(NqeValueInfo)
                .filter(NqeValueInfo.table_code == candidate.table_code)
                .filter(NqeValueInfo.column_code == candidate.column_code)
                .filter(NqeValueInfo.normalized_value == candidate.normalized_value)
                .one_or_none()
            )
            if info is None:
                session.add(NqeValueInfo(**info_row))
            else:
                self._assign(info, info_row)
            info_count += 1

            index_row = self._value_index_row(candidate, metadata_version=metadata_version)
            index = (
                session.query(NqeValueIndex)
                .filter(NqeValueIndex.domain_code == candidate.domain_code)
                .filter(NqeValueIndex.table_code == candidate.table_code)
                .filter(NqeValueIndex.column_code == candidate.column_code)
                .filter(NqeValueIndex.normalized_value == candidate.normalized_value)
                .one_or_none()
            )
            if index is None:
                session.add(NqeValueIndex(**index_row))
            else:
                self._assign(index, index_row)
            index_count += 1

        session.commit()
        return {"value_info": info_count, "value_index": index_count}

    def _distinct_sql(self, spec: NqeValueIndexColumnSpec, *, limit_per_column: int, timeout_ms: int) -> str:
        """生成受控 distinct SQL。

        参数：
            spec: 已校验字段白名单。
            limit_per_column: 单字段限制数量。
            timeout_ms: MySQL 执行时间提示。
        返回：
            带 LIMIT 和 MAX_EXECUTION_TIME hint 的 SQL 文本。
        """

        table_name = self._quote_identifier(spec.physical_table_name)
        column_name = self._quote_identifier(spec.physical_column_name)
        return (
            f"SELECT /*+ MAX_EXECUTION_TIME({timeout_ms}) */ "
            f"TRIM(CAST({column_name} AS CHAR)) AS raw_value, COUNT(*) AS freq "
            f"FROM {table_name} "
            f"WHERE {column_name} IS NOT NULL AND TRIM(CAST({column_name} AS CHAR)) <> '' "
            f"GROUP BY TRIM(CAST({column_name} AS CHAR)) "
            f"ORDER BY freq DESC "
            f"LIMIT :limit"
        )

    def _value_info_row(self, candidate: NqeValueCandidate, *, metadata_version: str) -> dict[str, Any]:
        """把候选转成 nqe_value_info 行。"""

        value_code = self._stable_code("value", candidate.domain_code, candidate.table_code, candidate.column_code, candidate.normalized_value)
        return {
            "code": value_code,
            "domain_code": candidate.domain_code,
            "table_code": candidate.table_code,
            "column_code": candidate.column_code,
            "value_code": value_code,
            "raw_value": candidate.raw_value,
            "normalized_value": candidate.normalized_value,
            "display_value": candidate.display_value,
            "aliases_json": self._json(candidate.aliases),
            "pinyin_key": None,
            "value_freq": candidate.freq,
            "last_seen_at": datetime.utcnow() if candidate.source_type == "mysql_distinct" else None,
            "quality_status": "trusted" if candidate.quality_score >= 80 else "candidate",
            "source_type": candidate.source_type,
            "source_ref": "nqe_value_index",
            "version": metadata_version,
            "status": "draft",
            "is_active": 1,
            "extra_json": self._json({"quality_score": candidate.quality_score}),
        }

    def _value_index_row(self, candidate: NqeValueCandidate, *, metadata_version: str) -> dict[str, Any]:
        """把候选转成 nqe_value_index 行。"""

        code = self._stable_code("value_index", candidate.domain_code, candidate.table_code, candidate.column_code, candidate.normalized_value)
        aliases = [self.normalize_value(alias) for alias in candidate.aliases if self.normalize_value(alias)]
        return {
            "code": code,
            "domain_code": candidate.domain_code,
            "table_code": candidate.table_code,
            "column_code": candidate.column_code,
            "normalized_value": candidate.normalized_value,
            "display_value": candidate.display_value,
            "match_text": candidate.normalized_value,
            "aliases_text": " ".join(sorted(set(aliases))) if aliases else None,
            "freq": candidate.freq,
            "quality_score": int(candidate.quality_score),
            "source_snapshot": self._json(candidate.source_snapshot),
            "source_type": candidate.source_type,
            "source_ref": "nqe_value_index",
            "version": metadata_version,
            "status": "draft",
            "is_active": 1,
            "extra_json": self._json({"raw_value": candidate.raw_value}),
        }

    @staticmethod
    def normalize_value(value: Any) -> str:
        """标准化取值。

        参数：
            value: 原始取值。
        返回：
            去首尾空白、压缩内部空白并转小写后的取值。
        """

        text_value = str(value or "").strip()
        text_value = re.sub(r"\s+", " ", text_value)
        return text_value.lower()

    @staticmethod
    def _is_safe_identifier(value: str) -> bool:
        """校验 SQL 标识符是否只包含字母、数字、下划线。"""

        return bool(SAFE_IDENTIFIER_PATTERN.fullmatch(value or ""))

    @staticmethod
    def _quote_identifier(value: str) -> str:
        """给已校验的 MySQL 标识符增加反引号。"""

        if not SAFE_IDENTIFIER_PATTERN.fullmatch(value or ""):
            raise ValueError("unsafe_identifier")
        return f"`{value}`"

    @staticmethod
    def _get(row: Any, key: str) -> Any:
        """兼容 ORM 对象和 dict 的字段读取。"""

        if isinstance(row, dict):
            return row.get(key)
        return getattr(row, key, None)

    @classmethod
    def _is_active(cls, row: Any) -> bool:
        """判断元数据是否处于启用状态。"""

        return int(cls._get(row, "is_active") or 0) == 1 and str(cls._get(row, "status") or "draft") != "disabled"

    @staticmethod
    def _json(value: Any) -> str:
        """生成稳定 JSON 字符串。"""

        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    @staticmethod
    def _json_list(value: str | None) -> list[Any]:
        """安全解析 JSON 数组。"""

        if not value:
            return []
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []

    @staticmethod
    def _domain_counts(candidates: Iterable[NqeValueCandidate]) -> dict[str, int]:
        """按业务域统计候选数量。"""

        counts: dict[str, int] = {}
        for candidate in candidates:
            counts[candidate.domain_code] = counts.get(candidate.domain_code, 0) + 1
        return counts

    @staticmethod
    def _assign(instance: Any, values: dict[str, Any]) -> None:
        """把字典字段覆盖到 ORM 实例。"""

        for key, value in values.items():
            if key != "id" and hasattr(instance, key):
                setattr(instance, key, value)

    @staticmethod
    def _stable_code(prefix: str, *parts: Any, max_length: int = 128) -> str:
        """生成长度受控且幂等的编码。"""

        raw = "__".join(str(part) for part in (prefix, *parts) if part is not None)
        slug = re.sub(r"[^a-zA-Z0-9_]+", "_", raw.lower()).strip("_")
        if len(slug) <= max_length:
            return slug
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
        return f"{slug[: max_length - 18]}__{digest}"


class NqeValueRecallService:
    """NQE value recall 服务。

    业务逻辑：
        只查询 nqe_value_index 索引表，不查询业务明细表；按精确、别名、包含顺序评分。
    """

    def __init__(self, session: Session) -> None:
        """初始化召回服务。

        参数：
            session: SQLAlchemy Session，只用于查询 nqe_value_index。
        """

        self.session = session

    def recall(
        self,
        *,
        query_terms: Iterable[str],
        domain_code: str,
        normalized_question: str | None = None,
        table_code: str | None = None,
        column_code: str | None = None,
        top_k: int = 10,
    ) -> list[NqeValueRecallCandidate]:
        """召回字段取值候选。

        参数：
            query_terms: NLU/实体抽取得到的候选词。
            domain_code: 业务域编码。
            normalized_question: 标准化后的用户问题，可辅助包含匹配。
            table_code: 可选表过滤。
            column_code: 可选字段过滤。
            top_k: 最大返回数量。
        返回：
            排序后的候选列表，带 score_breakdown 和 matched_by。
        """

        terms = [NqeValueIndexBuilder.normalize_value(term) for term in query_terms if NqeValueIndexBuilder.normalize_value(term)]
        question = NqeValueIndexBuilder.normalize_value(normalized_question or "")
        if question:
            terms.append(question)
        if not terms:
            return []

        query = self.session.query(NqeValueIndex).filter(NqeValueIndex.domain_code == domain_code).filter(NqeValueIndex.is_active == 1)
        if table_code:
            query = query.filter(NqeValueIndex.table_code == table_code)
        if column_code:
            query = query.filter(NqeValueIndex.column_code == column_code)

        scored: list[NqeValueRecallCandidate] = []
        for row in query.all():
            match = self._score_row(row, terms)
            if not match:
                continue
            score, matched_by, breakdown = match
            scored.append(
                NqeValueRecallCandidate(
                    value=row.normalized_value,
                    display_value=row.display_value,
                    domain_code=row.domain_code,
                    table_code=row.table_code,
                    column_code=row.column_code,
                    score=score,
                    score_breakdown=breakdown,
                    matched_by=matched_by,
                    needs_disambiguation=False,
                )
            )

        scored.sort(key=lambda item: (-item.score, item.domain_code, item.table_code, item.column_code, item.display_value))
        limited = scored[: max(1, int(top_k))]
        return self._mark_disambiguation(limited)

    @staticmethod
    def _score_row(row: NqeValueIndex, terms: list[str]) -> tuple[float, str, dict[str, float]] | None:
        """计算单条索引记录的匹配分。

        参数：
            row: nqe_value_index ORM 行。
            terms: 已标准化查询词。
        返回：
            (score, matched_by, score_breakdown)，未命中返回 None。
        """

        value = row.match_text or row.normalized_value
        aliases = row.aliases_text or ""
        freq_bonus = min(float(row.freq or 0) / 1000.0, 0.1)
        quality_bonus = min(float(row.quality_score or 0) / 1000.0, 0.1)

        best: tuple[float, str, dict[str, float]] | None = None
        for term in terms:
            base = 0.0
            matched_by = ""
            if term == value:
                base = 1.0
                matched_by = "exact"
            elif aliases and term in aliases.split():
                base = 0.88
                matched_by = "alias"
            elif term and (term in value or value in term or (aliases and term in aliases)):
                base = 0.68
                matched_by = "contains"
            if not matched_by:
                continue
            score = min(base + freq_bonus + quality_bonus, 1.0)
            breakdown = {"base": base, "freq_bonus": freq_bonus, "quality_bonus": quality_bonus}
            if best is None or score > best[0]:
                best = (score, matched_by, breakdown)
        return best

    @staticmethod
    def _mark_disambiguation(candidates: list[NqeValueRecallCandidate]) -> list[NqeValueRecallCandidate]:
        """标记多字段近分候选是否需要消歧。"""

        if len(candidates) < 2:
            return candidates
        first = candidates[0]
        needs = any(
            (item.table_code != first.table_code or item.column_code != first.column_code) and abs(item.score - first.score) <= 0.08
            for item in candidates[1:]
        )
        if not needs:
            return candidates
        return [
            NqeValueRecallCandidate(
                value=item.value,
                display_value=item.display_value,
                domain_code=item.domain_code,
                table_code=item.table_code,
                column_code=item.column_code,
                score=item.score,
                score_breakdown=item.score_breakdown,
                matched_by=item.matched_by,
                needs_disambiguation=True,
            )
            for item in candidates
        ]


__all__ = [
    "NqeValueCandidate",
    "NqeValueIndexBuilder",
    "NqeValueIndexColumnSpec",
    "NqeValueIndexSummary",
    "NqeValueRecallCandidate",
    "NqeValueRecallService",
]
