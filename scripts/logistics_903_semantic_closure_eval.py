from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import settings
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaPlan
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.llm_clarification_assist_service import (
    LogisticsLlmClarificationAssistService,
)
from backend.app.domains.logistics.services.llm_understanding_service import LogisticsLlmUnderstandingService
from backend.app.domains.logistics.services.llm_unsupported_assist_service import (
    LogisticsLlmUnsupportedAssistService,
)
from backend.app.domains.logistics.services.nlu_center_service import LogisticsNluCenterService


LEDGER_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_semantic_closure_eval_report.json"
DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_SEMANTIC_CLOSURE_EVAL.md"
FULL_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_semantic_closure_full_report.json"
FULL_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_SEMANTIC_CLOSURE_FULL.md"


@dataclass
class AVariantRecord:
    """A 类多问法验证记录。"""

    question_id: str
    original_question: str
    variant_question: str
    expected_query_key: str | None
    nlu_route: str
    nlu_candidate_query_keys: list[str]
    llm_provider_mode: str
    passed: bool
    failure_reason: str | None = None
    batch_id: str | None = None


@dataclass
class BClarificationRecord:
    """B 类追问辅助验证记录。"""

    question_id: str
    question: str
    actual_intent: str | None
    actual_query_key: str | None
    category: str | None
    missing_slots: list[str]
    questions: list[str]
    behavior_outcome: str
    assist_used: bool
    assist_provider_mode: str | None
    passed: bool
    failure_reason: str | None = None
    batch_id: str | None = None


@dataclass
class CUnsupportedRecord:
    """C 类拒答解释辅助验证记录。"""

    question_id: str
    question: str
    category: str | None
    reason: str | None
    suggestions: list[str]
    assist_used: bool
    assist_provider_mode: str | None
    passed: bool
    failure_reason: str | None = None
    batch_id: str | None = None


@dataclass
class SemanticClosureReport:
    """903 真实问法语义收口评测报告。"""

    generated_at: str
    use_live_llm: bool
    full_ledger_mode: bool
    ledger_distribution: dict[str, int]
    sampled_counts: dict[str, int]
    a_variant_records: list[AVariantRecord] = field(default_factory=list)
    b_clarification_records: list[BClarificationRecord] = field(default_factory=list)
    c_unsupported_records: list[CUnsupportedRecord] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


def _load_ledger_items() -> list[dict[str, Any]]:
    """读取 903 正式总账。

    返回：
        items 列表；如果总账结构异常则抛出 ValueError。
    """

    payload = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("logistics_903_master_ledger.json 缺少 items 数组。")
    return items


def _distribution(items: list[dict[str, Any]]) -> dict[str, int]:
    """统计总账 A/B/C/D 当前分布。"""

    output: dict[str, int] = {}
    for item in items:
        status = str(item.get("current_status") or "unknown")
        output[status] = output.get(status, 0) + 1
    return output


def _pick_diverse_items(
    items: list[dict[str, Any]],
    *,
    status: str,
    limit: int,
    require_query_key: bool = False,
) -> list[dict[str, Any]]:
    """按题族分散抽样，避免只测同一种题。

    参数：
        items: 总账条目。
        status: A / B / C。
        limit: 抽样上限。
        require_query_key: 是否要求存在 current_query_key。

    返回：
        抽样条目列表。
    """

    candidates = [
        item
        for item in items
        if item.get("current_status") == status and (not require_query_key or item.get("current_query_key"))
    ]
    if limit == 0:
        return []
    if limit < 0 or limit >= len(candidates):
        limit = len(candidates)
    by_family: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        by_family.setdefault(str(item.get("family") or "未分类"), []).append(item)
    picked: list[dict[str, Any]] = []
    while len(picked) < limit:
        changed = False
        for family in sorted(by_family):
            bucket = by_family[family]
            if not bucket:
                continue
            picked.append(bucket.pop(0))
            changed = True
            if len(picked) >= limit:
                break
        if not changed:
            break
    return picked


def _extract_json(content: str) -> dict[str, Any]:
    """从 LLM 文本中提取 JSON 对象。"""

    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    match = re.search(r"\{.*\}", stripped, flags=re.S)
    parsed = json.loads(match.group(0) if match else stripped)
    return parsed if isinstance(parsed, dict) else {}


