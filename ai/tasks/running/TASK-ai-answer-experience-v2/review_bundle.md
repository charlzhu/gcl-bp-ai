# AI Answer Experience V2 review bundle
## Scope
Backend stream/presentation safety and frontend narrative-first BusinessChat UI. Full diff is ai/tasks/running/TASK-ai-answer-experience-v2/diff.patch (1551 lines because two relevant files are currently untracked in git). This bundle contains focused excerpts.
## Static scan
- hardcoded_secrets=2: both are tests with api_key="test-key".
- shell_injection=0
- dangerous_eval_exec=0
- unsafe_pickle=0
- sql_formatting=0
## Tests already run
- python -m pytest tests/business_acceptance/test_business_chat_answer_format_preference.py -q => 10 passed
- python -m pytest tests/business_acceptance -q => 173 passed, 2 warnings
- frontend npm run build => passed
- browser E2E default narrative passed; rawResponse only retained result_table.

## backend/app/services/business_answer_stream_service.py:1-360
```
    1|from __future__ import annotations
    2|
    3|import json
    4|import re
    5|from copy import deepcopy
    6|from decimal import Decimal
    7|from typing import Any, Iterable
    8|
    9|from openai import OpenAI
   10|
   11|from backend.app.core.config import settings
   12|
   13|
   14|JSONLineEvent = dict[str, Any]
   15|
   16|
   17|def build_json_line_event(event: str, data: dict[str, Any]) -> str:
   18|    """构造前端可增量解析的一行 JSON 流事件。
   19|
   20|    参数：
   21|        event: 事件名，常用值包括 meta、delta、done、error。
   22|        data: 当前事件的数据体，必须可 JSON 序列化。
   23|
   24|    返回：
   25|        以换行符结尾的 JSON 字符串。
   26|    """
   27|
   28|    return json.dumps({"event": event, "data": data}, ensure_ascii=False, default=str) + "\n"
   29|
   30|
   31|class BusinessAnswerStreamService:
   32|    """业务智能问答的流式答案表达服务。
   33|
   34|    说明：
   35|        1. 后端先完成确定性查询、计算和表格生成；
   36|        2. 本服务只把“用户原问题 + 确定性结果快照”交给 LLM 做答案表达；
   37|        3. LLM 流式输出只替换 presentation.answer，不允许改表格、状态、查询结果和数值事实；
   38|        4. 未配置 LLM 或调用失败时，将确定性答案切块流式返回，保证前端体验不退化。
   39|    """
   40|
   41|    MAX_PROMPT_ROWS = 30
   42|    MAX_PROMPT_CHARS = 12000
   43|    FALLBACK_CHUNK_SIZE = 18
   44|    TECHNICAL_VISIBLE_PATTERNS = (
   45|        r"\bSQL\b",
   46|        r"\bsql\b",
   47|        r"\bquery_key\b",
   48|        r"\bplanner\b",
   49|        r"\bguardrail\b",
   50|        r"\bdebug\b",
   51|        r"\btrace_id\b",
   52|        r"\binternal\b",
   53|        r"\bods_[a-z0-9_]*",
   54|        r"\bdwd_[a-z0-9_]*",
   55|        r"\bdws_[a-z0-9_]*",
   56|        r"\b[a-z]+_[a-z0-9_]+\b",
   57|    )
   58|    NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])-?\d+(?:,\d{3})*(?:\.\d+)?")
   59|
   60|    def __init__(
   61|        self,
   62|        *,
   63|        enabled: bool | None = None,
   64|        base_url: str | None = None,
   65|        api_key: str | None = None,
   66|        model: str | None = None,
   67|        client: Any | None = None,
   68|        timeout: float | None = None,
   69|    ) -> None:
   70|        """初始化流式答案表达服务。
   71|
   72|        参数：
   73|            enabled: 是否启用 LLM 表达，默认跟随全局答案表达开关。
   74|            base_url: OpenAI 兼容接口地址。
   75|            api_key: OpenAI 兼容接口密钥。
   76|            model: 使用的表达模型名。
   77|            client: 测试注入的 OpenAI 兼容客户端。
   78|            timeout: 单次 LLM 调用超时时间。
   79|
   80|        返回：
   81|            无返回值。
   82|        """
   83|
   84|        self.enabled = settings.llm_answer_presentation_enabled if enabled is None else enabled
   85|        self.base_url = base_url if base_url is not None else settings.llm_base_url
   86|        self.api_key = api_key if api_key is not None else settings.llm_api_key
   87|        self.model = model if model is not None else (settings.llm_answer_presentation_model or settings.llm_model)
   88|        self.timeout = timeout if timeout is not None else settings.llm_answer_presentation_timeout
   89|        self._client = client
   90|        self._last_stream_source = "deterministic_fallback"
   91|        self._last_fallback_reason = "not_started"
   92|
   93|    def stream_answer(
   94|        self,
   95|        *,
   96|        domain: str,
   97|        question: str,
   98|        deterministic_payload: dict[str, Any],
   99|        fallback_answer: str | None = None,
  100|    ) -> Iterable[str]:
  101|        """流式生成业务答案文本。
  102|
  103|        参数：
  104|            domain: 业务域标识，例如 logistics 或 plan_bom。
  105|            question: 用户原始问题，必须进入 LLM 上下文。
  106|            deterministic_payload: 后端确定性结果快照。
  107|            fallback_answer: LLM 不可用时的确定性答案。
  108|
  109|        返回：
  110|            文本 chunk 迭代器；每个 chunk 都可直接追加到前端气泡中。
  111|        """
  112|
  113|        fallback = self._resolve_fallback_answer(deterministic_payload, fallback_answer)
  114|        if not self._is_llm_available():
  115|            self._last_stream_source = "deterministic_fallback"
  116|            self._last_fallback_reason = "llm_not_configured"
  117|            yield from self._chunk_text(fallback)
  118|            return
  119|        try:
  120|            self._last_stream_source = "llm"
  121|            self._last_fallback_reason = ""
  122|            stream = self._create_llm_stream(domain=domain, question=question, deterministic_payload=deterministic_payload)
  123|            chunks: list[str] = []
  124|            for event in stream:
  125|                chunk = self._extract_delta_text(event)
  126|                if not chunk:
  127|                    continue
  128|                chunks.append(chunk)
  129|            streamed_answer = "".join(chunks).strip()
  130|            if not streamed_answer:
  131|                self._last_stream_source = "deterministic_fallback"
  132|                self._last_fallback_reason = "llm_empty_stream"
  133|                yield from self._chunk_text(fallback)
  134|                return
  135|            validation_error = self._validate_streamed_answer(streamed_answer, deterministic_payload=deterministic_payload)
  136|            if validation_error:
  137|                self._last_stream_source = "deterministic_fallback"
  138|                self._last_fallback_reason = validation_error
  139|                yield from self._chunk_text(fallback)
  140|                return
  141|            for chunk in chunks:
  142|                yield chunk
  143|        except Exception as exc:  # noqa: BLE001
  144|            # LLM 只负责表达增强，失败不能影响确定性查询结果可用性。
  145|            self._last_stream_source = "deterministic_fallback"
  146|            self._last_fallback_reason = f"llm_stream_error:{type(exc).__name__}"
  147|            yield from self._chunk_text(fallback)
  148|
  149|    def apply_streamed_answer(
  150|        self,
  151|        *,
  152|        domain: str,
  153|        deterministic_payload: dict[str, Any],
  154|        streamed_answer: str,
  155|    ) -> dict[str, Any]:
  156|        """把流式答案合并回响应 payload。
  157|
  158|        参数：
  159|            domain: 业务域标识，用于兜底 presentation 标题。
  160|            deterministic_payload: 原始确定性响应，不会被原地修改。
  161|            streamed_answer: LLM 或降级流式输出的完整答案。
  162|
  163|        返回：
  164|            已更新 presentation.answer 的响应 payload；表格和状态保持确定性原值。
  165|        """
  166|
  167|        payload = deepcopy(deterministic_payload)
  168|        fallback = self._resolve_fallback_answer(payload, None)
  169|        candidate_answer = streamed_answer.strip()
  170|        validation_error = (
  171|            self._validate_streamed_answer(candidate_answer, deterministic_payload=payload)
  172|            if candidate_answer
  173|            else "stream_empty_answer"
  174|        )
  175|        if validation_error and candidate_answer != fallback:
  176|            # 最终写回前再校验一次，防止调用方绕过 stream_answer 直接合并不安全文本。
  177|            self._last_stream_source = "deterministic_fallback"
  178|            self._last_fallback_reason = validation_error
  179|            final_answer = fallback
  180|        else:
  181|            final_answer = candidate_answer or fallback
  182|        presentation = payload.get("presentation")
  183|        if not isinstance(presentation, dict):
  184|            presentation = {
  185|                "display_type": "narrative",
  186|                "title": self._default_title(domain),
  187|                "answer": final_answer,
  188|                "highlights": [],
  189|                "table_spec": None,
  190|                "caveats": [],
  191|                "debug": {},
  192|            }
  193|            payload["presentation"] = presentation
  194|        presentation["answer"] = final_answer
  195|        debug = presentation.get("debug")
  196|        if not isinstance(debug, dict):
  197|            debug = {}
  198|            presentation["debug"] = debug
  199|        debug["stream_answer_source"] = self._last_stream_source
  200|        debug["stream_fallback_reason"] = self._last_fallback_reason or None
  201|        if self._last_stream_source == "llm":
  202|            debug["llm_model_name"] = self.model
  203|        debug["stream_answer_domain"] = domain
  204|        return payload
  205|
  206|    def _create_llm_stream(self, *, domain: str, question: str, deterministic_payload: dict[str, Any]):
  207|        """创建 OpenAI 兼容流式响应对象。
  208|
  209|        参数：
  210|            domain: 业务域标识。
  211|            question: 用户原始问题。
  212|            deterministic_payload: 确定性结果快照。
  213|
  214|        返回：
  215|            OpenAI 兼容流式事件迭代器。
  216|        """
  217|
  218|        client = self._client or OpenAI(
  219|            base_url=self.base_url,
  220|            api_key=self.api_key,
  221|            timeout=self.timeout,
  222|            max_retries=settings.llm_answer_presentation_max_retries,
  223|        )
  224|        return client.chat.completions.create(
  225|            model=self.model,
  226|            temperature=0.2,
  227|            stream=True,
  228|            messages=[
  229|                {"role": "system", "content": self._build_system_prompt(domain)},
  230|                {"role": "user", "content": self._build_user_prompt(question, deterministic_payload)},
  231|            ],
  232|        )
  233|
  234|    def _is_llm_available(self) -> bool:
  235|        """判断 LLM 流式表达是否可用。"""
  236|
  237|        return bool(self.enabled and self.base_url and self.api_key and self.model)
  238|
  239|    @classmethod
  240|    def _build_system_prompt(cls, domain: str) -> str:
  241|        """构造约束 LLM 只做表达的系统提示词。"""
  242|
  243|        domain_label = "计划 BOM" if domain == "plan_bom" else "物流经营"
  244|        return (
  245|            f"你是{domain_label}智能问答的答案表达层。"
  246|            "你会收到用户原问题和后端确定性查询结果。"
  247|            "你的任务是用中文业务口吻流式输出更自然、更有 AI 感的答案。"
  248|            "严禁新增、猜测或改写订单、客户、供应商、金额、数量、比例、日期、规格、功率、CTM 等事实。"
  249|            "表格、状态和数值以系统给出的确定性结果为准；如果明细很多，只概括结论并提示用户查看下方表格。"
  250|            "不要输出 JSON、Markdown 表格或代码块；不要暴露字段名、SQL、内部状态码、debug 信息。"
  251|            "如果结果要求澄清或暂不支持，要温和说明原因并给出可执行的补充问法。"
  252|        )
  253|
  254|    def _build_user_prompt(self, question: str, deterministic_payload: dict[str, Any]) -> str:
  255|        """把用户原问题和确定性结果压缩为 LLM 上下文。"""
  256|
  257|        prompt_payload = {
  258|            "用户原问题": question,
  259|            "确定性结果": self._compact_payload(deterministic_payload),
  260|            "表达要求": [
  261|                "先直接回答业务员最关心的结论，再说明依据。",
  262|                "只引用确定性结果中出现的事实；不要补充外部知识。",
  263|                "结构化明细由前端表格展示，正文不要重复铺满所有行。",
  264|                "语气专业、清楚、有温度，但不要夸张营销。",
  265|            ],
  266|        }
  267|        text = json.dumps(prompt_payload, ensure_ascii=False, default=str)
  268|        if len(text) <= self.MAX_PROMPT_CHARS:
  269|            return text
  270|        return text[: self.MAX_PROMPT_CHARS] + "\n【上下文因过长已截断，请只基于已给出的确定性事实表达。】"
  271|
  272|    def _compact_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
  273|        """压缩确定性响应，避免把大表完整塞入 LLM 上下文。"""
  274|
  275|        compact = deepcopy(payload)
  276|        self._truncate_table(compact.get("result_table"))
  277|        presentation = compact.get("presentation")
  278|        if isinstance(presentation, dict):
  279|            self._truncate_table(presentation.get("table_spec"))
  280|            presentation.pop("debug", None)
  281|        compact.pop("trace_events", None)
  282|        compact.pop("raw_result", None)
  283|        return compact
  284|
  285|    def _validate_streamed_answer(self, answer: str, *, deterministic_payload: dict[str, Any]) -> str | None:
  286|        """校验流式答案是否可作为最终业务叙事。
  287|
  288|        参数：
  289|            answer: LLM 已完整输出的主回答文本。
  290|            deterministic_payload: 后端确定性结果快照。
  291|
  292|        返回：
  293|            None 表示可采用；非空错误码表示必须回落到确定性答案。
  294|        """
  295|
  296|        if not answer.strip():
  297|            return "stream_empty_answer"
  298|        if self._visible_text_has_technical_leak(answer):
  299|            return "stream_technical_visible_leak"
  300|        if not self._answer_numbers_are_safe(answer, deterministic_payload=deterministic_payload):
  301|            return "stream_text_number_hallucination"
  302|        return None
  303|
  304|    def _visible_text_has_technical_leak(self, answer: str) -> bool:
  305|        """判断流式主回答是否泄露 SQL、表名、字段名或内部编排信息。"""
  306|
  307|        return any(re.search(pattern, answer or "", flags=re.I) for pattern in self.TECHNICAL_VISIBLE_PATTERNS)
  308|
  309|    def _answer_numbers_are_safe(self, answer: str, *, deterministic_payload: dict[str, Any]) -> bool:
  310|        """判断流式主回答中的数字是否全部来自确定性上下文。"""
  311|
  312|        answer_tokens = self._extract_number_tokens(answer)
  313|        if not answer_tokens:
  314|            return True
  315|        allowed_tokens = self._collect_allowed_number_tokens(deterministic_payload)
  316|        return answer_tokens.issubset(allowed_tokens)
  317|
  318|    def _collect_allowed_number_tokens(self, payload: Any) -> set[str]:
  319|        """从确定性响应中收集允许被 LLM 复述的数字。"""
  320|
  321|        tokens: set[str] = set()
  322|        self._collect_number_tokens_from_value(payload, tokens=tokens, parent_key="")
  323|        return tokens
  324|
  325|    def _collect_number_tokens_from_value(self, value: Any, *, tokens: set[str], parent_key: str) -> None:
  326|        """递归读取确定性上下文里的数字，跳过 debug 和 trace 等内部排查字段。"""
  327|
  328|        key = parent_key.lower()
  329|        if any(marker in key for marker in ("debug", "trace_events", "raw_result")):
  330|            return
  331|        if isinstance(value, dict):
  332|            for child_key, child_value in value.items():
  333|                next_key = f"{parent_key}.{child_key}" if parent_key else str(child_key)
  334|                self._collect_number_tokens_from_value(child_value, tokens=tokens, parent_key=next_key)
  335|            return
  336|        if isinstance(value, list):
  337|            for item in value:
  338|                self._collect_number_tokens_from_value(item, tokens=tokens, parent_key=parent_key)
  339|            return
  340|        if value is None:
  341|            return
  342|        tokens.update(self._extract_number_tokens(str(value)))
  343|
  344|    def _extract_number_tokens(self, text: str) -> set[str]:
  345|        """抽取并归一化文本中的数字 token。"""
  346|
  347|        tokens: set[str] = set()
  348|        for match in re.finditer(r"(20\d{2})[-/年](\d{1,2})(?:[-/月](\d{1,2}))?", text or ""):
  349|            tokens.add(self._normalize_number_token(match.group(1)))
  350|            tokens.add(self._normalize_number_token(match.group(2)))
  351|            if match.group(3):
  352|                tokens.add(self._normalize_number_token(match.group(3)))
  353|        for raw in self.NUMBER_PATTERN.findall(text or ""):
  354|            try:
  355|                tokens.add(self._normalize_number_token(raw))
  356|            except Exception:  # noqa: BLE001
  357|                continue
  358|        return tokens
  359|
  360|    @staticmethod
```

