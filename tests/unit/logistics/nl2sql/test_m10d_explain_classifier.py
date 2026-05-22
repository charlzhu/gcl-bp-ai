#!/usr/bin/env python
"""M11-2：M10D EXPLAIN 结果分类器 focused tests。

目标：
    验证 LogisticsNl2SqlM10DExplainClassifier 能正确将 EXPLAIN 输出
    按 type 脱敏分类，不输出 SQL 原文、参数值、表名、字段名。
"""

from __future__ import annotations

from backend.app.domains.logistics.services.nl2sql.m10d_explain_classifier import (
    LogisticsNl2SqlM10DExplainClassification,
    classify_explain_outcome,
    EXPLAIN_CLASSIFIER_VERSION,
)
from backend.app.domains.logistics.services.nl2sql.sql_execution import (
    LogisticsSqlExecutionResult,
)


def _gen_result(ok: bool, error_codes: list[str] | None = None, explain_rows: list[dict] | None = None) -> LogisticsSqlExecutionResult:
    """构造测试用 EXPLAIN 结果。"""
    return LogisticsSqlExecutionResult(
        ok=ok,
        mode="explain",
        rows=explain_rows or [],
        errors=error_codes or [],
    )


# ── SUCCESS ──────────────────────────────────────────────────────


def test_classify_success_empty_explain() -> None:
    """EXPLAIN 通过但无行时仍分类为 SUCCESS。"""
    result = _gen_result(ok=True, explain_rows=[])
    classification = classify_explain_outcome(result)
    assert classification.type == "SUCCESS"
    assert classification.version == EXPLAIN_CLASSIFIER_VERSION
    assert classification.error_code == ""


def test_classify_success_with_rows() -> None:
    """EXPLAIN 通过且有行时分类为 SUCCESS。"""
    result = _gen_result(ok=True, explain_rows=[{"select_type": "SIMPLE", "table": "dws_logistics_detail_union"}])
    classification = classify_explain_outcome(result)
    assert classification.type == "SUCCESS"
    assert classification.error_code == ""


# ── ERROR_SYNTAX ──────────────────────────────────────────────────


def test_classify_syntax_error_1064() -> None:
    """MySQL 1064 语法错误分类为 ERROR_SYNTAX。"""
    result = _gen_result(ok=False, error_codes=["pymysql_error_1064_syntax_error"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_SYNTAX"
    # error_code 只保留匹配前缀，脱敏去除业务敏感后缀
    assert classification.error_code == "pymysql_error_1064"


def test_classify_syntax_error_1149() -> None:
    """MySQL 1149 语法错误分类为 ERROR_SYNTAX。"""
    result = _gen_result(ok=False, error_codes=["pymysql_error_1149"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_SYNTAX"


# ── ERROR_TABLE ──────────────────────────────────────────────────


def test_classify_table_not_found_1146() -> None:
    """MySQL 1146 表不存在分类为 ERROR_TABLE。"""
    result = _gen_result(ok=False, error_codes=["pymysql_error_1146_table_not_found"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_TABLE"
    assert "1146" in classification.error_code


def test_classify_table_not_found_1051() -> None:
    """MySQL 1051 未知表分类为 ERROR_TABLE。"""
    result = _gen_result(ok=False, error_codes=["pymysql_error_1051_unknown_table"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_TABLE"


# ── ERROR_COLUMN ────────────────────────────────────────────────


def test_classify_column_not_found_1054() -> None:
    """MySQL 1054 列不存在分类为 ERROR_COLUMN。"""
    result = _gen_result(ok=False, error_codes=["pymysql_error_1054_unknown_column"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_COLUMN"


# ── ERROR_TIMEOUT ──────────────────────────────────────────────


def test_classify_timeout_pymysql() -> None:
    """PyMySQL 超时错误分类为 ERROR_TIMEOUT。"""
    result = _gen_result(ok=False, error_codes=["pymysql_error_timeout"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_TIMEOUT"


def test_classify_timeout_operational() -> None:
    """数据库操作超时分类为 ERROR_TIMEOUT。"""
    result = _gen_result(ok=False, error_codes=["operational_error_timeout"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_TIMEOUT"


def test_classify_timeout_gateway() -> None:
    """网关超时分类为 ERROR_TIMEOUT。"""
    result = _gen_result(ok=False, error_codes=["gateway_timeout"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_TIMEOUT"


# ── ERROR_OTHER ──────────────────────────────────────────────────


def test_classify_other_generic_error() -> None:
    """无特定错误码时分类为 ERROR_OTHER。"""
    result = _gen_result(ok=False, error_codes=["generic_db_error"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_OTHER"


def test_classify_other_unknown_code() -> None:
    """不认识的自定义错误码分类为 ERROR_OTHER。"""
    result = _gen_result(ok=False, error_codes=["custom_unexpected_failure"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_OTHER"


def test_classify_other_multiple_unknown() -> None:
    """多个不认识错误码分类为 ERROR_OTHER。"""
    result = _gen_result(ok=False, error_codes=["err_a", "err_b", "err_c"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_OTHER"


# ── ERROR_COLUMN variants ────────────────────────────────────────


def test_classify_column_not_found_other_dialect() -> None:
    """列不存在错误，非标准前缀也正确识别。"""
    result = _gen_result(ok=False, error_codes=["mysql_error_1054"])
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_COLUMN"


# ── 脱敏边界 ──────────────────────────────────────────────────


def test_classification_never_exposes_sql() -> None:
    """分类结果不输出 SQL 原文、表名、字段名。"""
    result = _gen_result(ok=False, error_codes=["pymysql_error_1146_table_not_found"])
    classification = classify_explain_outcome(result)
    payload = classification.model_dump_json()
    assert "SELECT" not in payload
    assert "dws_logistics_detail_union" not in payload
    assert "shipment_mw" not in payload


def test_classification_error_code_no_table_name() -> None:
    """error_code 不暴露表名或字段名。"""
    result = _gen_result(ok=False, error_codes=["pymysql_error_1054_unknown_column_shipment_mw"])
    classification = classify_explain_outcome(result)
    classification = classify_explain_outcome(result)
    assert classification.type == "ERROR_COLUMN"
    # 错误码只保留稳定前缀，不会泄露业务字段名
    assert "shipment_mw" not in classification.error_code


# ── OK 路径 ──────────────────────────────────────────────────


def test_classify_with_safety_reason_code() -> None:
    """传入可选 reason 参数时正常传递。"""
    result = _gen_result(ok=True, explain_rows=[])
    classification = classify_explain_outcome(result)
    assert classification.type == "SUCCESS"
    assert classification.name == "EXPLAIN 通过"
