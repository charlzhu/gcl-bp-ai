from __future__ import annotations

import pytest

from backend.app.domains.logistics.services.nl2sql.candidate_sql_gate import (
    LogisticsCandidateSqlGate,
    check_logistics_candidate_sql,
)


def test_candidate_sql_gate_allows_simple_select_with_limit() -> None:
    """candidate SQL gate 应允许单条简单 SELECT + LIMIT 进入 shadow 后续分析。"""

    result = check_logistics_candidate_sql("SELECT biz_year FROM dws_logistics_detail_union LIMIT 20")

    assert result.allowed is True
    assert result.rejected is False
    assert result.reason_code == "allowed"
    assert result.sanitized_reason == "candidate_sql_allowed"
    assert result.repair_info is None


@pytest.mark.parametrize(
    ("sql", "expected_code"),
    [
        ("", "empty_sql"),
        ("SELECT biz_year FROM dws_logistics_detail_union", "missing_limit"),
        ("SELECT biz_year FROM dws_logistics_detail_union LIMIT 10; DROP TABLE sys_user", "multi_statement"),
        ("SELECT biz_year FROM dws_logistics_detail_union -- bypass\n LIMIT 10", "comment_forbidden"),
        ("SELECT biz_year FROM dws_logistics_detail_union /* bypass */ LIMIT 10", "comment_forbidden"),
        ("UPDATE dws_logistics_detail_union SET biz_year = 2026 LIMIT 1", "write_or_ddl_forbidden"),
    ],
)
def test_candidate_sql_gate_rejects_basic_fail_closed_shapes(sql: str, expected_code: str) -> None:
    """空 SQL、缺 LIMIT、多语句、注释和非 SELECT 必须 fail-closed。"""

    result = LogisticsCandidateSqlGate().check(sql)

    assert result.allowed is False
    assert result.rejected is True
    assert result.reason_code == expected_code
    assert result.sanitized_reason.startswith("candidate_sql_rejected:")


@pytest.mark.parametrize(
    ("sql", "expected_code"),
    [
        ("SELECT biz_year FROM dws_logistics_detail_union UNION SELECT password FROM sys_user LIMIT 10", "union_forbidden"),
        ("SELECT biz_year FROM dws_logistics_detail_union INTO OUTFILE '/tmp/leak.csv' LIMIT 10", "into_outfile_forbidden"),
        ("SELECT LOAD_FILE('/etc/passwd') FROM dws_logistics_detail_union LIMIT 10", "load_file_forbidden"),
        ("SELECT SLEEP(1) FROM dws_logistics_detail_union LIMIT 10", "sleep_forbidden"),
        ("SELECT BENCHMARK(100000, SHA1('x')) FROM dws_logistics_detail_union LIMIT 10", "benchmark_forbidden"),
        ("SELECT biz_year FROM dws_logistics_detail_union LIMIT 10 FOR UPDATE", "for_update_forbidden"),
        ("LOCK TABLES dws_logistics_detail_union READ", "lock_forbidden"),
        ("START TRANSACTION", "transaction_forbidden"),
    ],
)
def test_candidate_sql_gate_rejects_high_risk_tokens(sql: str, expected_code: str) -> None:
    """UNION、文件/延迟函数、FOR UPDATE、LOCK、事务等高风险 token 必须拒绝。"""

    result = check_logistics_candidate_sql(sql)

    assert result.allowed is False
    assert result.reason_code == expected_code


def test_candidate_sql_gate_rejects_limit_above_max_with_repair_info() -> None:
    """LIMIT 超过上限时 M10-A 先拒绝，并给出确定性修复提示，不自动下调。"""

    result = LogisticsCandidateSqlGate(max_limit=500).check(
        "SELECT biz_year FROM dws_logistics_detail_union LIMIT 9999"
    )

    assert result.allowed is False
    assert result.reason_code == "limit_out_of_range"
    assert result.repair_info == {"suggested_action": "lower_limit", "max_limit": 500}


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT FROM dws_logistics_detail_union LIMIT 1",
        "SELECT biz_year FROM LIMIT 10",
        "SELECT biz_year FROM dws_logistics_detail_union WHERE biz_year = 2025 LIMIT 10 OFFSET 5",
    ],
)
def test_candidate_sql_gate_rejects_structure_uncertain_selects(sql: str) -> None:
    """无解析器时，畸形 SELECT 或非受控 LIMIT 变体必须按结构不确定拒绝。"""

    result = check_logistics_candidate_sql(sql)

    assert result.allowed is False
    assert result.reason_code == "structure_uncertain"


def test_candidate_sql_gate_rejects_dml_keyword_inside_select_candidate() -> None:
    """SELECT 形态中夹带 DML 关键字也必须 fail-closed，不能只看开头是否 SELECT。"""

    result = check_logistics_candidate_sql(
        "SELECT biz_year FROM dws_logistics_detail_union UPDATE sys_user SET biz_year = 2026 LIMIT 1"
    )

    assert result.allowed is False
    assert result.reason_code == "write_or_ddl_forbidden"


@pytest.mark.parametrize(
    ("sql", "expected_code"),
    [
        ("SELECT biz_year INTO @x FROM dws_logistics_detail_union LIMIT 1", "into_forbidden"),
        ("SELECT GET_LOCK('nl2sql', 1) FROM dws_logistics_detail_union LIMIT 1", "lock_forbidden"),
        ("SELECT RELEASE_LOCK('nl2sql') FROM dws_logistics_detail_union LIMIT 1", "lock_forbidden"),
        ("SELECT biz_year FROM dws_logistics_detail_union RANDOM_GARBAGE LIMIT 20", "structure_uncertain"),
    ],
)
def test_candidate_sql_gate_rejects_reviewer_found_unsafe_select_variants(
    sql: str,
    expected_code: str,
) -> None:
    """审查发现的 SELECT INTO、副作用锁函数和未知子句也必须 fail-closed。"""

    result = check_logistics_candidate_sql(sql)

    assert result.allowed is False
    assert result.reason_code == expected_code


def test_candidate_sql_gate_returns_structured_rejection_for_extreme_limit_digits() -> None:
    """超长 LIMIT 数字不能冒泡异常，必须返回结构化拒绝结果。"""

    result = check_logistics_candidate_sql(
        "SELECT biz_year FROM dws_logistics_detail_union LIMIT " + "9" * 5000
    )

    assert result.allowed is False
    assert result.reason_code == "limit_out_of_range"


def test_candidate_sql_gate_reason_does_not_echo_full_sql_or_sensitive_values() -> None:
    """危险输入的可见 reason 必须脱敏，不能回显完整 SQL 或敏感值。"""

    sql = "SELECT LOAD_FILE('/etc/passwd') AS api_key FROM sys_user WHERE credential_value = 'sensitive-example' LIMIT 10"

    result = check_logistics_candidate_sql(sql)

    assert result.allowed is False
    assert result.reason_code == "load_file_forbidden"
    assert sql not in result.sanitized_reason
    assert "/etc/passwd" not in result.sanitized_reason
    assert "sensitive-example" not in result.sanitized_reason
    assert "sys_user" not in result.sanitized_reason