## backend/app/domains/logistics/services/llm_answer_presentation_service.py:170-260
```
  170|        if explicit_model is not None:
  171|            return explicit_model, "explicit"
  172|        if settings.llm_answer_presentation_model:
  173|            return settings.llm_answer_presentation_model, "LLM_ANSWER_PRESENTATION_MODEL"
  174|        if self.enabled and settings.llm_model:
  175|            return settings.llm_model, "LLM_MODEL"
  176|        return "", "not_configured"
  177|
  178|    def build_presentation(
  179|        self,
  180|        *,
  181|        question: str,
  182|        result: LogisticsDataQaResult,
  183|        trace_id: str | None = None,
  184|    ) -> LogisticsDataQaPresentation | None:
  185|        """生成答案展示编排。
  186|
  187|        参数：
  188|            question: 用户原始问题。
  189|            result: 后端确定性 data-qa 结果。
  190|            trace_id: 请求追踪 ID，仅写入 debug 便于排查。
  191|
  192|        返回：
  193|            presentation 结构；表达层关闭时返回 None。
  194|        """
  195|
  196|        if not self.enabled:
  197|            return None
  198|
  199|        fallback = self._build_deterministic_presentation(question=question, result=result)
  200|        fallback.debug.update(
  201|            {
  202|                "presentation_source": "deterministic",
  203|                "trace_id": trace_id,
  204|                "fallback_reason": None,
  205|                "requested_display": self._detect_requested_display(question),
  206|                "final_display_type": fallback.display_type,
  207|                "llm_model_name": self.model or None,
  208|                "llm_model_source": self.model_source,
  209|            }
  210|        )
  211|        if not self.is_llm_available():
  212|            fallback.debug["fallback_reason"] = "llm_not_configured"
  213|            return fallback
  214|
  215|        llm_payload, error = self._request_llm_presentation(question=question, result=result)
  216|        if error:
  217|            fallback.debug["fallback_reason"] = error
  218|            return fallback
  219|
  220|        normalized, validation_error = self._normalize_and_validate_llm_payload(
  221|            question=question,
  222|            result=result,
  223|            payload=llm_payload,
  224|            fallback=fallback,
  225|        )
  226|        if validation_error:
  227|            fallback.debug["fallback_reason"] = validation_error
  228|            return fallback
  229|        normalized.debug.update(
  230|            {
  231|                "presentation_source": "llm",
  232|                "trace_id": trace_id,
  233|                "fallback_reason": None,
  234|                "requested_display": self._detect_requested_display(question),
  235|                "final_display_type": normalized.display_type,
  236|                "llm_model_name": self.model,
  237|                "llm_model_source": self.model_source,
  238|            }
  239|        )
  240|        return normalized
  241|
  242|    def _build_deterministic_presentation(
  243|        self,
  244|        *,
  245|        question: str,
  246|        result: LogisticsDataQaResult,
  247|    ) -> LogisticsDataQaPresentation:
  248|        """构造不依赖 LLM 的确定性展示编排。
  249|
  250|        说明：
  251|            该方法是所有异常场景的降级路径，所有展示数据都来自 result。
  252|        """
  253|
  254|        status_code = result.status.code if result.status else self._resolve_status_code(result)
  255|        display_type = self._resolve_display_type(question=question, result=result, status_code=status_code)
  256|        title = self._build_title(result=result, status_code=status_code)
  257|        answer = result.answer_summary or result.status.message if result.status else result.answer_summary
  258|        requested_display = self._detect_requested_display(question)
  259|        caveats = self._build_caveats(result)
  260|        # 默认采用纯文字叙事，只有业务员明确要求表格/图表/指标卡时，才把结构化组件放进 presentation。
```

