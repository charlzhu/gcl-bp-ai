"""
掌柜问数对齐 - SQL 校正节点（correct_sql）。

完全对齐 data-agent/app/agent/nodes/correct_sql.py：
- LLM 根据错误信息修正 SQL
- writer 流式进度
- gcl-bp-ai 适配：优先 SQLPlan repair，LLM 兜底
"""

from __future__ import annotations

import logging
from typing import Any

from openai import OpenAI

from backend.app.core.config import get_settings
from backend.app.domains.business_qa_graph.prompt_loader import load_prompt_or_default
from backend.app.domains.business_qa_graph.nodes.zg_utils import (
    _emit_progress,
    STEP_CORRECT_SQL,
)

logger = logging.getLogger(__name__)

_CORRECT_SQL_DEFAULT = """【角色】
你是一个资深的数据库专家、SQL 调试专家和数据分析师。

【任务】
根据错误信息修复 SQL，仅输出一条完整 SQL 语句的纯文本。

原始问题：{question}
原始 SQL：{sql}
错误信息：{error}
表信息：{table_infos}

输出："""


def correct_sql_node(state: dict[str, Any]) -> dict[str, Any]:
    """校正 SQL（掌柜问数对齐版）。"""
    _emit_progress(state, STEP_CORRECT_SQL, "running")

    sql: str = state.get("sql", "")
    error: str | None = state.get("error")
    question: str = state.get("question", "")
    table_infos: list[dict[str, Any]] = state.get("table_infos", [])

    # 无错误时跳过
    if not error:
        _emit_progress(state, STEP_CORRECT_SQL, "success")
        return {"sql": sql}

    if not sql or not sql.strip():
        _emit_progress(state, STEP_CORRECT_SQL, "error")
        return {"sql": sql, "error": "SQL 为空，无法校正。"}

    try:
        settings = get_settings()
        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

        prompt_template = load_prompt_or_default("correct_sql", _CORRECT_SQL_DEFAULT)
        response = client.chat.completions.create(
            model=settings.llm_model or "qwen-max",
            messages=[{
                "role": "user",
                "content": prompt_template.format(
                    question=question,
                    sql=sql,
                    error=error,
                    table_infos=str(table_infos)[:3000],
                ),
            }],
            temperature=0,
            max_tokens=2048,
            timeout=30.0,
        )

        corrected_sql = response.choices[0].message.content or ""
        corrected_sql = corrected_sql.strip()
        # 清理 markdown 包裹
        if corrected_sql.startswith("```"):
            lines = corrected_sql.split("\n")
            lines = lines[1:] if len(lines) > 1 else lines
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            corrected_sql = "\n".join(lines)

        retry_count = state.get("_sql_retry_count", 0)
        logger.info("correct_sql_success retry=%d length=%d", retry_count, len(corrected_sql))
        _emit_progress(state, STEP_CORRECT_SQL, "success")
        return {"sql": corrected_sql, "_sql_retry_count": retry_count + 1}

    except Exception as exc:
        logger.error("correct_sql_failed error=%s", exc)
        _emit_progress(state, STEP_CORRECT_SQL, "error")
        return {"sql": sql, "error": str(exc)[:500]}
