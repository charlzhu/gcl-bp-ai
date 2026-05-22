"""
gcl-bp-ai 统一问数 — SQL 生成节点（generate_sql）。

LLM 根据 catalog 召回上下文直接生成 SQL 字符串（非 SQLPlan 中间层）。
完全对齐掌柜问数 generate_sql.py 的核心思路：LLM 自由生成 SQL，
但增强安全约束：表/字段必须来自 catalog，EXPLAIN 验证兜底。
"""

from __future__ import annotations

import json
import logging
from typing import Any

import yaml
from openai import OpenAI

from backend.app.core.config import get_settings
from backend.app.domains.business_qa_graph.prompt_loader import load_prompt_or_default
from backend.app.domains.business_qa_graph.nodes.zg_utils import (
    _emit_progress,
    STEP_GENERATE_SQL,
)

logger = logging.getLogger(__name__)

_GENERATE_SQL_DEFAULT = """【角色】
你是一个资深的数据库专家和经营计划数据分析师。你的任务是根据提供的 catalog 上下文信息，将用户的自然语言查询转换为一条语法正确的 SQL 语句。

【上下文信息】
可用数据表信息如下（包含表名、字段名、字段类型、字段描述）：
{table_infos}

可参考的指标信息如下：
{metric_infos}

当前的时间信息如下：
{date_info}

数据库环境如下：
{db_info}

【任务要求】
1. 仅允许使用数据表信息中真实存在的表与字段名称，禁止编造、猜测或引入未提供的表和字段。
2. 若指标信息中存在相关指标定义，必须严格遵循其业务口径、计算逻辑、过滤规则与时间口径。
3. 生成的 SQL 只能用于查询，不能涉及数据写入、更新、删除等操作。
4. 默认只生成一条 SQL，不可生成多条 SQL。
5. 输出必须仅包含一条完整 SQL 语句的纯文本，严禁使用```、```sql 等 Markdown代码块或任何格式化符号。

用户查询如下：
{query}

输出："""


def generate_sql_node(state: dict[str, Any]) -> dict[str, Any]:
    """LLM 根据 catalog 上下文直接生成 SQL（非 SQLPlan 模式）。

    参数：
        state: 当前 Graph 运行态，包含 question / table_infos / metric_infos / date_info / db_info。
    返回：
        包含 sql 的 state 更新字典。LLM 不可用时 fallback 到关键词兜底 SQL。
    """
    _emit_progress(state, STEP_GENERATE_SQL, "running")

    question: str = state.get("question", "")
    table_infos: list[dict[str, Any]] = state.get("table_infos", [])
    metric_infos: list[dict[str, Any]] = state.get("metric_infos", [])
    date_info: dict[str, Any] = state.get("date_info", {})
    db_info: dict[str, Any] = state.get("db_info", {})

    if not question:
        _emit_progress(state, STEP_GENERATE_SQL, "error")
        return {"sql": "", "error": "问题为空，无法生成 SQL。"}

    try:
        settings = get_settings()
        if settings.llm_api_key and table_infos:
            sql = _llm_generate_sql(question, table_infos, metric_infos, date_info, db_info, settings)
        else:
            sql = _fallback_sql(question, table_infos, date_info)

        logger.info("generate_sql_success length=%d preview=%s", len(sql), sql[:120])
        _emit_progress(state, STEP_GENERATE_SQL, "success")
        return {"sql": sql}

    except Exception as exc:
        logger.error("generate_sql_failed error=%s", exc)
        fallback = _fallback_sql(question, table_infos, date_info)
        _emit_progress(state, STEP_GENERATE_SQL, "error")
        return {"sql": fallback, "error": str(exc)[:500]}


def _llm_generate_sql(
    question: str,
    table_infos: list[dict[str, Any]],
    metric_infos: list[dict[str, Any]],
    date_info: dict[str, Any],
    db_info: dict[str, Any],
    settings: Any,
) -> str:
    """LLM 直接生成 SQL 字符串。

    与掌柜问数的核心逻辑完全一致：
    - PromptTemplate 填入 catalog 上下文
    - LLM 直接输出 SQL 文本
    - 不经过 SQLPlan / renderer 中间层
    """
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    prompt_template = load_prompt_or_default("generate_sqlplan", _GENERATE_SQL_DEFAULT)

    response = client.chat.completions.create(
        model=settings.llm_model or "qwen-max",
        messages=[{
            "role": "user",
            "content": prompt_template.format(
                query=question,
                table_infos=yaml.dump(table_infos, allow_unicode=True, sort_keys=False),
                metric_infos=yaml.dump(metric_infos, allow_unicode=True, sort_keys=False),
                date_info=yaml.dump(date_info, allow_unicode=True, sort_keys=False),
                db_info=yaml.dump(db_info, allow_unicode=True, sort_keys=False),
            ),
        }],
        temperature=0,
        max_tokens=2048,
        timeout=30.0,
    )

    sql = (response.choices[0].message.content or "").strip()
    # 清理可能的 Markdown 包裹
    if sql.startswith("```"):
        lines = sql.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        sql = "\n".join(lines).strip()
    return sql


def _fallback_sql(
    question: str,
    table_infos: list[dict[str, Any]],
    date_info: dict[str, Any],
) -> str:
    """无 LLM 时的关键词兜底 SQL。"""
    if not table_infos:
        return "SELECT 1"
    table = table_infos[0]
    table_name = table.get("name", "unknown_table")
    columns = [c.get("name", "*") for c in table.get("columns", [])]
    year = date_info.get("year", 2025)
    select_cols = ", ".join(columns[:5]) if columns else "*"
    return f"SELECT {select_cols} FROM {table_name} WHERE biz_year = {year} LIMIT 100"