## backend/app/domains/logistics/services/llm_answer_presentation_service.py:430-760
```
  430|    def _normalize_and_validate_llm_payload(
  431|        self,
  432|        *,
  433|        question: str,
  434|        result: LogisticsDataQaResult,
  435|        payload: dict[str, Any],
  436|        fallback: LogisticsDataQaPresentation,
  437|    ) -> tuple[LogisticsDataQaPresentation, str | None]:
  438|        """清洗并校验 LLM 展示编排。
  439|
  440|        返回：
  441|            (presentation, validation_error)。validation_error 非空时调用方必须降级。
  442|        """
  443|
  444|        if not isinstance(payload, dict) or not payload:
  445|            return fallback, "llm_empty_payload"
  446|        status_code = result.status.code if result.status else self._resolve_status_code(result)
  447|        llm_status = str(payload.get("status_code") or status_code)
  448|        if llm_status != status_code:
  449|            return fallback, "llm_status_changed"
  450|
  451|        display_type = str(payload.get("display_type") or fallback.display_type)
  452|        if display_type not in self.DISPLAY_TYPES:
  453|            return fallback, "llm_invalid_display_type"
  454|        if display_type not in self.STATUS_TO_DISPLAY_TYPE.get(status_code, set()):
  455|            return fallback, "llm_display_type_cross_boundary"
  456|        if self._display_type_ignores_user_request(
  457|            question=question,
  458|            result=result,
  459|            display_type=display_type,
  460|            fallback=fallback,
  461|        ):
  462|            return fallback, "llm_display_type_ignores_user_request"
  463|
  464|        presentation = LogisticsDataQaPresentation(
  465|            display_type=display_type,  # type: ignore[arg-type]
  466|            title=str(payload.get("title") or fallback.title),
  467|            answer=str(payload.get("answer") or fallback.answer),
  468|            highlights=self._normalize_string_list(payload.get("highlights")) or fallback.highlights,
  469|            caveats=self._normalize_string_list(payload.get("caveats")) or fallback.caveats,
  470|            caveat_items=self._normalize_caveat_items(payload.get("caveat_items")) or fallback.caveat_items,
  471|            debug=payload.get("debug") if isinstance(payload.get("debug"), dict) else {},
  472|        )
  473|        if self._visible_text_has_technical_leak(
  474|            [
  475|                presentation.title,
  476|                presentation.answer,
  477|                *presentation.highlights,
  478|                *presentation.caveats,
  479|                *[item.text for item in presentation.caveat_items],
  480|            ]
  481|        ):
  482|            # LLM 表达层面向业务用户，不能把表名、字段名、SQL 或内部 query_key 暴露到主展示。
  483|            return fallback, "llm_technical_visible_leak"
  484|        if not self._text_numbers_are_safe(
  485|            [
  486|                presentation.title,
  487|                presentation.answer,
  488|                *presentation.highlights,
  489|                *presentation.caveats,
  490|                *[item.text for item in presentation.caveat_items],
  491|            ],
  492|            result=result,
  493|        ):
  494|            return fallback, "llm_text_number_hallucination"
  495|
  496|        requested_display = self._detect_requested_display(question)
  497|        table_payload = payload.get("table_spec")
  498|        if display_type in {"table", "mixed"} and requested_display == "table" and isinstance(table_payload, dict):
  499|            table_spec = LogisticsDataQaTableSpec(
  500|                columns=[item for item in table_payload.get("columns", []) if isinstance(item, str)],
  501|                rows=[row for row in table_payload.get("rows", []) if isinstance(row, dict)],
  502|            )
  503|            if self._table_spec_is_safe(table_spec=table_spec, result=result):
  504|                presentation.table_spec = table_spec
  505|            else:
  506|                return fallback, "llm_table_data_not_from_backend"
  507|        else:
  508|            presentation.table_spec = fallback.table_spec
  509|
  510|        cards_payload = payload.get("cards")
  511|        if display_type in {"summary_cards", "mixed"} and requested_display == "summary_cards" and isinstance(cards_payload, list):
  512|            cards: list[LogisticsDataQaPresentationCard] = []
  513|            for item in cards_payload:
  514|                if not isinstance(item, dict) or "label" not in item:
  515|                    continue
  516|                card = LogisticsDataQaPresentationCard(
  517|                    label=str(item.get("label") or ""),
  518|                    value=item.get("value"),
  519|                    unit=str(item.get("unit")) if item.get("unit") is not None else None,
  520|                    description=str(item.get("description")) if item.get("description") is not None else None,
  521|                )
  522|                cards.append(card)
  523|            if self._cards_are_safe(cards=cards, result=result):
  524|                presentation.cards = cards
  525|            else:
  526|                return fallback, "llm_card_number_hallucination"
  527|        else:
  528|            presentation.cards = fallback.cards
  529|
  530|        chart_payload = payload.get("chart_spec")
  531|        if display_type in {"line_chart", "bar_chart", "pie_chart", "mixed"} and requested_display in {"line_chart", "bar_chart", "pie_chart"} and isinstance(chart_payload, dict):
  532|            chart_spec = self._normalize_chart_payload(chart_payload)
  533|            if chart_spec and self._chart_spec_is_safe(chart_spec=chart_spec, result=result):
  534|                presentation.chart_spec = chart_spec
  535|            elif chart_payload:
  536|                return fallback, "llm_chart_data_not_from_backend"
  537|        else:
  538|            presentation.chart_spec = fallback.chart_spec
  539|
  540|        if status_code == "CLARIFICATION_REQUIRED":
  541|            follow_up_payload = payload.get("follow_up")
  542|            if isinstance(follow_up_payload, dict):
  543|                presentation.follow_up = LogisticsDataQaFollowUp(
  544|                    questions=self._normalize_string_list(follow_up_payload.get("questions")) or list(result.clarification_questions),
  545|                    examples=self._normalize_string_list(follow_up_payload.get("examples")) or self._build_follow_up_examples(result),
  546|                )
  547|            else:
  548|                presentation.follow_up = fallback.follow_up
  549|        if status_code == "UNSUPPORTED_QUESTION":
  550|            unsupported_payload = payload.get("unsupported_explanation")
  551|            if isinstance(unsupported_payload, dict):
  552|                presentation.unsupported_explanation = LogisticsDataQaUnsupportedExplanation(
  553|                    reason=str(unsupported_payload.get("reason") or result.query_plan.unsupported_reason or result.answer_summary),
  554|                    suggestions=self._normalize_string_list(unsupported_payload.get("suggestions"))
  555|                    or list(result.query_plan.unsupported_suggestions),
  556|                )
  557|            else:
  558|                presentation.unsupported_explanation = fallback.unsupported_explanation
  559|        hygiene_error = self._find_presentation_hygiene_issue(
  560|            question=question,
  561|            result=result,
  562|            presentation=presentation,
  563|        )
  564|        if hygiene_error:
  565|            return fallback, f"llm_{hygiene_error}"
  566|        self._sanitize_presentation(presentation)
  567|        return presentation, None
  568|
  569|    def _resolve_display_type(self, *, question: str, result: LogisticsDataQaResult, status_code: str) -> str:
  570|        """根据状态、用户格式诉求和结构化数据选择默认展示形态。"""
  571|
  572|        if status_code == "CLARIFICATION_REQUIRED":
  573|            return "clarification"
  574|        if status_code == "UNSUPPORTED_QUESTION":
  575|            return "unsupported"
  576|        if status_code == "EMPTY_RESULT":
  577|            return "empty_result"
  578|        if status_code == "EXECUTION_ERROR":
  579|            return "error"
  580|        requested = self._detect_requested_display(question)
  581|        if requested == "pie_chart" and self._can_build_pie_chart(result):
  582|            return requested
  583|        if requested in {"line_chart", "bar_chart"} and self._can_build_chart(result):
  584|            return requested
  585|        if requested == "table" and result.result_table.rows:
  586|            return "table"
  587|        if requested == "summary_cards" and self._build_cards(question=question, result=result):
  588|            return "summary_cards"
  589|        return "narrative"
  590|
  591|    def _detect_requested_display(self, question: str) -> str | None:
  592|        """识别用户显式要求的展示方式。"""
  593|
  594|        if re.search(r"饼图|圆饼图|环形图|占比图|占比展示", question):
  595|            return "pie_chart"
  596|        if re.search(r"折线图|趋势图|看趋势|趋势", question):
  597|            return "line_chart"
  598|        if re.search(r"柱状图|柱形图|条形图|对比图|图表", question):
  599|            return "bar_chart"
  600|        if re.search(r"表格|表格展示|汇总表|明细表|数据表|清单表|列表|excel|Excel|导出", question):
  601|            return "table"
  602|        if re.search(r"指标卡|卡片|概览卡|汇总卡|数据卡", question):
  603|            return "summary_cards"
  604|        return None
  605|
  606|    def _build_title(self, *, result: LogisticsDataQaResult, status_code: str) -> str:
  607|        """构建展示标题。"""
  608|
  609|        if status_code == "CLARIFICATION_REQUIRED":
  610|            return "还需要补充几个条件"
  611|        if status_code == "UNSUPPORTED_QUESTION":
  612|            return "当前暂不支持直接回答"
  613|        if status_code == "EMPTY_RESULT":
  614|            return "查询成功，但暂无数据"
  615|        if status_code == "EXECUTION_ERROR":
  616|            return "当前查询失败"
  617|        metric_label = self._label(result.query_plan.metrics[0]) if result.query_plan.metrics else ""
  618|        return f"{metric_label}分析结果" if metric_label else "物流数据分析结果"
  619|
  620|    def _build_highlights(
  621|        self,
  622|        *,
  623|        result: LogisticsDataQaResult,
  624|        status_code: str,
  625|        answer: str,
  626|        display_type: str,
  627|    ) -> list[str]:
  628|        """构建关键结论列表。
  629|
  630|        参数：
  631|            result: 后端确定性查询结果。
  632|            status_code: 当前统一状态码。
  633|            answer: 主回答文本，用于避免标签重复主回答。
  634|            display_type: 当前展示类型，图表和表格态不再追加泛化行数标签。
  635|
  636|        返回：
  637|            去重后的业务提示列表。成功图表/表格的核心答案保留在 answer、图表和表格中，
  638|            highlights 只承载额外提醒，避免同一总费用在多个标签里重复展示。
  639|        """
  640|
  641|        highlights: list[str] = []
  642|        return self._dedupe_text_items(highlights, base_texts=[answer])[:4]
  643|
  644|    def _build_caveats(self, result: LogisticsDataQaResult) -> list[str]:
  645|        """构建口径和数据范围提醒。"""
  646|
  647|        caveats: list[str] = []
  648|        if result.calculation_logic:
  649|            caveats.extend(result.calculation_logic[:3])
  650|        if result.data_scope:
  651|            scope = self._summarize_scope(result.data_scope)
  652|            if scope:
  653|                caveats.append(scope)
  654|        return caveats[:5]
  655|
  656|    def _build_caveat_items(
  657|        self,
  658|        *,
  659|        result: LogisticsDataQaResult,
  660|        status_code: str,
  661|        caveats: list[str],
  662|    ) -> list[LogisticsDataQaCaveatItem]:
  663|        """构建兼容 caveats 的分级口径提醒。"""
  664|
  665|        items: list[LogisticsDataQaCaveatItem] = [
  666|            LogisticsDataQaCaveatItem(level="info", text=item)
  667|            for item in caveats
  668|            if item
  669|        ]
  670|        for warning in result.warnings[:5]:
  671|            if not warning:
  672|                continue
  673|            items.append(
  674|                LogisticsDataQaCaveatItem(
  675|                    level="danger" if self._is_danger_caveat(warning) else "warning",
  676|                    text=warning,
  677|                )
  678|            )
  679|        if status_code == "EXECUTION_ERROR" and result.status and result.status.message:
  680|            items.append(LogisticsDataQaCaveatItem(level="danger", text=result.status.message))
  681|        return self._dedupe_caveat_items(items)[:8]
  682|
  683|    def _build_cards(
  684|        self,
  685|        *,
  686|        question: str,
  687|        result: LogisticsDataQaResult,
  688|    ) -> list[LogisticsDataQaPresentationCard]:
  689|        """构建主结论指标卡。
  690|
  691|        参数：
  692|            question: 用户原始问题，用于识别显式图表诉求。
  693|            result: 后端确定性查询结果。
  694|
  695|        返回：
  696|            指标卡列表。单行结果沿用行内数值；多行月度或维度拆分结果只展示合计、
  697|            统计颗粒度和明细行数等主结论，不再把第一行明细冒充成总体结论。
  698|        """
  699|
  700|        if not result.result_table.rows:
  701|            return []
  702|        if len(result.result_table.rows) > 1:
  703|            return self._build_multi_row_cards(question=question, result=result)
  704|        row = result.result_table.rows[0]
  705|        cards: list[LogisticsDataQaPresentationCard] = []
  706|        for column in result.result_table.columns:
  707|            value = row.get(column)
  708|            if not self._is_number(value):
  709|                continue
  710|            cards.append(
  711|                LogisticsDataQaPresentationCard(
  712|                    label=self._label(column),
  713|                    value=value,
  714|                    unit=self._infer_unit(column),
  715|                    description=None,
  716|                )
  717|            )
  718|            if len(cards) >= 4:
  719|                break
  720|        return cards
  721|
  722|    def _build_multi_row_cards(
  723|        self,
  724|        *,
  725|        question: str,
  726|        result: LogisticsDataQaResult,
  727|    ) -> list[LogisticsDataQaPresentationCard]:
  728|        """为多行拆分结果生成总体指标卡。
  729|
  730|        参数：
  731|            question: 用户原始问题。
  732|            result: 多行结构化查询结果。
  733|
  734|        返回：
  735|            主结论指标卡，不包含任意单月或单维度首行明细。
  736|        """
  737|
  738|        cards: list[LogisticsDataQaPresentationCard] = []
  739|        x_axis = self._choose_x_axis(result.result_table.columns)
  740|        y_axis = self._choose_y_axis(result=result, x_axis=x_axis)
  741|        if y_axis:
  742|            metric_column = y_axis[0]
  743|            summary_value = self._extract_summary_metric_value(
  744|                result.answer_summary,
  745|                metric_column=metric_column,
  746|            )
  747|            if summary_value is not None:
  748|                cards.append(
  749|                    LogisticsDataQaPresentationCard(
  750|                        label=self._aggregate_label(metric_column),
  751|                        value=summary_value,
  752|                        unit=self._infer_unit(metric_column),
  753|                    )
  754|                )
  755|        dimension_count = self._count_distinct_dimension_values(
  756|            rows=result.result_table.rows,
  757|            x_axis=x_axis,
  758|        )
  759|        if dimension_count is not None:
  760|            cards.append(
```

