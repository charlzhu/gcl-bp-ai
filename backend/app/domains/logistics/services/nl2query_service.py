from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, TYPE_CHECKING

from backend.app.domains.logistics.schemas.query import LogisticsNLQuery
from backend.app.domains.logistics.services.dictionary_loader import LogisticsDictionaryLoader
from backend.app.domains.logistics.services.domain_router import LogisticsDomainRouter
from backend.app.domains.logistics.services.enum_mapper import LogisticsEnumMapper
from backend.app.domains.logistics.services.execution_audit_service import LogisticsExecutionAuditService
from backend.app.domains.logistics.services.hot_reload_service import LogisticsHotReloadService
from backend.app.domains.logistics.services.metric_resolver import LogisticsMetricResolver
from backend.app.domains.logistics.services.no_result_analyzer import LogisticsNoResultAnalyzer
from backend.app.domains.logistics.services.query_executor import LogisticsQueryExecutor
from backend.app.domains.logistics.services.query_param_validator import LogisticsQueryParamValidator
from backend.app.domains.logistics.services.query_response_standardizer import LogisticsQueryResponseStandardizer
from backend.app.domains.logistics.services.result_explainer import LogisticsResultExplainer
from backend.app.domains.logistics.services.result_count_helper import LogisticsResultCountHelper
from backend.app.domains.logistics.services.query_plan_store import LogisticsQueryPlanStore
from backend.app.domains.logistics.services.query_planner import LogisticsQueryPlanner
from backend.app.domains.logistics.services.sql_renderer import LogisticsSQLRenderer
from backend.app.domains.logistics.services.sql_template_registry import LogisticsSQLTemplateRegistry
from backend.app.domains.logistics.services.sql_whitelist import LogisticsSQLWhitelist
from backend.app.domains.logistics.services.template_loader import LogisticsTemplateLoader
from backend.app.domains.logistics.services.template_matcher import LogisticsTemplateMatcher
from backend.app.domains.logistics.services.text_normalizer import LogisticsTextNormalizer

if TYPE_CHECKING:
    # 只在类型检查阶段导入，避免单测环境没有 SQLAlchemy 时，因 query_service import 失败。
    from backend.app.domains.logistics.services.query_service import LogisticsQueryService

# 支持 25年3月 / 2025年3月 / 2025 年 3 月
_MONTH_PATTERN = re.compile(r"((?:20)?\d{2})\s*年\s*(\d{1,2})\s*月")
_YEAR_PATTERN = re.compile(r"((?:20)?\d{2})\s*年")

# 兼容中文问法里的常见编号提取。
_FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "contract_no": re.compile(r"(?:合同编号|合同号)\s*[:：]?\s*([A-Za-z0-9\-_]+)"),
    "inquiry_no": re.compile(r"(?:询比价编号|询价编号)\s*[:：]?\s*([A-Za-z0-9\-_]+)"),
    "ship_instruction_no": re.compile(r"(?:发货指令)\s*[:：]?\s*([A-Za-z0-9\-_]+)"),
    "sap_order_no": re.compile(r"(?:SAP(?:系统)?单号|SAP单号)\s*[:：]?\s*([A-Za-z0-9\-_]+)"),
    "vehicle_no": re.compile(r"(?:车牌号|车号)\s*[:：]?\s*([A-Z0-9一-龥\-]+)"),
    "task_id": re.compile(r"(?:任务ID|任务编号|任务号)\s*[:：]?\s*([A-Za-z0-9\-_]+)"),
}

_COMPARE_KEYWORDS = ("对比", "比较", "分别", "相较", "vs", "VS", "同比", "环比")
_DETAIL_KEYWORDS = ("明细", "详情", "记录", "列表", "清单")
_GROUP_BY_KEYWORDS = {
    "logistics_company_name": ("物流公司", "承运商"),
    "region_name": ("区域",),
    "transport_mode": ("运输方式", "汽运", "公路", "铁路", "铁运", "水运", "水路", "海运"),
    "biz_month": ("每月", "月度", "按月", "月份"),
}
_METRIC_KEYWORDS = {
    "total_fee": ("费用", "运费", "总费用", "运输成本"),
    "extra_fee": ("附加费", "异常费", "额外费用"),
    "shipment_trip_count": ("车次", "趟次", "车辆数"),
    "shipment_watt": ("运量", "发货量", "出货量", "发运量", "瓦数", "MW", "mw"),
}
_REGION_KEYWORDS = ("华东", "华北", "华南", "华中", "西北", "西南", "东北")
_TRANSPORT_MODE_CANONICAL = {
    "汽运": ("汽运", "公路"),
    "铁路": ("铁路", "铁运"),
    "水运": ("水运", "水路", "海运"),
}


