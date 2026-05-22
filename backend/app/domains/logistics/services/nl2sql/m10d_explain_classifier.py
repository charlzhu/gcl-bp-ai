from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.app.domains.logistics.services.nl2sql.sql_execution import (
    LogisticsSqlExecutionResult,
)

EXPLAIN_CLASSIFIER_VERSION = "logistics_nl2sql_m10d_explain_classifier.v1"

M10DExplainType = Literal[
    "SUCCESS",
    "ERROR_SYNTAX",
    "ERROR_TABLE",
    "ERROR_COLUMN",
    "ERROR_TIMEOUT",
    "ERROR_OTHER",
]

# 错误码模式 -> 分类类型映射，按优先级从高到低
_EXPLAIN_ERROR_CODE_PATTERNS: list[tuple[re.Pattern[str], M10DExplainType]] = [
    # 语法错误
    (re.compile(r"(?:pymysql_error|mysql_error|db_error)_?10(?:64|49)"), "ERROR_SYNTAX"),
    (re.compile(r"(?:pymysql_error|mysql_error|db_error)_?1149"), "ERROR_SYNTAX"),
    # 超时
    (re.compile(r"(?:pymysql_error|mysql_error|db_error|operational_error|gateway)_?timeout", re.IGNORECASE), "ERROR_TIMEOUT"),
    # 表不存在
    (re.compile(r"(?:pymysql_error|mysql_error|db_error)_?1146"), "ERROR_TABLE"),
    (re.compile(r"(?:pymysql_error|mysql_error|db_error)_?1051"), "ERROR_TABLE"),
    # 列不存在
    (re.compile(r"(?:pymysql_error|mysql_error|db_error)_?1054"), "ERROR_COLUMN"),
]

# 短分类名称
_EXPLAIN_TYPE_NAMES: dict[M10DExplainType, str] = {
    "SUCCESS": "EXPLAIN 通过",
    "ERROR_SYNTAX": "SQL 语法错误",
    "ERROR_TABLE": "表/视图不存在",
    "ERROR_COLUMN": "列不存在",
    "ERROR_TIMEOUT": "执行超时",
    "ERROR_OTHER": "其他 EXPLAIN 错误",
}


class LogisticsNl2SqlM10DExplainClassification(BaseModel):
    """EXPLAIN 结果脱敏分类。

    参数：
        version: 分类器版本标识。
        type: 分类类型。
        name: 业务化短名称。
        error_code: 脱敏后的稳定错误码（有匹配时保留第一个匹配码，否则为空字符串）。
    """

    model_config = ConfigDict(extra="forbid")

    version: str = EXPLAIN_CLASSIFIER_VERSION
    type: M10DExplainType
    name: str
    error_code: str = ""


def classify_explain_outcome(
    result: LogisticsSqlExecutionResult,
) -> LogisticsNl2SqlM10DExplainClassification:
    """将 EXPLAIN 执行结果按 type 脱敏分类。

    业务逻辑：
        1. ok=True 时直接分类为 SUCCESS。
        2. ok=False 时按 error_codes 中的错误码前缀匹配分类类型：
           - 匹配优先级从高到低（语法 > 超时 > 表 > 列 > 其他）。
           - 首个匹配即停止。
           - 无匹配时分类为 ERROR_OTHER。
        3. 所有分类结果不输出 SQL 原文、参数值、表名、字段名。

    参数：
        result: EXPLAIN 执行结果。

    返回：
        脱敏分类结果。
    """
    if result.ok:
        return LogisticsNl2SqlM10DExplainClassification(
            type="SUCCESS",
            name=_EXPLAIN_TYPE_NAMES["SUCCESS"],
        )

    # ok=False — 按 error_codes 匹配分类
    matched_type: M10DExplainType = "ERROR_OTHER"
    matched_code: str = ""

    for error_code in result.error_codes:
        for pattern, classify_type in _EXPLAIN_ERROR_CODE_PATTERNS:
            if pattern.search(error_code):
                matched_type = classify_type
                # error_code 脱敏：只保留匹配模式所在的前缀，去除业务敏感后缀
                match = pattern.search(error_code)
                if match:
                    matched_code = match.group(0)
                else:
                    matched_code = error_code.split("_", 3)[:3] if "_" in error_code else error_code[:30]
                break
        if matched_type != "ERROR_OTHER":
            break

    return LogisticsNl2SqlM10DExplainClassification(
        type=matched_type,
        name=_EXPLAIN_TYPE_NAMES[matched_type],
        error_code=matched_code,
    )


__all__ = [
    "EXPLAIN_CLASSIFIER_VERSION",
    "LogisticsNl2SqlM10DExplainClassification",
    "classify_explain_outcome",
]