## backend/app/domains/logistics/services/llm_answer_presentation_service.py:1180-1245
```
 1180|            "fee_per_watt",
 1181|            "signedfor_rate",
 1182|            "extra_fee_amount",
 1183|            "extra_fee",
 1184|            "shipment_trip_count",
 1185|            "trip_count",
 1186|        ]
 1187|        for column in business_priority:
 1188|            if column in numeric_columns and column not in y_axis:
 1189|                y_axis.append(column)
 1190|        if y_axis:
 1191|            return y_axis[:2]
 1192|        for column in numeric_columns:
 1193|            if self._is_quality_or_diagnostic_column(column):
 1194|                continue
 1195|            y_axis.append(column)
 1196|            if len(y_axis) >= 2:
 1197|                break
 1198|        if y_axis:
 1199|            return y_axis
 1200|        return numeric_columns[:1]
 1201|
 1202|    def _extract_summary_metric_value(self, text: str, *, metric_column: str) -> str | None:
 1203|        """从确定性摘要中提取主指标合计值。
 1204|
 1205|        参数：
 1206|            text: 后端 answer_summary。
 1207|            metric_column: 需要提取的主指标字段。
 1208|
 1209|        返回：
 1210|            字符串数值；未命中时返回 None。该方法只读取已有摘要，不重新计算业务结果。
 1211|        """
 1212|
 1213|        if not text:
 1214|            return None
 1215|        label_patterns = self._metric_summary_patterns(metric_column)
 1216|        for label_pattern in label_patterns:
 1217|            match = re.search(
 1218|                rf"(?:合计|总计)?{label_pattern}(?:为|是|约为)?\s*([0-9][0-9,]*(?:\.\d+)?)",
 1219|                text,
 1220|            )
 1221|            if match:
 1222|                return match.group(1).replace(",", "")
 1223|        return None
 1224|
 1225|    def _metric_summary_patterns(self, metric_column: str) -> list[str]:
 1226|        """返回摘要中可能表达主指标的中文模式。"""
 1227|
 1228|        mapping: dict[str, list[str]] = {
 1229|            "total_fee": ["总运费", "总费用", "运费"],
 1230|            "shipment_mw": ["发运量", "总发运量", "运量"],
 1231|            "shipment_watt": ["发运瓦数", "总瓦数", "运量"],
 1232|            "shipment_trip_count": ["车次", "总车次"],
 1233|            "trip_count": ["车次", "总车次"],
 1234|            "task_count": ["任务数"],
 1235|            "avg_fee": ["平均运费"],
 1236|            "avg_fee_per_watt": ["平均元/瓦", "单瓦成本"],
 1237|            "unit_fee_per_watt": ["平均元/瓦", "单瓦成本"],
 1238|            "signedfor_rate": ["签收率"],
 1239|            "extra_fee_amount": ["额外费用"],
 1240|            "extra_fee": ["额外费用"],
 1241|        }
 1242|        return mapping.get(metric_column, [re.escape(self._label(metric_column))])
 1243|
 1244|    def _aggregate_label(self, metric_column: str) -> str:
 1245|        """生成多行拆分结果的总体指标卡名称。"""
```

## backend/app/domains/logistics/schemas/data_qa.py:1-120
```
    1|from __future__ import annotations
    2|
    3|from typing import Any, Literal
    4|
    5|from pydantic import BaseModel, Field
    6|
    7|
    8|class LogisticsDataQaQueryRequest(BaseModel):
    9|    """物流数据问答请求。
   10|
   11|    参数：
   12|        question: 业务人员输入的自然语言问题。
   13|    """
   14|
   15|    question: str = Field(..., min_length=1, description="物流数据问答问题")
   16|
   17|
   18|class LogisticsDataQaStatus(BaseModel):
   19|    """物流数据问答状态。
   20|
   21|    说明：
   22|        1. 统一表达成功、澄清、暂不支持、空结果和错误态；
   23|        2. 既给前端正式页使用，也给查询历史快照复用；
   24|        3. 保持字段简单稳定，避免前端重复推断状态。
   25|    """
   26|
   27|    code: str
   28|    message: str
   29|    success: bool
   30|    severity: str = "info"
   31|
   32|
   33|class LogisticsDataQaPlan(BaseModel):
   34|    """受控查询计划。
   35|
   36|    说明：
   37|        1. 本结构只描述白名单内的意图、指标、维度和过滤条件；
   38|        2. 不承载任意 SQL；
   39|        3. 支持澄清和不支持问题的可审计输出。
   40|        4. unsupported_* 字段用于 C 类边界治理，给前端展示业务可理解拒答原因和可改问方向。
   41|    """
   42|
   43|    domain: Literal["logistics"] = "logistics"
   44|    intent: str
   45|    query_key: str | None = None
   46|    metrics: list[str] = Field(default_factory=list)
   47|    dimensions: list[str] = Field(default_factory=list)
   48|    filters: dict[str, Any] = Field(default_factory=dict)
   49|    group_by: list[str] = Field(default_factory=list)
   50|    sort: list[dict[str, Any]] = Field(default_factory=list)
   51|    limit: int | None = None
   52|    needs_clarification: bool = False
   53|    clarification_questions: list[str] = Field(default_factory=list)
   54|    clarification_category: str | None = None
   55|    clarification_reason: str | None = None
   56|    clarification_missing_slots: list[str] = Field(default_factory=list)
   57|    clarification_template: str | None = None
   58|    clarification_assist_used: bool = False
   59|    clarification_assist_provider_mode: str | None = None
   60|    unsupported_reason: str | None = None
   61|    unsupported_category: str | None = None
   62|    unsupported_template: str | None = None
   63|    unsupported_suggestions: list[str] = Field(default_factory=list)
   64|    unsupported_assist_used: bool = False
   65|    unsupported_assist_provider_mode: str | None = None
   66|
   67|
   68|class LogisticsDataQaTable(BaseModel):
   69|    """结构化结果表。"""
   70|
   71|    columns: list[str] = Field(default_factory=list)
   72|    rows: list[dict[str, Any]] = Field(default_factory=list)
   73|
   74|
   75|class LogisticsDataQaChartSpec(BaseModel):
   76|    """前端图表展示配置。
   77|
   78|    说明：
   79|        1. 图表只使用后端已经计算出的结构化 rows；
   80|        2. 不允许 LLM 在 chart_spec 中新增数据点；
   81|        3. 前端可按 chart_type 选择轻量 SVG 折线图、柱状图或饼图渲染。
   82|    """
   83|
   84|    chart_type: Literal["line", "bar", "pie"] | None = None
   85|    title: str = ""
   86|    x_axis: str = ""
   87|    y_axis: list[str] = Field(default_factory=list)
   88|    series: list[dict[str, Any]] = Field(default_factory=list)
   89|    unit: str | None = None
   90|    data: list[dict[str, Any]] = Field(default_factory=list)
   91|
   92|
   93|class LogisticsDataQaTableSpec(BaseModel):
   94|    """前端表格展示配置。"""
   95|
   96|    columns: list[str] = Field(default_factory=list)
   97|    rows: list[dict[str, Any]] = Field(default_factory=list)
   98|
   99|
  100|class LogisticsDataQaPresentationCard(BaseModel):
  101|    """前端指标卡配置。"""
  102|
  103|    label: str
  104|    value: Any
  105|    unit: str | None = None
  106|    description: str | None = None
  107|
  108|
  109|class LogisticsDataQaFollowUp(BaseModel):
  110|    """B 类追问展示配置。"""
  111|
  112|    questions: list[str] = Field(default_factory=list)
  113|    examples: list[str] = Field(default_factory=list)
  114|
  115|
  116|class LogisticsDataQaUnsupportedExplanation(BaseModel):
  117|    """C 类拒答解释展示配置。"""
  118|
  119|    reason: str = ""
  120|    suggestions: list[str] = Field(default_factory=list)
```