class LogisticsNL2QueryService:
    """物流域自然语言查询服务（V8）。

    V8 的重点不再是继续加问法，而是补“执行前安全治理能力”：
    1. 查询参数安全校验；
    2. SQL 模板白名单；
    3. 执行审计增强；
    4. 同时顺手修复 import 阶段对 SQLAlchemy 的强依赖问题，保证轻量单测可运行。
    """

    def __init__(
        self,
        query_service: "LogisticsQueryService",
        template_loader: LogisticsTemplateLoader | None = None,
        template_matcher: LogisticsTemplateMatcher | None = None,
        query_planner: LogisticsQueryPlanner | None = None,
        dictionary_loader: LogisticsDictionaryLoader | None = None,
        text_normalizer: LogisticsTextNormalizer | None = None,
        metric_resolver: LogisticsMetricResolver | None = None,
        enum_mapper: LogisticsEnumMapper | None = None,
        domain_router: LogisticsDomainRouter | None = None,
        hot_reload_service: LogisticsHotReloadService | None = None,
        sql_template_registry: LogisticsSQLTemplateRegistry | None = None,
        sql_renderer: LogisticsSQLRenderer | None = None,
        query_executor: LogisticsQueryExecutor | None = None,
        query_plan_store: LogisticsQueryPlanStore | None = None,
        query_param_validator: LogisticsQueryParamValidator | None = None,
        sql_whitelist: LogisticsSQLWhitelist | None = None,
        execution_audit_service: LogisticsExecutionAuditService | None = None,
        result_explainer: LogisticsResultExplainer | None = None,
        no_result_analyzer: LogisticsNoResultAnalyzer | None = None,
        query_response_standardizer: LogisticsQueryResponseStandardizer | None = None,
    ) -> None:
        self.query_service = query_service
        self.template_loader = template_loader or LogisticsTemplateLoader()
        self.template_matcher = template_matcher or LogisticsTemplateMatcher()
        self.query_planner = query_planner or LogisticsQueryPlanner()
        self.dictionary_loader = dictionary_loader or LogisticsDictionaryLoader()
        self.text_normalizer = text_normalizer or LogisticsTextNormalizer()
        self.metric_resolver = metric_resolver or LogisticsMetricResolver()
        self.enum_mapper = enum_mapper or LogisticsEnumMapper()
        self.domain_router = domain_router or LogisticsDomainRouter()
        self.hot_reload_service = hot_reload_service or LogisticsHotReloadService(self.template_loader)
        self.sql_template_registry = sql_template_registry or LogisticsSQLTemplateRegistry()
        self.sql_renderer = sql_renderer or LogisticsSQLRenderer()
        self.query_executor = query_executor or LogisticsQueryExecutor(self.query_service)
        self.query_plan_store = query_plan_store or LogisticsQueryPlanStore(self.query_service)
        self.query_param_validator = query_param_validator or LogisticsQueryParamValidator()
        self.sql_whitelist = sql_whitelist or LogisticsSQLWhitelist()
        self.execution_audit_service = execution_audit_service or LogisticsExecutionAuditService()
        self.result_explainer = result_explainer or LogisticsResultExplainer()
        self.no_result_analyzer = no_result_analyzer or LogisticsNoResultAnalyzer()
        self.query_response_standardizer = query_response_standardizer or LogisticsQueryResponseStandardizer()

    def parse_and_query(self, payload: LogisticsNLQuery, trace_id: str | None = None) -> dict[str, Any]:
        # 第一步：加载配置化字典。这里保持“按次读取”，以便和热更新策略一致。
        synonyms_config = self.dictionary_loader.load_synonyms()
        metric_dictionary = self.dictionary_loader.load_metric_dictionary()
        enum_config = self.dictionary_loader.load_enum_mappings()

        # 第二步：先对问题做文本归一，尽量把业务口语收敛成标准表达。
        normalized_question, hit_synonyms = self.text_normalizer.normalize(payload.question, synonyms_config)

        # 第三步：走规则解析，得到基础查询计划。
        # 这里仍然保留原始问题做规则抽取，避免中文关键词提前被归一后影响规则判断。
        base_parsed = self._rule_parse(payload.question)

        # 第四步：用指标字典进一步解析业务指标。
        resolved_metric, metric_display_name = self.metric_resolver.resolve(
            payload.question,
            metric_dictionary,
            fallback_metric=base_parsed.get("metric_type", "shipment_watt"),
        )
        base_parsed["metric_type"] = resolved_metric
        if metric_display_name:
            base_parsed["metric_display_name"] = metric_display_name

        # 第五步：用枚举映射统一运输方式、区域、来源范围等值。
        transport_mode, transport_hits = self.enum_mapper.map_value("transport_mode", payload.question, enum_config)
        if transport_mode:
            base_parsed["transport_mode"] = transport_mode
        region_name, region_hits = self.enum_mapper.map_value("region_name", payload.question, enum_config)
        if region_name:
            base_parsed["region_name"] = region_name
        source_scope, source_hits = self.enum_mapper.map_value("source_scope", payload.question, enum_config)
        if source_scope:
            base_parsed["source_scope"] = source_scope

        # 第六步：获取最新模板目录版本，并执行“多域路由”。
        catalog = self.hot_reload_service.get_catalog()
        config_version = self.hot_reload_service.get_version()
        route_result = self.domain_router.route(payload.question, normalized_question, base_parsed)
        selected_domain = route_result.get("selected_domain", "logistics")

        # 第七步：在选中的业务域模板里做匹配。
        templates = [
            *(catalog.get("global_templates", []) or []),
            *((catalog.get("domains", {}) or {}).get(selected_domain, []) or []),
        ]
        matched = self.template_matcher.match(
            normalized_question,
            base_parsed,
            templates,
            route_result=route_result,
        )
        parsed = self.query_planner.apply_template(
            base_parsed,
            matched,
            route_result=route_result,
            config_version=config_version,
            config_version_detail=self.hot_reload_service.get_version_detail(),
        )

        # 第八步：把归一结果和命中细节挂回 parsed，方便调试和后续前端展示。
        parsed["normalized_question"] = normalized_question
        parsed["hit_synonyms"] = hit_synonyms
        parsed["transport_mode_hits"] = transport_hits
        parsed["region_hits"] = region_hits
        parsed["source_scope_hits"] = source_hits
        parsed["current_execution_domain"] = "logistics"
        if selected_domain != "logistics":
            parsed["domain_execution_warning"] = "当前版本仅支持物流域执行，已保留路由结果供后续多域扩展使用。"

        # 第九步：做执行前参数校验。
        validation_result = self.query_param_validator.validate(parsed)
        normalized_parsed = validation_result.get("normalized_parsed", parsed)
        validation_snapshot = deepcopy(validation_result)
        validation_snapshot.pop("normalized_parsed", None)
        parsed = normalized_parsed
        parsed["validation"] = validation_snapshot

        # 第十步：把命中的查询模板与 SQL 模板进行绑定，并做 SQL 模板白名单校验。
        sql_template_id = parsed.get("sql_template_id")
        whitelist_result = self.sql_whitelist.check(sql_template_id)
        sql_text = self.sql_template_registry.load_sql(sql_template_id)
        sql_preview = self.sql_renderer.render_preview(sql_text, parsed)
        execution_binding = {
            "execution_mode": parsed.get("mode", "aggregate"),
            "sql_template": self.sql_template_registry.describe(sql_template_id),
            "sql_whitelist": whitelist_result,
            "sql_preview": sql_preview,
        }
        execution_binding_snapshot = deepcopy(execution_binding)
        parsed["execution_binding"] = execution_binding_snapshot

        # 第十一步：通过统一执行器执行查询。
        # 注意：V8 当前依然由 QueryService 执行真正查询，白名单主要用于执行治理和审计。
        try:
            query_result = self.query_executor.execute(parsed, trace_id=trace_id)
        except Exception as exc:
            # V9 增加异常兜底，避免自然语言入口因下游异常直接 500。
            query_result = {
                "query_type": parsed.get("mode", "aggregate"),
                "metric_type": parsed.get("metric_type"),
                "source_scope": parsed.get("source_scope"),
                "filters": self._build_result_filters(parsed),
                "total": 0,
                "items": [],
                "execution_mode": "error_fallback",
                "execution_error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                },
                "compatibility_notice": [
                    "当前查询在主执行链路中发生异常，系统已走 error_fallback 兜底返回。",
                    "请结合 execution_error、execution_audit 和服务日志排查问题。",
                ],
            }

        # 第十二步：对 detail 空结果做业务编号存在性探测。
        # 这一步只在“明细 + 空结果”时触发，用于把“编号不存在”和“过滤过严”区分开。
        probe_result = self._probe_detail_business_no(parsed=parsed, query_result=query_result)
        if probe_result is not None:
            query_result["business_no_probe"] = deepcopy(probe_result)

        # 第十三步：生成结果解释和无结果分析。
        result_explanation = self.result_explainer.build(
            question=payload.question,
            parsed=parsed,
            query_result=query_result,
        )
        no_result_analysis = self.no_result_analyzer.analyze(
            question=payload.question,
            parsed=parsed,
            query_result=query_result,
        )
        query_result["result_explanation"] = deepcopy(result_explanation)
        if no_result_analysis is not None:
            query_result["no_result_analysis"] = deepcopy(no_result_analysis)

        # 第十四步：补统一状态码和顶层 response_meta。
        # 这里把 V10 的状态标准化真正挂到主返回上，供前端稳定消费。
        status = self.query_response_standardizer.build_status(
            parsed=parsed,
            query_result=query_result,
            probe_result=probe_result,
        )
        query_result["status"] = deepcopy(status)
        response_meta = self.query_response_standardizer.build_response_meta(
            question=payload.question,
            parsed=parsed,
            query_result=query_result,
            status=status,
        )

        # 第十五步：生成执行审计摘要，并输出到日志。
        audit_payload = self.execution_audit_service.build_audit_payload(
            trace_id=trace_id,
            question=payload.question,
            parsed=parsed,
            validation_result=validation_result,
            whitelist_result=whitelist_result,
            execution_binding=execution_binding_snapshot,
            query_result=query_result,
        )
        parsed["execution_audit"] = deepcopy(audit_payload)
        self.execution_audit_service.log_summary(audit_payload)

        # 第十六步：把查询计划快照落库。
        # 使用统一结果数量提取逻辑，避免 aggregate 场景 result_count 被误判为 0。
        execution_summary = {
            "result_count": LogisticsResultCountHelper.extract_count(query_result),
            "route": query_result.get("route") if isinstance(query_result, dict) else None,
            "execution_mode": query_result.get("execution_mode") if isinstance(query_result, dict) else None,
            "sql_whitelist_allowed": whitelist_result.get("allowed"),
        }
        self.query_plan_store.save_plan(
            trace_id=trace_id,
            question=payload.question,
            parsed=parsed,
            execution_binding=execution_binding_snapshot,
            execution_summary=execution_summary,
            response_meta=response_meta,
            query_result=query_result,
        )

        return {
            "question": payload.question,
            "parsed": parsed,
            "query_result": query_result,
            "response_meta": response_meta,
        }


    @staticmethod
    def _build_result_filters(parsed: dict[str, Any]) -> dict[str, Any]:
        """从解析结果中抽取统一的 filters 结构。

        该方法主要用于异常兜底场景，保证前端和联调日志仍能拿到与正常查询一致的过滤条件快照。
        """
        return {
            "start_date": parsed.get("start_date"),
            "end_date": parsed.get("end_date"),
            "year_month_list": parsed.get("year_month_list") or [],
            "customer_name": parsed.get("customer_name"),
            "logistics_company_name": parsed.get("logistics_company_name"),
            "region_name": parsed.get("region_name"),
            "warehouse_name": parsed.get("warehouse_name"),
            "transport_mode": parsed.get("transport_mode"),
            "origin_place": parsed.get("origin_place"),
            "contract_no": parsed.get("contract_no"),
            "inquiry_no": parsed.get("inquiry_no"),
            "ship_instruction_no": parsed.get("ship_instruction_no"),
            "sap_order_no": parsed.get("sap_order_no"),
            "vehicle_no": parsed.get("vehicle_no"),
            "task_id": parsed.get("task_id"),
            "product_spec": parsed.get("product_spec"),
            "metric_type": parsed.get("metric_type"),
            "source_scope": parsed.get("source_scope"),
            "page": parsed.get("page"),
            "page_size": parsed.get("page_size"),
            "order_by": parsed.get("order_by"),
            "order_direction": parsed.get("order_direction"),
        }

    def _probe_detail_business_no(
        self,
        *,
        parsed: dict[str, Any],
        query_result: dict[str, Any],
    ) -> dict[str, Any] | None:
        """在 detail 空结果场景下探测业务编号是否真实存在。

        返回值说明：
        1. 若当前不是明细查询，直接返回 None；
        2. 若当前已有结果，不做额外探测；
        3. 若下游 QueryService 未实现探测方法，也直接返回 None；
        4. 探测成功时返回统一结构，供状态码和前端详情页复用。
        """
        if parsed.get("mode") != "detail":
            return None
        if LogisticsResultCountHelper.extract_count(query_result) > 0:
            return None

        probe_method = getattr(self.query_service, "probe_detail_business_no", None)
        if not callable(probe_method):
            return None

        for field_label, field_name in [
            ("合同编号", "contract_no"),
            ("询比价编号", "inquiry_no"),
            ("发货指令", "ship_instruction_no"),
            ("SAP 单号", "sap_order_no"),
            ("车牌号", "vehicle_no"),
            ("任务编号", "task_id"),
        ]:
            field_value = parsed.get(field_name)
            if not field_value:
                continue
            try:
                exists = bool(
                    probe_method(
                        field_name=field_name,
                        field_value=field_value,
                        source_scope=parsed.get("source_scope", "all"),
                    )
                )
            except Exception:
                return None
            return {
                "field_name": field_name,
                "field_label": field_label,
                "field_value": field_value,
                "exists": exists,
            }

        return None

    def _rule_parse(self, question: str) -> dict[str, Any]:
        compact_question = question.replace(" ", "")
        result: dict[str, Any] = {
            "mode": "aggregate",
            "metric_type": self._infer_metric(question),
            "source_scope": "all",
            "group_by": ["biz_month"],
            "order_direction": "desc",
            "limit": 100,
        }

        # 时间识别：优先月份，其次年份。
        months = self._extract_months(compact_question)
        years = self._extract_years(compact_question, months)
        is_compare = self._should_compare(compact_question, months, years)

        if months:
            normalized = [f"{y}-{int(m):02d}" for y, m in months]
            if is_compare and len(normalized) >= 2:
                result["mode"] = "compare"
                result["left"] = self._build_compare_side(normalized[0])
                result["right"] = self._build_compare_side(normalized[1])
            else:
                result["year_month_list"] = normalized
        elif years:
            normalized_years = [self._normalize_year_token(y) for y in years]
            if is_compare and len(normalized_years) >= 2:
                result["mode"] = "compare"
                result["left"] = self._build_compare_side_for_year(normalized_years[0])
                result["right"] = self._build_compare_side_for_year(normalized_years[1])
            else:
                year = normalized_years[0]
                result["start_date"] = f"{year}-01-01"
                result["end_date"] = f"{year}-12-31"

        # 明细意图识别：编号类字段或“明细/详情”优先走 detail。
        self._extract_exact_fields(compact_question, result)
        if self._should_detail(compact_question, result):
            result["mode"] = "detail"
            result["page"] = 1
            result["page_size"] = 20
            result["order_by"] = "biz_date"

        # group_by 识别：按业务问题集高频问法优先。
        result["group_by"] = self._infer_group_by(compact_question, default=result["group_by"])
        if result["mode"] == "compare":
            result["compare_dim"] = (
                result["group_by"][0] if result["group_by"] and result["group_by"][0] != "biz_month" else None
            )

        # 来源识别：显式关键字优先，其次按时间范围推断。
        result["source_scope"] = self._infer_source_scope(compact_question, result)

        # 维度槽位识别。
        region = self._extract_region(compact_question)
        if region:
            result["region_name"] = region
        transport_mode = self._extract_transport_mode(compact_question)
        if transport_mode:
            result["transport_mode"] = transport_mode

        # 排序语义：排名 / top / 前几，默认按指标倒序。
        if any(token in compact_question for token in ("排名", "排行", "top", "TOP", "前十", "前10")):
            result["order_by"] = result["metric_type"]
            result["order_direction"] = "desc"
            result["limit"] = 10
        return result

    @staticmethod
    def _normalize_year_token(year_token: str) -> str:
        return year_token if len(year_token) == 4 else f"20{year_token}"

    @classmethod
    def _extract_months(cls, question: str) -> list[tuple[str, str]]:
        normalized_question = question.replace("月份", "月")
        seen: set[str] = set()
        months: list[tuple[str, str]] = []
        for year_token, month_token in _MONTH_PATTERN.findall(normalized_question):
            year = cls._normalize_year_token(year_token)
            month_key = f"{year}-{int(month_token):02d}"
            if month_key in seen:
                continue
            seen.add(month_key)
            months.append((year, str(int(month_token))))
        return months

    @classmethod
    def _extract_years(cls, question: str, months: list[tuple[str, str]]) -> list[str]:
        month_years = {year for year, _ in months}
        years: list[str] = []
        seen: set[str] = set()
        for year_token in _YEAR_PATTERN.findall(question):
            year = cls._normalize_year_token(year_token)
            if year in month_years or year in seen:
                continue
            seen.add(year)
            years.append(year)
        return years

    @staticmethod
    def _should_compare(question: str, months: list[tuple[str, str]], years: list[str]) -> bool:
        token_count = len(months) if months else len(years)
        if token_count < 2:
            return False
        if any(keyword in question for keyword in _COMPARE_KEYWORDS):
            return True
        return "和" in question or "与" in question

    @staticmethod
    def _build_compare_side(month_key: str) -> dict[str, Any]:
        return {"label": month_key, "year_month_list": [month_key]}

    @staticmethod
    def _build_compare_side_for_year(year: str) -> dict[str, Any]:
        return {"label": year, "start_date": f"{year}-01-01", "end_date": f"{year}-12-31"}

    @staticmethod
    def _infer_metric(question: str) -> str:
        lowered = question.lower()
        for metric, keywords in _METRIC_KEYWORDS.items():
            if any(keyword.lower() in lowered for keyword in keywords):
                return metric
        return "shipment_watt"

    @staticmethod
    def _infer_group_by(question: str, default: list[str] | None = None) -> list[str]:
        for field, keywords in _GROUP_BY_KEYWORDS.items():
            if any(keyword in question for keyword in keywords):
                return [field]
        if "各" in question or "分别" in question:
            if "物流公司" in question or "承运商" in question:
                return ["logistics_company_name"]
            if "区域" in question:
                return ["region_name"]
        return default or ["biz_month"]

    @staticmethod
    def _should_detail(question: str, parsed: dict[str, Any]) -> bool:
        if any(keyword in question for keyword in _DETAIL_KEYWORDS):
            return True
        exact_hit_keys = {"contract_no", "inquiry_no", "ship_instruction_no", "sap_order_no", "vehicle_no", "task_id"}
        return any(parsed.get(key) for key in exact_hit_keys)

    @staticmethod
    def _extract_exact_fields(question: str, result: dict[str, Any]) -> None:
        for field, pattern in _FIELD_PATTERNS.items():
            match = pattern.search(question)
            if match:
                result[field] = match.group(1)

    @staticmethod
    def _extract_region(question: str) -> str | None:
        for region in _REGION_KEYWORDS:
            if region in question:
                return region
        return None

    @staticmethod
    def _extract_transport_mode(question: str) -> str | None:
        for canonical, aliases in _TRANSPORT_MODE_CANONICAL.items():
            if any(alias in question for alias in aliases):
                return canonical
        return None

    def _infer_source_scope(self, question: str, parsed: dict[str, Any]) -> str:
        if "历史" in question:
            return "hist"
        if "系统" in question or "正式" in question:
            return "sys"

        month_list = parsed.get("year_month_list") or []
        years: list[int] = []
        if month_list:
            years = [int(item.split("-")[0]) for item in month_list]
        elif parsed.get("left") and parsed.get("right"):
            for side in (parsed["left"], parsed["right"]):
                if side.get("year_month_list"):
                    years.extend(int(item.split("-")[0]) for item in side["year_month_list"])
                elif side.get("start_date"):
                    years.append(int(side["start_date"][:4]))
        elif parsed.get("start_date"):
            years.append(int(parsed["start_date"][:4]))

        if not years:
            return "all"
        if all(year <= 2025 for year in years):
            return "hist"
        if all(year >= 2026 for year in years):
            return "sys"
        return "all"
