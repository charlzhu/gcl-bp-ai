from __future__ import annotations

import importlib

from backend.app.db.base import Base


EXPECTED_TABLES = [
    "nqe_domain",
    "nqe_data_source",
    "nqe_table_info",
    "nqe_column_info",
    "nqe_value_info",
    "nqe_value_index",
    "nqe_metric_info",
    "nqe_dimension_info",
    "nqe_business_rule",
    "nqe_retrieval_chunk",
    "nqe_query_trace",
    "nqe_query_trace_step",
    "nqe_sql_revision",
    "nqe_metadata_version",
    "nqe_quality_gate",
]


def test_nqe_metadata_models_are_registered() -> None:
    """验证 NQE 元数据模型已挂载到统一 Base.metadata。"""

    import backend.app.models as registered_models

    for table_name in EXPECTED_TABLES:
        assert table_name in Base.metadata.tables

    for model_name in [
        "NqeDomain",
        "NqeDataSource",
        "NqeTableInfo",
        "NqeColumnInfo",
        "NqeValueInfo",
        "NqeValueIndex",
        "NqeMetricInfo",
        "NqeDimensionInfo",
        "NqeBusinessRule",
        "NqeRetrievalChunk",
        "NqeQueryTrace",
        "NqeQueryTraceStep",
        "NqeSqlRevision",
        "NqeMetadataVersion",
        "NqeQualityGate",
    ]:
        assert hasattr(registered_models, model_name)


def test_nqe_metadata_key_columns_exist() -> None:
    """验证首批 NQE 表覆盖元数据、召回、审计和治理关键字段。"""

    import backend.app.models  # noqa: F401  # 导入后触发模型注册

    required_columns = {
        "nqe_data_source": {"source_kind", "logical_name", "readonly_required", "connection_ref", "allow_explain", "timeout_ms", "max_rows"},
        "nqe_table_info": {"data_source_code", "physical_table_name", "table_role", "grain", "allow_select", "allow_detail", "default_limit_rows", "max_limit_rows", "sensitive_level"},
        "nqe_column_info": {
            "table_code",
            "column_code",
            "physical_column_name",
            "data_type",
            "semantic_type",
            "is_filterable",
            "is_groupable",
            "is_aggregatable",
            "allowed_aggregations",
            "sensitive_level",
            "sample_values_json",
            "value_index_enabled",
            "synonyms_json",
            "unit",
        },
        "nqe_value_info": {
            "code",
            "domain_code",
            "table_code",
            "column_code",
            "value_code",
            "raw_value",
            "normalized_value",
            "display_value",
            "aliases_json",
            "pinyin_key",
            "value_freq",
            "last_seen_at",
            "quality_status",
        },
        "nqe_value_index": {
            "code",
            "domain_code",
            "table_code",
            "column_code",
            "normalized_value",
            "display_value",
            "match_text",
            "aliases_text",
            "freq",
            "quality_score",
            "source_snapshot",
        },
        "nqe_metric_info": {"metric_code", "metric_type", "default_aggregation", "formula_text", "sql_expression_template", "base_table_code", "fallback_required"},
        "nqe_dimension_info": {"dimension_code", "dimension_type", "table_code", "column_code", "hierarchy_json"},
        "nqe_business_rule": {"rule_code", "rule_type", "title", "rule_text", "applies_to_json", "priority", "requires_clarification", "fallback_required", "visible_to_user"},
        "nqe_retrieval_chunk": {"chunk_code", "asset_type", "asset_id", "asset_code", "chunk_text", "keywords_json", "synonyms_json", "embedding_model", "embedding_hash", "index_status", "last_indexed_at"},
        "nqe_query_trace": {"trace_id", "user_question", "gray_mode", "route_status", "final_status", "selected_tables_json", "selected_metrics_json", "final_sql_hash", "result_row_count", "latency_ms", "fallback_used", "old_query_log_id", "error_code", "error_message"},
        "nqe_query_trace_step": {"trace_id", "step_order", "node_name", "step_status", "input_summary_json", "output_summary_json", "prompt_code", "prompt_version", "latency_ms", "error_message"},
        "nqe_sql_revision": {"trace_id", "revision_no", "source", "sql_hash", "sql_redacted", "metadata_version", "prompt_version", "safety_status", "explain_status", "error_code"},
        "nqe_metadata_version": {"metadata_version", "version_status", "published_by", "published_at", "rollback_from_version", "change_note"},
        "nqe_quality_gate": {"gate_code", "gate_type", "metadata_version", "gate_status", "passed_count", "failed_count", "report_ref", "error_message"},
    }

    for table_name, column_names in required_columns.items():
        actual_columns = set(Base.metadata.tables[table_name].columns.keys())
        assert column_names <= actual_columns


def test_nqe_metadata_migration_shape() -> None:
    """验证 Alembic 迁移链路和首批建表清单。"""

    migration = importlib.import_module("backend.alembic.versions.20260523_0006_create_nqe_metadata_tables")
    value_migration = importlib.import_module("backend.alembic.versions.20260523_0007_create_nqe_value_index_tables")

    assert migration.revision == "20260523_0006"
    assert migration.down_revision == "20260518_0005"
    assert set(migration.NQE_TABLES) <= set(EXPECTED_TABLES)
    assert value_migration.revision == "20260523_0007"
    assert value_migration.down_revision == "20260523_0006"


def test_nqe_value_tables_constraints_and_indexes_exist() -> None:
    """验证 value 表关键唯一约束和索引存在。"""

    import backend.app.models  # noqa: F401  # 导入后触发模型注册

    value_info = Base.metadata.tables["nqe_value_info"]
    value_index = Base.metadata.tables["nqe_value_index"]

    info_constraints = {constraint.name for constraint in value_info.constraints}
    index_constraints = {constraint.name for constraint in value_index.constraints}
    assert "uk_nqe_value_info_table_column_value" in info_constraints
    assert "uk_nqe_value_index_domain_table_column_value" in index_constraints

    info_indexes = {index.name for index in value_info.indexes}
    value_indexes = {index.name for index in value_index.indexes}
    assert "idx_nqe_value_info_domain_column_value" in info_indexes
    assert "idx_nqe_value_info_domain_column_freq" in info_indexes
    assert "idx_nqe_value_index_domain_column_match" in value_indexes
    assert "idx_nqe_value_index_domain_column_freq" in value_indexes