## frontend/src/utils/businessChatSessions.ts:397-480
```
  397|}
  398|
  399|/**
  400| * 归一化助手消息中可持久化的原始响应。
  401| *
  402| * 参数：value 后端返回的原始业务响应。
  403| * 返回：仅包含安全明细表的最小对象；无可用明细时返回 null。
  404| * 说明：聊天历史不能持久化完整响应，避免内部规划、调试字段和大对象泄露；
  405| *       但需要保留 result_table 供“展开明细”和“导出 Excel”二级操作使用。
  406| */
  407|function normalizeMessageRawResponse(value: unknown): Record<string, any> | null {
  408|  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  409|  const raw = value as Record<string, any>
  410|  const safeResultTable = normalizeSafeResultTable(raw.result_table)
  411|  if (!safeResultTable) return null
  412|  return { result_table: safeResultTable }
  413|}
  414|
  415|/**
  416| * 白名单保留结果明细表。
  417| *
  418| * 参数：value 候选表格对象。
  419| * 返回：只含 columns/rows 的表格；没有行数据时返回 null。
  420| */
  421|function normalizeSafeResultTable(value: unknown): { columns: string[]; rows: Array<Record<string, string | number | boolean | null>> } | null {
  422|  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  423|  const raw = value as Record<string, unknown>
  424|  if (!Array.isArray(raw.rows)) return null
  425|  const rawRows = raw.rows.filter(isPlainObject)
  426|  if (!rawRows.length) return null
  427|
  428|  const rawColumns = Array.isArray(raw.columns) ? raw.columns : Object.keys(rawRows[0] || {})
  429|  const columns = rawColumns
  430|    .map((column) => String(column || '').trim())
  431|    .filter((column, index, source) => Boolean(column) && source.indexOf(column) === index)
  432|  if (!columns.length) return null
  433|
  434|  const rows = rawRows.map((row) => {
  435|    const next: Record<string, string | number | boolean | null> = {}
  436|    columns.forEach((column) => {
  437|      next[column] = normalizeSafeResultCell(row[column])
  438|    })
  439|    return next
  440|  })
  441|  return { columns, rows }
  442|}
  443|
  444|/** 判断候选值是否为普通对象。 */
  445|function isPlainObject(value: unknown): value is Record<string, unknown> {
  446|  return Boolean(value && typeof value === 'object' && !Array.isArray(value))
  447|}
  448|
  449|/**
  450| * 归一化可持久化的表格单元格。
  451| *
  452| * 参数：value 原始单元格值。
  453| * 返回：浏览器本地安全保存和导出的基础类型。
  454| */
  455|function normalizeSafeResultCell(value: unknown): string | number | boolean | null {
  456|  if (value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value
  457|  if (value === undefined) return ''
  458|  return String(value)
  459|}
  460|
  461|/**
  462| * 规范化消息并移除不参与展示的原始接口大对象。
  463| */
  464|function normalizeMessage(value: unknown): BusinessChatMessage | null {
  465|  if (!isMessage(value)) return null
  466|  const raw = value as Record<string, any>
  467|  return {
  468|    id: raw.id,
  469|    role: raw.role,
  470|    content: raw.content,
  471|    domain: raw.domain,
  472|    status: typeof raw.status === 'string' ? raw.status : undefined,
  473|    presentation: raw.presentation && typeof raw.presentation === 'object' && !Array.isArray(raw.presentation) ? raw.presentation : null,
  474|    createdAt: raw.createdAt,
  475|    rawResponse: normalizeMessageRawResponse(raw.rawResponse),
  476|    loading: Boolean(raw.loading),
  477|    error: typeof raw.error === 'string' ? raw.error : undefined,
  478|  }
  479|}
  480|
```

## frontend/src/views/business-chat/BusinessChatPage.vue:40-190
```
   40|          :data-status="message.status"
   41|          :data-domain="message.domain"
   42|        >
   43|          <div class="message-meta">
   44|            <span class="message-sender">{{ message.role === 'user' ? '我' : '经营计划智能助手' }}</span>
   45|            <em v-if="message.domain !== 'auto'" class="message-domain">{{ domainLabelMap[message.domain] }}</em>
   46|            <time v-if="message.createdAt" class="message-time">{{ formatRelativeTime(message.createdAt) }}</time>
   47|          </div>
   48|
   49|          <!-- 助手消息状态标签 -->
   50|          <div v-if="message.role === 'assistant' && !message.loading && !message.presentation && resolveStatusBadge(message.status)" class="message-status-row">
   51|            <span :class="['status-badge', `status-badge--${resolveStatusBadge(message.status)?.type}`]">
   52|              {{ resolveStatusBadge(message.status)?.label }}
   53|            </span>
   54|          </div>
   55|
   56|          <div class="bubble">
   57|            <div
   58|              v-if="message.content && !message.presentation"
   59|              :class="['message-content', { 'streaming-answer': message.role === 'assistant' && message.loading }]"
   60|              data-testid="message-content"
   61|            >
   62|              <div
   63|                v-if="message.role === 'assistant'"
   64|                class="assistant-markdown"
   65|                v-html="renderBusinessMarkdown(message.content)"
   66|              />
   67|              <p v-else>{{ message.content }}</p>
   68|            </div>
   69|
   70|            <!-- 加载动画：三点跳动 -->
   71|            <div v-if="message.loading" class="loading-row" data-testid="message-loading" aria-live="polite">
   72|              <span class="typing-indicator">
   73|                <span /><span /><span />
   74|              </span>
   75|              <span class="loading-text" aria-label="AI 正在生成回答">{{ resolveLoadingText(message) }}</span>
   76|            </div>
   77|
   78|            <div v-if="message.error" class="error" data-testid="message-error">{{ message.error }}</div>
   79|
   80|            <div
   81|              v-if="message.presentation"
   82|              :class="['result', `result--${resolveResultTone(message.status)}`, resolveAssistantResultLayout(message)]"
   83|              data-testid="assistant-result"
   84|            >
   85|              <div class="result-hero">
   86|                <div class="result-hero__meta">
   87|                  <span
   88|                    v-if="resolveStatusBadge(message.status)"
   89|                    :class="['status-badge', `status-badge--${resolveStatusBadge(message.status)?.type}`]"
   90|                  >
   91|                    {{ resolveStatusBadge(message.status)?.label }}
   92|                  </span>
   93|                  <span v-if="message.presentation.displayType" class="display-badge">
   94|                    {{ formatDisplayTypeLabel(message.presentation.displayType) }}
   95|                  </span>
   96|                  <span class="display-badge display-badge--layout">
   97|                    {{ resolveAssistantReplyKicker(message) }}
   98|                  </span>
   99|                </div>
  100|                <div v-if="message.presentation.title" class="result-title" data-testid="result-title">{{ message.presentation.title }}</div>
  101|                <div
  102|                  v-if="message.presentation.answer"
  103|                  class="result-answer assistant-prose assistant-markdown"
  104|                  data-testid="result-answer"
  105|                  v-html="renderBusinessMarkdown(message.presentation.answer)"
  106|                />
  107|                <div v-if="shouldShowSecondaryActions(message)" class="answer-secondary-actions" data-testid="answer-secondary-actions">
  108|                  <el-button
  109|                    size="small"
  110|                    round
  111|                    plain
  112|                    :disabled="!hasAssistantBasis(message)"
  113|                    @click="toggleAssistantBasisDetails(message)"
  114|                  >
  115|                    查看数据依据
  116|                  </el-button>
  117|                  <el-button
  118|                    size="small"
  119|                    round
  120|                    plain
  121|                    :disabled="!getAssistantAuditTable(message)?.rows.length"
  122|                    @click="toggleAssistantTable(message)"
  123|                  >
  124|                    {{ isAssistantTableExpanded(message) ? '收起明细' : '展开明细' }}
  125|                  </el-button>
  126|                  <el-button
  127|                    size="small"
  128|                    round
  129|                    plain
  130|                    :disabled="!getAssistantAuditTable(message)?.rows.length"
  131|                    @click="exportAssistantTableToExcel(message)"
  132|                  >
  133|                    导出 Excel
  134|                  </el-button>
  135|                </div>
  136|                <div v-if="buildResultSummaryItems(message).length" class="result-summary-strip">
  137|                  <span
  138|                    v-for="item in buildResultSummaryItems(message)"
  139|                    :key="`${message.id}-${item.label}`"
  140|                    class="result-summary-strip__item"
  141|                  >
  142|                    <strong>{{ item.value }}</strong>{{ item.label }}
  143|                  </span>
  144|                </div>
  145|              </div>
  146|
  147|              <div v-if="message.presentation.highlights.length" class="highlight-list" data-testid="result-highlights">
  148|                <div class="section-label">关键结论</div>
  149|                <span v-for="text in message.presentation.highlights" :key="text">{{ text }}</span>
  150|              </div>
  151|
  152|              <div v-if="shouldShowPresentationChart(message)" class="presentation-chart" data-testid="result-chart">
  153|                <div class="presentation-chart__title">
  154|                  {{ buildChartTitle(message.presentation.chart) }}
  155|                </div>
  156|                <div class="presentation-chart__meta">{{ buildChartMeta(message.presentation.chart) }}</div>
  157|                <svg
  158|                  v-if="message.presentation.chart.chart_type === 'line'"
  159|                  class="presentation-chart__svg"
  160|                  viewBox="0 0 640 220"
  161|                  role="img"
  162|                  :aria-label="buildChartAriaLabel(message.presentation.chart)"
  163|                >
  164|                  <polyline
  165|                    class="presentation-chart__line"
  166|                    :points="buildLineChartPoints(message.presentation.chart)"
  167|                    fill="none"
  168|                  />
  169|                  <circle
  170|                    v-for="point in buildLineChartCircles(message.presentation.chart)"
  171|                    :key="`${message.id}-line-${point.x}-${point.y}`"
  172|                    class="presentation-chart__point"
  173|                    :cx="point.x"
  174|                    :cy="point.y"
  175|                    r="4"
  176|                  />
  177|                  <text
  178|                    v-for="label in buildChartLabels(message.presentation.chart)"
  179|                    :key="`${message.id}-line-label-${label.x}-${label.text}`"
  180|                    class="presentation-chart__label"
  181|                    :x="label.x"
  182|                    y="210"
  183|                    text-anchor="middle"
  184|                  >
  185|                    {{ label.text }}
  186|                  </text>
  187|                </svg>
  188|                <div
  189|                  v-else-if="message.presentation.chart.chart_type === 'pie'"
  190|                  class="presentation-chart__pie-layout"
```