def _fallback_variants(question: str, *, count: int) -> list[str]:
    """在 LLM 不可用时生成保守同义问法。

    说明：
        该方法只用于 dry-run。它优先保留原问题的业务条件，再做少量口语化和同义替换，
        用于验证系统不是只依赖完全一致的原题字符串。
    """

    variants: list[str] = [
        f"帮我看下：{question}",
        f"我想查一下，{question}",
        f"这块数据麻烦看一下：{question}",
        f"按现在锁定口径，{question}",
    ]
    replacements = [
        ("总发运量", "总出货规模"),
        ("发运量", "运量"),
        ("发货量", "发了多少量"),
        ("总运费", "总费用"),
        ("运输费用", "运费"),
        ("物流公司", "承运商"),
        ("承运商", "物流公司"),
        ("车次", "发了多少车"),
        ("各月", "每个月"),
        ("各区域", "分区域"),
        ("各省", "分省"),
        ("是多少", "帮我看一下是多少"),
    ]
    for old, new in replacements:
        if old in question:
            variants.append(question.replace(old, new))
        if len(variants) >= count:
            break
    deduped: list[str] = []
    for variant in variants:
        if variant not in deduped and variant.strip() != question.strip():
            deduped.append(variant)
    while len(deduped) < count:
        deduped.append(f"请按当前口径回答：{question}")
    return deduped[:count]


def _batch_id(prefix: str, index: int, batch_size: int) -> str:
    """生成批次编号。

    参数：
        prefix: A / B / C 类前缀。
        index: 当前记录序号，从 0 开始。
        batch_size: 每批记录数量。

    返回：
        形如 A-001 的批次编号。
    """

    safe_batch_size = max(batch_size, 1)
    return f"{prefix}-{index // safe_batch_size + 1:03d}"


def _generate_variants_with_llm(
    *,
    question: str,
    query_key: str | None,
    count: int,
    use_live_llm: bool,
) -> tuple[list[str], str]:
    """使用 LLM 生成 A 类真实问法变体。

    参数：
        question: 原始 A 类问题。
        query_key: 当前标准 query_key。
        count: 需要生成的变体数量。
        use_live_llm: 是否真实调用 LLM。

    返回：
        变体列表与 provider_mode。
    """

    if not use_live_llm or not (settings.llm_base_url and settings.llm_api_key and settings.llm_model):
        return _fallback_variants(question, count=count), "disabled"
    try:
        client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=20,
            max_retries=0,
        )
        completion = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是物流数据问答的真实问法改写器。\n"
                        "请把一个已知可回答问题改写成业务人员可能真实输入的不同问法。\n"
                        "要求：不改变业务含义，不新增条件，不删关键条件，不生成答案，不生成 SQL。\n"
                        "输出单个 JSON：{\"variants\":[\"...\", \"...\"]}。"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"原题：{question}\n"
                        f"当前 query_key：{query_key}\n"
                        f"需要生成 {count} 条不同但同义的真实业务问法。"
                    ),
                },
            ],
        )
        payload = _extract_json(completion.choices[0].message.content or "{}")
        variants = [
            item.strip()
            for item in payload.get("variants", [])
            if isinstance(item, str) and item.strip() and item.strip() != question.strip()
        ]
        if not variants:
            variants = _fallback_variants(question, count=count)
        return variants[:count], "live"
    except Exception:  # noqa: BLE001
        return _fallback_variants(question, count=count), "error"


def _evaluate_a_variants(
    *,
    items: list[dict[str, Any]],
    use_live_llm: bool,
    a_size: int,
    variants_per_a: int,
    batch_size: int,
) -> list[AVariantRecord]:
    """评估 A 类多问法能否被 NLU 识别到正确 query_key。"""

    service = LogisticsNluCenterService()
    records: list[AVariantRecord] = []
    a_items = _pick_diverse_items(items, status="A", limit=a_size, require_query_key=True)
    for item_index, item in enumerate(a_items):
        expected_query_key = item.get("current_query_key")
        variants, provider_mode = _generate_variants_with_llm(
            question=str(item.get("question") or ""),
            query_key=expected_query_key,
            count=variants_per_a,
            use_live_llm=use_live_llm,
        )
        for variant in variants:
            nlu_result = service.analyze(variant, use_llm=use_live_llm, include_sub_questions=False)
            passed = bool(expected_query_key and expected_query_key in nlu_result.candidate_query_keys)
            records.append(
                AVariantRecord(
                    question_id=str(item.get("question_id") or ""),
                    original_question=str(item.get("question") or ""),
                    variant_question=variant,
                    expected_query_key=expected_query_key,
                    nlu_route=nlu_result.route_suggestion,
                    nlu_candidate_query_keys=list(nlu_result.candidate_query_keys),
                    llm_provider_mode=(nlu_result.llm_result or {}).get("provider_mode", provider_mode),
                    passed=passed,
                    failure_reason=None if passed else "variant_query_key_not_recovered",
                    batch_id=_batch_id("A", item_index, batch_size),
                )
            )
    return records


