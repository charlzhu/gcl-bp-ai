from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from openai import OpenAI

from backend.app.core.config import settings
from backend.app.domains.logistics.schemas.data_qa import (
    LogisticsDataQaChartSpec,
    LogisticsDataQaCaveatItem,
    LogisticsDataQaFollowUp,
    LogisticsDataQaPresentation,
    LogisticsDataQaPresentationCard,
    LogisticsDataQaResult,
    LogisticsDataQaTableSpec,
    LogisticsDataQaUnsupportedExplanation,
)


class LogisticsLlmAnswerPresentationService:
    """物流 data-qa 答案表达层。

    说明：
        1. 本服务只在确定性 data-qa 结果生成后介入；
        2. LLM 只允许优化表达和建议展示形态，不允许查数、生成 SQL、改状态或改数值；
        3. 任何 LLM 异常、JSON 解析失败、状态越权或数值幻觉都会自动降级到确定性展示编排；
        4. 当表达层开关关闭时返回 None，前端会继续按旧结构展示。
    """

    INTERACTIVE_TIMEOUT_CAP_SECONDS = 6.0
    INTERACTIVE_MAX_RETRIES_CAP = 0

    DISPLAY_TYPES = {
        "narrative",
        "summary_cards",
        "table",
        "line_chart",
        "bar_chart",
        "pie_chart",
        "mixed",
        "clarification",
        "unsupported",
        "empty_result",
        "error",
    }
    STATUS_TO_DISPLAY_TYPE = {
        "OK": {"narrative", "summary_cards", "table", "line_chart", "bar_chart", "pie_chart", "mixed"},
        "CLARIFICATION_REQUIRED": {"clarification"},
        "UNSUPPORTED_QUESTION": {"unsupported"},
        "EMPTY_RESULT": {"empty_result"},
        "EXECUTION_ERROR": {"error"},
    }
    COLUMN_LABELS = {
        "shipment_mw": "发运量",
        "shipment_watt": "发运瓦数",
        "trip_count": "车次",
        "total_fee": "总运费",
        "avg_fee": "平均运费",
        "avg_fee_per_watt": "平均元/瓦",
        "fee_per_watt": "元/瓦",
        "signedfor_rate": "签收率",
        "record_count": "记录数",
        "row_count": "记录数",
        "task_count": "任务数",
        "parse_fail_count": "未纳入运费统计任务数",
        "price_missing_count": "缺少价格任务数",
        "customer_name": "客户",
        "carrier_name": "承运商",
        "company_name": "承运商",
        "region_name": "区域",
        "province": "省份",
        "city": "城市",
        "biz_month": "月份",
        "month": "月份",
        "scope_label": "统计范围",
    }
    TECHNICAL_VISIBLE_TOKENS = (
        "query_key",
        "planner",
        "guardrail",
        "SQL",
        "sql",
        "dwd_logistics_",
        "ods_logistic_",
        "dws_logistics_",
        "actual_watt",
    )

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
    ) -> None:
        """初始化答案表达层服务。

        参数：
            enabled: 是否启用表达层；False 时不返回 presentation 字段。
            base_url: LLM 服务地址，默认读取 settings.llm_base_url。
            api_key: LLM 密钥，默认读取 settings.llm_api_key。
            model: 表达层模型名；默认先读取 LLM_ANSWER_PRESENTATION_MODEL，未配置时兜底读取通用 LLM_MODEL。
            client: 测试用 OpenAI 兼容客户端。
            timeout_seconds: 单次 LLM 调用超时时间。
            max_retries: LLM 调用重试次数。

        返回：
            无返回值。
        """

        self.enabled = settings.llm_answer_presentation_enabled if enabled is None else enabled
        self.base_url = base_url if base_url is not None else settings.llm_base_url
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        configured_model, model_source = self._resolve_model(model)
        self.model = configured_model
        self.model_source = model_source
        self._client = client
        configured_timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.llm_answer_presentation_timeout
        )
        configured_max_retries = (
            max_retries
            if max_retries is not None
            else settings.llm_answer_presentation_max_retries
        )
        # 物流问答是前台同步接口，确定性查询结果必须优先返回给业务用户。
        # 表达层只做润色和展示编排，不能因为供应商响应慢而拖到前端 30 秒超时。
        # 显式传参的测试场景保留原值；默认运行态对 LLM 表达层做低延迟上限。
        self.timeout_seconds = (
            configured_timeout
            if timeout_seconds is not None
            else min(float(configured_timeout), self.INTERACTIVE_TIMEOUT_CAP_SECONDS)
        )
        self.max_retries = (
            configured_max_retries
            if max_retries is not None
            else min(int(configured_max_retries), self.INTERACTIVE_MAX_RETRIES_CAP)
        )

    def is_llm_available(self) -> bool:
        """判断当前环境是否具备真实 LLM 表达层调用条件。"""

        return bool(self.base_url and self.api_key and self.model)

    def _resolve_model(self, explicit_model: str | None) -> tuple[str, str]:
        """解析答案表达层模型。

        参数：
            explicit_model: 调用方显式传入的模型名，通常用于测试或定制调用。

        返回：
            二元组：(模型名, 模型来源)。模型来源用于报告和调试，不包含任何密钥。

        说明：
            1. 显式传入的模型优先级最高；
            2. 生产配置优先使用专用 LLM_ANSWER_PRESENTATION_MODEL；
            3. 专用模型未配置时，允许在表达层开关开启的前提下兜底使用通用 LLM_MODEL；
            4. api_key 和 base_url 始终只来自环境配置或显式参数，不写入代码。
        """

        if explicit_model is not None:
            return explicit_model, "explicit"
        if settings.llm_answer_presentation_model:
            return settings.llm_answer_presentation_model, "LLM_ANSWER_PRESENTATION_MODEL"
        if self.enabled and settings.llm_model:
            return settings.llm_model, "LLM_MODEL"
        return "", "not_configured"

    def build_presentation(
        self,
        *,
        question: str,
        result: LogisticsDataQaResult,
        trace_id: str | None = None,
    ) -> LogisticsDataQaPresentation | None:
        """生成答案展示编排。

        参数：
            question: 用户原始问题。
            result: 后端确定性 data-qa 结果。
            trace_id: 请求追踪 ID，仅写入 debug 便于排查。

        返回：
            presentation 结构；表达层关闭时返回 None。
        """

        if not self.enabled:
            return None

        fallback = self._build_deterministic_presentation(question=question, result=result)
        fallback.debug.update(
            {
                "presentation_source": "deterministic",
                "trace_id": trace_id,
                "fallback_reason": None,
                "requested_display": self._detect_requested_display(question),
                "final_display_type": fallback.display_type,
                "llm_model_name": self.model or None,
                "llm_model_source": self.model_source,
            }
        )
        if not self.is_llm_available():
            fallback.debug["fallback_reason"] = "llm_not_configured"
            return fallback

        llm_payload, error = self._request_llm_presentation(question=question, result=result)
        if error:
            fallback.debug["fallback_reason"] = error
            return fallback

        normalized, validation_error = self._normalize_and_validate_llm_payload(
            question=question,
            result=result,
            payload=llm_payload,
            fallback=fallback,
        )
        if validation_error:
            fallback.debug["fallback_reason"] = validation_error
            return fallback
        normalized.debug.update(
            {
                "presentation_source": "llm",
                "trace_id": trace_id,
                "fallback_reason": None,
                "requested_display": self._detect_requested_display(question),
                "final_display_type": normalized.display_type,
                "llm_model_name": self.model,
                "llm_model_source": self.model_source,
            }
        )
        return normalized

    def _build_deterministic_presentation(
        self,
        *,
        question: str,
        result: LogisticsDataQaResult,
    ) -> LogisticsDataQaPresentation:
        """构造不依赖 LLM 的确定性展示编排。

        说明：
            该方法是所有异常场景的降级路径，所有展示数据都来自 result。
        """

        status_code = result.status.code if result.status else self._resolve_status_code(result)
        display_type = self._resolve_display_type(question=question, result=result, status_code=status_code)
        title = self._build_title(result=result, status_code=status_code)
        answer = self._build_deterministic_answer(question=question, result=result, status_code=status_code)
        requested_display = self._detect_requested_display(question)
        caveats = self._build_caveats(result)
        # 默认采用纯文字叙事，只有业务员明确要求表格/图表/指标卡时，才把结构化组件放进 presentation。
        # 原始 result_table 仍保留在响应根节点，便于审计和后续导出能力复用，但不再强制占用主回答界面。
        presentation = LogisticsDataQaPresentation(
            display_type=display_type,
            title=title,
            answer=answer or title,
            highlights=self._build_highlights(
                result=result,
                status_code=status_code,
                answer=answer or title,
                display_type=display_type,
            ),
            table_spec=LogisticsDataQaTableSpec(
                columns=list(result.result_table.columns),
                rows=list(result.result_table.rows),
            )
            if display_type in {"table", "mixed"} and result.result_table.rows
            else None,
            cards=self._build_cards(question=question, result=result)
            if display_type in {"summary_cards", "mixed"}
            else [],
            caveats=caveats,
            caveat_items=self._build_caveat_items(
                result=result,
                status_code=status_code,
                caveats=caveats,
            ),
            debug={
                "status_code": status_code,
                "query_key": result.query_plan.query_key,
                "requested_display": requested_display,
                "final_display_type": display_type,
            },
        )
        chart_spec = self._build_chart_spec(question=question, result=result, display_type=display_type)
        if chart_spec:
            presentation.chart_spec = chart_spec
        if status_code == "CLARIFICATION_REQUIRED":
            presentation.follow_up = LogisticsDataQaFollowUp(
                questions=list(result.clarification_questions),
                examples=self._build_follow_up_examples(result),
            )
        if status_code == "UNSUPPORTED_QUESTION":
            presentation.unsupported_explanation = LogisticsDataQaUnsupportedExplanation(
                reason=result.query_plan.unsupported_reason or result.answer_summary,
                suggestions=list(result.query_plan.unsupported_suggestions),
            )
        self._sanitize_presentation(presentation)
        return presentation

    def _request_llm_presentation(
        self,
        *,
        question: str,
        result: LogisticsDataQaResult,
    ) -> tuple[dict[str, Any], str | None]:
        """调用 LLM 生成展示编排候选。

        返回：
            (payload, error)。error 非空时调用方必须降级。
        """

        last_error: Exception | None = None
        for _ in range(max(1, self.max_retries + 1)):
            try:
                client = self._client or OpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key,
                    timeout=self.timeout_seconds,
                    max_retries=0,
                )
                completion = client.chat.completions.create(
                    model=self.model,
                    temperature=0,
                    messages=[
                        {"role": "system", "content": self._build_system_prompt()},
                        {"role": "user", "content": self._build_user_prompt(question=question, result=result)},
                    ],
                )
                content = completion.choices[0].message.content or "{}"
                return self._extract_json(content), None
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        return {}, self._format_llm_error(last_error)

    def _format_llm_error(self, error: Exception | None) -> str:
        """把 LLM 调用异常归一成可审计但不暴露敏感信息的错误码。

        参数：
            error: OpenAI 兼容客户端抛出的异常。

        返回：
            归一后的错误码。错误码不包含 API Key、请求头或完整堆栈。
        """

        if error is None:
            return "llm_error:unknown"
        message = str(error).lower()
        if "model_not_found" in message or "does not exist" in message:
            return "llm_error:model_not_found"
        if "timeout" in message or "timed out" in message:
            return "llm_error:timeout"
        if "unauthorized" in message or "invalid_api_key" in message or "401" in message:
            return "llm_error:unauthorized"
        if "rate_limit" in message or "quota" in message or "429" in message:
            return "llm_error:rate_limited"
        return "llm_error:provider_error"

    def _build_system_prompt(self) -> str:
        """构建答案表达层系统提示词。"""

        return (
            "你是物流数据问答系统的“答案表达层 / 展示编排层”。\n"
            "你不是查数模型，不能查数据库，不能生成 SQL，不能改写 planner/query_key，不能改变 A/B/C/空结果/错误状态。\n"
            "你只能根据输入中的后端确定性结果，组织更自然、更专业、更适合业务用户阅读的展示结构。\n"
            "硬性规则：\n"
            "1. 所有数值只能来自输入 result_table.rows、answer_summary、data_scope 或 calculation_logic；不得新增、猜测、修正任何数字。\n"
            "1.1 不要重新合计、不要自行计算同比/环比/占比、不要四舍五入、不要改小数位；需要写总计时优先原样引用 answer_summary。\n"
            "1.2 如果不确定某个数字是否来自输入，就不要在 title/answer/highlights/caveats 中写这个数字。\n"
            "1.3 不要输出“最高/最低/峰值/占比/环比/同比/平均/单次/单车/原因推测”等派生判断，除非这些文字和数字已在 answer_summary 中明确给出。\n"
            "1.4 图表类回答的 answer 只做展示说明，例如“已按月份整理为折线图，具体数值见图表和表格”，不要在 answer/highlights 中复述或推导多组数字。\n"
            "2. status_code 必须原样返回，不得把 clarification/unsupported/empty/error 改成 success。\n"
            "3. 不得把 B/C 问题包装成可回答结论。\n"
            "4. 未明确要求表格、图表或指标卡时，display_type 必须使用 narrative，chart_spec/table_spec/cards 必须为空；不要固定输出“指标卡/明细数据/对比图”。\n"
            "4.1 用户明确要求饼图/折线图/柱状图/图表时，如果结构化数据支持，才输出对应 chart_spec；数据不支持时选择 narrative。\n"
            "4.2 用户明确要求表格/明细表/清单表/导出时，才输出 table_spec；用户只是说“统计/列出/汇总/合计”时优先用文字回答。\n"
            "4.3 用户明确要求指标卡/卡片时，才输出 cards。\n"
            "5. chart_spec 必须使用字段 chart_type，不要使用 type；chart_type 只能是 line、bar 或 pie。\n"
            "5.1 chart_spec 的 x_axis、y_axis、series.field 必须使用 result_table.columns 里的后端原始字段名，不要改成中文字段名。\n"
            "5.2 chart_spec.data 必须原样使用 result_table.rows；series 里的每个点必须是 {\"x\": row[x_axis], \"y\": row[field]}，不要省略 data。\n"
            "6. 技术词如 query_key、slot、planner、guardrail 不要出现在主展示，只能放 debug。\n"
            "7. OK 状态下不要生成 follow_up 追问；clarification 状态才生成 follow_up。\n"
            "8. caveats 只能摘录输入中的 calculation_logic/data_scope/warnings，不要自行汇总缺失记录数或新增口径数字。\n"
            "9. 输出必须是单个 JSON 对象，不要在 JSON 外包 markdown。answer 字段可以使用清晰的 Markdown 段落、加粗和列表。\n"
            "JSON 字段：status_code,display_type,title,answer,highlights,chart_spec,table_spec,cards,follow_up,unsupported_explanation,caveats,caveat_items,debug。\n"
            "caveat_items 的每项格式为 {\"level\":\"info|warning|danger\",\"text\":\"...\"}，只能来自 calculation_logic/data_scope/warnings。\n"
            "chart_spec 示例：{\"chart_type\":\"line\",\"title\":\"...\",\"x_axis\":\"biz_month\",\"y_axis\":[\"shipment_mw\"],\"series\":[{\"name\":\"发运量\",\"field\":\"shipment_mw\",\"data\":[{\"x\":\"2026-01\",\"y\":864.728}]}],\"unit\":\"MW\",\"data\":[...]}\n"
            "display_type 只能是 narrative,summary_cards,table,line_chart,bar_chart,pie_chart,mixed,clarification,unsupported,empty_result,error。\n"
            "文风：专业、温馨、清晰，先给结论，再给依据；像可靠的业务助手，不要固定套模板。"
        )

    def _build_user_prompt(self, *, question: str, result: LogisticsDataQaResult) -> str:
        """构建答案表达层用户提示词。"""

        status_code = result.status.code if result.status else self._resolve_status_code(result)
        payload = {
            "raw_question": question,
            "status_code": status_code,
            "planner": {
                "intent": result.query_plan.intent,
                "query_key": result.query_plan.query_key,
                "metrics": result.query_plan.metrics,
                "dimensions": result.query_plan.dimensions,
                "filters": result.query_plan.filters,
                "group_by": result.query_plan.group_by,
            },
            "answer_summary": result.answer_summary,
            "result_table": result.result_table.model_dump(mode="json"),
            "data_scope": result.data_scope,
            "calculation_logic": result.calculation_logic,
            "warnings": result.warnings,
            "needs_clarification": result.needs_clarification,
            "clarification_questions": result.clarification_questions,
            "unsupported_reason": result.query_plan.unsupported_reason,
            "unsupported_suggestions": result.query_plan.unsupported_suggestions,
            "allow_chart": bool(result.result_table.rows),
            "requested_display": self._detect_requested_display(question),
        }
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _normalize_and_validate_llm_payload(
        self,
        *,
        question: str,
        result: LogisticsDataQaResult,
        payload: dict[str, Any],
        fallback: LogisticsDataQaPresentation,
    ) -> tuple[LogisticsDataQaPresentation, str | None]:
        """清洗并校验 LLM 展示编排。

        返回：
            (presentation, validation_error)。validation_error 非空时调用方必须降级。
        """

        if not isinstance(payload, dict) or not payload:
            return fallback, "llm_empty_payload"
        status_code = result.status.code if result.status else self._resolve_status_code(result)
        llm_status = str(payload.get("status_code") or status_code)
        if llm_status != status_code:
            return fallback, "llm_status_changed"

        display_type = str(payload.get("display_type") or fallback.display_type)
        if display_type not in self.DISPLAY_TYPES:
            return fallback, "llm_invalid_display_type"
        if display_type not in self.STATUS_TO_DISPLAY_TYPE.get(status_code, set()):
            return fallback, "llm_display_type_cross_boundary"
        if self._display_type_ignores_user_request(
            question=question,
            result=result,
            display_type=display_type,
            fallback=fallback,
        ):
            return fallback, "llm_display_type_ignores_user_request"

        presentation = LogisticsDataQaPresentation(
            display_type=display_type,  # type: ignore[arg-type]
            title=str(payload.get("title") or fallback.title),
            answer=str(payload.get("answer") or fallback.answer),
            highlights=self._normalize_string_list(payload.get("highlights")) or fallback.highlights,
            caveats=self._normalize_string_list(payload.get("caveats")) or fallback.caveats,
            caveat_items=self._normalize_caveat_items(payload.get("caveat_items")) or fallback.caveat_items,
            debug=payload.get("debug") if isinstance(payload.get("debug"), dict) else {},
        )
        if self._visible_text_has_technical_leak(
            [
                presentation.title,
                presentation.answer,
                *presentation.highlights,
                *presentation.caveats,
                *[item.text for item in presentation.caveat_items],
            ]
        ):
            # LLM 表达层面向业务用户，不能把表名、字段名、SQL 或内部 query_key 暴露到主展示。
            return fallback, "llm_technical_visible_leak"
        if not self._text_numbers_are_safe(
            [
                presentation.title,
                presentation.answer,
                *presentation.highlights,
                *presentation.caveats,
                *[item.text for item in presentation.caveat_items],
            ],
            result=result,
        ):
            return fallback, "llm_text_number_hallucination"

        requested_display = self._detect_requested_display(question)
        table_payload = payload.get("table_spec")
        if display_type in {"table", "mixed"} and requested_display == "table" and isinstance(table_payload, dict):
            table_spec = LogisticsDataQaTableSpec(
                columns=[item for item in table_payload.get("columns", []) if isinstance(item, str)],
                rows=[row for row in table_payload.get("rows", []) if isinstance(row, dict)],
            )
            if self._table_spec_is_safe(table_spec=table_spec, result=result):
                presentation.table_spec = table_spec
            else:
                return fallback, "llm_table_data_not_from_backend"
        else:
            presentation.table_spec = fallback.table_spec

        cards_payload = payload.get("cards")
        if display_type in {"summary_cards", "mixed"} and requested_display == "summary_cards" and isinstance(cards_payload, list):
            cards: list[LogisticsDataQaPresentationCard] = []
            for item in cards_payload:
                if not isinstance(item, dict) or "label" not in item:
                    continue
                card = LogisticsDataQaPresentationCard(
                    label=str(item.get("label") or ""),
                    value=item.get("value"),
                    unit=str(item.get("unit")) if item.get("unit") is not None else None,
                    description=str(item.get("description")) if item.get("description") is not None else None,
                )
                cards.append(card)
            if self._cards_are_safe(cards=cards, result=result):
                presentation.cards = cards
            else:
                return fallback, "llm_card_number_hallucination"
        else:
            presentation.cards = fallback.cards

        chart_payload = payload.get("chart_spec")
        if display_type in {"line_chart", "bar_chart", "pie_chart", "mixed"} and requested_display in {"line_chart", "bar_chart", "pie_chart"} and isinstance(chart_payload, dict):
            chart_spec = self._normalize_chart_payload(chart_payload)
            if chart_spec and self._chart_spec_is_safe(chart_spec=chart_spec, result=result):
                presentation.chart_spec = chart_spec
            elif chart_payload:
                return fallback, "llm_chart_data_not_from_backend"
        else:
            presentation.chart_spec = fallback.chart_spec

        if status_code == "CLARIFICATION_REQUIRED":
            follow_up_payload = payload.get("follow_up")
            if isinstance(follow_up_payload, dict):
                presentation.follow_up = LogisticsDataQaFollowUp(
                    questions=self._normalize_string_list(follow_up_payload.get("questions")) or list(result.clarification_questions),
                    examples=self._normalize_string_list(follow_up_payload.get("examples")) or self._build_follow_up_examples(result),
                )
            else:
                presentation.follow_up = fallback.follow_up
        if status_code == "UNSUPPORTED_QUESTION":
            unsupported_payload = payload.get("unsupported_explanation")
            if isinstance(unsupported_payload, dict):
                presentation.unsupported_explanation = LogisticsDataQaUnsupportedExplanation(
                    reason=str(unsupported_payload.get("reason") or result.query_plan.unsupported_reason or result.answer_summary),
                    suggestions=self._normalize_string_list(unsupported_payload.get("suggestions"))
                    or list(result.query_plan.unsupported_suggestions),
                )
            else:
                presentation.unsupported_explanation = fallback.unsupported_explanation
        hygiene_error = self._find_presentation_hygiene_issue(
            question=question,
            result=result,
            presentation=presentation,
        )
        if hygiene_error:
            return fallback, f"llm_{hygiene_error}"
        self._sanitize_presentation(presentation)
        return presentation, None

    def _resolve_display_type(self, *, question: str, result: LogisticsDataQaResult, status_code: str) -> str:
        """根据状态、用户格式诉求和结构化数据选择默认展示形态。"""

        if status_code == "CLARIFICATION_REQUIRED":
            return "clarification"
        if status_code == "UNSUPPORTED_QUESTION":
            return "unsupported"
        if status_code == "EMPTY_RESULT":
            return "empty_result"
        if status_code == "EXECUTION_ERROR":
            return "error"
        requested = self._detect_requested_display(question)
        if requested == "pie_chart" and self._can_build_pie_chart(result):
            return requested
        if requested in {"line_chart", "bar_chart"} and self._can_build_chart(result):
            return requested
        if requested == "table" and result.result_table.rows:
            return "table"
        if requested == "summary_cards" and self._build_cards(question=question, result=result):
            return "summary_cards"
        return "narrative"

    def _detect_requested_display(self, question: str) -> str | None:
        """识别用户显式要求的展示方式。"""

        if re.search(r"饼图|圆饼图|环形图|占比图|占比展示", question):
            return "pie_chart"
        if re.search(r"折线图|趋势图|看趋势|趋势", question):
            return "line_chart"
        if re.search(r"柱状图|柱形图|条形图|对比图|图表", question):
            return "bar_chart"
        if re.search(r"表格|表格展示|汇总表|明细表|数据表|清单表|列表|excel|Excel|导出", question):
            return "table"
        if re.search(r"指标卡|卡片|概览卡|汇总卡|数据卡", question):
            return "summary_cards"
        return None

    def _build_title(self, *, result: LogisticsDataQaResult, status_code: str) -> str:
        """构建展示标题。"""

        if status_code == "CLARIFICATION_REQUIRED":
            return "还需要补充几个条件"
        if status_code == "UNSUPPORTED_QUESTION":
            return "当前暂不支持直接回答"
        if status_code == "EMPTY_RESULT":
            return "查询成功，但暂无数据"
        if status_code == "EXECUTION_ERROR":
            return "当前查询失败"
        metric_label = self._label(result.query_plan.metrics[0]) if result.query_plan.metrics else ""
        return f"{metric_label}分析结果" if metric_label else "物流数据分析结果"

    def _build_highlights(
        self,
        *,
        result: LogisticsDataQaResult,
        status_code: str,
        answer: str,
        display_type: str,
    ) -> list[str]:
        """构建关键结论列表。

        参数：
            result: 后端确定性查询结果。
            status_code: 当前统一状态码。
            answer: 主回答文本，用于避免标签重复主回答。
            display_type: 当前展示类型，图表和表格态不再追加泛化行数标签。

        返回：
            去重后的业务提示列表。成功图表/表格的核心答案保留在 answer、图表和表格中，
            highlights 只承载额外提醒，避免同一总费用在多个标签里重复展示。
        """

        highlights: list[str] = []
        return self._dedupe_text_items(highlights, base_texts=[answer])[:4]

    def _build_caveats(self, result: LogisticsDataQaResult) -> list[str]:
        """构建口径和数据范围提醒。"""

        caveats: list[str] = []
        if result.calculation_logic:
            caveats.extend(result.calculation_logic[:3])
        if result.data_scope:
            scope = self._summarize_scope(result.data_scope)
            if scope:
                caveats.append(scope)
        return caveats[:5]

    def _build_caveat_items(
        self,
        *,
        result: LogisticsDataQaResult,
        status_code: str,
        caveats: list[str],
    ) -> list[LogisticsDataQaCaveatItem]:
        """构建兼容 caveats 的分级口径提醒。"""

        items: list[LogisticsDataQaCaveatItem] = [
            LogisticsDataQaCaveatItem(level="info", text=item)
            for item in caveats
            if item
        ]
        for warning in result.warnings[:5]:
            if not warning:
                continue
            items.append(
                LogisticsDataQaCaveatItem(
                    level="danger" if self._is_danger_caveat(warning) else "warning",
                    text=warning,
                )
            )
        if status_code == "EXECUTION_ERROR" and result.status and result.status.message:
            items.append(LogisticsDataQaCaveatItem(level="danger", text=result.status.message))
        return self._dedupe_caveat_items(items)[:8]

    def _build_cards(
        self,
        *,
        question: str,
        result: LogisticsDataQaResult,
    ) -> list[LogisticsDataQaPresentationCard]:
        """构建主结论指标卡。

        参数：
            question: 用户原始问题，用于识别显式图表诉求。
            result: 后端确定性查询结果。

        返回：
            指标卡列表。单行结果沿用行内数值；多行月度或维度拆分结果只展示合计、
            统计颗粒度和明细行数等主结论，不再把第一行明细冒充成总体结论。
        """

        if not result.result_table.rows:
            return []
        if len(result.result_table.rows) > 1:
            return self._build_multi_row_cards(question=question, result=result)
        row = result.result_table.rows[0]
        cards: list[LogisticsDataQaPresentationCard] = []
        for column in result.result_table.columns:
            value = row.get(column)
            if not self._is_number(value):
                continue
            cards.append(
                LogisticsDataQaPresentationCard(
                    label=self._label(column),
                    value=value,
                    unit=self._infer_unit(column),
                    description=None,
                )
            )
            if len(cards) >= 4:
                break
        return cards

    def _build_multi_row_cards(
        self,
        *,
        question: str,
        result: LogisticsDataQaResult,
    ) -> list[LogisticsDataQaPresentationCard]:
        """为多行拆分结果生成总体指标卡。

        参数：
            question: 用户原始问题。
            result: 多行结构化查询结果。

        返回：
            主结论指标卡，不包含任意单月或单维度首行明细。
        """

        cards: list[LogisticsDataQaPresentationCard] = []
        x_axis = self._choose_x_axis(result.result_table.columns)
        y_axis = self._choose_y_axis(result=result, x_axis=x_axis)
        if y_axis:
            metric_column = y_axis[0]
            summary_value = self._extract_summary_metric_value(
                result.answer_summary,
                metric_column=metric_column,
            )
            if summary_value is not None:
                cards.append(
                    LogisticsDataQaPresentationCard(
                        label=self._aggregate_label(metric_column),
                        value=summary_value,
                        unit=self._infer_unit(metric_column),
                    )
                )
        dimension_count = self._count_distinct_dimension_values(
            rows=result.result_table.rows,
            x_axis=x_axis,
        )
        if dimension_count is not None:
            cards.append(
                LogisticsDataQaPresentationCard(
                    label=self._dimension_count_label(x_axis),
                    value=dimension_count,
                    unit=self._dimension_count_unit(x_axis),
                )
            )
        if self._detect_requested_display(question) not in {"line_chart", "bar_chart", "pie_chart"}:
            cards.append(
                LogisticsDataQaPresentationCard(
                    label="明细行数",
                    value=len(result.result_table.rows),
                    unit="行",
                )
            )
        return cards[:4]

    def _build_chart_spec(
        self,
        *,
        question: str,
        result: LogisticsDataQaResult,
        display_type: str,
    ) -> LogisticsDataQaChartSpec | None:
        """按后端 rows 构造轻量图表配置。"""

        if display_type not in {"line_chart", "bar_chart", "pie_chart", "mixed"}:
            return None
        if not self._can_build_chart(result):
            return None
        x_axis = self._choose_x_axis(result.result_table.columns)
        y_axis = self._choose_y_axis(result=result, x_axis=x_axis)
        if not x_axis or not y_axis:
            return None
        requested = self._detect_requested_display(question)
        chart_type = "line" if requested == "line_chart" else "pie" if requested == "pie_chart" else "bar"
        if chart_type == "pie" and not self._pie_values_have_positive_total(result=result, x_axis=x_axis, y_axis=y_axis[0]):
            return None
        if display_type == "mixed" and requested not in {"line_chart", "pie_chart"}:
            chart_type = "bar"
        series = [
            {
                "name": self._label(column),
                "field": column,
                "data": [
                    {"x": row.get(x_axis), "y": row.get(column)}
                    for row in result.result_table.rows
                    if row.get(x_axis) is not None and self._is_number(row.get(column))
                ],
            }
            for column in y_axis
        ]
        return LogisticsDataQaChartSpec(
            chart_type=chart_type,
            title=f"{self._label(y_axis[0])}{'趋势图' if chart_type == 'line' else '占比图' if chart_type == 'pie' else '对比图'}",
            x_axis=x_axis,
            y_axis=y_axis,
            series=series,
            unit=self._infer_unit(y_axis[0]) if y_axis else None,
            data=list(result.result_table.rows),
        )

    def _build_follow_up_examples(self, result: LogisticsDataQaResult) -> list[str]:
        """根据缺失槽位生成补充示例。"""

        missing_slots = set(result.query_plan.clarification_missing_slots)
        examples: list[str] = []
        if "time_range" in missing_slots:
            examples.append("补充：限定为2025年全年。")
        if "metric_definition" in missing_slots or "evaluation_metric" in missing_slots:
            examples.append("补充：按总运费或单瓦成本口径判断。")
        if "dimension_split" in missing_slots:
            examples.append("补充：按承运商或省份维度拆分。")
        if not examples:
            examples.append("补充具体时间范围、统计指标和拆分维度后再查询。")
        return examples[:3]

    def _resolve_status_code(self, result: LogisticsDataQaResult) -> str:
        """兜底生成状态码。"""

        if result.needs_clarification:
            return "CLARIFICATION_REQUIRED"
        if not result.supported:
            return "UNSUPPORTED_QUESTION"
        if not result.result_table.rows:
            return "EMPTY_RESULT"
        return "OK"

    def _extract_json(self, content: str) -> dict[str, Any]:
        """从 LLM 文本中提取 JSON 对象。"""

        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        json_text = match.group(0) if match else stripped
        parsed = json.loads(json_text)
        return parsed if isinstance(parsed, dict) else {}

    def _normalize_chart_payload(self, payload: dict[str, Any]) -> LogisticsDataQaChartSpec | None:
        """清洗 LLM chart_spec。"""

        chart_type = payload.get("chart_type")
        if chart_type not in {"line", "bar", "pie"}:
            return None
        return LogisticsDataQaChartSpec(
            chart_type=chart_type,
            title=str(payload.get("title") or ""),
            x_axis=str(payload.get("x_axis") or ""),
            y_axis=[item for item in payload.get("y_axis", []) if isinstance(item, str)],
            series=[item for item in payload.get("series", []) if isinstance(item, dict)],
            unit=str(payload.get("unit")) if payload.get("unit") is not None else None,
            data=[item for item in payload.get("data", []) if isinstance(item, dict)],
        )

    def _table_spec_is_safe(self, *, table_spec: LogisticsDataQaTableSpec, result: LogisticsDataQaResult) -> bool:
        """校验 LLM 表格是否来自后端表格。"""

        backend_columns = set(result.result_table.columns)
        if not set(table_spec.columns).issubset(backend_columns):
            return False
        compare_columns = table_spec.columns or result.result_table.columns
        backend_rows = {self._row_signature(row, columns=compare_columns) for row in result.result_table.rows}
        for row in table_spec.rows:
            if not set(row.keys()).issubset(backend_columns):
                return False
            if self._row_signature(row, columns=compare_columns) not in backend_rows:
                return False
        return True

    def _chart_spec_is_safe(self, *, chart_spec: LogisticsDataQaChartSpec, result: LogisticsDataQaResult) -> bool:
        """校验 LLM 图表数据是否来自后端 rows。"""

        columns = set(result.result_table.columns)
        if chart_spec.x_axis not in columns:
            return False
        if not set(chart_spec.y_axis).issubset(columns):
            return False
        if chart_spec.data:
            table_spec = LogisticsDataQaTableSpec(columns=result.result_table.columns, rows=chart_spec.data)
            if not self._table_spec_is_safe(table_spec=table_spec, result=result):
                return False
        for series in chart_spec.series:
            field = series.get("field")
            if field and field not in columns:
                return False
            for item in series.get("data", []):
                if not isinstance(item, dict):
                    return False
                x_value = item.get("x")
                y_value = item.get("y")
                matched = any(
                    row.get(chart_spec.x_axis) == x_value
                    and any(row.get(column) == y_value for column in chart_spec.y_axis)
                    for row in result.result_table.rows
                )
                if not matched:
                    return False
        return True

    def _cards_are_safe(self, *, cards: list[LogisticsDataQaPresentationCard], result: LogisticsDataQaResult) -> bool:
        """校验指标卡中的数值是否来自后端 rows。"""

        allowed_numbers = self._collect_backend_number_tokens(result)
        for card in cards:
            if self._is_number(card.value) and self._number_token(card.value) not in allowed_numbers:
                return False
        return True

    def _text_numbers_are_safe(self, texts: list[str], *, result: LogisticsDataQaResult) -> bool:
        """校验主文案未新增后端不存在的数值。"""

        allowed = self._collect_backend_number_tokens(result) | self._collect_context_number_tokens(result)
        for text in texts:
            for token in self._extract_number_tokens(text):
                if token not in allowed:
                    return False
        return True

    def _visible_text_has_technical_leak(self, texts: list[str]) -> bool:
        """判断主展示文案是否泄露内部技术实现词。

        参数：
            texts: title、answer、highlights、caveats 等业务用户可见文案。
        返回：
            命中表名、字段名、SQL 或内部编排 key 时返回 True。
        业务逻辑：
            表格列名、debug 可保留后端字段；但自然语言展示必须面向业务口径，
            不能出现 dwd/ods/dws 表名、actual_watt、query_key 等实现细节。
        """

        visible_text = "\n".join(text for text in texts if text)
        if not visible_text:
            return False
        return any(token in visible_text for token in self.TECHNICAL_VISIBLE_TOKENS)

    def _collect_backend_number_tokens(self, result: LogisticsDataQaResult) -> set[str]:
        """收集后端结果中允许出现的数值 token。"""

        tokens: set[str] = set()
        for row in result.result_table.rows:
            for value in row.values():
                if self._is_number(value):
                    tokens.add(self._number_token(value))
        for token in self._extract_number_tokens(result.answer_summary):
            tokens.add(token)
        for item in result.calculation_logic:
            tokens.update(self._extract_number_tokens(item))
        return tokens

    def _collect_context_number_tokens(self, result: LogisticsDataQaResult) -> set[str]:
        """收集筛选条件和日期范围中允许出现在主文案里的数字。

        说明：
            年、月、季度和日期属于查询条件，不是业务指标值。
            允许这些数字出现在 LLM 主文案中，避免“2026年1月到3月”被误判为数值幻觉；
            指标卡、表格和图表仍必须来自后端 rows。
        """

        tokens: set[str] = set()
        context_payloads = [result.query_plan.filters, result.data_scope]
        for payload in context_payloads:
            self._collect_context_tokens_from_value(payload, tokens=tokens, parent_key="")
        for row in result.result_table.rows:
            for key, value in row.items():
                if self._is_context_key(key):
                    tokens.update(self._extract_context_number_tokens(str(value)))
        return tokens

    def _collect_context_tokens_from_value(self, value: Any, *, tokens: set[str], parent_key: str) -> None:
        """递归收集上下文字段里的日期/时间数字 token。"""

        if isinstance(value, dict):
            for key, child in value.items():
                next_key = f"{parent_key}.{key}" if parent_key else str(key)
                self._collect_context_tokens_from_value(child, tokens=tokens, parent_key=next_key)
            return
        if isinstance(value, list):
            for item in value:
                self._collect_context_tokens_from_value(item, tokens=tokens, parent_key=parent_key)
            return
        if value is None:
            return
        if self._is_context_key(parent_key):
            tokens.update(self._extract_context_number_tokens(str(value)))

    def _extract_context_number_tokens(self, text: str) -> set[str]:
        """提取时间/范围上下文里的安全数字。

        说明：
            日期字符串里的连字符不是负号，例如 2026-03 应允许 2026 和 3，
            但不能把它当成业务指标 -3。
        """

        tokens = self._extract_number_tokens(text)
        for match in re.finditer(r"(20\d{2})[-/年](\d{1,2})(?:[-/月](\d{1,2}))?", text or ""):
            tokens.add(self._number_token(match.group(1)))
            tokens.add(self._number_token(match.group(2)))
            if match.group(3):
                tokens.add(self._number_token(match.group(3)))
        return tokens

    def _is_context_key(self, key: str) -> bool:
        """判断字段是否属于时间/范围等非指标上下文。"""

        normalized = key.lower()
        return any(
            marker in normalized
            for marker in (
                "year",
                "month",
                "date",
                "time",
                "quarter",
                "range",
                "scope",
                "start",
                "end",
                "biz_month",
            )
        )

    def _display_type_ignores_user_request(
        self,
        *,
        question: str,
        result: LogisticsDataQaResult,
        display_type: str,
        fallback: LogisticsDataQaPresentation,
    ) -> bool:
        """判断 LLM 是否忽略了用户明确要求的展示形式。"""

        requested = self._detect_requested_display(question)
        if requested is None:
            # 用户没有明确要求图表/表格/指标卡时，LLM 不能主动切换到结构化展示。
            return display_type in {"summary_cards", "table", "line_chart", "bar_chart", "pie_chart", "mixed"}
        if requested in {"line_chart", "bar_chart", "pie_chart"}:
            can_build = self._can_build_pie_chart(result) if requested == "pie_chart" else self._can_build_chart(result)
            if can_build:
                return display_type not in {requested, "mixed"}
            return False
        if requested == "table" and result.result_table.rows:
            return display_type not in {"table", "mixed"} and fallback.table_spec is not None
        if requested == "summary_cards" and self._build_cards(question=question, result=result):
            return display_type not in {"summary_cards", "mixed"}
        return False

    def _extract_number_tokens(self, text: str) -> set[str]:
        """从文本中提取规范化数字 token。"""

        tokens: set[str] = set()
        for raw in re.findall(r"-?\d+(?:,\d{3})*(?:\.\d+)?", text or ""):
            normalized = raw.replace(",", "")
            try:
                tokens.add(self._number_token(normalized))
            except Exception:  # noqa: BLE001
                continue
        return tokens

    def _number_token(self, value: Any) -> str:
        """把数字统一成可比较 token。"""

        number = Decimal(str(value).replace(",", ""))
        normalized = number.normalize()
        return format(normalized, "f").rstrip("0").rstrip(".") or "0"

    def _row_signature(self, row: dict[str, Any], *, columns: list[str]) -> str:
        """生成行签名，用于防止 LLM 新增行。"""

        return json.dumps({column: row.get(column) for column in columns}, ensure_ascii=False, sort_keys=True, default=str)

    def _can_build_chart(self, result: LogisticsDataQaResult) -> bool:
        """判断是否具备图表展示基础。"""

        if len(result.result_table.rows) < 2:
            return False
        x_axis = self._choose_x_axis(result.result_table.columns)
        y_axis = self._choose_y_axis(result=result, x_axis=x_axis)
        return bool(x_axis and y_axis)

    def _can_build_pie_chart(self, result: LogisticsDataQaResult) -> bool:
        """判断当前结果是否适合饼图展示。

        返回：
            True 表示存在维度字段、主指标字段，且主指标至少有一个正值。
            全零或无正值时不画饼图，避免业务用户误读空占比。
        """

        if not self._can_build_chart(result):
            return False
        x_axis = self._choose_x_axis(result.result_table.columns)
        y_axis = self._choose_y_axis(result=result, x_axis=x_axis)
        return bool(y_axis and self._pie_values_have_positive_total(result=result, x_axis=x_axis, y_axis=y_axis[0]))

    def _pie_values_have_positive_total(self, *, result: LogisticsDataQaResult, x_axis: str, y_axis: str) -> bool:
        """校验饼图切片数值是否有正向总量。

        参数：
            result: 后端确定性查询结果。
            x_axis: 饼图切片维度字段。
            y_axis: 饼图数值字段。

        返回：
            至少一个切片为正数时返回 True。
        """

        if not x_axis or not y_axis:
            return False
        total = Decimal("0")
        for row in result.result_table.rows:
            if row.get(x_axis) is None or not self._is_number(row.get(y_axis)):
                continue
            number = Decimal(str(row.get(y_axis)).replace(",", ""))
            if number < 0:
                return False
            total += number
        return total > 0

    def _choose_x_axis(self, columns: list[str]) -> str:
        """选择图表 X 轴字段。"""

        preferred = ["biz_month", "month", "year_month", "scope_label", "province", "region_name", "customer_name", "carrier_name", "company_name", "transport_mode", "city"]
        for column in preferred:
            if column in columns:
                return column
        return columns[0] if columns else ""

    def _choose_y_axis(self, *, result: LogisticsDataQaResult, x_axis: str) -> list[str]:
        """选择图表 Y 轴字段。

        参数：
            result: 后端确定性查询结果。
            x_axis: 已选定的 X 轴字段。

        返回：
            图表主指标字段列表。优先使用 query_plan.metrics 中的业务指标，
            避免把 task_count、parse_fail_count 等质量辅助字段混进总运费条形图。
        """

        columns = list(result.result_table.columns)
        rows = list(result.result_table.rows)
        numeric_columns = [
            column
            for column in columns
            if column != x_axis and any(self._is_number(row.get(column)) for row in rows)
        ]
        y_axis: list[str] = []
        for metric in result.query_plan.metrics:
            if metric in numeric_columns and metric not in y_axis:
                y_axis.append(metric)
        if y_axis:
            return y_axis[:2]
        business_priority = [
            "total_fee",
            "shipment_mw",
            "shipment_watt",
            "avg_fee",
            "avg_fee_per_watt",
            "unit_fee_per_watt",
            "fee_per_watt",
            "signedfor_rate",
            "extra_fee_amount",
            "extra_fee",
            "shipment_trip_count",
            "trip_count",
        ]
        for column in business_priority:
            if column in numeric_columns and column not in y_axis:
                y_axis.append(column)
        if y_axis:
            return y_axis[:2]
        for column in numeric_columns:
            if self._is_quality_or_diagnostic_column(column):
                continue
            y_axis.append(column)
            if len(y_axis) >= 2:
                break
        if y_axis:
            return y_axis
        return numeric_columns[:1]

    def _extract_summary_metric_value(self, text: str, *, metric_column: str) -> str | None:
        """从确定性摘要中提取主指标合计值。

        参数：
            text: 后端 answer_summary。
            metric_column: 需要提取的主指标字段。

        返回：
            字符串数值；未命中时返回 None。该方法只读取已有摘要，不重新计算业务结果。
        """

        if not text:
            return None
        label_patterns = self._metric_summary_patterns(metric_column)
        for label_pattern in label_patterns:
            match = re.search(
                rf"(?:合计|总计)?{label_pattern}(?:为|是|约为)?\s*([0-9][0-9,]*(?:\.\d+)?)",
                text,
            )
            if match:
                return match.group(1).replace(",", "")
        return None

    def _metric_summary_patterns(self, metric_column: str) -> list[str]:
        """返回摘要中可能表达主指标的中文模式。"""

        mapping: dict[str, list[str]] = {
            "total_fee": ["总运费", "总费用", "运费"],
            "shipment_mw": ["发运量", "总发运量", "运量"],
            "shipment_watt": ["发运瓦数", "总瓦数", "运量"],
            "shipment_trip_count": ["车次", "总车次"],
            "trip_count": ["车次", "总车次"],
            "task_count": ["任务数"],
            "avg_fee": ["平均运费"],
            "avg_fee_per_watt": ["平均元/瓦", "单瓦成本"],
            "unit_fee_per_watt": ["平均元/瓦", "单瓦成本"],
            "signedfor_rate": ["签收率"],
            "extra_fee_amount": ["额外费用"],
            "extra_fee": ["额外费用"],
        }
        return mapping.get(metric_column, [re.escape(self._label(metric_column))])

    def _aggregate_label(self, metric_column: str) -> str:
        """生成多行拆分结果的总体指标卡名称。"""

        if metric_column in {"total_fee", "shipment_mw", "shipment_watt", "shipment_trip_count", "trip_count"}:
            return f"合计{self._label(metric_column)}"
        return self._label(metric_column)

    def _count_distinct_dimension_values(self, *, rows: list[dict[str, Any]], x_axis: str) -> int | None:
        """统计 X 轴维度去重数量。"""

        if not rows or not x_axis:
            return None
        values = {row.get(x_axis) for row in rows if row.get(x_axis) is not None}
        return len(values) if values else None

    def _dimension_count_label(self, x_axis: str) -> str:
        """生成维度数量卡片名称。"""

        if x_axis in {"biz_month", "month", "year_month"}:
            return "统计月份"
        return f"{self._label(x_axis)}数"

    def _dimension_count_unit(self, x_axis: str) -> str:
        """生成维度数量卡片单位。"""

        if x_axis in {"biz_month", "month", "year_month"}:
            return "个月"
        return "项"

    def _is_quality_or_diagnostic_column(self, column: str) -> bool:
        """判断字段是否为质量提示或诊断辅助字段。"""

        normalized = column.lower()
        return any(
            marker in normalized
            for marker in (
                "missing",
                "fail",
                "parse",
                "error",
                "warning",
                "row_count",
                "record_count",
                "strict_scope",
                "available_count",
            )
        )

    def _sanitize_presentation(self, presentation: LogisticsDataQaPresentation) -> None:
        """对最终 presentation 做展示卫生清理。

        参数：
            presentation: 待输出给前端的展示编排。

        返回：
            无返回值，直接原地去掉重复文案。
        """

        presentation.highlights = self._dedupe_text_items(
            presentation.highlights,
            base_texts=[presentation.answer, presentation.title],
        )
        presentation.caveats = self._dedupe_text_items(presentation.caveats)
        presentation.caveat_items = self._dedupe_caveat_items(presentation.caveat_items)

    def _find_presentation_hygiene_issue(
        self,
        *,
        question: str,
        result: LogisticsDataQaResult,
        presentation: LogisticsDataQaPresentation,
    ) -> str | None:
        """识别 LLM 展示候选中的鲁棒性问题。

        参数：
            question: 用户原始问题。
            result: 后端确定性查询结果。
            presentation: LLM 归一化后的展示候选。

        返回：
            问题编码；没有问题返回 None。调用方据此回落到确定性安全展示。
        """

        requested = self._detect_requested_display(question)
        if requested in {"line_chart", "bar_chart", "pie_chart"}:
            can_build = self._can_build_pie_chart(result) if requested == "pie_chart" else self._can_build_chart(result)
        else:
            can_build = False
        if requested in {"line_chart", "bar_chart", "pie_chart"} and can_build:
            if not presentation.chart_spec:
                return "chart_missing"
            expected_chart_type = "line" if requested == "line_chart" else "pie" if requested == "pie_chart" else "bar"
            if presentation.chart_spec.chart_type != expected_chart_type:
                return "chart_type_mismatch"
        if any(self._is_similar_text(item, presentation.answer) for item in presentation.highlights):
            return "repeated_text"
        if self._cards_look_like_first_row(cards=presentation.cards, result=result):
            return "cards_from_first_row"
        return None

    def _cards_look_like_first_row(
        self,
        *,
        cards: list[LogisticsDataQaPresentationCard],
        result: LogisticsDataQaResult,
    ) -> bool:
        """判断多行结果的指标卡是否直接来自第一行明细。"""

        if len(result.result_table.rows) <= 1 or not cards:
            return False
        first_row = result.result_table.rows[0]
        first_row_tokens = {
            self._number_token(value)
            for value in first_row.values()
            if self._is_number(value)
        }
        if not first_row_tokens:
            return False
        card_tokens = {
            self._number_token(card.value)
            for card in cards
            if self._is_number(card.value)
        }
        if not card_tokens:
            return False
        return bool(card_tokens) and card_tokens.issubset(first_row_tokens)

    def _dedupe_text_items(self, items: list[str], *, base_texts: list[str] | None = None) -> list[str]:
        """按业务展示语义去重文案列表。"""

        result: list[str] = []
        anchors = [item for item in (base_texts or []) if item]
        for item in items:
            if not item:
                continue
            if any(self._is_similar_text(item, anchor) for anchor in anchors):
                continue
            if any(self._is_similar_text(item, existing) for existing in result):
                continue
            result.append(item)
        return result

    def _is_similar_text(self, left: str, right: str) -> bool:
        """判断两段展示文案是否重复或高度相似。"""

        left_norm = self._normalize_text_for_dedupe(left)
        right_norm = self._normalize_text_for_dedupe(right)
        if not left_norm or not right_norm:
            return False
        if left_norm == right_norm:
            return True
        shorter, longer = sorted((left_norm, right_norm), key=len)
        return len(shorter) >= 12 and shorter in longer

    def _normalize_text_for_dedupe(self, text: str) -> str:
        """归一化展示文案，供去重比较使用。"""

        return re.sub(r"[\s，。,.；;：:、（）()]+", "", text or "").lower()

    def _normalize_string_list(self, value: Any) -> list[str]:
        """清洗字符串列表。"""

        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    def _normalize_caveat_items(self, value: Any) -> list[LogisticsDataQaCaveatItem]:
        """清洗 LLM 返回的分级口径提醒。"""

        if not isinstance(value, list):
            return []
        items: list[LogisticsDataQaCaveatItem] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            level = str(item.get("level") or "info")
            if not text or level not in {"info", "warning", "danger"}:
                continue
            items.append(LogisticsDataQaCaveatItem(level=level, text=text))  # type: ignore[arg-type]
        return self._dedupe_caveat_items(items)

    def _dedupe_caveat_items(self, items: list[LogisticsDataQaCaveatItem]) -> list[LogisticsDataQaCaveatItem]:
        """按提醒文本去重，同时保留更高风险等级。"""

        rank = {"info": 0, "warning": 1, "danger": 2}
        deduped: dict[str, LogisticsDataQaCaveatItem] = {}
        for item in items:
            key = self._normalize_text_for_dedupe(item.text)
            if not key:
                continue
            existing = deduped.get(key)
            if existing is None or rank[item.level] > rank[existing.level]:
                deduped[key] = item
        return list(deduped.values())

    def _is_danger_caveat(self, text: str) -> bool:
        """判断提醒是否需要在前端按醒目风险展示。"""

        value = text or ""
        # “异常值归入其他”属于普通口径兜底说明，不代表查询失败或结果不可用；
        # danger 只保留给会让结果不可用、严重缺失或执行失败的风险，避免普通回答被大红框打断。
        if re.search(r"异常值归入[“\"]?其他[”\"]?", value):
            return False
        return bool(re.search(r"失败|错误|严重|高风险|无法|中断|结果不可用|数据异常|系统异常|计算异常", value))

    def _summarize_scope(self, data_scope: dict[str, Any]) -> str:
        """把数据范围简要转换成业务可读提醒。"""

        important_keys = ["table", "tables", "year", "months", "province", "region_name", "customer_name", "carrier_name", "transport_mode"]
        parts: list[str] = []
        for key in important_keys:
            if key not in data_scope:
                continue
            value = data_scope[key]
            if value is None or value == "":
                continue
            if isinstance(value, list):
                value_text = "、".join(str(item) for item in value)
            else:
                value_text = str(value)
            parts.append(f"{self._label(key)}：{value_text}")
        return "数据范围：" + "；".join(parts) if parts else ""

    def _label(self, column: str) -> str:
        """返回字段中文展示名。"""

        return self.COLUMN_LABELS.get(column, column.replace("_", " "))

    def _infer_unit(self, column: str) -> str | None:
        """按字段名推断单位。"""

        if "mw" in column:
            return "MW"
        if "watt" in column and "per" not in column:
            return "W"
        if "fee" in column and "per_watt" not in column:
            return "元"
        if "rate" in column or "ratio" in column or "share" in column:
            return "%"
        if "count" in column or "trip" in column:
            return "次"
        return None

    def _is_number(self, value: Any) -> bool:
        """判断值是否可作为数值展示。"""

        if value is None or value == "":
            return False
        try:
            Decimal(str(value).replace(",", ""))
            return True
        except Exception:  # noqa: BLE001
            return False