## frontend/src/views/business-chat/BusinessChatPage.vue:974-1065
```
  974|/** 将物流结果适配为统一展示结构，前端不反推或修改业务事实。 */
  975|function adaptLogisticsResult(data: LogisticsDataQaResult): UnifiedResult {
  976|  const presentation = data.presentation
  977|  const unsupported = presentation?.unsupported_explanation
  978|  const answer = presentation?.answer || data.answer_summary || data.status?.message || ''
  979|  return normalizeResult({
  980|    displayType: presentation?.display_type || '',
  981|    title: presentation?.title || '物流数据问答结果',
  982|    answer,
  983|    highlights: filterBusinessTexts(dedupeBusinessTexts(presentation?.highlights || [], [answer])),
  984|    cards: localizeCards(presentation?.cards || []),
  985|    chart: normalizeChart(presentation?.chart_spec || null),
  986|    table: resolvePresentationTable(presentation),
  987|    followUps: localizeFollowUps(presentation?.follow_up?.questions || data.clarification_questions || []),
  988|    suggestions: filterBusinessTexts(unsupported?.suggestions || data.query_plan?.unsupported_suggestions || []),
  989|    caveats: filterBusinessTexts(presentation?.caveats || []),
  990|    caveatItems: normalizeCaveatItems((presentation as Record<string, any> | null | undefined)?.caveat_items, presentation?.caveats || []),
  991|  })
  992|}
  993|
  994|/** 将计划 BOM 结果适配为统一展示结构，前端只展示后端确定性返回。 */
  995|function adaptPlanBomResult(data: PlanBomQaResponse): UnifiedResult {
  996|  const presentation = data.presentation
  997|  const followUp = presentation?.follow_up as { questions?: string[]; examples?: string[] } | null | undefined
  998|  const unsupported = presentation?.unsupported_explanation as { reason?: string; suggestions?: string[] } | null | undefined
  999|  const answer = presentation?.answer || data.answer_summary || data.status?.message || ''
 1000|  return normalizeResult({
 1001|    displayType: (presentation as Record<string, any> | null | undefined)?.display_type || '',
 1002|    title: presentation?.title || `计划 BOM 问答结果（${data.classification || '未知'}）`,
 1003|    answer,
 1004|    highlights: filterBusinessTexts(dedupeBusinessTexts(presentation?.highlights || [], [answer])),
 1005|    cards: [],
 1006|    chart: null,
 1007|    table: resolvePresentationTable(presentation),
 1008|    followUps: localizeFollowUps(followUp?.questions || []),
 1009|    suggestions: filterBusinessTexts(unsupported?.suggestions || []),
 1010|    caveats: filterBusinessTexts((presentation as Record<string, any> | null | undefined)?.caveats || []),
 1011|    caveatItems: normalizeCaveatItems((presentation as Record<string, any> | null | undefined)?.caveat_items, (presentation as Record<string, any> | null | undefined)?.caveats || []),
 1012|  })
 1013|}
 1014|
 1015|/** 只尊重后端 presentation 明确编排的表格，不再因原始 result_table 存在而固定展示“明细数据”。 */
 1016|function resolvePresentationTable(presentation: { table_spec?: UnifiedTable | null } | null | undefined): UnifiedTable | null {
 1017|  return presentation?.table_spec || null
 1018|}
 1019|
 1020|/** 补齐展示默认值，避免字段缺失导致页面异常。 */
 1021|function normalizeResult(value: Partial<UnifiedResult>): UnifiedResult {
 1022|  return {
 1023|    displayType: value.displayType || '',
 1024|    title: value.title || '',
 1025|    answer: value.answer || '',
 1026|    highlights: value.highlights || [],
 1027|    cards: value.cards || [],
 1028|    chart: value.chart || null,
 1029|    table: normalizeTable(value.table || null),
 1030|    followUps: value.followUps || [],
 1031|    suggestions: value.suggestions || [],
 1032|    caveats: value.caveats || [],
 1033|    caveatItems: normalizeCaveatItems(value.caveatItems, value.caveats || []),
 1034|  }
 1035|}
 1036|
 1037|/**
 1038| * 归一化后端分级口径提醒。
 1039| *
 1040| * 参数：
 1041| *   caveatItems: 后端新协议返回的分级口径提醒；
 1042| *   caveats: 旧协议普通口径提醒，用作 info 级兜底。
 1043| *
 1044| * 返回：
 1045| *   去重后的 CaveatItem 数组。前端只展示业务可读文本，不暴露技术字段。
 1046| */
 1047|function normalizeCaveatItems(caveatItems?: CaveatItem[] | null, caveats: string[] = []): CaveatItem[] {
 1048|  const candidates: CaveatItem[] = []
 1049|  if (Array.isArray(caveatItems)) {
 1050|    caveatItems.forEach((item) => {
 1051|      const text = String((item as CaveatItem)?.text || '').trim()
 1052|      if (!text || !filterBusinessTexts([text]).length) return
 1053|      candidates.push({
 1054|        level: normalizeCaveatLevel((item as CaveatItem)?.level),
 1055|        text,
 1056|      })
 1057|    })
 1058|  }
 1059|  filterBusinessTexts(caveats).forEach((text) => candidates.push({ level: 'info', text }))
 1060|
 1061|  const seen = new Set<string>()
 1062|  return candidates.filter((item) => {
 1063|    const key = `${item.level}:${normalizeBusinessText(item.text)}`
 1064|    if (seen.has(key)) return false
 1065|    seen.add(key)
```

