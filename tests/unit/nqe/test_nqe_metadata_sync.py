from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.app.models  # noqa: F401  # 触发 NQE 模型注册
from backend.app.db.base import Base
from backend.app.models.nqe_metadata import (
    NqeBusinessRule,
    NqeColumnInfo,
    NqeDimensionInfo,
    NqeDomain,
    NqeMetricInfo,
    NqeRetrievalChunk,
    NqeTableInfo,
)
from backend.app.services.nqe_metadata_sync import (
    NqeMetadataSyncBuilder,
    build_nqe_context_package_from_bundle,
    upsert_nqe_metadata_bundle,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CATALOG_ROOT = PROJECT_ROOT / "backend/app/domains/logistics/config/nl2sql_catalog"
SENSITIVE_WORDS = (
    "ho" + "st",
    "us" + "er",
    "pass" + "word",
    "d" + "sn",
    "tok" + "en",
    "api " + "key",
    "api" + "key",
    "sec" + "ret",
)


def test_builder_generates_non_empty_metadata_bundle() -> None:
    """验证 dry-run builder 能从现有受控 catalog 生成非空元数据资产。"""

    bundle = NqeMetadataSyncBuilder(CATALOG_ROOT).build()

    assert {domain["domain_code"] for domain in bundle.domains} >= {"logistics", "business_analysis", "plan_bom"}
    assert bundle.tables
    assert bundle.columns
    assert bundle.metrics
    assert bundle.dimensions
    assert bundle.business_rules
    assert bundle.retrieval_chunks
    assert bundle.metadata_versions
    assert bundle.quality_gates


def test_source_ref_is_relative_and_redacted() -> None:
    """验证 source_ref 不含本机绝对路径或敏感连接关键词。"""

    bundle = NqeMetadataSyncBuilder(CATALOG_ROOT).build()
    all_rows = (
        bundle.domains
        + bundle.data_sources
        + bundle.tables
        + bundle.columns
        + bundle.metrics
        + bundle.dimensions
        + bundle.business_rules
        + bundle.retrieval_chunks
        + bundle.metadata_versions
        + bundle.quality_gates
    )

    for row in all_rows:
        source_ref = row.get("source_ref") or ""
        assert not source_ref.startswith("/")
        assert str(Path.home()) not in source_ref
        assert not any(word in source_ref.lower() for word in SENSITIVE_WORDS)


def test_codes_are_idempotent_and_within_model_limit() -> None:
    """验证 code/chunk_code 幂等稳定，且长度不超过模型字段限制。"""

    first = NqeMetadataSyncBuilder(CATALOG_ROOT).build()
    second = NqeMetadataSyncBuilder(CATALOG_ROOT).build()

    first_codes = _collect_codes(first)
    second_codes = _collect_codes(second)
    assert first_codes == second_codes
    assert first_codes
    assert all(len(code) <= 128 for code in first_codes)


def test_upsert_twice_does_not_duplicate_rows() -> None:
    """验证 SQLite 内存库重复 upsert 后行数不翻倍。"""

    bundle = NqeMetadataSyncBuilder(CATALOG_ROOT).build()
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        first_stats = upsert_nqe_metadata_bundle(session, bundle)
        second_stats = upsert_nqe_metadata_bundle(session, bundle)

        assert first_stats == second_stats
        assert session.query(NqeDomain).count() == len(bundle.domains)
        assert session.query(NqeTableInfo).count() == len(bundle.tables)
        assert session.query(NqeColumnInfo).count() == len(bundle.columns)
        assert session.query(NqeMetricInfo).count() == len(bundle.metrics)
        assert session.query(NqeDimensionInfo).count() == len(bundle.dimensions)
        assert session.query(NqeBusinessRule).count() == len(bundle.business_rules)
        assert session.query(NqeRetrievalChunk).count() == len(bundle.retrieval_chunks)


def test_missing_yaml_file_fail_soft_with_warn(tmp_path: Path) -> None:
    """验证缺少某类 YAML 时只生成 warn 门禁，不抛不可恢复异常。"""

    (tmp_path / "tables.yaml").write_text(
        """
catalog_version: test.v1
domain: logistics
tables:
  - table_name: demo_table
    display_name: 演示表
    source_system: middle_db
    allowed_read: true
    columns:
      - {name: amount, data_type: decimal, business_name: 金额, semantic_role: metric}
""",
        encoding="utf-8",
    )
    (tmp_path / "metrics.yaml").write_text(
        """
catalog_version: test.v1
domain: logistics
metrics:
  - metric_id: demo_amount
    display_name: 演示金额
    table: demo_table
    aliases: [金额]
    aggregation: sum
""",
        encoding="utf-8",
    )
    (tmp_path / "dimensions.yaml").write_text(
        """
catalog_version: test.v1
domain: logistics
dimensions:
  - dimension_id: demo_month
    display_name: 演示月份
    table: demo_table
    column: biz_month
""",
        encoding="utf-8",
    )

    bundle = NqeMetadataSyncBuilder(tmp_path).build()

    assert bundle.tables
    assert any("rules.yaml" in warning for warning in bundle.warnings)
    assert bundle.quality_gates[0]["gate_status"] == "warn"


def test_cli_dry_run_writes_json_summary(tmp_path: Path) -> None:
    """验证 dry-run CLI 能生成 JSON 摘要。"""

    output_json = tmp_path / "dry-run-summary.json"
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/sync_nqe_metadata.py"),
            "--catalog-root",
            str(CATALOG_ROOT),
            "--output-json",
            str(output_json),
            "--metadata-version",
            "nqe_catalog_test",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "nqe_catalog_test" in result.stdout
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["metadata_version"] == "nqe_catalog_test"
    assert summary["counts"]["domains"] >= 3
    assert summary["counts"]["retrieval_chunks"] > 0
    assert summary["quality_gate_status"] in {"passed", "warn"}


def test_builder_include_domains_filters_logistics_only() -> None:
    """验证 include_domains 可只构建物流域，默认全域行为保持不变。"""

    full_bundle = NqeMetadataSyncBuilder(CATALOG_ROOT).build()
    logistics_bundle = NqeMetadataSyncBuilder(CATALOG_ROOT, include_domains=("logistics",)).build()

    assert {domain["domain_code"] for domain in logistics_bundle.domains} == {"logistics"}
    assert {table["domain_code"] for table in logistics_bundle.tables} == {"logistics"}
    assert "business_analysis" not in {domain["domain_code"] for domain in logistics_bundle.domains}
    assert "plan_bom" not in {domain["domain_code"] for domain in logistics_bundle.domains}
    assert len(logistics_bundle.tables) < len(full_bundle.tables)
    assert len(logistics_bundle.retrieval_chunks) < len(full_bundle.retrieval_chunks)


def test_context_package_from_bundle_is_safe_and_contains_logistics_assets() -> None:
    """验证从 bundle 生成的 NQE 上下文包只含非敏感字段与相对来源。"""

    bundle = NqeMetadataSyncBuilder(CATALOG_ROOT, include_domains=("logistics",), metadata_version="nqe_ctx_test").build()
    package = build_nqe_context_package_from_bundle(bundle)
    payload = json.dumps(package, ensure_ascii=False, sort_keys=True)

    assert package["ready"] is True
    assert package["domain_code"] == "logistics"
    assert package["metadata_version"] == "nqe_ctx_test"
    assert package["allowed_tables"]
    assert package["table_columns"]
    assert package["columns_by_table"] == package["table_columns"]
    assert package["retrieval_assets"]["summary"]["tables"] == len(package["allowed_tables"])
    assert str(Path.home()) not in payload
    assert not any(word in payload.lower() for word in SENSITIVE_WORDS)


def test_cli_domain_logistics_outputs_single_domain(tmp_path: Path) -> None:
    """验证 CLI --domain logistics dry-run 只输出物流单域摘要。"""

    output_json = tmp_path / "logistics-summary.json"
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/sync_nqe_metadata.py"),
            "--catalog-root",
            str(CATALOG_ROOT),
            "--output-json",
            str(output_json),
            "--metadata-version",
            "nqe_catalog_logistics_test",
            "--domain",
            "logistics",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "logistics" in result.stdout
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["domains"] == ["logistics"]
    assert summary["counts"]["domains"] == 1


def _collect_codes(bundle) -> list[str]:
    """收集 bundle 中所有需要验证长度与幂等性的编码。"""

    codes: list[str] = []
    for group_name in (
        "domains",
        "data_sources",
        "tables",
        "columns",
        "metrics",
        "dimensions",
        "business_rules",
        "retrieval_chunks",
        "metadata_versions",
        "quality_gates",
    ):
        for row in getattr(bundle, group_name):
            codes.append(row["code"])
            if "chunk_code" in row:
                codes.append(row["chunk_code"])
    return codes
