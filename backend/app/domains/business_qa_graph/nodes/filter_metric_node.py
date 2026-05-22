"""
掌柜问数对齐 - 过滤指标节点（filter_metric）。

完全对齐 data-agent/app/agent/nodes/filter_metric.py：
- LLM 判断指标相关性并过滤
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
    STEP_FILTER_METRIC,
)

logger = logging.getLogger(__name__)

_FILTER_METRIC_DEFAULT = '请从候选指标中选出回答用户问题所需的指标，仅输出 JSON 数组。\n用户问题：{question}\n\n候选指标信息：{metric_infos}\n\n输出：'


def filter_metric_node(state: dict[str, Any]) -> dict[str, Any]:
    """过滤指标信息节点（掌柜问数对齐版）。"""
    _emit_progress(state, STEP_FILTER_METRIC, "running")

    question: str = state.get("question", "")
    metric_infos: list[dict[str, Any]] = state.get("metric_infos", [])

    if not question or not metric_infos:
        _emit_progress(state, STEP_FILTER_METRIC, "success")
        return {"metric_infos": metric_infos}

    try:
        settings = get_settings()
        client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

        prompt_template = load_prompt_or_default("filter_metric_info", _FILTER_METRIC_DEFAULT)
        response = client.chat.completions.create(
            model=settings.llm_model or "qwen-max",
            messages=[{
                "role": "user",
                "content": prompt_template.format(
                    question=question,
                    metric_infos=json.dumps([m.get("name", "") for m in metric_infos], ensure_ascii=False),
                ),
            }],
            temperature=0,
            max_tokens=512,
            timeout=30.0,
        )

        result_text = response.choices[0].message.content or "[]"
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
        selected_names = json.loads(result_text)

        filtered = [m for m in metric_infos if m.get("name") in selected_names]
        logger.info("filter_metric_success before=%d after=%d", len(metric_infos), len(filtered))
        _emit_progress(state, STEP_FILTER_METRIC, "success")
        return {"metric_infos": filtered}

    except Exception as exc:
        logger.error("filter_metric_failed error=%s", exc)
        _emit_progress(state, STEP_FILTER_METRIC, "error")
        return {"metric_infos": metric_infos}