## frontend/src/views/business-chat/BusinessChatPage.vue:1804-1972
```
 1804|/** 生成结果摘要条，优先展示行数、图表类型和指标卡数量等展示事实。 */
 1805|function buildResultSummaryItems(message: BusinessChatMessage): ResultSummaryItem[] {
 1806|  const presentation = message.presentation as UnifiedResult | null | undefined
 1807|  if (!presentation) return []
 1808|  const items: ResultSummaryItem[] = []
 1809|  const table = getAssistantResultTable(message)
 1810|  if (shouldShowResultTable(message) && table?.rows.length) {
 1811|    items.push({ label: '行明细', value: String(table.rows.length) })
 1812|  }
 1813|  if (shouldShowMetricCards(message)) {
 1814|    items.push({ label: '项指标', value: String(presentation.cards.length) })
 1815|  }
 1816|  if (shouldShowPresentationChart(message) && presentation.chart) {
 1817|    items.push({ label: '图表', value: formatChartTypeLabel(presentation.chart.chart_type) })
 1818|  }
 1819|  return items
 1820|}
 1821|
 1822|/** 判断助手回复应采用叙事、数据还是图表布局；只控制 UI 层，不改变后端业务结果。 */
 1823|function resolveAssistantResultLayout(message: BusinessChatMessage): AssistantResultLayoutClass {
 1824|  if (shouldShowPresentationChart(message)) return 'ai-response-card--chart'
 1825|  if (shouldShowResultTable(message) || shouldShowMetricCards(message)) return 'ai-response-card--data'
 1826|  return 'ai-response-card--narrative'
 1827|}
 1828|
 1829|/** 指标卡只在后端返回卡片且当前布局需要数据摘要时展示。 */
 1830|function shouldShowMetricCards(message: BusinessChatMessage): boolean {
 1831|  const presentation = message.presentation as UnifiedResult | null | undefined
 1832|  return Boolean(presentation && cardDisplayTypes.has(presentation.displayType) && presentation.cards.length)
 1833|}
 1834|
 1835|/** 图表只在后端按用户显式图表意图返回 chart display_type 时展示。 */
 1836|function shouldShowPresentationChart(message: BusinessChatMessage): boolean {
 1837|  const presentation = message.presentation as UnifiedResult | null | undefined
 1838|  return Boolean(presentation?.chart && chartDisplayTypes.has(presentation.displayType))
 1839|}
 1840|
 1841|/**
 1842| * 判断是否展示二级操作。
 1843| *
 1844| * 参数：message 当前助手消息。
 1845| * 返回：存在数据口径或审计明细时返回 true，把结构化结果放到主回答下方的次级入口。
 1846| */
 1847|function shouldShowSecondaryActions(message: BusinessChatMessage): boolean {
 1848|  return Boolean(message.presentation && (hasAssistantBasis(message) || getAssistantAuditTable(message)?.rows.length))
 1849|}
 1850|
 1851|/** 判断当前回答是否有可展开的数据口径。 */
 1852|function hasAssistantBasis(message: BusinessChatMessage): boolean {
 1853|  return getCaveatItemsByLevel(message, 'info').length > 0
 1854|}
 1855|
 1856|/** 判断“数据口径”折叠区是否由二级按钮展开。 */
 1857|function isAssistantBasisExpanded(message: BusinessChatMessage): boolean {
 1858|  return expandedBasisMessageIds.value.has(message.id)
 1859|}
 1860|
 1861|/** 切换“查看数据依据”折叠区，只影响 UI 展开状态，不改变后端事实。 */
 1862|function toggleAssistantBasisDetails(message: BusinessChatMessage) {
 1863|  expandedBasisMessageIds.value = toggleMessageIdSet(expandedBasisMessageIds.value, message.id)
 1864|}
 1865|
 1866|/** 按等级读取口径提醒；没有新协议 caveatItems 时兼容旧 caveats。 */
 1867|function getCaveatItemsByLevel(message: BusinessChatMessage, level: CaveatItem['level']): CaveatItem[] {
 1868|  const presentation = message.presentation as UnifiedResult | null | undefined
 1869|  if (!presentation) return []
 1870|  const items = presentation.caveatItems.length ? presentation.caveatItems : normalizeCaveatItems([], presentation.caveats)
 1871|  return items.filter((item) => item.level === level)
 1872|}
 1873|
 1874|/** 获取审计/导出可用的明细表；叙事回答默认不展示，但仍保留给用户手动展开和导出。 */
 1875|function getAssistantAuditTable(message: BusinessChatMessage): UnifiedTable | null {
 1876|  const presentation = message.presentation as UnifiedResult | null | undefined
 1877|  const presentationTable = normalizeTable(presentation?.table || null)
 1878|  if (presentationTable) return presentationTable
 1879|  const rawResponse = message.rawResponse as Record<string, any> | null | undefined
 1880|  return normalizeTable((rawResponse?.result_table || rawResponse?.data?.result_table || null) as UnifiedTable | null)
 1881|}
 1882|
 1883|/** 判断明细表当前是否应展开；显式表格问题默认展开，普通叙事问题需用户点击“展开明细”。 */
 1884|function isAssistantTableExpanded(message: BusinessChatMessage): boolean {
 1885|  if (collapsedTableMessageIds.value.has(message.id)) return false
 1886|  const presentation = message.presentation as UnifiedResult | null | undefined
 1887|  const hasRows = Boolean(getAssistantAuditTable(message)?.rows.length)
 1888|  if (presentation && tableDisplayTypes.has(presentation.displayType) && hasRows) return true
 1889|  return expandedTableMessageIds.value.has(message.id)
 1890|}
 1891|
 1892|/** 切换明细展开状态，支持显式表格回答收起、叙事回答手动展开。 */
 1893|function toggleAssistantTable(message: BusinessChatMessage) {
 1894|  if (!getAssistantAuditTable(message)?.rows.length) return
 1895|  if (isAssistantTableExpanded(message)) {
 1896|    const nextExpanded = new Set(expandedTableMessageIds.value)
 1897|    nextExpanded.delete(message.id)
 1898|    expandedTableMessageIds.value = nextExpanded
 1899|    collapsedTableMessageIds.value = addMessageIdToSet(collapsedTableMessageIds.value, message.id)
 1900|    return
 1901|  }
 1902|  expandedTableMessageIds.value = addMessageIdToSet(expandedTableMessageIds.value, message.id)
 1903|  collapsedTableMessageIds.value = removeMessageIdFromSet(collapsedTableMessageIds.value, message.id)
 1904|}
 1905|
 1906|/** 获取当前助手消息的可见明细表；默认只在显式表格或用户手动展开时返回。 */
 1907|function getAssistantResultTable(message: BusinessChatMessage): UnifiedTable | null {
 1908|  const presentation = message.presentation as UnifiedResult | null | undefined
 1909|  if (!presentation || !isAssistantTableExpanded(message)) return null
 1910|  if (tableDisplayTypes.has(presentation.displayType)) return getAssistantAuditTable(message)
 1911|  return expandedTableMessageIds.value.has(message.id) ? getAssistantAuditTable(message) : null
 1912|}
 1913|
 1914|/** 表格只在后端返回有效列和行且当前允许展开时展示，避免空表占据叙事型回答空间。 */
 1915|function shouldShowResultTable(message: BusinessChatMessage): boolean {
 1916|  const table = getAssistantResultTable(message)
 1917|  return Boolean(table?.columns.length && table.rows.length)
 1918|}
 1919|
 1920|/** 切换 Set 中的消息 ID，返回新 Set 以触发 Vue 响应式更新。 */
 1921|function toggleMessageIdSet(source: Set<string>, messageId: string): Set<string> {
 1922|  const next = new Set(source)
 1923|  if (next.has(messageId)) next.delete(messageId)
 1924|  else next.add(messageId)
 1925|  return next
 1926|}
 1927|
 1928|/** 向消息 ID Set 添加一项，返回新 Set 以触发 Vue 响应式更新。 */
 1929|function addMessageIdToSet(source: Set<string>, messageId: string): Set<string> {
 1930|  const next = new Set(source)
 1931|  next.add(messageId)
 1932|  return next
 1933|}
 1934|
 1935|/** 从消息 ID Set 移除一项，返回新 Set 以触发 Vue 响应式更新。 */
 1936|function removeMessageIdFromSet(source: Set<string>, messageId: string): Set<string> {
 1937|  const next = new Set(source)
 1938|  next.delete(messageId)
 1939|  return next
 1940|}
 1941|
 1942|/**
 1943| * 将当前助手回复中的明细表导出为 Excel。
 1944| *
 1945| * 参数：
 1946| *   message: 当前助手消息，导出其中 presentation.table 的已展示明细。
 1947| *
 1948| * 返回：
 1949| *   无返回值；浏览器侧触发 xlsx 文件下载。
 1950| */
 1951|function exportAssistantTableToExcel(message: BusinessChatMessage) {
 1952|  const table = getAssistantAuditTable(message)
 1953|  if (!table?.columns.length || !table.rows.length) {
 1954|    ElMessage.warning('当前回答没有可导出的明细数据')
 1955|    return
 1956|  }
 1957|
 1958|  const exportRows = buildAssistantTableExportRows(table)
 1959|  const worksheet = XLSX.utils.json_to_sheet(exportRows, { header: table.columns })
 1960|  const exportMerges = buildAssistantTableExportMerges(table)
 1961|  if (exportMerges.length) worksheet['!merges'] = exportMerges
 1962|  applyAssistantTableExportAlignment(worksheet)
 1963|  // 按中文列名和单元格内容给出保守列宽，避免导出后业务用户第一眼只能看到截断内容。
 1964|  worksheet['!cols'] = table.columns.map((column) => ({
 1965|    wch: Math.max(12, Math.min(36, String(column).length + 8)),
 1966|  }))
 1967|  const workbook = XLSX.utils.book_new()
 1968|  XLSX.utils.book_append_sheet(workbook, worksheet, '明细数据')
 1969|  XLSX.writeFile(workbook, buildAssistantTableExportFileName(message))
 1970|  ElMessage.success(`已导出 ${table.rows.length} 行明细数据`)
 1971|}
 1972|
```

