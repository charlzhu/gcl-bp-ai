from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from openai import OpenAI

from backend.app.core.config import settings
from backend.app.domains.plan_bom.constants import CORE_MATERIAL_CATEGORIES
from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
from backend.app.domains.plan_bom.schemas.qa import PlanBomNluCandidate


class PlanBomNluCenterService:
    """计划 BOM NLU Center。

    说明：
        1. 先用规则层抽取订单、材料、版本、型号、国家、年份和输出形态；
        2. 可选调用 qwen-plus / OpenAI 兼容 LLM 生成候选理解；
        3. LLM 候选必须经过订单、材料和版本索引校验，不能越权生成事实；
        4. 最终输出只作为受控 query/service 的输入，不直接回答业务问题。
    """

    INTENTS = {
        "single_order_material_specs",
        "multi_order_material_table",
        "cross_order_material_compare",
        "bom_version_compare",
        "specific_material_query",
        "scope_material_list",
        "batch_export_table",
        "material_presence_check",
        "material_consistency_check",
        "supplier_reuse_quote_prepare",
        "power_cell_requirement",
        "unsupported",
        "clarification",
    }
    INTENT_ALIASES = {
        "单订单关键材料规格查询": "single_order_material_specs",
        "单订单材料规格查询": "single_order_material_specs",
        "多订单关键材料规格表": "multi_order_material_table",
        "多订单材料规格表": "multi_order_material_table",
        "跨订单材料差异对比": "cross_order_material_compare",
        "订单材料差异对比": "cross_order_material_compare",
        "BOM版本差异对比": "bom_version_compare",
        "版本差异对比": "bom_version_compare",
        "指定材料查询": "specific_material_query",
        "指定客户国家型号范围查询": "scope_material_list",
        "范围材料清单": "scope_material_list",
        "批量导表": "batch_export_table",
        "是否有某类物料": "material_presence_check",
        "物料存在性检查": "material_presence_check",
        "某类物料规格是否一致": "material_consistency_check",
        "材料一致性检查": "material_consistency_check",
        "供应商物料复用询价准备": "supplier_reuse_quote_prepare",
        "功率电池需求": "power_cell_requirement",
        "功率/电池片需求类问题": "power_cell_requirement",
        "无法基于当前BOM数据回答的问题": "unsupported",
        "无法回答": "unsupported",
        "需要追问": "clarification",
    }

    def __init__(
        self,
        *,
        repository: PlanBomQueryRepository,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
    ) -> None:
        """初始化计划 BOM NLU。

        参数：
            repository: BOM 查询仓储，用于校验订单、版本和材料索引；
            base_url: LLM 服务地址，默认读取全局配置；
            api_key: LLM 密钥，默认读取全局配置；
            model: LLM 模型名，默认读取 LLM_MODEL；
            client: 测试或脚本注入客户端。

        返回：
            无返回值。
        """

        self.repository = repository
        self.base_url = base_url if base_url is not None else settings.llm_base_url
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model if model is not None else settings.llm_model
        self._client = client
        self.material_aliases = self._load_material_aliases()

    def understand(self, question: str, *, use_llm: bool = True) -> PlanBomNluCandidate:
        """理解计划 BOM 自然语言问题。

        参数：
            question: 用户问题；
            use_llm: 是否允许调用 LLM 候选理解。

        返回：
            经过 Guardrail 校验后的 NLU 候选。
        """

        rule_candidate = self._rule_understand(question)
        if not use_llm or not self._is_llm_available():
            if use_llm:
                rule_candidate.provider_mode = "disabled"
                rule_candidate.guardrail_notes.append("LLM 未配置，已使用规则层理解。")
            return rule_candidate

        llm_payload, error = self._request_llm_candidate(question)
        if error:
            rule_candidate.provider_mode = "error"
            rule_candidate.guardrail_notes.append(f"LLM 候选失败，已回退规则层：{error}")
            return rule_candidate

        return self._merge_llm_candidate(rule_candidate, llm_payload)

    def _rule_understand(self, question: str) -> PlanBomNluCandidate:
        """用规则层抽取意图和槽位。

        参数：
            question: 用户问题。

        返回：
            规则层 NLU 候选。
        """

        normalized = question.strip()
        slots: dict[str, Any] = {}
        slots["order_tail_no"] = self._extract_order_tails(normalized)
        slots["compare_orders"] = slots["order_tail_no"][:]
        slots["material_category"] = self._extract_material_categories(normalized)
        slots["non_core_material_category"] = self._extract_non_core_material_categories(normalized)
        slots["material_alias"] = self._extract_material_aliases(normalized)
        slots["bom_version"] = self._extract_versions(normalized)
        slots["model"] = self._extract_model(normalized)
        slots["year"] = self._extract_year(normalized)
        slots["country"] = self._extract_country(normalized)
        slots["need_table"] = any(word in normalized for word in ("表格", "清单", "列表", "统计出来", "列出来"))
        slots["need_excel"] = any(word.lower() in normalized.lower() for word in ("excel", "导表", "导出"))
        slots["output_format"] = "excel" if slots["need_excel"] else ("table" if slots["need_table"] else "narrative")

        intent = self._detect_intent(normalized, slots)
        missing_slots = self._detect_missing_slots(intent, slots)
        confidence = 0.78 if not missing_slots else 0.58
        return PlanBomNluCandidate(
            question=question,
            intent=intent,
            slots=slots,
            missing_slots=missing_slots,
            confidence=confidence,
            provider_mode="rule",
            guardrail_notes=["规则层完成初始意图和槽位抽取。"],
        )

    def _detect_intent(self, question: str, slots: dict[str, Any]) -> str:
        """判断受控意图。

        参数：
            question: 用户问题；
            slots: 规则层已抽取槽位。

        返回：
            受控 intent 编码。
        """

        if any(word in question for word in ("功率预测", "满足订单需求功率", "需要什么样的电池", "功率倒推")):
            return "power_cell_requirement"
        if "到" in question and len(slots.get("bom_version") or []) >= 2:
            return "bom_version_compare"
        if any(word in question for word in ("版本", "A0", "A1", "A2", "A3", "变更")) and len(slots.get("bom_version") or []) >= 2:
            return "bom_version_compare"
        if any(word in question for word in ("不一样", "差异", "对比", "比较")):
            return "cross_order_material_compare" if len(slots.get("order_tail_no") or []) >= 2 else "material_consistency_check"
        if any(word in question for word in ("哪些订单没有", "没有接线盒", "是否有", "有没有")):
            return "material_presence_check"
        if any(word in question for word in ("所有", "全部", "多个订单", "清单", "Excel", "excel", "导出")):
            return "scope_material_list" if slots.get("model") or slots.get("year") else "multi_order_material_table"
        if len(slots.get("order_tail_no") or []) >= 2:
            return "multi_order_material_table"
        if slots.get("material_category") and slots.get("order_tail_no"):
            return "single_order_material_specs"
        if slots.get("material_category"):
            return "specific_material_query"
        return "clarification"

    def _detect_missing_slots(self, intent: str, slots: dict[str, Any]) -> list[str]:
        """识别缺失槽位。

        参数：
            intent: 受控意图；
            slots: 当前槽位。

        返回：
            缺失槽位名称列表。
        """

        missing: list[str] = []
        if intent in {"single_order_material_specs", "specific_material_query", "bom_version_compare"} and not slots.get("order_tail_no"):
            missing.append("order_id")
        if intent in {"multi_order_material_table", "cross_order_material_compare"} and len(slots.get("order_tail_no") or []) < 2:
            missing.append("compare_orders")
        if intent in {"single_order_material_specs", "multi_order_material_table", "cross_order_material_compare"} and not slots.get("material_category"):
            missing.append("material_category")
        if intent == "scope_material_list" and not (slots.get("year") or slots.get("model") or slots.get("country")):
            missing.append("scope")
        return missing

    def _request_llm_candidate(self, question: str) -> tuple[dict[str, Any] | None, str | None]:
        """请求 LLM 候选理解。

        参数：
            question: 用户问题。

        返回：
            二元组：(候选 JSON, 错误信息)。错误为空表示可进入校验。
        """

        try:
            client = self._client or OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=15, max_retries=0)
            completion = client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": self._build_llm_system_prompt()},
                    {"role": "user", "content": question},
                ],
            )
            content = completion.choices[0].message.content or "{}"
            return self._extract_json(content), None
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    def _merge_llm_candidate(self, rule_candidate: PlanBomNluCandidate, payload: dict[str, Any] | None) -> PlanBomNluCandidate:
        """合并 LLM 候选并执行 Guardrail。

        参数：
            rule_candidate: 规则层候选；
            payload: LLM 输出 JSON。

        返回：
            最终 NLU 候选；校验失败时保持规则层。
        """

        if not isinstance(payload, dict):
            rule_candidate.guardrail_notes.append("LLM 未返回 JSON 对象，保持规则层。")
            return rule_candidate
        raw_intent = str(payload.get("intent_candidate") or payload.get("intent") or "").strip()
        intent = self._normalize_intent(raw_intent)
        if intent not in self.INTENTS:
            rule_candidate.guardrail_notes.append(f"LLM intent 不在 BOM 白名单，保持规则层：{raw_intent}")
            return rule_candidate
        slot_candidate = payload.get("slot_candidate") or payload.get("slots") or {}
        if not isinstance(slot_candidate, dict):
            rule_candidate.guardrail_notes.append("LLM slots 非对象，保持规则层。")
            return rule_candidate

        validated_slots = dict(rule_candidate.slots)
        rejected_reasons: list[str] = []
        if "material_category" in slot_candidate:
            llm_core_materials, llm_non_core_materials = self._normalize_material_candidates(
                slot_candidate.get("material_category") or []
            )
            if llm_core_materials:
                validated_slots["material_category"] = llm_core_materials
            if llm_non_core_materials:
                validated_slots["non_core_material_category"] = llm_non_core_materials
                rule_candidate.guardrail_notes.append(
                    "LLM 非核心材料候选已识别，但当前 detail/compare 主链路仅支持核心五类，未写入 material_category。"
                )
            if not llm_core_materials and not llm_non_core_materials:
                rule_candidate.guardrail_notes.append("LLM 材料候选未通过 BOM 材料别名白名单校验，未采纳材料槽位。")
        if "order_tail_no" in slot_candidate:
            tails = [self._normalize_order_tail(str(item)) for item in slot_candidate.get("order_tail_no") or []]
            tails = [item for item in tails if item]
            if tails and self._all_order_tails_exist(tails):
                validated_slots["order_tail_no"] = tails
                validated_slots["compare_orders"] = tails
            else:
                rejected_reasons.append("LLM 订单候选未通过 BOM 索引校验，未采纳订单槽位。")
        if "bom_version" in slot_candidate:
            versions = [str(item).upper().strip() for item in slot_candidate.get("bom_version") or [] if str(item).strip()]
            if versions and self._versions_are_allowed(versions, rule_candidate=rule_candidate, validated_slots=validated_slots):
                validated_slots["bom_version"] = versions
            elif versions:
                rule_candidate.guardrail_notes.append("LLM BOM 版本候选未通过问题原文或 BOM 版本索引校验，未采纳版本槽位。")
        if rejected_reasons:
            rule_candidate.guardrail_notes.extend(rejected_reasons)
            rule_candidate.guardrail_notes.append("LLM 候选被拒绝，已保持规则层边界。")
            return rule_candidate

        final_intent = intent
        final_missing = self._detect_missing_slots(intent, validated_slots)
        if intent != rule_candidate.intent and final_missing and not rule_candidate.missing_slots:
            # LLM 候选不能把规则层已闭合的问题改成缺槽问题；这种冲突保持规则 intent，避免安全可答问题被降级。
            final_intent = rule_candidate.intent
            final_missing = self._detect_missing_slots(final_intent, validated_slots)
            rule_candidate.guardrail_notes.append(f"LLM intent 会引入缺失槽位，保持规则层 intent：{rule_candidate.intent}。")
        if intent != rule_candidate.intent:
            rule_candidate.guardrail_notes.append(f"LLM intent 与规则层存在冲突：{rule_candidate.intent} -> {intent}。")
        merged = PlanBomNluCandidate(
            question=rule_candidate.question,
            intent=final_intent if not rule_candidate.missing_slots else rule_candidate.intent,
            slots=validated_slots,
            missing_slots=final_missing,
            confidence=max(rule_candidate.confidence, min(float(payload.get("confidence", 0.0) or 0.0), 0.95)),
            provider_mode="live",
            guardrail_notes=[*rule_candidate.guardrail_notes, "LLM 候选已通过白名单和索引校验，仅作为理解辅助。"],
        )
        return merged

    def _normalize_intent(self, raw_intent: str) -> str:
        """归一 LLM intent，兼容中文意图名和轻微格式差异。

        参数：
            raw_intent: LLM 输出的原始 intent。

        返回：
            受控 intent 编码；无法归一时返回原文。
        """

        cleaned = raw_intent.strip().strip("`").replace(" ", "").replace("_", "_")
        if cleaned in self.INTENTS:
            return cleaned
        compact = cleaned.replace("/", "").replace(" ", "")
        return self.INTENT_ALIASES.get(compact, self.INTENT_ALIASES.get(cleaned, raw_intent))

    def _normalize_material_candidates(self, values: list[Any]) -> tuple[list[str], list[str]]:
        """归一 LLM 材料候选，支持 canonical key 和中文别名。

        参数：
            values: LLM 输出的材料候选列表。

        返回：
            二元组：(当前核心五类材料, 已识别但当前主链路不支持的非核心材料)。
        """

        core_materials: list[str] = []
        non_core_materials: list[str] = []
        alias_index: dict[str, str] = {}
        for category, aliases in self.material_aliases.items():
            alias_index[category.lower().replace(" ", "")] = category
            for alias in aliases:
                alias_index[str(alias).lower().replace(" ", "")] = category
        for value in values:
            key = str(value).lower().replace(" ", "").strip()
            category = alias_index.get(key)
            if not category:
                continue
            # 当前 QA detail/compare 请求 schema 只允许核心五类；非核心材料单独保留，交由 QA 层受控追问或解释。
            if category in CORE_MATERIAL_CATEGORIES and category not in core_materials:
                core_materials.append(category)
            elif category not in CORE_MATERIAL_CATEGORIES and category not in non_core_materials:
                non_core_materials.append(category)
        return core_materials, non_core_materials

    def _versions_are_allowed(self, versions: list[str], *, rule_candidate: PlanBomNluCandidate, validated_slots: dict[str, Any]) -> bool:
        """校验 LLM 版本槽位是否来自问题原文或真实 BOM 索引。

        参数：
            versions: LLM 候选版本；
            rule_candidate: 规则层候选，用于检查原文显式版本；
            validated_slots: 已通过校验的槽位。

        返回：
            版本可采纳返回 True。
        """

        rule_versions = set(rule_candidate.slots.get("bom_version") or [])
        if set(versions).issubset(rule_versions):
            return True
        tails = validated_slots.get("order_tail_no") or []
        if not tails:
            return False
        available_versions: set[str] = set()
        for tail in tails:
            for header in self.repository.list_active_headers(order_no_like=tail, order_name_like=tail):
                if header.version_no:
                    available_versions.add(str(header.version_no).upper())
        return set(versions).issubset(available_versions)

    def _all_order_tails_exist(self, tails: list[str]) -> bool:
        """校验订单尾号是否至少能命中一个 BOM 头。

        参数：
            tails: 订单短号或完整订单号。

        返回：
            所有尾号均可命中时返回 True。
        """

        for tail in tails:
            if not self.repository.list_active_headers(order_no_like=tail, order_name_like=tail):
                return False
        return True

    def _extract_order_tails(self, question: str) -> list[str]:
        """抽取订单号和短编号。

        参数：
            question: 用户问题。

        返回：
            去重后的订单尾号列表。
        """

        candidates = re.findall(r"20\d{2}[-_]\d{5}|(?<!\d)\d{5}(?!\d)", question)
        normalized: list[str] = []
        for item in candidates:
            tail = self._normalize_order_tail(item)
            if tail and tail not in normalized:
                normalized.append(tail)
        return normalized

    @staticmethod
    def _normalize_order_tail(value: str) -> str:
        """归一订单尾号。

        参数：
            value: 原始订单表达。

        返回：
            五位尾号或完整订单表达中的尾号。
        """

        match = re.search(r"(\d{5})$", value.strip())
        return match.group(1) if match else value.strip()

    def _extract_material_categories(self, question: str) -> list[str]:
        """抽取材料类别。

        参数：
            question: 用户问题。

        返回：
            标准材料类别编码列表。
        """

        categories: list[str] = []
        normalized = question.lower().replace(" ", "")
        for category, aliases in self.material_aliases.items():
            if category not in CORE_MATERIAL_CATEGORIES:
                continue
            if any(alias.lower().replace(" ", "") in normalized for alias in aliases):
                categories.append(category)
        if categories:
            return categories
        if any(word in question for word in ("五类", "关键材料", "核心材料", "核心辅材", "关键辅材")):
            return list(CORE_MATERIAL_CATEGORIES)
        return categories

    def _extract_non_core_material_categories(self, question: str) -> list[str]:
        """抽取已知但当前核心五类主链路不支持的材料类别。

        参数：
            question: 用户问题。

        返回：
            非核心材料 canonical 类别列表，用于 QA 层受控追问或解释。
        """

        categories: list[str] = []
        normalized = question.lower().replace(" ", "")
        for category, aliases in self.material_aliases.items():
            if category in CORE_MATERIAL_CATEGORIES:
                continue
            if any(alias.lower().replace(" ", "") in normalized for alias in aliases):
                categories.append(category)
        return categories

    def _extract_material_aliases(self, question: str) -> list[str]:
        """抽取用户原始材料别名。

        参数：
            question: 用户问题。

        返回：
            命中的材料别名列表。
        """

        aliases: list[str] = []
        normalized = question.lower().replace(" ", "")
        for values in self.material_aliases.values():
            for alias in values:
                if alias.lower().replace(" ", "") in normalized and alias not in aliases:
                    aliases.append(alias)
        return aliases

    @staticmethod
    def _extract_versions(question: str) -> list[str]:
        """抽取 BOM 版本号。

        参数：
            question: 用户问题。

        返回：
            版本号列表，例如 A0、A1。
        """

        versions = re.findall(r"\b[A-Ea-e]\d{0,2}\b", question)
        return [item.upper() if len(item) > 1 else f"{item.upper()}0" for item in versions]

    @staticmethod
    def _extract_model(question: str) -> str | None:
        """抽取产品型号。

        参数：
            question: 用户问题。

        返回：
            型号字符串；未命中时返回 None。
        """

        match = re.search(r"NT[0-9A-Z]+/[0-9A-Z]+GDF|NT[0-9A-Z]+GDF", question, flags=re.I)
        return match.group(0).upper() if match else None

    @staticmethod
    def _extract_year(question: str) -> int | None:
        """抽取年份。

        参数：
            question: 用户问题。

        返回：
            四位年份；未命中时返回 None。
        """

        match = re.search(r"20\d{2}", question)
        return int(match.group(0)) if match else None

    @staticmethod
    def _extract_country(question: str) -> str | None:
        """抽取常见国家表达。

        参数：
            question: 用户问题。

        返回：
            国家名称；未命中时返回 None。
        """

        countries = ("哥伦比亚", "法国", "德国", "日本", "意大利", "英国", "西班牙", "印尼", "加拿大", "美国")
        for country in countries:
            if country in question:
                return country
        return None

    def _load_material_aliases(self) -> dict[str, list[str]]:
        """读取材料别名配置。

        返回：
            材料类别到别名列表的映射。
        """

        path = Path(__file__).resolve().parent.parent / "config" / "material_aliases.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _is_llm_available(self) -> bool:
        """判断 LLM 配置是否可用。

        返回：
            base_url、api_key、model 同时存在时返回 True。
        """

        return bool(self.base_url and self.api_key and self.model)

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        """从 LLM 文本中提取 JSON。

        参数：
            content: 模型返回文本。

        返回：
            JSON 对象；解析失败会向上抛异常。
        """

        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        return json.loads(match.group(0) if match else stripped)

    def _build_llm_system_prompt(self) -> str:
        """构造 BOM NLU LLM 系统提示词。

        返回：
            受控 JSON 输出提示词。
        """

        return (
            "你是计划 BOM 问答系统的语言理解层，只能输出候选 intent_candidate 和 slot_candidate。\n"
            "你不能查数、不能直接回答业务问题、不能编造订单、不能编造物料、不能编造版本、不能输出规格答案。\n"
            "你不能改变 A/B/C 边界；信息不足时只输出 missing_slots 候选，不要强行补全。\n"
            "订单必须尽量从用户问题原文提取，不要自行补全不存在的订单号。\n"
            f"intent_candidate 只能取：{sorted(self.INTENTS)}。\n"
            "slot_candidate 可包含 order_tail_no、model、customer、country、year、bom_version、material_category、output_format、need_table、need_excel、missing_slots。\n"
            f"material_category 必须优先取核心五类：{sorted(CORE_MATERIAL_CATEGORIES)}；如用户明确问非核心材料，只输出原始候选，不能自行扩展成核心材料。\n"
            "严格输出单个 JSON 对象，不要 markdown，不要解释性自然语言。\n"
            "示例：{\"intent_candidate\":\"single_order_material_specs\",\"slot_candidate\":{\"order_tail_no\":[\"00104\"],\"material_category\":[\"glass\",\"junction_box\"],\"need_table\":true},\"confidence\":0.85}"
        )


__all__ = ["PlanBomNluCenterService"]
