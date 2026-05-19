from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from backend.app.core.config import settings
from backend.app.domains.plan_bom.constants import MATERIAL_CATEGORY_LABELS
from backend.app.domains.plan_bom.schemas.qa import PlanBomPresentation, PlanBomQaResponse, PlanBomTableSpec


class PlanBomAnswerPresentationService:
    """计划 BOM 答案表达层。

    说明：
        1. 复用物流答案表达层的边界策略：LLM 只做表达优化和展示编排；
        2. 所有事实数据必须来自确定性 BOM 查询结果；
        3. LLM 不能修改状态、订单、物料、版本、规格或表格行；
        4. 校验失败时自动 fallback 到确定性展示。
    """

    DISPLAY_TYPES = {
        "narrative",
        "table",
        "comparison_table",
        "summary_cards",
        "clarification",
        "unsupported",
        "empty_result",
        "mixed",
        "error",
    }
    POWER_INTENTS = {"plan_power_prediction", "plan_power_supplier_recommendation", "plan_power_factor_effect_compare"}
    TECHNICAL_VISIBLE_PATTERNS = (
        r"槽位",
        r"字段",
        r"表定义",
        r"库定义",
        r"数据库",
        r"\bSQL\b",
        r"\bsql\b",
        r"\bquery(?:[-_ ]?plan|_key)?\b",
        r"\bqueryKey\b",
        r"\bplanner\b",
        r"\bguard\s*rail\b",
        r"\bguardrail\b",
        r"\bdebug\b",
        r"\braw_result\b",
        r"\bschema\b",
        r"\bLLM\b",
        r"\b[a-z]+_[a-z0-9_]+\b",
    )
    FOLLOW_UP_TEXT_MAP = {
        "order_id": "请补充要查询或对比的订单号、订单尾号，或明确订单范围。",
        "order_tail_no": "请补充订单尾号或更完整的订单号。",
        "material_category": "请确认要看的材料范围，例如玻璃、焊带、汇流条或接线盒。",
        "compare_orders": "请补充需要放在一起比较的订单。",
        "candidate": "当前条件命中多个订单实例，请补充更完整订单号或确认具体文件实例。",
        "order_identity": "当前条件命中多个订单实例，请补充项目名、客户或文件名来缩小范围。",
        "bom_version": "请确认要查看或对比的 BOM 版本。",
        "target_power_ratio": "请补充目标功率档比例，例如 620W 50%、625W 50%。",
        "power_configuration": "请补充功率预测所需配置，例如玻璃、线缆、标板或供应商。",
        "power_factor_options": "请确认需要对比的两个功率模型配置选项。",
        "supported_material_category": "请确认是否改查玻璃、间隙贴膜、焊带、汇流条或接线盒。",
    }
    INTENT_LABELS = {
        "single_order_material_specs": "单订单材料规格查询",
        "specific_material_query": "指定材料规格查询",
        "multi_order_material_table": "多订单材料清单查询",
        "scope_material_list": "范围材料清单查询",
        "batch_export_table": "批量清单查询",
        "cross_order_material_compare": "跨订单材料差异对比",
        "bom_version_compare": "BOM 版本差异对比",
        "material_consistency_check": "材料一致性核查",
        "material_presence_check": "物料存在性检查",
        "plan_power_prediction": "计划 BOM 功率预测",
        "plan_power_supplier_recommendation": "供应商功率匹配推荐",
        "plan_power_factor_effect_compare": "功率模型配置影响值对比",
    }

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
    ) -> None:
        """初始化计划 BOM 表达层。

        参数：
            enabled: 是否启用表达层，默认跟随全局答案表达层开关；
            base_url: LLM 服务地址；
            api_key: LLM 密钥；
            model: 表达层模型名，优先使用专用模型，未配置时兜底通用模型；
            client: 测试注入客户端。

        返回：
            无返回值。
        """

        self.enabled = settings.llm_answer_presentation_enabled if enabled is None else enabled
        self.base_url = base_url if base_url is not None else settings.llm_base_url
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model if model is not None else (settings.llm_answer_presentation_model or settings.llm_model)
        self._client = client

    def build_presentation(self, response: PlanBomQaResponse) -> PlanBomPresentation:
        """生成计划 BOM presentation。

        参数：
            response: 确定性 BOM QA 响应。

        返回：
            安全可用的 presentation，LLM 不可用或校验失败时返回确定性版本。
        """

        fallback = self._build_deterministic_presentation(response)
        if response.nlu.intent in self.POWER_INTENTS:
            # 功率预测类答案包含中心功率、档位比例、供应商匹配度等数值结果。
            # 这些结果只能来自 M3 确定性服务，表达层不调用 LLM，避免改写或新增数值事实。
            fallback.debug["fallback_reason"] = "plan_power_deterministic_only"
            return fallback
        if not self.enabled:
            fallback.debug["fallback_reason"] = "presentation_disabled"
            return fallback
        if not self._is_llm_available():
            fallback.debug["fallback_reason"] = "llm_not_configured"
            return fallback
        payload, error = self._request_llm(response, fallback)
        if error:
            fallback.debug["fallback_reason"] = error
            return fallback
        normalized, validation_error = self._normalize_and_validate(response, fallback, payload)
        if validation_error:
            fallback.debug["fallback_reason"] = validation_error
            return fallback
        normalized.debug.update({"presentation_source": "llm", "llm_model_name": self.model})
        return normalized

    def _build_deterministic_presentation(self, response: PlanBomQaResponse) -> PlanBomPresentation:
        """构造确定性展示。

        参数：
            response: 确定性 BOM QA 响应。

        返回：
            不依赖 LLM 的 presentation。
        """

        display_type = self._resolve_display_type(response)
        if response.nlu.intent == "plan_power_factor_effect_compare":
            caveats = [
                "回答依据为当前已生效的功率测试基准模型；未在模型中命中的版型或配置不参与本次结论。",
                "配置影响值按模型原始选项返回；如需核对，可展开数据依据查看明细。",
            ]
        else:
            caveats = [
                "回答依据为当前系统已导入的计划 BOM 数据；未导入或未匹配到的订单版本不会参与本次结论。",
                "规格、供应商、用量等信息按源 BOM 记录原样展示；如需核对，可展开数据依据查看明细。",
            ]
        if response.nlu.intent in self.POWER_INTENTS:
            caveats.append("功率相关结果按已生效的功率模型版本计算，前端展示不会重新计算。")
        presentation = PlanBomPresentation(
            display_type=display_type,
            title=self._build_title(response),
            answer=self._build_deterministic_answer(response),
            highlights=self._build_highlights(response),
            table_spec=response.result_table if display_type in {"table", "comparison_table", "mixed"} and response.result_table.rows else None,
            caveats=caveats,
            debug={"presentation_source": "deterministic", "status_code": response.status.code},
        )
        if response.classification == "B":
            presentation.follow_up = {
                "questions": self._build_follow_up_questions(response),
                "examples": self._build_follow_up_examples(response),
            }
        if response.classification == "C":
            presentation.unsupported_explanation = {
                "reason": presentation.answer,
                "suggestions": ["请补充可定位的订单、BOM 版本、材料类别，或提供业务规则后再问。"],
            }
        return presentation

    def _build_deterministic_answer(self, response: PlanBomQaResponse) -> str:
        """生成不依赖 LLM 的业务化主回答。

        参数：
            response: 确定性 BOM QA 响应。

        返回：
            面向业务员的自然语言答案，不暴露槽位名、字段名、表名或内部实现词。
        """

        if response.classification == "B" or response.status.code == "CLARIFICATION_REQUIRED":
            return self._build_clarification_answer(response)
        if response.classification == "A" and response.status.code == "OK":
            return self._build_success_answer(response)
        if response.status.code == "EMPTY_RESULT":
            return self._build_empty_answer(response)
        if response.status.code == "UNSUPPORTED_QUESTION" or response.classification == "C":
            return self._build_unsupported_answer(response)
        return self._safe_business_text(response.answer_summary) or "我已完成本次计划 BOM 查询，请查看下方结果和数据依据。"

    def _build_clarification_answer(self, response: PlanBomQaResponse) -> str:
        """生成业务化追问说明。"""

        intent_label = self.INTENT_LABELS.get(response.nlu.intent, "计划 BOM 查询")
        missing_labels = self._missing_slot_labels(response)
        missing_text = "、".join(missing_labels) if missing_labels else "订单、版本或材料范围"
        if response.nlu.intent == "plan_power_factor_effect_compare":
            return (
                f"我先判断了一下，你是在问“{intent_label}”。这类问题需要明确功率版型、配置项和两个要对比的配置选项，"
                "再到已生效的功率测试基准模型中核对影响值，最后才能给出差值。\n\n"
                f"目前还不能直接给出完整结果，主要是缺少：{missing_text}。"
                "请补充后继续提问，我会按模型中的真实配置值计算差异。"
            )
        return (
            f"我先判断了一下，你是在问“{intent_label}”。这类问题需要先明确要查询或对比的范围，"
            "再到已导入的计划 BOM 数据里定位对应订单和版本，最后才能逐项整理规格差异或材料明细。\n\n"
            f"目前还不能直接给出完整结果，主要是缺少：{missing_text}。"
            "请补充这些业务条件后继续提问，我会按订单维度把结论和明细依据一起整理出来。"
        )

    def _build_success_answer(self, response: PlanBomQaResponse) -> str:
        """生成已答结果的完整业务叙事。"""

        safe_summary = self._safe_business_text(response.answer_summary)
        intro = f"查到了。{safe_summary}" if safe_summary else "查到了。我已根据当前计划 BOM 数据完成这次查询。"
        if response.nlu.intent == "plan_power_factor_effect_compare":
            process = (
                "我先识别功率版型、配置项和两个配置选项，再从当前已生效的功率测试基准模型中核对对应影响值，"
                "最后只基于模型中的真实数值计算差异。"
            )
            rows = response.result_table.rows or []
            row_lines = self._format_small_result_rows(rows)
            detail = "\n".join(f"- {line}" for line in row_lines) if row_lines else "- 本次无额外明细。"
            return f"{intro}\n\n{process}\n\n本次配置影响值明细如下：\n{detail}"
        process = (
            "我先根据你的问题定位订单、版本和材料范围，再从当前已导入的计划 BOM 数据中提取匹配记录，"
            "最后只基于这些记录整理结论，不对未出现的规格、供应商或用量做推测。"
        )
        rows = response.result_table.rows or []
        if not rows:
            return f"{intro}\n\n{process}\n\n本次没有需要展开的明细记录。"

        if len(rows) <= 5:
            row_lines = self._format_small_result_rows(rows)
            if row_lines:
                return (
                    f"{intro}\n\n{process}\n\n本次结果共涉及 {len(rows)} 条记录，关键内容如下：\n"
                    + "\n".join(f"- {line}" for line in row_lines)
                    + "\n\n如需进一步核对来源，可展开数据依据或导出明细。"
                )
        return (
            f"{intro}\n\n{process}\n\n本次结果共涉及 {len(rows)} 条记录。为避免正文过长，我先保留核心结论；"
            "你可以点击展开明细查看每条订单、材料和规格。"
        )

    def _build_empty_answer(self, response: PlanBomQaResponse) -> str:
        """生成空结果业务说明。"""

        reason = self._safe_business_text(response.status.message) or self._safe_business_text(response.answer_summary)
        reason_text = f"原因是：{reason}" if reason else "当前条件下没有命中可用记录。"
        if response.nlu.intent == "plan_power_factor_effect_compare":
            return (
                "我先按你的问题定位了功率版型、配置项和配置选项，再在当前已生效的功率测试基准模型中核对。"
                f"最后没有找到可以支撑结论的结果，{reason_text}。"
                "你可以确认版型名称或配置选项写法后再查。"
            )
        return (
            "我先按你的问题定位了订单、版本和材料范围，再在当前已导入的计划 BOM 数据中核对匹配记录。"
            f"最后没有找到可以支撑结论的结果，{reason_text}。"
            "你可以换一个订单号、补充更明确的版本，或扩大材料范围后再查。"
        )

    def _build_unsupported_answer(self, response: PlanBomQaResponse) -> str:
        """生成暂不支持问题的业务说明。"""

        safe_summary = self._safe_business_text(response.answer_summary)
        detail = safe_summary or "当前问题需要额外业务规则或尚未导入的数据支持，不能只凭现有计划 BOM 数据直接判断。"
        return (
            f"这个问题暂时不能直接给出可靠结论。{detail}\n\n"
            "我先确认了当前问题需要的判断依据，再核对系统里已有的计划 BOM 信息；目前缺少可用于判断的业务规则或数据来源，"
            "所以不会强行生成答案。你可以补充规则、订单版本或材料范围后继续。"
        )

    def _format_small_result_rows(self, rows: list[dict[str, Any]]) -> list[str]:
        """把五行以内的小结果转成业务化短句。"""

        lines: list[str] = []
        for row in rows:
            parts: list[str] = []
            for key, value in row.items():
                if value is None or value == "":
                    continue
                label = self._business_column_label(str(key))
                if not label:
                    continue
                text_value = self._business_value(value)
                if not text_value or self._visible_text_has_technical_leak(text_value):
                    continue
                parts.append(f"{label}：{text_value}")
                if len(parts) >= 4:
                    break
            if parts:
                lines.append("；".join(parts))
        return lines

    def _missing_slot_labels(self, response: PlanBomQaResponse) -> list[str]:
        """把内部缺失项转换成业务可读名称。"""

        labels: list[str] = []
        for slot in response.nlu.missing_slots or ["order_id", "material_category"]:
            text = self.FOLLOW_UP_TEXT_MAP.get(slot, "请补充更明确的查询条件。")
            label = re.sub(r"^请补充|^请确认", "", text).strip("。")
            if label and label not in labels:
                labels.append(label)
        return labels

    def _build_follow_up_questions(self, response: PlanBomQaResponse) -> list[str]:
        """生成业务化追问按钮文案。"""

        questions: list[str] = []
        for slot in response.nlu.missing_slots or ["order_id", "material_category"]:
            text = self.FOLLOW_UP_TEXT_MAP.get(slot, "请补充更明确的查询条件后继续。")
            if text not in questions:
                questions.append(text)
        return questions

    @classmethod
    def _business_column_label(cls, key: str) -> str:
        """把结果列名转换成业务展示名，未知内部列不展示。"""

        raw = (key or "").strip()
        lowered = raw.lower()
        mapping = {
            "order_id": "订单",
            "order_no": "订单",
            "order_tail_no": "订单尾号",
            "order": "订单",
            "order_name": "项目",
            "material_category": "材料",
            "material_name": "物料名称",
            "material_spec": "规格",
            "spec": "规格",
            "specification": "规格",
            "description": "规格描述",
            "supplier_name": "供应商",
            "version_no": "版本",
            "bom_version": "版本",
            "revision_version": "版本",
            "quantity": "数量",
            "qty": "数量",
            "unit": "单位",
            "compare_pair": "对比项",
            "left_instance": "左侧订单",
            "right_instance": "右侧订单",
            "left_description": "左侧规格",
            "right_description": "右侧规格",
            "compare_status": "对比结果",
            "diff_summary": "差异说明",
        }
        if lowered in mapping:
            return mapping[lowered]
        if cls._visible_text_has_technical_leak(raw):
            return ""
        return raw

    @staticmethod
    def _business_value(value: Any) -> str:
        """把内部枚举值转换成业务可读值。"""

        text = str(value).strip()
        return MATERIAL_CATEGORY_LABELS.get(text, text)

    @classmethod
    def _safe_business_text(cls, text: str | None) -> str:
        """返回不含技术痕迹的业务文本；不安全则置空。"""

        value = str(text or "").strip()
        if not value or cls._visible_text_has_technical_leak(value):
            return ""
        return value

    @classmethod
    def _visible_text_has_technical_leak(cls, text: str) -> bool:
        """判断可见文案是否包含技术字段、表名、内部编排信息或英文蛇形字段名。"""

        return any(re.search(pattern, text or "", flags=re.I) for pattern in cls.TECHNICAL_VISIBLE_PATTERNS)

    def _resolve_display_type(self, response: PlanBomQaResponse) -> str:
        """根据状态解析展示类型。

        参数：
            response: QA 响应。

        返回：
            presentation display_type。
        """

        if response.status.code == "CLARIFICATION_REQUIRED":
            return "clarification"
        if response.status.code == "UNSUPPORTED_QUESTION":
            return "unsupported"
        if response.status.code == "EMPTY_RESULT":
            return "empty_result"
        if response.status.code == "EXECUTION_ERROR":
            return "error"
        requested_display = self._detect_requested_display(response.question)
        # 业务员未明确要求表格/明细时，默认只输出文字说明；结构化明细仍保留在 response.result_table 供审计和导出扩展使用。
        if requested_display == "table" and response.result_table.rows:
            if response.nlu.intent in {"cross_order_material_compare", "bom_version_compare", "material_consistency_check"}:
                return "comparison_table"
            return "table"
        return "narrative"

    @staticmethod
    def _detect_requested_display(question: str) -> str | None:
        """识别用户是否明确要求结构化展示。

        参数：
            question: 用户原始问题。

        返回：
            当前计划 BOM 前端只支持表格类结构化展示；未命中时返回 None。
        """

        if re.search(r"表格|表格展示|明细表|清单表|数据表|列表|excel|Excel|导出", question or ""):
            return "table"
        return None

    @staticmethod
    def _build_title(response: PlanBomQaResponse) -> str:
        """生成业务化标题。

        参数：
            response: QA 响应。

        返回：
            标题文本。
        """

        if response.classification == "A":
            if response.nlu.intent == "plan_power_prediction":
                return "计划 BOM 功率预测结果"
            if response.nlu.intent == "plan_power_supplier_recommendation":
                return "计划 BOM 供应商功率推荐结果"
            if response.nlu.intent == "plan_power_factor_effect_compare":
                return "功率模型配置影响值对比结果"
            return "计划 BOM 查询结果"
        if response.classification == "B":
            return "需要补充条件后继续查询"
        if response.classification == "C":
            return "当前 BOM 数据暂不能直接回答"
        return "计划 BOM 问题待确认"

    def _build_highlights(self, response: PlanBomQaResponse) -> list[str]:
        """生成关键结论。

        参数：
            response: QA 响应。

        返回：
            关键结论列表。
        """

        highlights = []
        status_message = self._safe_business_text(response.status.message)
        if status_message:
            highlights.append(status_message)
        if response.result_table.rows:
            if response.nlu.intent == "plan_power_factor_effect_compare":
                highlights.append(f"生成 {len(response.result_table.rows)} 条配置影响值明细。")
            else:
                highlights.append(f"命中 {len(response.result_table.rows)} 条 BOM 记录。")
        material_values = response.nlu.slots.get("material_category")
        if material_values:
            material_labels = [self._business_value(item) for item in material_values]
            highlights.append(f"材料范围：{', '.join(material_labels)}")
        if response.nlu.intent in {"plan_power_prediction", "plan_power_supplier_recommendation"}:
            model_code = response.raw_result.get("bom_config_resolution", {}).get("model_code")
            if model_code:
                highlights.append(f"功率版型：{model_code}")
            if response.raw_result.get("power_prediction", {}).get("supplier_name"):
                highlights.append(f"供应商：{response.raw_result['power_prediction']['supplier_name']}")
            if response.raw_result.get("power_recommendation", {}).get("recommendations"):
                highlights.append(f"推荐供应商数：{len(response.raw_result['power_recommendation']['recommendations'])}")
        if response.nlu.intent == "plan_power_factor_effect_compare":
            compare_payload = response.raw_result.get("power_factor_effect_compare") or {}
            if compare_payload.get("model_code"):
                highlights.append(f"功率版型：{compare_payload['model_code']}")
            if compare_payload.get("factor_label"):
                highlights.append(f"配置项：{compare_payload['factor_label']}")
        return [item for item in highlights if not self._visible_text_has_technical_leak(item)]

    @staticmethod
    def _build_follow_up_examples(response: PlanBomQaResponse) -> list[str]:
        """生成补槽示例。

        参数：
            response: QA 响应。

        返回：
            可点击或可复制的示例问法。
        """

        if "order_id" in response.nlu.missing_slots:
            if response.nlu.intent in {"plan_power_prediction", "plan_power_supplier_recommendation"}:
                return ["请补充订单号，例如：订单00104做功率预测。"]
            return ["请补充订单号，例如：订单00104的接线盒规格是什么？"]
        if "target_power_ratio" in response.nlu.missing_slots:
            return ["请补充目标功率比例，例如：订单00104目标620W 50%，625W 50%，推荐供应商。"]
        if "power_configuration" in response.nlu.missing_slots:
            return ["请确认未识别的功率配置，例如玻璃、接线盒线径、标板基准或供应商。"]
        if "power_factor_options" in response.nlu.missing_slots:
            return ["请补充同一版型下要对比的两个配置选项，例如：NT12-66GDF，汇流条A和汇流条B相差多少。"]
        if "compare_orders" in response.nlu.missing_slots:
            return ["请补充两个订单号，例如：订单00067和00106的接线盒有什么不一样？"]
        return ["请补充订单、版本、材料类别或查询范围后继续。"]

    def _request_llm(self, response: PlanBomQaResponse, fallback: PlanBomPresentation) -> tuple[dict[str, Any] | None, str | None]:
        """请求 LLM 表达优化。

        参数：
            response: 确定性 QA 响应；
            fallback: 确定性展示，用于限定字段。

        返回：
            二元组：(LLM JSON, 错误信息)。
        """

        try:
            client = self._client or OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=15, max_retries=0)
            completion = client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": self._build_system_prompt()},
                    {"role": "user", "content": self._build_user_prompt(response, fallback)},
                ],
            )
            content = completion.choices[0].message.content or "{}"
            return self._extract_json(content), None
        except Exception as exc:  # noqa: BLE001
            return None, str(exc)

    def _normalize_and_validate(
        self,
        response: PlanBomQaResponse,
        fallback: PlanBomPresentation,
        payload: dict[str, Any] | None,
    ) -> tuple[PlanBomPresentation | None, str | None]:
        """归一并校验 LLM 表达结果。

        参数：
            response: 确定性 QA 响应；
            fallback: 确定性展示；
            payload: LLM 返回 JSON。

        返回：
            二元组：(presentation, 校验错误)。错误为空表示可采用。
        """

        if not isinstance(payload, dict):
            return None, "llm_payload_not_object"
        display_type = str(payload.get("display_type") or fallback.display_type)
        if display_type not in self.DISPLAY_TYPES:
            return None, "llm_display_type_invalid"
        if display_type != fallback.display_type:
            # 展示形式由确定性层根据用户显式意图裁决，LLM 只优化文字，不能主动加表格或取消用户要求的表格。
            return None, "llm_display_type_changed"
        table_payload = payload.get("table_spec")
        table_spec = fallback.table_spec
        if table_payload is not None:
            try:
                candidate = PlanBomTableSpec.model_validate(table_payload)
            except Exception:  # noqa: BLE001
                return None, "llm_table_schema_invalid"
            if candidate.model_dump(mode="json") != (fallback.table_spec.model_dump(mode="json") if fallback.table_spec else None):
                return None, "llm_table_changed"
            table_spec = candidate
        answer = str(payload.get("answer") or fallback.answer)
        title = str(payload.get("title") or fallback.title)
        highlights = [str(item) for item in payload.get("highlights") or fallback.highlights]
        caveats = [str(item) for item in payload.get("caveats") or fallback.caveats]
        visible_text = "\n".join([title, answer, *highlights, *caveats])
        if self._visible_text_has_technical_leak(visible_text):
            return None, "llm_visible_technical_leak"
        if not self._answer_mentions_only_existing_values(answer, response):
            return None, "llm_answer_contains_unverified_value"
        return (
            PlanBomPresentation(
                display_type=display_type,
                title=title,
                answer=answer,
                highlights=highlights,
                table_spec=table_spec,
                caveats=caveats,
                follow_up=fallback.follow_up,
                unsupported_explanation=fallback.unsupported_explanation,
                debug=dict(fallback.debug),
            ),
            None,
        )

    @classmethod
    def _answer_mentions_only_existing_values(cls, answer: str, response: PlanBomQaResponse) -> bool:
        """校验回答文本是否只引用可追溯事实。

        参数：
            answer: LLM 回答文本；
            response: 确定性 QA 响应。

        返回：
            回答里的订单号和数字都能在确定性响应中找到时返回 True。
        """

        known_text = json.dumps(response.model_dump(mode="json"), ensure_ascii=False)
        for order in re.findall(r"20\d{2}-\d{5}|\b\d{5}\b", answer):
            if order not in known_text:
                return False
        answer_numbers = cls._extract_number_tokens(answer)
        if not answer_numbers:
            return True
        allowed_numbers = cls._collect_allowed_number_tokens(response)
        return answer_numbers.issubset(allowed_numbers)

    @classmethod
    def _collect_allowed_number_tokens(cls, response: PlanBomQaResponse) -> set[str]:
        """收集计划 BOM 确定性结果中允许表达层复述的数字。

        参数：
            response: 确定性 QA 响应。

        返回：
            归一化后的数字 token 集合；额外包含结果行数，允许业务化表述“共 N 条记录”。
        """

        tokens = cls._extract_number_tokens(json.dumps(response.model_dump(mode="json"), ensure_ascii=False))
        tokens.add(cls._normalize_number_token(len(response.result_table.rows or [])))
        tokens.add(cls._normalize_number_token(len(response.result_table.columns or [])))
        return tokens

    @classmethod
    def _extract_number_tokens(cls, text: str) -> set[str]:
        """抽取并归一化可见文本里的数字，供事实白名单校验使用。"""

        tokens: set[str] = set()
        for raw in re.findall(r"(?<![A-Za-z0-9_])-?\d+(?:,\d{3})*(?:\.\d+)?", text or ""):
            try:
                tokens.add(cls._normalize_number_token(raw))
            except Exception:  # noqa: BLE001
                continue
        return tokens

    @staticmethod
    def _normalize_number_token(value: Any) -> str:
        """把数字文本统一为可比较 token，避免 50 与 50.0 被误判不同。"""

        normalized = str(value).replace(",", "").strip()
        if not normalized:
            return "0"
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        return normalized or "0"

    def _is_llm_available(self) -> bool:
        """判断 LLM 是否可用。

        返回：
            配置齐全时返回 True。
        """

        return bool(self.base_url and self.api_key and self.model)

    @staticmethod
    def _extract_json(content: str) -> dict[str, Any]:
        """从 LLM 文本中提取 JSON。

        参数：
            content: LLM 返回文本。

        返回：
            JSON 对象。
        """

        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        parsed = json.loads(match.group(0) if match else stripped)
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _build_system_prompt() -> str:
        """构造表达层系统提示词。

        返回：
            约束 LLM 只做表达的提示词。
        """

        return (
            "你是计划 BOM 问答的答案表达层，只能优化文字和展示编排。\n"
            "不能新增订单、物料、版本、规格、用量或供应商；不能把追问/拒答包装成可答。\n"
            "面向业务员的可见回答中，禁止出现槽位、字段、表名、库名、SQL、query、schema、guardrail、debug、LLM 或英文蛇形命名等技术词。\n"
            "未明确要求表格/明细/清单/导出时，display_type 必须保持 narrative，table_spec 必须为空；不要固定展示明细数据。\n"
            "answer 可以使用清晰 Markdown 段落、加粗和列表，语气要专业、温馨、清晰，先给结论，再说明查询思路和依据。\n"
            "输出单个 JSON，字段可包含 display_type,title,answer,highlights,table_spec,caveats。"
        )

    def _build_user_prompt(self, response: PlanBomQaResponse, fallback: PlanBomPresentation) -> str:
        """构造表达层用户提示词。

        参数：
            response: 确定性 QA 响应；
            fallback: 确定性展示。

        返回：
            JSON 上下文文本。
        """

        public_context = {
            "用户原问题": response.question,
            "状态": response.status.message,
            "业务结论草稿": fallback.answer,
            "展示形式": fallback.display_type,
            "关键结论": fallback.highlights,
            "数据口径": fallback.caveats,
            "结果表": {
                "columns": [self._business_column_label(column) for column in response.result_table.columns],
                "rows": [
                    {
                        self._business_column_label(str(key)): self._business_value(value)
                        for key, value in row.items()
                        if self._business_column_label(str(key)) and value is not None and value != ""
                    }
                    for row in response.result_table.rows[:30]
                ],
                "total_rows": len(response.result_table.rows),
            },
            "表达要求": [
                "先给结论，再说明你按什么业务顺序核对。",
                "只能使用这里给出的事实，不补充外部信息。",
                "不要出现槽位、字段、表名、库名或英文蛇形命名。",
            ],
        }
        return json.dumps(public_context, ensure_ascii=False, default=str)


__all__ = ["PlanBomAnswerPresentationService"]