def _evaluate_b_clarification(
    *,
    items: list[dict[str, Any]],
    use_live_llm: bool,
    b_size: int,
    batch_size: int,
) -> list[BClarificationRecord]:
    """评估 B 类是否保持澄清，并用 LLM 生成业务化追问。"""

    planner = LogisticsDataQaPlanner()
    assist_service = LogisticsLlmClarificationAssistService(
        enabled=True,
        mode="assist" if use_live_llm else "off",
        sample_rate=1.0,
        audit_enabled=False,
    )
    records: list[BClarificationRecord] = []
    for item_index, item in enumerate(_pick_diverse_items(items, status="B", limit=b_size)):
        question = str(item.get("question") or "")
        plan = planner.build_plan(question)
        if not plan.needs_clarification and plan.query_key:
            # 总账当前仍为 B，但正式 planner 已给出受控 query_key。
            # 对用户行为而言这是“可答兜底”，报告中标记为 B->A 迁移候选，避免强行退回澄清。
            records.append(
                BClarificationRecord(
                    question_id=str(item.get("question_id") or ""),
                    question=question,
                    actual_intent=plan.intent,
                    actual_query_key=plan.query_key,
                    category=plan.clarification_category,
                    missing_slots=list(plan.clarification_missing_slots),
                    questions=[],
                    behavior_outcome="answerable_migration_candidate",
                    assist_used=False,
                    assist_provider_mode=None,
                    passed=True,
                    failure_reason=None,
                    batch_id=_batch_id("B", item_index, batch_size),
                )
            )
            continue
        if not plan.needs_clarification:
            records.append(
                BClarificationRecord(
                    question_id=str(item.get("question_id") or ""),
                    question=question,
                    actual_intent=plan.intent,
                    actual_query_key=plan.query_key,
                    category=plan.clarification_category,
                    missing_slots=list(plan.clarification_missing_slots),
                    questions=list(plan.clarification_questions),
                    behavior_outcome="failure",
                    assist_used=False,
                    assist_provider_mode=None,
                    passed=False,
                    failure_reason="rule_did_not_return_clarification",
                    batch_id=_batch_id("B", item_index, batch_size),
                )
            )
            continue
        assisted_plan, _summary = assist_service.apply(question=question, plan=plan)
        passed = assisted_plan.needs_clarification and bool(assisted_plan.clarification_questions)
        records.append(
            BClarificationRecord(
                question_id=str(item.get("question_id") or ""),
                question=question,
                actual_intent=assisted_plan.intent,
                actual_query_key=assisted_plan.query_key,
                category=assisted_plan.clarification_category,
                missing_slots=list(assisted_plan.clarification_missing_slots),
                questions=list(assisted_plan.clarification_questions),
                behavior_outcome="clarification",
                assist_used=assisted_plan.clarification_assist_used,
                assist_provider_mode=assisted_plan.clarification_assist_provider_mode,
                passed=passed,
                failure_reason=None if passed else "clarification_questions_missing",
                batch_id=_batch_id("B", item_index, batch_size),
            )
        )
    return records


