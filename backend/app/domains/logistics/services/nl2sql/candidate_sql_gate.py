from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


COMMENT_MARKERS = ("--", "#", "/*", "*/")
LIMIT_ANY_RE = re.compile(r"\bLIMIT\b", re.IGNORECASE)
LIMIT_RE = re.compile(r"\bLIMIT\s+(?P<limit>\d+)\s*$", re.IGNORECASE)
MAX_LIMIT_DIGITS = 18
SELECT_WITH_LIMIT_RE = re.compile(
    r"^\s*SELECT\s+(?P<select>.+?)\s+FROM\s+"
    r"(?P<table>[A-Za-z_][A-Za-z0-9_]*)(?P<body>.*?)\s+LIMIT\s+(?P<limit>\d+)\s*$",
    re.IGNORECASE | re.DOTALL,
)
RESERVED_TABLE_IDENTIFIERS = {"from", "where", "group", "order", "limit", "select", "union"}


class LogisticsCandidateSqlGateResult(BaseModel):
    """候选 SQL 安全门禁的结构化返回。"""

    model_config = ConfigDict(extra="forbid")

    allowed: bool
    rejected: bool
    reason_code: str
    sanitized_reason: str
    repair_info: dict[str, Any] | None = Field(default=None)


class LogisticsCandidateSqlGate:
    """物流 NL2SQL candidate SQL 的 shadow-only 安全门禁。

    业务逻辑：
        本类只接收候选 SQL 字符串并做保守文本门禁，不执行 SQL，也不接入正式物流 QA
        主链路。M10-A 阶段不依赖 sqlglot；遇到不确定形态时按 fail-closed 处理。
    """

    def __init__(self, *, max_limit: int = 500) -> None:
        """初始化 candidate SQL gate。

        参数：
            max_limit: M10-A shadow gate 接受的最大 LIMIT；超过时先拒绝，不自动下调。
        返回：
            无。
        """

        self.max_limit = max_limit

    def check(self, sql: str | None) -> LogisticsCandidateSqlGateResult:
        """校验候选 SQL 字符串。

        参数：
            sql: LLM/候选生成器输出的原始 SQL 字符串。
        返回：
            `LogisticsCandidateSqlGateResult`，包含 allowed/rejected、稳定 reason code、
            脱敏 reason 和可选修复提示。
        """

        normalized_sql = (sql or "").strip()
        if not normalized_sql:
            return self._reject("empty_sql", {"suggested_action": "provide_select_with_limit"})

        lower_sql = normalized_sql.lower()
        basic_rejection = self._check_basic_shape(normalized_sql, lower_sql)
        if basic_rejection is not None:
            return basic_rejection

        risk_rejection = self._check_high_risk_tokens(lower_sql)
        if risk_rejection is not None:
            return risk_rejection

        if not lower_sql.startswith("select"):
            return self._reject("not_select", {"suggested_action": "use_single_select"})

        if not LIMIT_ANY_RE.search(normalized_sql):
            repair = {"suggested_action": "add_limit", "max_limit": self.max_limit}
            return self._reject("missing_limit", repair)
        if not LIMIT_RE.search(normalized_sql):
            return self._reject("structure_uncertain", {"suggested_action": "use_plain_numeric_limit"})

        if not re.search(r"\bfrom\b", lower_sql):
            return self._reject("structure_uncertain", {"suggested_action": "use_select_from_limit"})

        structure_match = SELECT_WITH_LIMIT_RE.search(normalized_sql)
        if not structure_match or not self._select_structure_is_safe(structure_match):
            return self._reject("structure_uncertain", {"suggested_action": "use_select_from_limit"})

        limit_token = structure_match.group("limit")
        if len(limit_token) > MAX_LIMIT_DIGITS:
            repair = {"suggested_action": "lower_limit", "max_limit": self.max_limit}
            return self._reject("limit_out_of_range", repair)

        try:
            limit_value = int(limit_token)
        except ValueError:
            repair = {"suggested_action": "use_plain_numeric_limit", "max_limit": self.max_limit}
            return self._reject("limit_out_of_range", repair)

        if limit_value < 1 or limit_value > self.max_limit:
            repair = {"suggested_action": "lower_limit", "max_limit": self.max_limit}
            return self._reject("limit_out_of_range", repair)

        return LogisticsCandidateSqlGateResult(
            allowed=True,
            rejected=False,
            reason_code="allowed",
            sanitized_reason="candidate_sql_allowed",
            repair_info=None,
        )

    def _select_structure_is_safe(self, match: re.Match[str]) -> bool:
        """在无 SQL 解析器时做最小 SELECT/FROM/LIMIT 形态确认。

        参数：
            match: `SELECT_WITH_LIMIT_RE` 对候选 SQL 的匹配结果。
        返回：
            True 表示该候选满足 M10-A 可证明的最小结构；False 表示结构不确定。
        业务逻辑：
            这里只证明 select list 非空、FROM 后有普通表名、LIMIT 为末尾数字，且 FROM 与 LIMIT
            之间没有额外未解析子句。复杂或变体语法留给后续 sqlglot/renderer 阶段，
            本 gate 先 fail-closed。
        """

        select_list = match.group("select").strip()
        table_name = match.group("table").strip().lower()
        body = match.group("body").strip()
        if not select_list or select_list.lower() in RESERVED_TABLE_IDENTIFIERS:
            return False
        if table_name in RESERVED_TABLE_IDENTIFIERS:
            return False
        if body:
            return False
        return True

    def _check_basic_shape(
        self,
        sql: str,
        lower_sql: str,
    ) -> LogisticsCandidateSqlGateResult | None:
        """校验空白之外的最基础危险形态。

        参数：
            sql: 原始 SQL。
            lower_sql: 小写 SQL。
        返回：
            发现危险形态时返回拒绝结果，否则返回 None。
        """

        if ";" in sql:
            return self._reject("multi_statement", {"suggested_action": "use_single_select"})
        if any(marker in sql for marker in COMMENT_MARKERS):
            return self._reject("comment_forbidden")
        if re.search(r"\bunion\b", lower_sql):
            return self._reject("union_forbidden")
        return None

    def _check_high_risk_tokens(self, lower_sql: str) -> LogisticsCandidateSqlGateResult | None:
        """校验高风险关键字、函数和事务/锁语句。

        参数：
            lower_sql: 小写 SQL。
        返回：
            命中风险时返回拒绝结果，否则返回 None。
        """

        high_risk_patterns = [
            (r"\binto\s+outfile\b", "into_outfile_forbidden"),
            (r"\binto\s+dumpfile\b", "into_outfile_forbidden"),
            (r"\binto\b", "into_forbidden"),
            (r"\bload_file\s*\(", "load_file_forbidden"),
            (r"\bsleep\s*\(", "sleep_forbidden"),
            (r"\bbenchmark\s*\(", "benchmark_forbidden"),
            (r"\b(get_lock|release_lock|is_free_lock|is_used_lock)\s*\(", "lock_forbidden"),
            (r"\bfor\s+update\b", "for_update_forbidden"),
            (r"\block\b", "lock_forbidden"),
            (r"\b(start\s+transaction|begin|commit|rollback|savepoint)\b", "transaction_forbidden"),
            (
                r"\b(drop|alter|truncate|create|insert|update|upsert|delete|merge|call|grant|revoke|replace|copy|set|use|show|describe)\b",
                "write_or_ddl_forbidden",
            ),
        ]
        for pattern, reason_code in high_risk_patterns:
            if re.search(pattern, lower_sql):
                return self._reject(reason_code)
        return None

    @staticmethod
    def _reject(
        reason_code: str,
        repair_info: dict[str, Any] | None = None,
    ) -> LogisticsCandidateSqlGateResult:
        """构造脱敏拒绝结果。

        参数：
            reason_code: 稳定拒绝原因码。
            repair_info: 可选修复提示，不包含原始 SQL。
        返回：
            rejected=True 的结构化结果。
        """

        return LogisticsCandidateSqlGateResult(
            allowed=False,
            rejected=True,
            reason_code=reason_code,
            sanitized_reason=f"candidate_sql_rejected:{reason_code}",
            repair_info=repair_info,
        )


def check_logistics_candidate_sql(
    sql: str | None,
    *,
    max_limit: int = 500,
) -> LogisticsCandidateSqlGateResult:
    """函数式入口：校验物流 NL2SQL candidate SQL 字符串。"""

    return LogisticsCandidateSqlGate(max_limit=max_limit).check(sql)


__all__ = [
    "LogisticsCandidateSqlGate",
    "LogisticsCandidateSqlGateResult",
    "check_logistics_candidate_sql",
]
