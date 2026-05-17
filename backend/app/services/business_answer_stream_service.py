from __future__ import annotations

import json
import re
from copy import deepcopy
from decimal import Decimal
from typing import Any, Iterable

from openai import OpenAI

from backend.app.core.config import settings


JSONLineEvent = dict[str, Any]


def build_json_line_event(event: str, data: dict[str, Any]) -> str:
    """构造前端可增量解析的一行 JSON 流事件。

    参数：
        event: 事件名，常用值包括 meta、delta、done、error。
        data: 当前事件的数据体，必须可 JSON 序列化。

    返回：
        以换行符结尾的 JSON 字符串。
    """

    return json.dumps({"event": event, "data": data}, ensure_ascii=False, default=str) + "\n"


class BusinessAnswerStreamService:
    """业务智能问答的流式答案表达服务。

    说明：
        1. 后端先完成确定性查询、计算和表格生成；
        2. 本服务只把“用户原问题 + 确定性结果快照”交给 LLM 做答案表达；
        3. LLM 流式输出只替换 presentation.answer，不允许改表格、状态、查询结果和数值事实；
        4. 未配置 LLM 或调用失败时，将确定性答案切块流式返回，保证前端体验不退化。
    """

    MAX_PROMPT_ROWS = 30
    MAX_PROMPT_CHARS = 12000
    FALLBACK_CHUNK_SIZE = 18
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
        r"\btrace_id\b",
        r"\binternal\b",
        r"\braw_result\b",
        r"\bschema\b",
        r"\bLLM\b",
        r"\bods_[a-z0-9_]*",
        r"\bdwd_[a-z0-9_]*",
        r"\bdws_[a-z0-9_]*",
        r"\b[a-z]+_[a-z0-9_]+\b",
    )
    NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])-?\d+(?:,\d{3})*(?:\.\d+)?")

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        client: Any | None = None,
        timeout: float | None = None,
    ) -> None:
        """初始化流式答案表达服务。

        参数：
            enabled: 是否启用 LLM 表达，默认跟随全局答案表达开关。
            base_url: OpenAI 兼容接口地址。
            api_key: OpenAI 兼容接口密钥。
            model: 使用的表达模型名。
            client: 测试注入的 OpenAI 兼容客户端。
            timeout: 单次 LLM 调用超时时间。

        返回：
            无返回值。
        """

        self.enabled = settings.llm_answer_presentation_enabled if enabled is None else enabled
        self.base_url = base_url if base_url is not None else settings.llm_base_url
        self.api_key = api_key if api_key is not None else settings.llm_api_key
        self.model = model if model is not None else (settings.llm_answer_presentation_model or settings.llm_model)
        self.timeout = timeout if timeout is not None else settings.llm_answer_presentation_timeout
        self._client = client
        self._last_stream_source = "deterministic_fallback"
        self._last_fallback_reason = "not_started"

    def stream_answer(
        self,
        *,
        domain: str,
        question: str,
        deterministic_payload: dict[str, Any],
        fallback_answer: str | None = None,
    ) -> Iterable[str]:
        """流式生成业务答案文本。

        参数：
            domain: 业务域标识，例如 logistics 或 plan_bom。
            question: 用户原始问题，必须进入 LLM 上下文。
            deterministic_payload: 后端确定性结果快照。
            fallback_answer: LLM 不可用时的确定性答案。

        返回：
            文本 chunk 迭代器；每个 chunk 都可直接追加到前端气泡中。
        """

        fallback = self._resolve_fallback_answer(deterministic_payload, fallback_answer)
        if not self._is_llm_available():
            self._last_stream_source = "deterministic_fallback"
            self._last_fallback_reason = "llm_not_configured"
            yield from self._chunk_text(fallback)
            return
        try:
            self._last_stream_source = "llm"
            self._last_fallback_reason = ""
            stream = self._create_llm_stream(domain=domain, question=question, deterministic_payload=deterministic_payload)
            chunks: list[str] = []
            buffered_chunks: list[str] = []
            for event in stream:
                chunk = self._extract_delta_text(event)
                if not chunk:
                    continue
                chunks.append(chunk)
                if not buffered_chunks and self._can_yield_chunk_before_full_validation(
                    chunk,
                    deterministic_payload=deterministic_payload,
                ):
                    # 首段如果不含数字、技术词或英文内部标识，可以先给前端，避免流式体验退化为“等完整输出”。
                    # 含业务数值的片段仍要等整段校验通过后再输出，防止 LLM 新增或错配事实。
                    yield chunk
                    continue
                buffered_chunks.append(chunk)
            streamed_answer = "".join(chunks).strip()
            if not streamed_answer:
                self._last_stream_source = "deterministic_fallback"
                self._last_fallback_reason = "llm_empty_stream"
                yield from self._chunk_text(fallback)
                return
            validation_error = self._validate_streamed_answer(streamed_answer, deterministic_payload=deterministic_payload)
            if validation_error:
                self._last_stream_source = "deterministic_fallback"
                self._last_fallback_reason = validation_error
                yield from self._chunk_text(fallback)
                return
            for chunk in buffered_chunks:
                yield chunk
        except Exception as exc:  # noqa: BLE001
            # LLM 只负责表达增强，失败不能影响确定性查询结果可用性。
            self._last_stream_source = "deterministic_fallback"
            self._last_fallback_reason = f"llm_stream_error:{type(exc).__name__}"
            yield from self._chunk_text(fallback)

    def apply_streamed_answer(
        self,
        *,
        domain: str,
        deterministic_payload: dict[str, Any],
        streamed_answer: str,
    ) -> dict[str, Any]:
        """把流式答案合并回响应 payload。

        参数：
            domain: 业务域标识，用于兜底 presentation 标题。
            deterministic_payload: 原始确定性响应，不会被原地修改。
            streamed_answer: LLM 或降级流式输出的完整答案。

        返回：
            已更新 presentation.answer 的响应 payload；表格和状态保持确定性原值。
        """

        payload = deepcopy(deterministic_payload)
        fallback = self._resolve_fallback_answer(payload, None)
        candidate_answer = streamed_answer.strip()
        validation_error = (
            self._validate_streamed_answer(candidate_answer, deterministic_payload=payload)
            if candidate_answer
            else "stream_empty_answer"
        )
        if validation_error and candidate_answer != fallback:
            # 最终写回前再校验一次，防止调用方绕过 stream_answer 直接合并不安全文本。
            self._last_stream_source = "deterministic_fallback"
            self._last_fallback_reason = validation_error
            final_answer = fallback
        else:
            final_answer = candidate_answer or fallback
        presentation = payload.get("presentation")
        if not isinstance(presentation, dict):
            presentation = {
                "display_type": "narrative",
                "title": self._default_title(domain),
                "answer": final_answer,
                "highlights": [],
                "table_spec": None,
                "caveats": [],
                "debug": {},
            }
            payload["presentation"] = presentation
        presentation["answer"] = final_answer
        debug = presentation.get("debug")
        if not isinstance(debug, dict):
            debug = {}
            presentation["debug"] = debug
        debug["stream_answer_source"] = self._last_stream_source
        debug["stream_fallback_reason"] = self._last_fallback_reason or None
        if self._last_stream_source == "llm":
            debug["llm_model_name"] = self.model
        debug["stream_answer_domain"] = domain
        return payload

    def _create_llm_stream(self, *, domain: str, question: str, deterministic_payload: dict[str, Any]):
        """创建 OpenAI 兼容流式响应对象。

        参数：
            domain: 业务域标识。
            question: 用户原始问题。
            deterministic_payload: 确定性结果快照。

        返回：
            OpenAI 兼容流式事件迭代器。
        """

        client = self._client or OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout,
            max_retries=settings.llm_answer_presentation_max_retries,
        )
        return client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            stream=True,
            messages=[
                {"role": "system", "content": self._build_system_prompt(domain)},
                {"role": "user", "content": self._build_user_prompt(question, deterministic_payload)},
            ],
        )

    def _is_llm_available(self) -> bool:
        """判断 LLM 流式表达是否可用。"""

        return bool(self.enabled and self.base_url and self.api_key and self.model)

    @classmethod
    def _build_system_prompt(cls, domain: str) -> str:
        """构造约束 LLM 只做表达的系统提示词。"""

        domain_label = "计划 BOM" if domain == "plan_bom" else "物流经营"
        return (
            f"你是{domain_label}智能问答的答案表达层。"
            "你会收到用户原问题和后端确定性查询结果。"
            "你的任务是用中文业务口吻流式输出更自然、更有 AI 感的答案。"
            "严禁新增、猜测或改写订单、客户、供应商、金额、数量、比例、日期、规格、功率、CTM 等事实。"
            "表格、状态和数值以系统给出的确定性结果为准；如果明细很多，只概括结论并提示用户查看下方表格。"
            "对排名、排行、TopN、前几名这类问题，如果确定性结果表是五行以内的小表，请逐项复述每个名称和对应数值；超过五行时只概括前几项并提示查看明细。"
            "逐项表达时优先使用中文序号或项目符号，不要使用 1./2. 这类阿拉伯数字序号，避免被误认为业务指标。"
            "不要输出 JSON、Markdown 表格或代码块；不要暴露字段名、SQL、内部状态码、debug 信息。"
            "如果结果要求澄清或暂不支持，要温和说明原因并给出可执行的补充问法。"
        )

    def _build_user_prompt(self, question: str, deterministic_payload: dict[str, Any]) -> str:
        """把用户原问题和确定性结果压缩为 LLM 上下文。"""

        prompt_payload = {
            "用户原问题": question,
            "确定性结果": self._compact_payload(deterministic_payload),
            "表达要求": [
                "先直接回答业务员最关心的结论，再说明依据。",
                "只引用确定性结果中出现的事实；不要补充外部知识。",
                "如果是排名/排行/TopN/前几名问题，且结构化结果在五行以内，请在正文里逐项写出每个名称和对应数值，让回答更完整。",
                "如果结构化结果超过五行，可以只概括关键结论并提示用户查看下方表格，不要把大表全文搬进正文。",
                "语气专业、清楚、有温度，但不要夸张营销。",
            ],
        }
        text = json.dumps(prompt_payload, ensure_ascii=False, default=str)
        if len(text) <= self.MAX_PROMPT_CHARS:
            return text
        return text[: self.MAX_PROMPT_CHARS] + "\n【上下文因过长已截断，请只基于已给出的确定性事实表达。】"

    def _compact_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """压缩确定性响应，白名单保留 LLM 表达所需事实。

        业务逻辑：
            LLM 只做答案表达，不需要 query_plan、debug、planner、guardrail 等内部编排信息。
            这里改为白名单构造 prompt 上下文，并把内部实现键转换成业务可读键，只保留
            业务结论、查询状态、结构化结果、展示建议和口径提示，降低内部字段泄露风险。
        """

        compact: dict[str, Any] = {}
        if payload.get("answer_summary") is not None:
            compact["业务结论"] = payload.get("answer_summary")
        status = payload.get("status")
        if isinstance(status, dict):
            compact["查询状态"] = {
                key: status.get(key)
                for key in ("message", "success")
                if status.get(key) is not None
            }
        result_table = payload.get("result_table")
        if isinstance(result_table, dict):
            compact["结构化结果"] = {
                key: deepcopy(result_table.get(key))
                for key in ("columns", "rows")
                if key in result_table
            }
            self._truncate_table(compact["结构化结果"])
        presentation = payload.get("presentation")
        if isinstance(presentation, dict):
            compact_presentation: dict[str, Any] = {}
            if presentation.get("title") is not None:
                compact_presentation["标题"] = deepcopy(presentation.get("title"))
            if presentation.get("answer") is not None:
                compact_presentation["业务回答草稿"] = deepcopy(presentation.get("answer"))
            if presentation.get("caveats") is not None:
                compact_presentation["数据口径"] = deepcopy(presentation.get("caveats"))
            if presentation.get("caveat_items") is not None:
                compact_presentation["口径提示"] = deepcopy(presentation.get("caveat_items"))
            if presentation.get("table_spec") is not None:
                compact_presentation["展示明细"] = deepcopy(presentation.get("table_spec"))
                self._truncate_table(compact_presentation.get("展示明细"))
            if compact_presentation:
                compact["展示建议"] = compact_presentation
        for key, label in (("caveats", "数据口径"), ("caveat_items", "口径提示"), ("warnings", "风险提示")):
            if payload.get(key) is not None:
                compact[label] = deepcopy(payload.get(key))
        self._remove_internal_prompt_fields(compact)
        return compact

    def _can_yield_chunk_before_full_validation(self, chunk: str, *, deterministic_payload: dict[str, Any]) -> bool:
        """判断一个流式片段是否可在完整答案校验前先发给前端。

        参数：
            chunk: LLM 当前增量片段。
            deterministic_payload: 后端确定性结果快照；保留参数便于后续扩展更细粒度安全判断。

        返回：
            True 表示片段不包含数字、英文内部标识或技术词，可先输出；False 表示必须等完整校验。
        """

        _ = deterministic_payload
        text = str(chunk or "")
        if not text:
            return False
        if len(text) > 30:
            return False
        if self._extract_number_tokens(text):
            return False
        if self._visible_text_has_technical_leak(text):
            return False
        return not re.search(r"[A-Za-z_]", text)

    def _remove_internal_prompt_fields(self, value: Any) -> None:
        """从发给 LLM 的表达上下文中移除内部排查字段。"""

        sanitized = self._sanitize_prompt_value(value)
        if isinstance(value, dict):
            value.clear()
            if isinstance(sanitized, dict):
                value.update(sanitized)
            return
        if isinstance(value, list):
            value.clear()
            if isinstance(sanitized, list):
                value.extend(sanitized)

    def _sanitize_prompt_value(self, value: Any) -> Any | None:
        """递归清理 prompt 上下文中的内部键和值。

        返回：
            清理后的值；None 表示该字段/列表项应被删除。
        """

        if isinstance(value, dict):
            sanitized: dict[Any, Any] = {}
            for key, child_value in value.items():
                if self._is_internal_prompt_text(str(key)):
                    continue
                child = self._sanitize_prompt_value(child_value)
                if child is not None:
                    sanitized[key] = child
            return sanitized
        if isinstance(value, list):
            sanitized_items: list[Any] = []
            for item in value:
                child = self._sanitize_prompt_value(item)
                if child is not None:
                    sanitized_items.append(child)
            return sanitized_items
        if isinstance(value, str) and self._is_internal_prompt_text(value):
            return None
        return value

    @staticmethod
    def _is_internal_prompt_text(text: str) -> bool:
        """判断 prompt 键或文本值是否包含不应给 LLM 的内部字段/技术痕迹。"""

        lowered = (text or "").lower()
        internal_markers = (
            "槽位", "字段", "表定义", "库定义", "数据库", "query_key", "query_plan", "query-plan", "query plan",
            "group_by", "debug", "trace", "raw_result", "schema", "planner", "guardrail", "guard rail", "sql", "internal",
            "ods_", "dwd_", "dws_", "llm",
        )
        return any(marker in lowered for marker in internal_markers)

    def _validate_streamed_answer(self, answer: str, *, deterministic_payload: dict[str, Any]) -> str | None:
        """校验流式答案是否可作为最终业务叙事。

        参数：
            answer: LLM 已完整输出的主回答文本。
            deterministic_payload: 后端确定性结果快照。

        返回：
            None 表示可采用；非空错误码表示必须回落到确定性答案。
        """

        if not answer.strip():
            return "stream_empty_answer"
        if self._visible_text_has_technical_leak(answer):
            return "stream_technical_visible_leak"
        if not self._answer_numbers_are_safe(answer, deterministic_payload=deterministic_payload):
            return "stream_text_number_hallucination"
        if not self._answer_row_bindings_are_safe(answer, deterministic_payload=deterministic_payload):
            return "stream_structured_fact_mismatch"
        return None

    @classmethod
    def _visible_text_has_technical_leak(cls, answer: str) -> bool:
        """判断流式主回答或兜底文本是否泄露 SQL、表名、字段名或内部编排信息。"""

        return any(re.search(pattern, answer or "", flags=re.I) for pattern in cls.TECHNICAL_VISIBLE_PATTERNS)

    def _answer_numbers_are_safe(self, answer: str, *, deterministic_payload: dict[str, Any]) -> bool:
        """判断流式主回答中的数字是否全部来自确定性上下文。"""

        answer_tokens = self._extract_number_tokens(answer)
        if not answer_tokens:
            return True
        allowed_context = self._compact_payload(deterministic_payload)
        allowed_tokens = self._collect_allowed_number_tokens(allowed_context)
        return answer_tokens.issubset(allowed_tokens)

    def _answer_row_bindings_are_safe(self, answer: str, *, deterministic_payload: dict[str, Any]) -> bool:
        """校验结构化行中的“名称-数值”绑定没有被 LLM 错配。

        业务逻辑：
            数字白名单只能保证 LLM 没有新增数字，但不能防止把“华东 120.5MW”说成
            “华北 120.5MW”。因此只要主回答复述了某一行的指标数字，就要求同一语句
            中同时出现该行的非数字维度值。若 LLM 错配名称和值，则降级到确定性答案。
        """

        clauses = self._split_answer_fact_clauses(answer)
        if not clauses:
            return True
        for table in self._iter_structured_tables(deterministic_payload):
            rows = table.get("rows") if isinstance(table, dict) else None
            if not isinstance(rows, list):
                continue
            row_bindings: list[tuple[list[str], set[str]]] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                entity_values = self._collect_row_entity_values(row)
                metric_tokens = self._collect_row_metric_number_tokens(row)
                if entity_values and metric_tokens:
                    row_bindings.append((entity_values, metric_tokens))
            if not row_bindings:
                continue
            for clause in clauses:
                clause_tokens = self._extract_number_tokens(clause)
                if not clause_tokens:
                    continue
                mentioned_entities = [
                    entity
                    for entity_values, _metric_tokens in row_bindings
                    for entity in entity_values
                    if entity in clause
                ]
                for token in clause_tokens:
                    allowed_entities_for_token = [
                        entity
                        for entity_values, metric_tokens in row_bindings
                        if token in metric_tokens
                        for entity in entity_values
                    ]
                    if not allowed_entities_for_token:
                        continue
                    if not mentioned_entities:
                        return False
                    if not any(entity in allowed_entities_for_token for entity in mentioned_entities):
                        return False
                    if any(entity not in allowed_entities_for_token for entity in mentioned_entities):
                        return False
        return True

    def _split_answer_fact_clauses(self, answer: str) -> list[str]:
        """把答案切成适合校验名称-数值绑定的短分句。"""

        return [clause.strip() for clause in re.split(r"[\n。；;！？!?，,、]+", answer or "") if clause.strip()]

    def _iter_structured_tables(self, payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
        """遍历可用于答案事实绑定校验的结构化表格。"""

        result_table = payload.get("result_table")
        if isinstance(result_table, dict):
            yield result_table
        presentation = payload.get("presentation")
        if isinstance(presentation, dict):
            table_spec = presentation.get("table_spec")
            if isinstance(table_spec, dict):
                yield table_spec

    def _collect_row_entity_values(self, row: dict[str, Any]) -> list[str]:
        """提取一行中的维度实体值，如城市、订单号、功率档等。

        业务逻辑：
            维度实体不一定是纯文本，BOM 单号、功率档 620W、型号等都可能带数字。
            因此不能简单因为值里有数字就排除；应优先按字段角色判断，只有指标/时间
            字段才不作为绑定实体。
        """

        entities: list[str] = []
        for column, value in row.items():
            if value is None:
                continue
            text = str(value).strip()
            if not text or len(text) < 2:
                continue
            entity_like = self._is_entity_like_column(column)
            metric_like = self._is_metric_like_column(column)
            if self._is_time_like_column(column) or (metric_like and (not entity_like or self._is_plain_numeric_text(text))):
                continue
            if entity_like or not self._is_plain_numeric_text(text):
                entities.append(text)
        return entities

    def _collect_row_metric_number_tokens(self, row: dict[str, Any]) -> set[str]:
        """提取一行中的指标数字 token。"""

        tokens: set[str] = set()
        for column, value in row.items():
            if value is None:
                continue
            # 年月日常作为筛选或分组口径，不作为“名称-指标值”绑定校验对象。
            # 指标字段优先于实体字段判断，避免 paid_amount 这类字段因包含 id 子串被误跳过。
            if self._is_time_like_column(column):
                continue
            if self._is_entity_like_column(column) and not self._is_metric_like_column(column):
                continue
            text = str(value).strip()
            if not text:
                continue
            value_tokens = self._extract_number_tokens(text)
            if value_tokens:
                tokens.update(value_tokens)
        return tokens

    @staticmethod
    def _is_time_like_column(column: Any) -> bool:
        """判断字段是否为时间口径字段。"""

        key = str(column).lower()
        return any(marker in key for marker in ("year", "month", "date", "time", "年份", "年度", "年月", "月份", "日期", "时间"))

    @staticmethod
    def _is_entity_like_column(column: Any) -> bool:
        """判断字段是否为维度实体字段，允许实体值包含数字。"""

        key = str(column).lower()
        tokens = [token for token in re.split(r"[^a-z0-9]+", key.replace("_", " ")) if token]
        english_markers = {
            "name", "city", "province", "region", "customer", "supplier", "vendor", "carrier", "company",
            "order", "bom", "model", "type", "code", "no", "id", "category", "dimension", "bin", "level",
        }
        chinese_markers = (
            "名称", "城市", "省份", "区域", "客户", "供应商", "厂家", "承运商", "公司", "订单", "单号", "编号",
            "型号", "版型", "档", "类别", "分类", "维度", "项目", "产品", "物料", "组件",
        )
        return any(token in english_markers for token in tokens) or any(marker in key for marker in chinese_markers)

    @staticmethod
    def _is_strong_entity_like_column(column: Any) -> bool:
        """判断字段是否明显表示编号、型号、档位等实体，避免被功率/预测等词误判为指标。"""

        key = str(column).lower()
        tokens = [token for token in re.split(r"[^a-z0-9]+", key.replace("_", " ")) if token]
        strong_english_markers = {"order", "bom", "model", "type", "code", "no", "id", "category", "dimension", "bin", "level"}
        strong_chinese_markers = ("订单", "单号", "编号", "型号", "版型", "档", "类别", "分类", "维度", "项目", "产品", "物料", "组件")
        return any(token in strong_english_markers for token in tokens) or any(marker in key for marker in strong_chinese_markers)

    def _is_metric_like_column(self, column: Any) -> bool:
        """判断字段是否为数值指标字段。"""

        if self._is_strong_entity_like_column(column):
            return False
        key = str(column).lower()
        metric_markers = (
            "amount", "fee", "cost", "price", "total", "sum", "avg", "average", "mw", "watt", "power", "rate", "ratio", "share",
            "count", "trip", "weight", "qty", "quantity", "percent", "score", "value", "metric",
            "金额", "费用", "运费", "成本", "价格", "总", "合计", "平均", "发运量", "比例", "占比", "比率",
            "数量", "次数", "车次", "重量", "分数", "指标", "数值", "预测",
        )
        return any(marker in key for marker in metric_markers)

    def _is_plain_numeric_text(self, text: str) -> bool:
        """判断文本是否基本只是数字/单位/符号，避免把未知金额字段误当实体。"""

        stripped = text.strip()
        if not stripped:
            return False
        if not self._extract_number_tokens(stripped):
            return False
        return bool(re.fullmatch(r"[\d\s,，.。+\-/%％元万亿元MWmwWwKGkg吨次台个件]+", stripped))

    def _collect_allowed_number_tokens(self, payload: Any) -> set[str]:
        """从确定性响应中收集允许被 LLM 复述的数字。"""

        tokens: set[str] = set()
        self._collect_number_tokens_from_value(payload, tokens=tokens, parent_key="")
        return tokens

    def _collect_number_tokens_from_value(self, value: Any, *, tokens: set[str], parent_key: str) -> None:
        """递归读取确定性上下文里的数字，跳过 debug 和 trace 等内部排查字段。"""

        key = parent_key.lower()
        if any(marker in key for marker in ("debug", "trace_events", "raw_result")):
            return
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                next_key = f"{parent_key}.{child_key}" if parent_key else str(child_key)
                self._collect_number_tokens_from_value(child_value, tokens=tokens, parent_key=next_key)
            return
        if isinstance(value, list):
            for item in value:
                self._collect_number_tokens_from_value(item, tokens=tokens, parent_key=parent_key)
            return
        if value is None:
            return
        tokens.update(self._extract_number_tokens(str(value)))

    def _extract_number_tokens(self, text: str) -> set[str]:
        """抽取并归一化文本中的数字 token。"""

        tokens: set[str] = set()
        for match in re.finditer(r"(20\d{2})[-/年](\d{1,2})(?:[-/月](\d{1,2}))?", text or ""):
            tokens.add(self._normalize_number_token(match.group(1)))
            tokens.add(self._normalize_number_token(match.group(2)))
            if match.group(3):
                tokens.add(self._normalize_number_token(match.group(3)))
        for raw in self.NUMBER_PATTERN.findall(text or ""):
            try:
                tokens.add(self._normalize_number_token(raw))
            except Exception:  # noqa: BLE001
                continue
        return tokens

    @staticmethod
    def _normalize_number_token(value: Any) -> str:
        """把数字统一为可比较 token，避免 120.50 与 120.5 被误判不同。"""

        number = Decimal(str(value).replace(",", ""))
        normalized = number.normalize()
        return format(normalized, "f").rstrip("0").rstrip(".") or "0"

    def _truncate_table(self, table: Any) -> None:
        """把表格行数限制到 prompt 可控范围，同时保留总行数提示。"""

        if not isinstance(table, dict):
            return
        rows = table.get("rows")
        if not isinstance(rows, list):
            return
        original_count = len(rows)
        if original_count > self.MAX_PROMPT_ROWS:
            table["rows"] = rows[: self.MAX_PROMPT_ROWS]
            table["truncated_for_llm"] = True
            table["total_rows"] = original_count

    @staticmethod
    def _extract_delta_text(event: Any) -> str:
        """从 OpenAI 兼容 chunk 中提取增量文本。"""

        try:
            if isinstance(event, dict):
                choice = (event.get("choices") or [{}])[0]
                delta = choice.get("delta") or {}
                return str(delta.get("content") or "")
            choices = getattr(event, "choices", None) or []
            if not choices:
                return ""
            delta = getattr(choices[0], "delta", None)
            return str(getattr(delta, "content", "") or "")
        except Exception:  # noqa: BLE001
            return ""

    @classmethod
    def _chunk_text(cls, text: str) -> Iterable[str]:
        """把降级答案切成小块，模拟流式输出体验。"""

        value = text or "当前没有可展示的答案。"
        for index in range(0, len(value), cls.FALLBACK_CHUNK_SIZE):
            yield value[index : index + cls.FALLBACK_CHUNK_SIZE]

    @classmethod
    def _resolve_fallback_answer(cls, payload: dict[str, Any], fallback_answer: str | None) -> str:
        """从响应快照中提取安全降级答案。

        业务逻辑：
            正常情况下 deterministic presentation 已经过业务层控制，不应包含内部字段。
            但如果异常数据把 SQL、query_key、planner 等技术痕迹带入兜底文本，
            兜底路径也不能把它原样流给前端；此时跳过该候选，选择安全的状态消息
            或通用完成提示，确保“无 LLM/LLM 失败”路径同样不泄露内部实现。
        """

        candidates: list[Any] = []
        if fallback_answer:
            candidates.append(fallback_answer)
        presentation = payload.get("presentation")
        if isinstance(presentation, dict) and presentation.get("answer"):
            candidates.append(presentation.get("answer"))
        if payload.get("answer_summary"):
            candidates.append(payload.get("answer_summary"))
        status = payload.get("status")
        if isinstance(status, dict) and status.get("message"):
            candidates.append(status.get("message"))
        candidates.append("当前查询已完成，请查看下方结构化结果。")

        for candidate in candidates:
            text = str(candidate or "").strip()
            if text and not cls._visible_text_has_technical_leak(text):
                return text
        return "当前查询已完成，请查看下方结构化结果。"

    @staticmethod
    def _default_title(domain: str) -> str:
        """生成缺省展示标题。"""

        if domain == "plan_bom":
            return "计划 BOM 智能回答"
        if domain == "logistics":
            return "物流经营智能回答"
        return "智能回答"


__all__ = ["BusinessAnswerStreamService", "build_json_line_event"]
