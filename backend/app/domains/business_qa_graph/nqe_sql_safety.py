"""NQE 独立 Graph 内部查询安全预检。

本模块只做确定性字符串级安全拦截，不连接数据库、不访问真实业务入口，
也不把内部候选文本暴露给用户。
"""

from __future__ import annotations

import re
from typing import Any


DEFAULT_RESULT_CAP = 200

_COMMENT_TOKENS = ("--", "/*", "*/", "#")
_BANNED_STATEMENT_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "merge",
    "create",
    "alter",
    "drop",
    "truncate",
    "replace",
    "call",
    "exec",
    "execute",
    "grant",
    "revoke",
    "commit",
    "rollback",
}
_BANNED_EXPRESSION_PATTERNS = (
    "sleep",
    "pg_sleep",
    "benchmark",
    "load_file",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "dblink",
    "dblink_exec",
    "xp_cmdshell",
    "sys_exec",
    "sys_eval",
    "lo_import",
    "lo_export",
    "outfile",
    "dumpfile",
    "into outfile",
    "into dumpfile",
)
_SYSTEM_OBJECT_PREFIXES = (
    "information_schema",
    "performance_schema",
    "mysql",
    "sys",
    "pg_catalog",
    "pg_toast",
    "sqlite_master",
)
_IDENTIFIER_PATTERN = r"[`\"\[]?[A-Za-z_][\w$]*(?:\s*\.\s*[`\"\[]?[A-Za-z_][\w$]*){0,2}"
_TABLE_REF_PATTERN = re.compile(
    rf"\b(?:from|join)\s+({_IDENTIFIER_PATTERN})",
    re.IGNORECASE,
)
_LEADING_TABLE_REF_PATTERN = re.compile(rf"^\s*({_IDENTIFIER_PATTERN})\b", re.IGNORECASE)
_CLAUSE_STOP_PATTERN = re.compile(
    r"\b(?:where|group\s+by|order\s+by|having|limit|union|intersect|except|for\s+update)\b",
    re.IGNORECASE,
)
_FROM_CLAUSE_PATTERN = re.compile(
    r"\bfrom\b\s+([^()]*?)(?=\)|\bwhere\b|\bgroup\s+by\b|\border\s+by\b|\bhaving\b|\blimit\b|\bunion\b|\bintersect\b|\bexcept\b|$)",
    re.IGNORECASE,
)
_LIMIT_PATTERN = re.compile(r"\blimit\s+(\d+)\b", re.IGNORECASE)


def _normalize_identifier(identifier: str) -> str:
    """归一化对象标识。

    参数：
        identifier: 候选文本中或上下文白名单中出现的对象名称。
    返回：
        去除常见引用符号并统一小写后的对象名称。
    业务逻辑：
        仅做确定性规整，不补全业务对象，也不把非白名单对象自动映射为可用对象。
    """
    parts = []
    for part in identifier.split("."):
        cleaned = part.strip().strip("`\"[]").strip()
        if cleaned:
            parts.append(cleaned.lower())
    return ".".join(parts)


def _extract_allowed_tables(context_package: dict[str, Any]) -> set[str]:
    """从召回上下文包中读取白名单对象。

    参数：
        context_package: Graph 上游注入的召回上下文包。
    返回：
        归一化后的白名单集合；缺失或格式不合法时返回空集合。
    业务逻辑：
        安全预检只信任上下文包显式注入的白名单，不读取外部配置或业务元数据。
    """
    raw_allowed = (
        context_package.get("allowed_tables")
        or context_package.get("allowed_table_names")
        or context_package.get("table_whitelist")
        or context_package.get("whitelist_tables")
    )
    if not isinstance(raw_allowed, list | tuple | set):
        return set()

    allowed: set[str] = set()
    for item in raw_allowed:
        if isinstance(item, str):
            normalized = _normalize_identifier(item)
        elif isinstance(item, dict):
            normalized = _normalize_identifier(
                str(
                    item.get("name")
                    or item.get("table")
                    or item.get("table_name")
                    or item.get("object_name")
                    or item.get("qualified_name")
                    or ""
                )
            )
        else:
            normalized = ""
        if normalized:
            allowed.add(normalized)
    return allowed


def _normalize_sql_text(sql_text: str) -> tuple[str, list[str]]:
    """归一化候选文本并识别基础文本风险。

    参数：
        sql_text: 待预检的内部候选文本。
    返回：
        二元组：归一化文本、违规原因列表。
    业务逻辑：
        单条语句可带一个末尾分号；多分号、内嵌分号或注释标记一律拒绝。
    """
    violations: list[str] = []
    stripped = str(sql_text or "").strip()
    if not stripped:
        return "", ["missing_candidate"]

    lowered = stripped.lower()
    if any(token in lowered for token in _COMMENT_TOKENS):
        violations.append("comment_token_detected")

    semicolon_count = stripped.count(";")
    if semicolon_count > 1 or (semicolon_count == 1 and not stripped.endswith(";")):
        violations.append("multiple_statements")
    if semicolon_count == 1:
        stripped = stripped[:-1].strip()

    normalized = " ".join(stripped.split())
    return normalized, violations