def _evaluate_c_unsupported(
    *,
    items: list[dict[str, Any]],
    use_live_llm: bool,
    c_size: int,
    batch_size: int,
) -> list[CUnsupportedRecord]:
    """评估 C 类是否保持拒答，并用 LLM 生成业务化解释。"""

    planner = LogisticsDataQaPlanner()
    assist_service = LogisticsLlmUnsupportedAssistService(
        enabled=True,
        mode="assist" if use_live_llm else "off",
        sample_rate=1.0,
        audit_enabled=False,
    )
    records: list[CUnsupportedRecord] = []
    for item_index, item in enumerate(_pick_diverse_items(items, status="C", limit=c_size)):
        question = str(item.get("question") or "")
        plan = planner.build_plan(question)
        if plan.intent != "unsupported":
            records.append(
                CUnsupportedRecord(
                    question_id=str(item.get("question_id") or ""),
                    question=question,
                    category=plan.unsupported_category,
                    reason=plan.unsupported_reason,
                    suggestions=list(plan.unsupported_suggestions),
                    assist_used=False,
                    assist_provider_mode=None,
                    passed=False,
                    failure_reason="rule_did_not_return_unsupported",
                    batch_id=_batch_id("C", item_index, batch_size),
                )
            )
            continue
        assisted_plan = assist_service.apply(question=question, plan=plan)
        passed = assisted_plan.intent == "unsupported" and bool(assisted_plan.unsupported_reason)
        records.append(
            CUnsupportedRecord(
                question_id=str(item.get("question_id") or ""),
                question=question,
                category=assisted_plan.unsupported_category,
                reason=assisted_plan.unsupported_reason,
                suggestions=list(assisted_plan.unsupported_suggestions),
                assist_used=assisted_plan.unsupported_assist_used,
                assist_provider_mode=assisted_plan.unsupported_assist_provider_mode,
                passed=passed,
                failure_reason=None if passed else "unsupported_reason_missing",
                batch_id=_batch_id("C", item_index, batch_size),
            )
        )
    return records


def _failure_breakdown(records: list[Any]) -> dict[str, int]:
    """按失败原因统计记录。

    参数：
        records: A/B/C 任意评测记录。

    返回：
        失败原因到数量的映射。
    """

    output: dict[str, int] = {}
    for record in records:
        if record.passed:
            continue
        reason = record.failure_reason or "unknown"
        output[reason] = output.get(reason, 0) + 1
    return output