## tests/business_acceptance/test_business_chat_answer_format_preference.py:1-330
```
    1|from __future__ import annotations
    2|
    3|from backend.app.domains.logistics.schemas.data_qa import (
    4|    LogisticsDataQaPlan,
    5|    LogisticsDataQaResult,
    6|    LogisticsDataQaStatus,
    7|    LogisticsDataQaTable,
    8|)
    9|from backend.app.domains.logistics.services.llm_answer_presentation_service import LogisticsLlmAnswerPresentationService
   10|from backend.app.domains.plan_bom.schemas.qa import (
   11|    PlanBomNluCandidate,
   12|    PlanBomQaResponse,
   13|    PlanBomQaStatus,
   14|    PlanBomTableSpec,
   15|)
   16|from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
   17|from backend.app.services.business_answer_stream_service import BusinessAnswerStreamService
   18|
   19|
   20|class _FakeStreamClient:
   21|    """构造 OpenAI 兼容的测试流式客户端。"""
   22|
   23|    def __init__(self, chunks: list[str]) -> None:
   24|        self.chat = _FakeChat(chunks)
   25|
   26|
   27|class _FakeChat:
   28|    """承载 completions 入口，避免测试访问真实 LLM。"""
   29|
   30|    def __init__(self, chunks: list[str]) -> None:
   31|        self.completions = _FakeCompletions(chunks)
   32|
   33|
   34|class _FakeCompletions:
   35|    """返回固定 chunk 的流式 completion。"""
   36|
   37|    def __init__(self, chunks: list[str]) -> None:
   38|        self._chunks = chunks
   39|
   40|    def create(self, **_kwargs: object) -> list[dict[str, object]]:
   41|        """返回 OpenAI chat.completions.create 兼容事件。"""
   42|
   43|        return [{"choices": [{"delta": {"content": chunk}}]} for chunk in self._chunks]
   44|
   45|
   46|def _logistics_result(*, rows: list[dict[str, object]] | None = None) -> LogisticsDataQaResult:
   47|    """构造可复用的物流确定性结果。
   48|
   49|    参数：
   50|        rows: 后端查询返回的结构化行。
   51|    返回值：
   52|        一个 OK 状态的 LogisticsDataQaResult。
   53|    业务逻辑：
   54|        测试只关注展示编排，不依赖真实数据库。
   55|    """
   56|
   57|    result_rows = rows or [
   58|        {"region_name": "华东", "shipment_mw": 120.5},
   59|        {"region_name": "华南", "shipment_mw": 88.2},
   60|    ]
   61|    return LogisticsDataQaResult(
   62|        answer_summary="2026年发运量统计已完成，华东 120.5MW，华南 88.2MW。",
   63|        result_table=LogisticsDataQaTable(columns=["region_name", "shipment_mw"], rows=result_rows),
   64|        calculation_logic=["发运量按 MW 口径汇总。"],
   65|        data_scope={"year": 2026},
   66|        query_plan=LogisticsDataQaPlan(
   67|            intent="shipment_summary",
   68|            query_key="sys_region_mw",
   69|            metrics=["shipment_mw"],
   70|            dimensions=["region_name"],
   71|            filters={"year": 2026},
   72|            group_by=["region_name"],
   73|        ),
   74|        status=LogisticsDataQaStatus(code="OK", message="查询成功", success=True),
   75|    )
   76|
   77|
   78|def _stream_payload() -> dict[str, object]:
   79|    """构造流式答案安全测试使用的确定性 payload。"""
   80|
   81|    result = _logistics_result()
   82|    service = LogisticsLlmAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
   83|    presentation = service.build_presentation(question="统计2026年各区域发运量", result=result)
   84|    assert presentation is not None
   85|    result.presentation = presentation
   86|    return result.model_dump(mode="json")
   87|
   88|
   89|def _plan_bom_response(question: str) -> PlanBomQaResponse:
   90|    """构造计划 BOM 确定性结果。
   91|
   92|    参数：
   93|        question: 用户原始问题，用于测试展示意图识别。
   94|    返回值：
   95|        一个 A 类 OK 的 PlanBomQaResponse。
   96|    业务逻辑：
   97|        计划 BOM 表格事实仍保留在 result_table，presentation 是否展示由问题意图决定。
   98|    """
   99|
  100|    return PlanBomQaResponse(
  101|        question=question,
  102|        classification="A",
  103|        status=PlanBomQaStatus(code="OK", message="查询成功"),
  104|        nlu=PlanBomNluCandidate(question=question, intent="plan_power_prediction", slots={"order_tail_no": ["00104"]}),
  105|        answer_summary="订单00104功率预测已完成，中心功率为620W。",
  106|        result_table=PlanBomTableSpec(
  107|            columns=["功率档", "预测比例"],
  108|            rows=[{"功率档": "620W", "预测比例": "50%"}, {"功率档": "625W", "预测比例": "50%"}],
  109|        ),
  110|        raw_result={"power_prediction": {"center_power": 620}},
  111|    )
  112|
  113|
  114|def test_logistics_answer_defaults_to_text_only_when_no_visual_request() -> None:
  115|    """未明确要求图表/表格/指标卡时，物流智能回答只给 Markdown 文字，不固定渲染数据组件。"""
  116|
  117|    service = LogisticsLlmAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
  118|    presentation = service.build_presentation(question="统计2026年各区域发运量", result=_logistics_result())
  119|
  120|    assert presentation is not None
  121|    assert presentation.display_type == "narrative"
  122|    assert presentation.table_spec is None
  123|    assert presentation.chart_spec is None
  124|    assert presentation.cards == []
  125|    assert presentation.title != "查询结果"
  126|    assert not any("本次返回" in item for item in presentation.highlights)
  127|    assert presentation.caveat_items
  128|    assert presentation.debug["presentation_source"] == "deterministic"
  129|    assert "requested_display" in presentation.debug
  130|    assert presentation.debug["final_display_type"] == presentation.display_type
  131|    assert "fallback_reason" in presentation.debug
  132|
  133|
  134|def test_logistics_caveat_levels_do_not_treat_generic_other_bucket_text_as_danger() -> None:
  135|    """普通区域兜底口径不应因“异常值归入其他”几个字被渲染为危险大块风险。"""
  136|
  137|    result = _logistics_result()
  138|    result.warnings = ["区域口径优先使用 delivery_area；为空时用 delivery_province 映射七大区域，异常值归入“其他”。"]
  139|    service = LogisticsLlmAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
  140|
  141|    presentation = service.build_presentation(question="统计2026年各区域发运量", result=result)
  142|
  143|    assert presentation is not None
  144|    levels_by_text = {item.text: item.level for item in presentation.caveat_items}
  145|    assert levels_by_text[result.warnings[0]] == "warning"
  146|
  147|
  148|def test_logistics_answer_respects_explicit_visual_requests() -> None:
  149|    """只有用户明确要求展示形式时，才返回对应的表格、图表或指标卡组件。"""
  150|
  151|    service = LogisticsLlmAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
  152|
  153|    table = service.build_presentation(question="请用表格展示2026年各区域发运量", result=_logistics_result())
  154|    chart = service.build_presentation(question="请用柱状图展示2026年各区域发运量", result=_logistics_result())
  155|    cards = service.build_presentation(question="请用指标卡展示2026年发运量概览", result=_logistics_result(rows=[{"scope_label": "2026年", "shipment_mw": 208.7}]))
  156|
  157|    assert table is not None and table.display_type == "table" and table.table_spec is not None
  158|    assert table.chart_spec is None and table.cards == []
  159|    assert chart is not None and chart.display_type == "bar_chart" and chart.chart_spec is not None
  160|    assert chart.table_spec is None and chart.cards == []
  161|    assert cards is not None and cards.display_type == "summary_cards" and cards.cards
  162|    assert cards.table_spec is None and cards.chart_spec is None
  163|
  164|
  165|def test_plan_bom_answer_defaults_to_text_only_but_keeps_raw_result_table() -> None:
  166|    """计划 BOM 未明确要求表格时，presentation 只做文字回答，原始 result_table 仍保留给后续导出/追溯。"""
  167|
  168|    service = PlanBomAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
  169|    response = _plan_bom_response("订单00104做功率预测")
  170|
  171|    presentation = service.build_presentation(response)
  172|
  173|    assert response.result_table.rows
  174|    assert presentation.display_type == "narrative"
  175|    assert presentation.table_spec is None
  176|
  177|
  178|def test_plan_bom_answer_uses_table_only_when_user_requests_table() -> None:
  179|    """计划 BOM 明确要求表格时，presentation 才携带 table_spec。"""
  180|
  181|    service = PlanBomAnswerPresentationService(enabled=True, base_url=None, api_key=None, model="")
  182|    response = _plan_bom_response("请用表格展示订单00104功率预测")
  183|
  184|    presentation = service.build_presentation(response)
  185|
  186|    assert presentation.display_type == "table"
  187|    assert presentation.table_spec is not None
  188|    assert presentation.table_spec.rows == response.result_table.rows
  189|
  190|
  191|def test_business_chat_frontend_does_not_fallback_to_raw_tables_for_narrative_presentation() -> None:
  192|    """前端已有 presentation 时应尊重展示编排，不能因 raw result_table 存在而固定显示“明细数据”。"""
  193|
  194|    page = "frontend/src/views/business-chat/BusinessChatPage.vue"
  195|    with open(page, encoding="utf-8") as file:
  196|        chat = file.read()
  197|
  198|    assert "function resolvePresentationTable" in chat
  199|    assert "function shouldShowPresentationChart" in chat
  200|    assert "presentation?.table_spec || data.result_table || null" not in chat
  201|    assert "v-if=\"shouldShowPresentationChart(message)\"" in chat
  202|    assert "tableDisplayTypes.has(presentation.displayType)" in chat
  203|    assert "cardDisplayTypes.has(presentation.displayType)" in chat
  204|
  205|
  206|def test_streamed_answer_rejects_new_numbers_and_keeps_structured_fields() -> None:
  207|    """LLM 流式表达新增确定性上下文外数值时，必须降级且不改结构化事实。"""
  208|
  209|    payload = _stream_payload()
  210|    fallback_answer = str(payload["answer_summary"])
  211|    service = BusinessAnswerStreamService(
  212|        enabled=True,
  213|        base_url="http://llm.local",
  214|        api_key="test-key",
  215|        model="test-model",
  216|        client=_FakeStreamClient(["华东 120.5MW，华南 88.2MW，另有华北 999MW。"]),
  217|    )
  218|
  219|    streamed_answer = "".join(
  220|        service.stream_answer(
  221|            domain="logistics",
  222|            question="统计2026年各区域发运量",
  223|            deterministic_payload=payload,
  224|            fallback_answer=fallback_answer,
  225|        )
  226|    )
  227|    final_payload = service.apply_streamed_answer(
  228|        domain="logistics",
  229|        deterministic_payload=payload,
  230|        streamed_answer=streamed_answer,
  231|    )
  232|
  233|    assert streamed_answer == fallback_answer
  234|    assert final_payload["presentation"]["answer"] == fallback_answer
  235|    assert final_payload["result_table"] == payload["result_table"]
  236|    assert final_payload["presentation"]["table_spec"] == payload["presentation"]["table_spec"]
  237|    assert final_payload["presentation"]["debug"]["stream_answer_source"] == "deterministic_fallback"
  238|    assert final_payload["presentation"]["debug"]["stream_fallback_reason"] == "stream_text_number_hallucination"
  239|
  240|
  241|def test_streamed_answer_rejects_visible_technical_leaks() -> None:
  242|    """LLM 流式表达暴露 SQL、query_key、planner 或数仓表名时，必须降级到确定性答案。"""
  243|
  244|    payload = _stream_payload()
  245|    fallback_answer = str(payload["answer_summary"])
  246|    service = BusinessAnswerStreamService(
  247|        enabled=True,
  248|        base_url="http://llm.local",
  249|        api_key="test-key",
  250|        model="test-model",
  251|        client=_FakeStreamClient(["planner 命中 query_key=sys_region_mw，SQL 来自 dws_logistics_detail_union。"]),
  252|    )
  253|
  254|    streamed_answer = "".join(
  255|        service.stream_answer(
  256|            domain="logistics",
  257|            question="统计2026年各区域发运量",
  258|            deterministic_payload=payload,
  259|            fallback_answer=fallback_answer,
  260|        )
  261|    )
  262|    final_payload = service.apply_streamed_answer(
  263|        domain="logistics",
  264|        deterministic_payload=payload,
  265|        streamed_answer=streamed_answer,
  266|    )
  267|
  268|    assert streamed_answer == fallback_answer
  269|    assert final_payload["presentation"]["answer"] == fallback_answer
  270|    assert final_payload["presentation"]["debug"]["stream_answer_source"] == "deterministic_fallback"
  271|    assert final_payload["presentation"]["debug"]["stream_fallback_reason"] == "stream_technical_visible_leak"
  272|
  273|
  274|def test_business_chat_frontend_uses_caveat_levels_secondary_actions_and_stream_stages() -> None:
  275|    """前端主回答应以 answer 为主，并把口径、明细和导出放到二级动作中。"""
  276|
  277|    page = "frontend/src/views/business-chat/BusinessChatPage.vue"
  278|    with open(page, encoding="utf-8") as file:
  279|        chat = file.read()
  280|    template = chat.split("<script setup", 1)[0]
  281|
  282|    assert "caveatItems" in chat
  283|    assert "data-testid=\"answer-secondary-actions\"" in template
  284|    assert "查看数据依据" in template
  285|    assert "展开明细" in template
  286|    assert "getAssistantAuditTable" in chat
  287|    assert "result-caveats--info" in chat
  288|    assert "result-caveats--warning" in chat
  289|    assert "result-caveats--danger" in chat
  290|    assert "function resolveLoadingText" in chat
  291|    assert "function updateAssistantStreamMeta" in chat
  292|    assert "正在理解问题" in chat
  293|    assert "正在查询数据" in chat
  294|    assert "正在组织回答" in chat
  295|    assert "正在生成回答" in chat
  296|    assert "onMeta:" in chat
  297|    assert "rawResponse?.query_plan" not in chat
  298|    assert "rawResponse?.presentation?.debug" not in chat
  299|
  300|
  301|def test_business_chat_session_keeps_only_safe_audit_table_for_secondary_actions() -> None:
  302|    """会话持久化不能丢失明细依据，但只能白名单保留 result_table，避免暴露 query_key/debug。"""
  303|
  304|    page = "frontend/src/utils/businessChatSessions.ts"
  305|    with open(page, encoding="utf-8") as file:
  306|        sessions = file.read()
  307|
  308|    assert "rawResponse: normalizeMessageRawResponse(raw.rawResponse)" in sessions
  309|    assert "function normalizeMessageRawResponse" in sessions
  310|    assert "result_table: safeResultTable" in sessions
  311|    assert "query_plan" not in sessions
  312|    assert "presentation?.debug" not in sessions
  313|    assert "rawResponse: null" not in sessions
```