def _split_top_level_commas(clause: str) -> list[str]:
    """按顶层逗号拆分 FROM 片段。

    参数：
        clause: FROM 后、WHERE/GROUP/LIMIT 等边界前的文本片段。
    返回：
        顶层逗号拆分后的片段列表。
    业务逻辑：
        逗号连接是常见白名单绕过点；拆分时忽略括号内逗号，无法解析的片段由上层拒绝。
    """
    parts: list[str] = []
    start = 0
    depth = 0
    for index, char in enumerate(clause):
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        elif char == "," and depth == 0:
            parts.append(clause[start:index].strip())
            start = index + 1
    parts.append(clause[start:].strip())
    return [part for part in parts if part]


def _extract_from_clause(normalized_sql: str) -> str:
    """截取主 FROM 子句中可用于对象抽取的片段。

    参数：
        normalized_sql: 已压缩空白并去掉末尾分号的候选文本。
    返回：
        FROM 后到 WHERE/GROUP/ORDER/LIMIT 等边界前的片段；缺少 FROM 时返回空字符串。
    业务逻辑：
        本骨架不解析完整 SQL AST，只做安全前置拦截；能定位的 FROM 范围越窄，越不容易把 SELECT 列表逗号误当成表。
    """
    match = re.search(r"\bfrom\b\s+(.+)", normalized_sql, re.IGNORECASE)
    if not match:
        return ""
    clause = match.group(1)
    stop_match = _CLAUSE_STOP_PATTERN.search(clause)
    if stop_match:
        clause = clause[: stop_match.start()]
    return clause.strip()


def _extract_from_clauses(normalized_sql: str) -> list[str]:
    """抽取候选文本中所有 FROM 片段。

    参数：
        normalized_sql: 已压缩空白并去掉末尾分号的候选文本。
    返回：
        每个 FROM 后到 WHERE/GROUP/右括号等边界前的片段列表。
    业务逻辑：
        安全预检必须覆盖嵌套子查询；只取首个 FROM 会漏掉子查询里的逗号连接对象。
        本函数用保守边界扫描所有 FROM 片段，无法解析的复杂片段由上层 fail-closed。
    """
    clauses: list[str] = []
    for match in _FROM_CLAUSE_PATTERN.finditer(normalized_sql):
        clause = match.group(1).strip()
        if clause:
            clauses.append(clause)
    return clauses


def _extract_table_refs(normalized_sql: str) -> tuple[set[str], list[str]]:
    """抽取候选文本中的对象引用。

    参数：
        normalized_sql: 已压缩空白并去掉末尾分号的候选文本。
    返回：
        二元组：归一化后的对象引用集合、对象抽取违规原因列表。
    业务逻辑：
        同时覆盖 FROM/JOIN、顶层逗号连接和嵌套子查询里的逗号连接。遇到子查询、函数表或无法识别的逗号片段时保守拒绝，避免漏抽非白名单对象。
    """
    refs: set[str] = set()
    violations: list[str] = []
    for match in _TABLE_REF_PATTERN.finditer(normalized_sql):
        normalized = _normalize_identifier(match.group(1))
        if normalized:
            refs.add(normalized)

    for from_clause in _extract_from_clauses(normalized_sql):
        comma_parts = _split_top_level_commas(from_clause)
        for part in comma_parts[1:]:
            if part.lstrip().startswith("("):
                violations.append("unsupported_table_reference")
                continue
            match = _LEADING_TABLE_REF_PATTERN.search(part)
            if not match:
                violations.append("unsupported_table_reference")
                continue
            normalized = _normalize_identifier(match.group(1))
            if normalized:
                refs.add(normalized)
            else:
                violations.append("unsupported_table_reference")
    return refs, violations


def _is_system_or_high_risk_object(table_ref: str) -> bool:
    """判断对象是否属于系统库或高风险对象。

    参数：
        table_ref: 已归一化的对象引用。
    返回：
        属于系统库、高风险前缀或外部系统对象时返回 True。
    业务逻辑：
        系统对象即使被误放入白名单也拒绝，避免通过白名单配置错误绕过安全边界。
    """
    parts = table_ref.split(".")
    first_part = parts[0] if parts else table_ref
    return first_part in _SYSTEM_OBJECT_PREFIXES or table_ref in _SYSTEM_OBJECT_PREFIXES


def _is_table_ref_allowed(table_ref: str, allowed_tables: set[str]) -> bool:
    """判断候选对象是否被白名单精确授权。

    参数：
        table_ref: 从候选文本中抽取并归一化后的对象名。
        allowed_tables: 上下文包显式给出的白名单对象集合。
    返回：
        候选对象与白名单对象完全一致时返回 True。
    业务逻辑：
        不能用 basename 放行跨 schema 对象；例如白名单只有 `table_a` 时，
        `other_schema.table_a` 必须拒绝，避免同名对象绕过业务域边界。
    """
    return table_ref in allowed_tables


