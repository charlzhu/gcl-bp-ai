"""
gcl-bp-ai 统一问数 — 领域路由节点（domain_route）。

LLM 根据 catalog 上下文对用户问题进行语义域分类，
输出 business domain（logistics/plan_bom/business_analysis/material_mgmt/unknown）。
同时保留关键词白名单作为快速路径。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from backend.app.core.config import get_settings
from backend.app.domains.business_qa_graph.domain_registry import BusinessQaDomainRegistry
from backend.app.domains.business_qa_graph.prompt_loader import load_prompt_or_default
from backend.app.domains.business_qa_graph.schemas.event import BusinessQaGraphEvent
from backend.app.domains.business_qa_graph.schemas.state import BusinessQaGraphState

logger = logging.getLogger(__name__)

_DOMAIN_ROUTE_DEFAULT = """你是一个经营计划智能助手的领域分类器。请根据用户问题和 catalog 上下文，将问题分类到最匹配的业务域。

业务域选项：
- logistics: 物流运输相关（发运、运输、车次、线路、运费、承运商等）
- plan_bom: 计划BOM相关（BOM配置、版型、评审号、物料清单、功率等）
- business_analysis: 经营分析相关（产量、销量、产销存、达成率、库存分析等）
- material_management: 物控物管相关（库存、出入库、物料管理等）

用户问题：{question}

catalog 上下文摘要：{catalog_summary}

请输出 JSON: {{"domain": "业务域ID", "confidence": 0.0-1.0, "reason": "简短理由"}}
"""


def domain_route_node(state: BusinessQaGraphState) -> BusinessQaGraphState:
    """LLM 语义域分类 + 关键词白名单快速路径。

    优先走关键词白名单（快速、确定性），不匹配时走 LLM 语义分类。
    unknown 时进入 clarify 终端节点。
    """
    question = str(state.get("question") or "").strip()
    domain_hint = state.get("domain_hint")
    trace = list(state.get("trace") or [])

    # ---- 快速路径：关键词白名单 ----
    registry = BusinessQaDomainRegistry.default()
    route = registry.route(question, domain_hint=domain_hint)

    if route.status == "ROUTED" and route.domain != "unknown":
        return _build_routed_state(state, route, trace, "keyword")

    # ---- LLM 语义分类兜底 ----
    try:
        settings = get_settings()
        if settings.llm_api_key:
            llm_domain = _llm_classify_domain(question, settings)
            if llm_domain and llm_domain != "unknown":
                # 让 registry 构建合法的 route 结构
                fallback_route = registry.route(question, domain_hint=llm_domain)
                if fallback_route.domain != "unknown":
                    return _build_routed_state(state, fallback_route, trace, "llm_semantic")
    except Exception as exc:
        logger.warning("domain_route_llm_fallback_failed error=%s", exc)

    # ---- 兜底：CLARIFY ----
    event = BusinessQaGraphEvent(
        node="domain_route",
        event_type="domain_route_clarification",
        message="无法安全识别业务域，已生成澄清候选。",
        payload={"question": question, "method": "fallback"},
    )
    next_state: BusinessQaGraphState = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["status"] = "CLARIFY"
    next_state["domain"] = "unknown"
    next_state["capabilities"] = []
    next_state["domain_route"] = route.model_dump(mode="json")
    return next_state


def _build_routed_state(
    state: BusinessQaGraphState,
    route: Any,
    trace: list[dict[str, Any]],
    method: str,
) -> BusinessQaGraphState:
    """构建已路由 state。"""
    route_payload = route.model_dump(mode="json")
    event = BusinessQaGraphEvent(
        node="domain_route",
        event_type="domain_routed",
        message=f"已识别业务域（{method}）：{route.domain}。",
        payload={**route_payload, "route_method": method},
    )
    next_state: BusinessQaGraphState = dict(state)
    next_state["trace"] = [*trace, event.model_dump(mode="json")]
    next_state["status"] = "DOMAIN_ROUTED"
    next_state["execution_mode"] = "domain_routing_only"
    next_state["domain"] = route.domain
    next_state["capabilities"] = list(route.capabilities)
    next_state["domain_route"] = route_payload
    return next_state


def _llm_classify_domain(question: str, settings: Any) -> str:
    """LLM 语义域分类。"""
    client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)
    prompt_template = load_prompt_or_default("domain_route", _DOMAIN_ROUTE_DEFAULT)

    # 从 catalog 获取简短摘要（如有）
    catalog_summary = _get_catalog_summary()

    response = client.chat.completions.create(
        model=settings.llm_model or "qwen-max",
        messages=[{
            "role": "user",
            "content": prompt_template.format(
                question=question,
                catalog_summary=catalog_summary,
            ),
        }],
        temperature=0,
        max_tokens=256,
        timeout=10.0,
    )

    result = json.loads(response.choices[0].message.content or "{}")
    domain = result.get("domain", "unknown")
    confidence = result.get("confidence", 0)
    logger.info("domain_route_llm domain=%s confidence=%.2f", domain, confidence)
    return domain if confidence >= 0.5 else "unknown"


def _get_catalog_summary() -> str:
    """获取 catalog 简短摘要（表名+描述），供 LLM 分类参考。"""
    try:
        from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
            LogisticsCatalogRecallService,
        )
        recall_service = LogisticsCatalogRecallService()
        # 获取所有已注册的 domain 概览
        return (
            "当前 catalog 注册的域：\n"
            "- logistics: 物流发运台账（logistics_shipment）、线路运价\n"
            "- plan_bom: 计划BOM详情（plan_bom_detail）、BOM对比\n"
            "- business_analysis: 产销存月度数据（production_monthly）、库存表\n"
            "- material_management: 库存出入库（V_HF_SAP_INOUT_DAILY）、物料库存（V_SAP_HFFN_CRKLSZ）\n"
        )
    except Exception:
        return "catalog 不可用。"
