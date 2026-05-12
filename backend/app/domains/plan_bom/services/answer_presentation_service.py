from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from backend.app.core.config import settings
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
    POWER_INTENTS = {"plan_power_prediction", "plan_power_supplier_recommendation"}

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
            # 这些结果只能来自 M3 确定性服务，表达层不再调用 LLM，避免改写或新增数值事实。
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
        caveats = [
            "所有订单、物料、版本和规格均来自已导入的计划 BOM 结构化数据。",
            "LLM 只允许优化表达，不作为查数或改写结果来源。",
        ]
        if response.nlu.intent in {"plan_power_prediction", "plan_power_supplier_recommendation"}:
            caveats.append("功率预测数值来自后端确定性功率模型；LLM、前端和 Excel 宏均不参与计算。")
        presentation = PlanBomPresentation(
            display_type=display_type,
            title=self._build_title(response),
            answer=response.answer_summary,
            highlights=self._build_highlights(response),
            table_spec=response.result_table if display_type in {"table", "comparison_table", "mixed"} and response.result_table.rows else None,
            caveats=caveats,
            debug={"presentation_source": "deterministic", "status_code": response.status.code},
        )
        if response.classification == "B":
            presentation.follow_up = {
                "questions": response.nlu.missing_slots,
                "examples": self._build_follow_up_examples(response),
            }
        if response.classification == "C":
            presentation.unsupported_explanation = {
                "reason": response.answer_summary,
                "suggestions": ["请补充可定位的订单、BOM 版本、材料类别，或提供功率倒推规则后再问。"],
            }
        return presentation

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
            return "计划 BOM 查询结果"
        if response.classification == "B":
            return "需要补充条件后继续查询"
        if response.classification == "C":
            return "当前 BOM 数据暂不能直接回答"
        return "计划 BOM 问题待确认"

    @staticmethod
    def _build_highlights(response: PlanBomQaResponse) -> list[str]:
        """生成关键结论。

        参数：
            response: QA 响应。

        返回：
            关键结论列表。
        """

        highlights = [response.status.message]
        if response.result_table.rows:
            highlights.append(f"返回 {len(response.result_table.rows)} 条结构化记录。")
        if response.nlu.slots.get("material_category"):
            highlights.append(f"材料范围：{', '.join(response.nlu.slots['material_category'])}")
        if response.nlu.intent in {"plan_power_prediction", "plan_power_supplier_recommendation"}:
            model_code = response.raw_result.get("bom_config_resolution", {}).get("model_code")
            if model_code:
                highlights.append(f"功率模型版型：{model_code}")
            if response.raw_result.get("power_prediction", {}).get("supplier_name"):
                highlights.append(f"供应商：{response.raw_result['power_prediction']['supplier_name']}")
            if response.raw_result.get("power_recommendation", {}).get("recommendations"):
                highlights.append(f"推荐供应商数：{len(response.raw_result['power_recommendation']['recommendations'])}")
        return highlights

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
        if not self._answer_mentions_only_existing_values(answer, response):
            return None, "llm_answer_contains_unverified_value"
        return (
            PlanBomPresentation(
                display_type=display_type,
                title=str(payload.get("title") or fallback.title),
                answer=answer,
                highlights=[str(item) for item in payload.get("highlights") or fallback.highlights],
                table_spec=table_spec,
                caveats=[str(item) for item in payload.get("caveats") or fallback.caveats],
                follow_up=fallback.follow_up,
                unsupported_explanation=fallback.unsupported_explanation,
                debug=dict(fallback.debug),
            ),
            None,
        )

    @staticmethod
    def _answer_mentions_only_existing_values(answer: str, response: PlanBomQaResponse) -> bool:
        """校验回答文本是否只引用可追溯事实。

        参数：
            answer: LLM 回答文本；
            response: 确定性 QA 响应。

        返回：
            当前采用保守策略：只要没有明显新增订单号格式即可通过。
        """

        known_text = json.dumps(response.model_dump(mode="json"), ensure_ascii=False)
        for order in re.findall(r"20\d{2}-\d{5}|\b\d{5}\b", answer):
            if order not in known_text:
                return False
        return True

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
            "未明确要求表格/明细/清单/导出时，display_type 必须保持 narrative，table_spec 必须为空；不要固定展示明细数据。\n"
            "answer 可以使用清晰 Markdown 段落、加粗和列表，语气要专业、温馨、清晰，先给结论再说明依据。\n"
            "输出单个 JSON，字段可包含 display_type,title,answer,highlights,table_spec,caveats。"
        )

    @staticmethod
    def _build_user_prompt(response: PlanBomQaResponse, fallback: PlanBomPresentation) -> str:
        """构造表达层用户提示词。

        参数：
            response: 确定性 QA 响应；
            fallback: 确定性展示。

        返回：
            JSON 上下文文本。
        """

        return json.dumps(
            {
                "deterministic_response": response.model_dump(mode="json", exclude={"presentation"}),
                "allowed_table_spec": fallback.table_spec.model_dump(mode="json") if fallback.table_spec else None,
            },
            ensure_ascii=False,
        )


__all__ = ["PlanBomAnswerPresentationService"]
