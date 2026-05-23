"""
掌柜问数对齐 - 过滤表格节点（filter_table）。

完全对齐 data-agent/app/agent/nodes/filter_table.py：
- LLM 判断表/字段相关性并过滤
- writer 流式进度
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from backend.app.core.config import get_settings
from backend.app.domains.business_qa_graph.prompt_loader import load_prompt_or_default
from backend.app.domains.business_qa_graph.nodes.zg_utils import (
    _emit_progress,
    STEP_FILTER_TABLE,
)

logger = logging.getLogger(__name__)

_FILTER_TABLE_DEFAULT = '请从候选表中选择回答用户问题所需的表与字段，仅输出 JSON 对象。\n用户问题：{question}\n\n候选表及字段信息：\n{table_infos}\n\n输出：'


def filter_table_node(state: dict[str, Any]) -> dict[str, Any]:
    """过滤表信息节点（掌柜问数对齐版，空输入短路优化）。"""
    _emit_progress(state, STEP_FILTER_TABLE, "running")

    question: str = state.get("question", "")
    table_infos: list[dict[str, Any]] = state.get("table_infos", [])

    if not question or not table_infos:
        _emit_progress(state, STEP_FILTER_TABLE, "success")
        return {"table_infos": table_infos}

    try:
        settings = get_settings()
        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

        prompt_template = load_prompt_or_default("filter_table_info", _FILTER_TABLE_DEFAULT)
        response = client.chat.completions.create(
            model=settings.llm_model or "qwen-max",
            messages=[{
                "role": "user",
                "content": prompt_template.format(
                    question=question,
                    table_infos=json.dumps(table_infos, ensure_ascii=False, indent=2),
                ),
            }],
            temperature=0,
            max_tokens=1024,
            timeout=30.0,
        )

        result_text = response.choices[0].message.content or "{}"
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        result = json.loads(result_text)

        # 过滤：保留 LLM 选中的表和字段
        filtered = []
        for table_info in table_infos:
            table_name = table_info.get("name", "")
            if table_name in result:
                selected_columns = result[table_name]
                columns = [
                    col for col in table_info.get("columns", [])
                    if col.get("name") in selected_columns
                ]
                if columns:
                    filtered.append({**table_info, "columns": columns})

        logger.info("filter_table_success before=%d after=%d", len(table_infos), len(filtered))
        _emit_progress(state, STEP_FILTER_TABLE, "success")
        return {"table_infos": filtered}

    except Exception as exc:
        logger.error("filter_table_failed error=%s", exc)
        _emit_progress(state, STEP_FILTER_TABLE, "error")
        return {"table_infos": table_infos}