def _apply_result_cap(normalized_sql: str, result_cap: int) -> tuple[str, bool, list[str]]:
    """校验或追加结果行数上限。

    参数：
        normalized_sql: 已通过基础安全检查的候选文本。
        result_cap: 允许的最大结果行数。
    返回：
        三元组：带上限的安全候选、是否由预检修改上限、违规原因列表。
    业务逻辑：
        无上限时追加最小上限；已有上限超过 cap 时收敛到 cap；无法解析时拒绝。
    """
    violations: list[str] = []
    limit_matches = list(_LIMIT_PATTERN.finditer(normalized_sql))
    if len(limit_matches) > 1:
        return normalized_sql, False, ["invalid_limit"]
    if not limit_matches:
        return f"{normalized_sql} LIMIT {result_cap}", True, violations

    limit_match = limit_matches[0]
    if re.search(r"\blimit\s+\d+\s*,\s*\d+\b", normalized_sql, re.IGNORECASE):
        return normalized_sql, False, ["invalid_limit"]
    try:
        limit_value = int(limit_match.group(1))
    except ValueError:
        return normalized_sql, False, ["invalid_limit"]
    if limit_value <= 0:
        return normalized_sql, False, ["invalid_limit"]
    if limit_value <= result_cap:
        return normalized_sql, False, violations

    capped_sql = f"{normalized_sql[: limit_match.start(1)]}{result_cap}{normalized_sql[limit_match.end(1) :]}"
    return capped_sql, True, violations


def precheck_nqe_sql_safety(
    sql_text: str | None,
    context_package: dict[str, Any] | None,
    domain: str | None = None,
    *,
    result_cap: int = DEFAULT_RESULT_CAP,
) -> dict[str, Any]:
    """执行 NQE 内部候选文本安全预检。

    参数：
        sql_text: Graph 生成或测试注入的内部候选文本。
        context_package: 上游召回上下文包，必须显式包含对象白名单。
        domain: 当前业务域，仅用于结构化结果追溯，不参与放宽校验。
        result_cap: 默认结果行数上限，必须为正整数。
    返回：
        结构化预检结果，包含 status、reason_code、normalized_sql、safe_sql、
        limit_applied、violations、allowed_tables。
    业务逻辑：
        预检采用 fail-closed：缺少候选、缺少白名单、非只读、多语句、系统对象、
        非白名单对象或无法确定时全部拒绝。
    """
    context = dict(context_package or {})
    cap = result_cap if isinstance(result_cap, int) and result_cap > 0 else DEFAULT_RESULT_CAP
    allowed_tables = _extract_allowed_tables(context)
    normalized_sql, violations = _normalize_sql_text(sql_text or "")
    domain_value = str(domain or context.get("domain") or "").strip()

    if not allowed_tables:
        violations.append("missing_whitelist")
    if not normalized_sql:
        violations.append("missing_candidate")

    lowered = normalized_sql.lower()
    if normalized_sql and not lowered.startswith("select "):
        violations.append("not_select_only")

    keyword_matches = {
        keyword for keyword in _BANNED_STATEMENT_KEYWORDS if re.search(rf"\b{re.escape(keyword)}\b", lowered)
    }
    if keyword_matches:
        violations.append("mutating_or_ddl_keyword")

    expression_matches = {
        pattern for pattern in _BANNED_EXPRESSION_PATTERNS if re.search(rf"\b{re.escape(pattern)}\b", lowered)
    }
    if re.search(r"\bdblink(?:_\w+)?\s*\(", lowered):
        # dblink 扩展函数族可建立外部连接或读取远端结果，不能只拦截精确 dblink/dblink_exec。
        expression_matches.add("dblink_family")
    if expression_matches:
        violations.append("dangerous_expression")

    if any(prefix in lowered for prefix in _SYSTEM_OBJECT_PREFIXES):
        violations.append("system_object")

    extracted_table_refs = _extract_table_refs(normalized_sql) if normalized_sql else (set(), [])
    table_refs, table_ref_warnings = extracted_table_refs
    violations.extend(table_ref_warnings)
    if normalized_sql and not table_refs:
        violations.append("missing_table_reference")

    for table_ref in table_refs:
        if _is_system_or_high_risk_object(table_ref):
            violations.append("system_object")
        if not _is_table_ref_allowed(table_ref, allowed_tables):
            violations.append("table_not_whitelisted")

    safe_sql = ""
    limit_applied = False
    if not violations:
        safe_sql, limit_applied, limit_violations = _apply_result_cap(normalized_sql, cap)
        violations.extend(limit_violations)

    unique_violations = sorted(set(violations))
    status = "pass" if not unique_violations else "reject"
    reason_code = "safe" if status == "pass" else unique_violations[0]

    return {
        "status": status,
        "reason_code": reason_code,
        "normalized_sql": normalized_sql,
        "safe_sql": safe_sql if status == "pass" else "",
        "limit_applied": limit_applied if status == "pass" else False,
        "violations": unique_violations,
        "allowed_tables": sorted(allowed_tables),
        "referenced_tables": sorted(table_refs),
        "domain": domain_value,
    }
