"""NQE Raw User Question Safety Gate。

在 LLM SQL generation 之前拦截危险原始问题。
不依赖 LLM，纯规则模式 — 这是安全底线，不是语义理解。
"""

from __future__ import annotations
import re
from typing import Any


# 危险模式：大写标准化后匹配
DANGER_PATTERNS = [
    # DDL
    (r'\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX|VIEW)\b', 'drop_statement'),
    (r'\bTRUNCATE\s+(TABLE\s+)?', 'truncate_statement'),
    (r'\bALTER\s+(TABLE|DATABASE)\b', 'alter_statement'),
    (r'\bCREATE\s+(TABLE|DATABASE|SCHEMA|INDEX)\b', 'create_statement'),

    # DML
    (r'\bUPDATE\s+\w+\s+SET\b', 'update_statement'),
    (r'\bDELETE\s+FROM\b', 'delete_statement'),
    (r'\bINSERT\s+INTO\b', 'insert_statement'),
    (r'\bREPLACE\s+INTO\b', 'replace_statement'),
    (r'\bMERGE\s+INTO\b', 'merge_statement'),

    # 权限
    (r'\bGRANT\s+', 'grant_statement'),
    (r'\bREVOKE\s+', 'revoke_statement'),

    # 系统库探测
    (r'\binformation_schema\b', 'system_schema_access'),
    (r'\bmysql\.', 'mysql_system_access'),
    (r'\bperformance_schema\b', 'performance_schema_access'),
    (r'\bsys\.', 'sys_schema_access'),

    # 多语句 / SQL 注入特征
    (r';\s*(SELECT|DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|EXEC)\b', 'multi_statement_injection'),
    (r'\bUNION\s+(ALL\s+)?SELECT\b', 'union_injection'),
    (r'\bOR\s+[\'"]?\d+\s*=\s*[\'"]?\d+', 'tautology_injection'),
    (r'\bOR\s+[\'"]?\w+[\'"]?\s*=\s*[\'"]?\w+[\'"]?\s*--', 'comment_injection'),
    (r'\bEXEC\s*\(', 'exec_injection'),
    (r'\bEXECUTE\s+IMMEDIATE\b', 'execute_immediate'),
    (r'\bSLEEP\s*\(', 'sleep_injection'),
    (r'\bBENCHMARK\s*\(', 'benchmark_injection'),

    # 文件操作
    (r'\bLOAD_FILE\s*\(', 'load_file'),
    (r'\bINTO\s+(OUTFILE|DUMPFILE)\b', 'file_export'),
]


def check_raw_question_safety(question: str) -> dict[str, Any]:
    """检查原始用户问题是否包含危险 SQL/攻击模式。

    参数：
        question: 用户原始问题文本。

    返回：
        {
            "safe": True/False,
            "matched_rules": [...],  # 命中的规则列表
            "blocked_before_llm": True,  # 如果 unsafe
        }
    """
    if not question or not question.strip():
        return {"safe": False, "matched_rules": ["empty_question"], "blocked_before_llm": True}

    upper = question.upper()
    matched_rules = []

    for pattern, rule_name in DANGER_PATTERNS:
        if re.search(pattern, upper, re.IGNORECASE):
            matched_rules.append(rule_name)

    if matched_rules:
        return {
            "safe": False,
            "matched_rules": matched_rules,
            "blocked_before_llm": True,
            "error_code": "raw_question_safety_blocked",
            "user_visible_message": "该问题涉及高风险数据库操作，已拦截",
        }

    return {"safe": True, "matched_rules": [], "blocked_before_llm": False}