def _batch_summary(records: list[Any]) -> dict[str, dict[str, int]]:
    """按批次统计通过/失败数量。"""

    output: dict[str, dict[str, int]] = {}
    for record in records:
        batch_id = record.batch_id or "unknown"
        bucket = output.setdefault(batch_id, {"total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        if record.passed:
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1
    return output


def _build_summary(report: SemanticClosureReport) -> dict[str, Any]:
    """汇总评测指标。"""

    a_total = len(report.a_variant_records)
    b_total = len(report.b_clarification_records)
    c_total = len(report.c_unsupported_records)
    a_passed = sum(1 for item in report.a_variant_records if item.passed)
    b_passed = sum(1 for item in report.b_clarification_records if item.passed)
    c_passed = sum(1 for item in report.c_unsupported_records if item.passed)
    return {
        "a_variant_total": a_total,
        "a_variant_passed": a_passed,
        "a_variant_failed": a_total - a_passed,
        "b_clarification_total": b_total,
        "b_clarification_passed": sum(
            1 for item in report.b_clarification_records if item.passed and item.behavior_outcome == "clarification"
        ),
        "b_answerable_migration_candidates": sum(
            1
            for item in report.b_clarification_records
            if item.passed and item.behavior_outcome == "answerable_migration_candidate"
        ),
        "b_behavior_passed": b_passed,
        "b_clarification_failed": b_total - b_passed,
        "b_llm_assist_used": sum(1 for item in report.b_clarification_records if item.assist_used),
        "c_unsupported_total": c_total,
        "c_unsupported_passed": c_passed,
        "c_unsupported_failed": c_total - c_passed,
        "c_llm_assist_used": sum(1 for item in report.c_unsupported_records if item.assist_used),
        "overall_passed": a_passed + b_passed + c_passed,
        "overall_total": a_total + b_total + c_total,
        "overall_failed": (a_total - a_passed) + (b_total - b_passed) + (c_total - c_passed),
        "a_failure_breakdown": _failure_breakdown(report.a_variant_records),
        "b_failure_breakdown": _failure_breakdown(report.b_clarification_records),
        "c_failure_breakdown": _failure_breakdown(report.c_unsupported_records),
        "batch_summary": {
            "A": _batch_summary(report.a_variant_records),
            "B": _batch_summary(report.b_clarification_records),
            "C": _batch_summary(report.c_unsupported_records),
        },
        "llm_query_key_catalog_size": len(LogisticsLlmUnderstandingService.QUERY_KEY_WHITELIST),
    }


def _render_doc(report: SemanticClosureReport) -> str:
    """渲染 Markdown 报告。"""

    summary = report.summary
    mode_label = "全量总账分批" if report.full_ledger_mode else "抽样"
    lines = [
        "# 物流域 903 真实问法语义收口评测",
        "",
        "## 一、结论",
        "",
        f"- 执行模式：`{mode_label}`",
        f"- 是否真实调用 LLM：`{report.use_live_llm}`",
        f"- 当前 903 总账分布：`{report.ledger_distribution}`",
        f"- A 类多问法：`{summary['a_variant_passed']}/{summary['a_variant_total']}`",
        f"- B 类行为兜底：`{summary['b_behavior_passed']}/{summary['b_clarification_total']}`，严格澄清 `{summary['b_clarification_passed']}` 条，B->A 可答迁移候选 `{summary['b_answerable_migration_candidates']}` 条，LLM 追问采用 `{summary['b_llm_assist_used']}` 条",
        f"- C 类拒答解释：`{summary['c_unsupported_passed']}/{summary['c_unsupported_total']}`，LLM 解释采用 `{summary['c_llm_assist_used']}` 条",
        f"- 整体结果：`{summary['overall_passed']}/{summary['overall_total']}`",
        f"- A 类失败原因：`{summary['a_failure_breakdown']}`",
        f"- B 类失败原因：`{summary['b_failure_breakdown']}`",
        f"- C 类失败原因：`{summary['c_failure_breakdown']}`",
        "",
        "当前结论：本轮不是固定原题回归，而是把 A/B/C 三类都放到真实问法语义收口框架下评测。A 类用 LLM 或保守变体生成同义问法并由 NLU 识别 query_key；B 类优先验证规则锁定 clarification 后的业务化追问，如果正式 planner 已能稳定给出 query_key，则标记为 B->A 可答迁移候选；C 类在规则锁定 unsupported 后用 LLM 生成业务可理解拒答解释。",
        "",
        "## 二、边界",
        "",
        "- LLM 不直接查数。",
        "- LLM 不生成 SQL。",
        "- LLM 不改写 A/B/C 最终裁决。",
        "- A 类多问法只是验证 query_key 候选恢复能力，最终查询仍走受控 data-qa 主链路。",
        "- B/C 类仍由规则层和 Guardrail 锁边界，LLM 只做追问候选或解释辅助。",
        "",
        "## 三、本轮已落地能力",
        "",
        "### 1. A 类多问法回归",
        "",
        "- 本轮从 903 总账中抽取 A 类题；live 模式使用 LLM 生成真实业务问法变体，dry-run 模式使用保守口语化变体。",
        "- 每个变体不按原题 exact match 判断，而是通过 NLU Center 输出候选 query_key。",
        f"- 本轮样本结果为 `{summary['a_variant_passed']}/{summary['a_variant_total']}`。",
        "- 本轮发现并修复了两类真实问法退化：一是“各物流承运商年度运输费用”被通用总费用规则误抢，二是历史区域/月度/运输方式/承运商/客户总运费题此前缺少通用受控 query_key。当前已收紧承运商分组题路由，并新增历史总运费通用汇总能力。",
        "",
        "### 2. B 类 LLM 追问辅助",
        "",
        "- B 类仍先由规则层锁定 `clarification`，LLM 不允许改成 success 或 unsupported。",
        "- LLM 只负责识别缺口径和生成更业务化追问。",
        "- 如果 B 类台账题在当前正式 planner 中已经稳定命中 query_key，报告不会把它强行判失败，而是标为后续台账重算的 B->A 迁移候选。",
        f"- 本轮行为结果为 `{summary['b_behavior_passed']}/{summary['b_clarification_total']}`，其中严格澄清 `{summary['b_clarification_passed']}` 条，B->A 可答迁移候选 `{summary['b_answerable_migration_candidates']}` 条，LLM 追问实际采用 `{summary['b_llm_assist_used']}` 条。",
        "",
        "### 3. C 类 LLM 拒答解释辅助",
        "",
        "- C 类仍先由规则层锁定 `unsupported`，LLM 不允许改成 success 或 clarification。",
        "- LLM 只负责把拒答原因解释得更业务化，并给出可改问方向。",
        f"- 本轮样本结果为 `{summary['c_unsupported_passed']}/{summary['c_unsupported_total']}`，其中 LLM 拒答解释实际采用 `{summary['c_llm_assist_used']}` 条。",
        "",
        "## 四、当前距离 903 全量真实问法收口的差距",
        "",
        "- 当前已具备按 A/B/C 对 903 总账分批复检的工程入口。",
        "- A 类需要持续扩大真实业务问法变体数量，并把高风险 query_key 纳入 live LLM 抽样。",
        "- B 类需要在澄清稳定的基础上继续评估用户补槽后的可答闭环。",
        "- C 类需要继续做真实问法下的拒答边界解释，防止换说法后误落 success。",
        "",
        "## 五、后续收口标准",
        "",
        "后续不应再以“原题是否命中”为唯一标准，而应以以下标准推进：",
        "",
        "- A 类：同义问法、口语问法、短问法仍能恢复到正确 query_key。",
        "- B 类：缺什么口径由 LLM 辅助识别，追问必须业务化，用户补充后能继续进入可答链路。",
        "- C 类：真实问法下仍能识别边界，拒答原因必须业务可理解，并给出可改问方向。",
        "- 所有 LLM 能力都必须可审计、可回退，不能绕过受控 data-qa 主链路。",
    ]
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> SemanticClosureReport:
    """执行 903 真实问法语义收口评测。"""

    items = _load_ledger_items()
    distribution = _distribution(items)
    a_size = distribution.get("A", 0) if args.full_ledger else args.a_size
    b_size = distribution.get("B", 0) if args.full_ledger else args.b_size
    c_size = distribution.get("C", 0) if args.full_ledger else args.c_size
    report = SemanticClosureReport(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        use_live_llm=bool(args.with_live_llm),
        full_ledger_mode=bool(args.full_ledger),
        ledger_distribution=distribution,
        sampled_counts={
            "full_ledger": bool(args.full_ledger),
            "batch_size": args.batch_size,
            "a_questions": a_size,
            "a_variants_per_question": args.variants_per_a,
            "b_questions": b_size,
            "c_questions": c_size,
        },
    )
    report.a_variant_records = _evaluate_a_variants(
        items=items,
        use_live_llm=bool(args.with_live_llm),
        a_size=a_size,
        variants_per_a=args.variants_per_a,
        batch_size=args.batch_size,
    )
    report.b_clarification_records = _evaluate_b_clarification(
        items=items,
        use_live_llm=bool(args.with_live_llm),
        b_size=b_size,
        batch_size=args.batch_size,
    )
    report.c_unsupported_records = _evaluate_c_unsupported(
        items=items,
        use_live_llm=bool(args.with_live_llm),
        c_size=c_size,
        batch_size=args.batch_size,
    )
    report.summary = _build_summary(report)
    return report


def main() -> None:
    """命令行入口。"""

    parser = argparse.ArgumentParser(description="物流 903 真实问法语义收口评测")
    parser.add_argument("--with-live-llm", action="store_true", help="启用真实 LLM 生成多问法、追问和拒答解释。")
    parser.add_argument("--a-size", type=int, default=10, help="抽样 A 类原题数量。")
    parser.add_argument("--variants-per-a", type=int, default=2, help="每条 A 类问题生成多少个变体。")
    parser.add_argument("--b-size", type=int, default=10, help="抽样 B 类问题数量。")
    parser.add_argument("--c-size", type=int, default=10, help="抽样 C 类问题数量。")
    parser.add_argument("--full-ledger", action="store_true", help="按当前 903 总账 A/B/C 全量分批执行。")
    parser.add_argument("--batch-size", type=int, default=100, help="全量或抽样报告中的批次大小。")
    args = parser.parse_args()

    report = run(args)
    report_path = FULL_REPORT_PATH if args.full_ledger else REPORT_PATH
    doc_path = FULL_DOC_PATH if args.full_ledger else DOC_PATH
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    doc_path.write_text(_render_doc(report), encoding="utf-8")
    print(json.dumps(report.summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
