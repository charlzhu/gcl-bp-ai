from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import backend.app.models  # noqa: F401  # 触发 NQE 模型注册
from backend.app.db.base import Base
from backend.app.models.nqe_metadata import NqeValueIndex, NqeValueInfo
from backend.app.services.nqe_metadata_sync import NqeMetadataSyncBuilder
from backend.app.services.nqe_value_index import (
    NqeValueCandidate,
    NqeValueIndexBuilder,
    NqeValueIndexColumnSpec,
    NqeValueRecallService,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CATALOG_ROOT = PROJECT_ROOT / "backend/app/domains/logistics/config/nl2sql_catalog"
SENSITIVE_WORDS = (
    "pass" + "word",
    "pass" + "wd",
    "tok" + "en",
    "api" + "key",
    "api_" + "key",
    "d" + "sn",
    "connection string",
)


class FakeResult:
    """模拟 SQLAlchemy execute 结果。"""

    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def mappings(self) -> "FakeResult":
        """返回自身以支持 mappings().all() 链式调用。"""

        return self

    def all(self) -> list[dict]:
        """返回 fake 行。"""

        return self.rows


class FakeSession:
    """记录 execute 调用的 fake session。"""

    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []

    def execute(self, sql, params=None) -> FakeResult:
        """记录 SQL 文本并返回固定 distinct 行。"""

        self.executed.append((str(sql), params or {}))
        return FakeResult([{"raw_value": "华东", "freq": 12}, {"raw_value": "华南", "freq": 8}])


def test_catalog_examples_generate_value_candidates() -> None:
    """验证 catalog 安全样例值能生成非空 value candidates。"""

    bundle = NqeMetadataSyncBuilder(CATALOG_ROOT, metadata_version="nqe_value_test").build()
    candidates, summary = NqeValueIndexBuilder().build_from_catalog_examples(bundle)

    assert candidates
    assert summary.total_values == len(candidates)
    assert {"logistics", "business_analysis", "plan_bom"} <= set(summary.domain_counts)
    assert all(candidate.domain_code and candidate.table_code and candidate.column_code for candidate in candidates)
    assert any(candidate.display_value == "华东" for candidate in candidates)


def test_column_whitelist_skips_sensitive_disabled_and_non_filterable() -> None:
    """验证敏感、未启用、不可过滤不可分组字段不会进入白名单。"""

    tables = [
        {
            "code": "table_demo",
            "domain_code": "logistics",
            "physical_table_name": "demo_table",
            "allow_select": 1,
            "status": "draft",
            "is_active": 1,
        }
    ]
    columns = [
        _column("ok_col", "ok_col", value_index_enabled=1, is_filterable=1),
        _column("secret_col", "secret_col", value_index_enabled=1, is_filterable=1, sensitive_level="secret"),
        _column("disabled_col", "disabled_col", value_index_enabled=0, is_filterable=1),
        _column("measure_col", "measure_col", value_index_enabled=1, is_filterable=0, is_groupable=0),
    ]

    specs, summary = NqeValueIndexBuilder().build_column_specs_from_metadata(tables, columns)

    assert [spec.column_code for spec in specs] == ["ok_col"]
    assert summary.skipped_columns == 3
    assert any("敏感字段" in warning for warning in summary.warnings)


def test_invalid_identifiers_are_skipped_and_no_sql_is_generated() -> None:
    """验证非法表名或字段名会被跳过，dry-run 不执行 SQL。"""

    fake_session = FakeSession()
    specs = [
        NqeValueIndexColumnSpec(
            domain_code="logistics",
            table_code="table_bad",
            column_code="col_bad",
            physical_table_name="demo_table;drop",
            physical_column_name="ok_col",
            value_index_enabled=True,
        )
    ]

    candidates, summary = NqeValueIndexBuilder().build_from_mysql(fake_session, specs, dry_run=True)

    assert candidates == []
    assert fake_session.executed == []
    assert summary.indexed_columns == 0
    assert summary.skipped_columns == 1
    assert any("非法表名" in warning for warning in summary.warnings)


def test_dry_run_mysql_does_not_execute_session() -> None:
    """验证 dry-run MySQL 构建不调用 session.execute。"""

    fake_session = FakeSession()
    specs = [_spec()]

    candidates, summary = NqeValueIndexBuilder().build_from_mysql(fake_session, specs, dry_run=True)

    assert candidates == []
    assert fake_session.executed == []
    assert summary.dry_run is True
    assert summary.indexed_columns == 1


def test_apply_mysql_uses_limited_whitelisted_distinct_sql() -> None:
    """验证 apply 模式 SQL 带 LIMIT、超时 hint，且只使用白名单标识符。"""

    fake_session = FakeSession()
    candidates, summary = NqeValueIndexBuilder().build_from_mysql(fake_session, [_spec()], limit_per_column=2, timeout_ms=3000, dry_run=False)

    assert len(candidates) == 2
    assert summary.dry_run is False
    assert len(fake_session.executed) == 1
    sql_text, params = fake_session.executed[0]
    assert "MAX_EXECUTION_TIME(3000)" in sql_text
    assert "LIMIT :limit" in sql_text
    assert params["limit"] == 2
    assert "`demo_table`" in sql_text
    assert "`region_name`" in sql_text
    assert "drop" not in sql_text.lower()


def test_upsert_twice_does_not_duplicate_value_rows() -> None:
    """验证候选值重复 upsert 不会产生重复 value_info/value_index 行。"""

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    candidates = [
        NqeValueCandidate(
            domain_code="logistics",
            table_code="table_demo",
            column_code="region_name",
            raw_value="华东",
            normalized_value="华东",
            display_value="华东",
            aliases=["华东地区"],
            freq=3,
        )
    ]

    with Session(engine) as session:
        builder = NqeValueIndexBuilder()
        first = builder.upsert_value_candidates(session, candidates, metadata_version="nqe_value_test")
        second = builder.upsert_value_candidates(session, candidates, metadata_version="nqe_value_test")

        assert first == second == {"value_info": 1, "value_index": 1}
        assert session.query(NqeValueInfo).count() == 1
        assert session.query(NqeValueIndex).count() == 1


def test_recall_exact_alias_contains_topk_and_disambiguation() -> None:
    """验证 value recall 支持精确、别名、包含匹配、topK 和近分消歧。"""

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    candidates = [
        NqeValueCandidate(
            domain_code="logistics",
            table_code="table_a",
            column_code="region_name",
            raw_value="华东",
            normalized_value="华东",
            display_value="华东",
            aliases=["华东地区"],
            freq=10,
        ),
        NqeValueCandidate(
            domain_code="logistics",
            table_code="table_b",
            column_code="delivery_area",
            raw_value="华东",
            normalized_value="华东",
            display_value="华东",
            aliases=["华东片区"],
            freq=9,
        ),
        NqeValueCandidate(
            domain_code="logistics",
            table_code="table_c",
            column_code="city",
            raw_value="上海",
            normalized_value="上海",
            display_value="上海",
            aliases=["沪"],
            freq=1,
        ),
    ]

    with Session(engine) as session:
        NqeValueIndexBuilder().upsert_value_candidates(session, candidates)
        exact = NqeValueRecallService(session).recall(query_terms=["华东"], domain_code="logistics", top_k=2)
        alias = NqeValueRecallService(session).recall(query_terms=["沪"], domain_code="logistics", top_k=5)
        contains = NqeValueRecallService(session).recall(query_terms=["请看上海地区"], domain_code="logistics", top_k=5)

        assert len(exact) == 2
        assert exact[0].matched_by == "exact"
        assert exact[0].score_breakdown["base"] == 1.0
        assert exact[0].needs_disambiguation is True
        assert alias[0].display_value == "上海"
        assert alias[0].matched_by == "alias"
        assert contains[0].matched_by == "contains"


def test_cli_dry_run_writes_json_summary(tmp_path: Path) -> None:
    """验证 value index CLI dry-run 能生成 JSON 摘要。"""

    output_json = tmp_path / "dry-run-summary.json"
    result = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/rebuild_nqe_value_index.py"),
            "--catalog-root",
            str(CATALOG_ROOT),
            "--output-json",
            str(output_json),
            "--metadata-version",
            "nqe_value_cli_test",
            "--limit-per-column",
            "20",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    assert "nqe_value_cli_test" in result.stdout
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["metadata_version"] == "nqe_value_cli_test"
    assert summary["dry_run"] is True
    assert summary["total_values"] > 0
    assert summary["indexed_columns"] > 0
    assert summary["domain_counts"]["logistics"] > 0


def test_scoped_output_contains_no_local_paths_or_credentials(tmp_path: Path) -> None:
    """验证 CLI 摘要不含本机绝对路径、真实连接凭证或禁用外部标识。"""

    output_json = tmp_path / "dry-run-summary.json"
    subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts/rebuild_nqe_value_index.py"),
            "--catalog-root",
            str(CATALOG_ROOT),
            "--output-json",
            str(output_json),
        ],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )

    payload_text = output_json.read_text(encoding="utf-8")
    lower_payload = payload_text.lower()
    assert str(Path.home()) not in payload_text
    assert str(PROJECT_ROOT) not in payload_text
    assert not any(word in lower_payload for word in SENSITIVE_WORDS)


def _spec() -> NqeValueIndexColumnSpec:
    """返回测试用合法字段白名单。"""

    return NqeValueIndexColumnSpec(
        domain_code="logistics",
        table_code="table_demo",
        column_code="region_name",
        physical_table_name="demo_table",
        physical_column_name="region_name",
        semantic_type="dimension",
        sensitive_level="normal",
        value_index_enabled=True,
    )


def _column(
    column_code: str,
    physical_column_name: str,
    *,
    value_index_enabled: int,
    is_filterable: int = 0,
    is_groupable: int = 0,
    sensitive_level: str = "normal",
) -> dict:
    """返回测试用字段元数据。"""

    return {
        "code": f"col_{column_code}",
        "domain_code": "logistics",
        "table_code": "table_demo",
        "column_code": column_code,
        "physical_column_name": physical_column_name,
        "semantic_type": "dimension",
        "sensitive_level": sensitive_level,
        "value_index_enabled": value_index_enabled,
        "is_filterable": is_filterable,
        "is_groupable": is_groupable,
        "status": "draft",
        "is_active": 1,
    }
