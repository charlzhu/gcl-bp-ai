from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.domains.business_analysis.services.inventory_sales_production.semantic_catalog import (
    InventorySalesProductionCatalogDimension,
    InventorySalesProductionCatalogMetric,
    InventorySalesProductionCatalogTable,
    InventorySalesProductionSemanticCatalog,
    InventorySalesProductionSemanticCatalogLoader,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.sql_plan import (
    REQUIRED_ISP_SEMANTIC_CATALOG_VERSION,
    InventorySalesProductionSqlPlan,
    InventorySalesProductionSqlPlanValidationResult,
    InventorySalesProductionSqlPlanValidator,
)

M6_ISP_LIVE_PROVIDER_GATE_VERSION = "business_analysis_inventory_sales_production_m6_live_provider_gate.v1"
DEFAULT_M6_RECORDS_FILENAME = "m6-live-provider-shadow-records.jsonl"
DEFAULT_M6_REPORT_FILENAME = "m6-live-provider-shadow-report.json"

_SECRET_VALUE_RE = re.compile(r"sk-[A-Za-z0-9_-]{6,}|Bearer\s+[^\s,'\"}]+", re.IGNORECASE)
_SECRET_KEY_RE = re.compile(
    r"(?i)\b(api[_-]?key|password|passwd|token|access[_-]?token|refresh[_-]?token|secret|authorization)\b"
)
_URL_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s,'\")]+")
_HOST_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{2,5})?\b")
_INTERNAL_TOKEN_RE = re.compile(
    r"dwd_ba_isp_[a-z0-9_]+|dim_ba_isp_[a-z0-9_]+|ods_ba_isp_[a-z0-9_]+|sys_query_log|raw_payload|"
    r"select\s+\*|\bfrom\b|\bwhere\b|bailian|deepseek|oracle|mysql://",
    re.IGNORECASE,
)


class InventorySalesProductionM6CatalogRecallDocument(BaseModel):
    """产销存 M6 catalog recall 文档。

    参数：
        catalog_id: 受控目录引用 ID，例如 metric:shipment_volume。
        catalog_version: 目录版本，必须与当前产销存 Semantic Catalog 一致。
        domain/sub_domain: 业务域边界，固定为经营分析/产销存。
        doc_type: 文档类型，区分 table、metric、dimension、rule。
        title: 面向召回的业务标题。
        retrieval_text: 可送入 embedding/召回的业务化文本，不包含 SQL 或密钥。
        keywords: 同义词和关键词。
        required_catalog_refs: 由本地 canonical catalog 推导出的依赖引用。
        metadata: 仅保留公开安全的辅助元数据。
    返回：
        Pydantic 文档对象。
    """

    model_config = ConfigDict(extra="forbid")

    catalog_id: str
    catalog_version: str = REQUIRED_ISP_SEMANTIC_CATALOG_VERSION
    domain: str = "business_analysis"
    sub_domain: str = "inventory_sales_production"
    doc_type: Literal["table", "metric", "dimension", "rule"]
    title: str
    retrieval_text: str
    keywords: list[str] = Field(default_factory=list)
    required_catalog_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class InventorySalesProductionM6CatalogRecallHit(BaseModel):
    """产销存 M6 catalog recall 命中。

    参数：document 为命中的目录文档；score 为本地轻量召回分；source 表示召回来源。
    返回：召回命中对象。
    """

    model_config = ConfigDict(extra="forbid")

    document: InventorySalesProductionM6CatalogRecallDocument
    score: float = 0.0
    source: str = "local_catalog"


class InventorySalesProductionM6CatalogRecallResult(BaseModel):
    """产销存 M6 catalog recall 结果。

    参数：status 表示召回是否成功；hits 为命中文档；error 为公开安全错误码。
    返回：召回结果对象。
    """

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "empty", "error"] = "ok"
    hits: list[InventorySalesProductionM6CatalogRecallHit] = Field(default_factory=list)
    error: str | None = None

    def catalog_refs(self) -> list[str]:
        """返回命中文档及其本地依赖引用，供 SQLPlan candidate 归一化使用。"""

        refs: list[str] = []
        for hit in self.hits:
            refs.append(hit.document.catalog_id)
            refs.extend(hit.document.required_catalog_refs)
        return _dedupe(refs)


class InventorySalesProductionM6CatalogRecallDocumentBuilder:
    """从产销存本地 canonical Semantic Catalog 构建 M6 召回文档。

    业务逻辑：
        M6 reindex/retrieval 只能读取智能助手中间库的本地目录定义；不得把外部源、ODS、
        日志表、SQL 片段或 provider debug 信息写入召回文档。
    """

    def __init__(self, catalog: InventorySalesProductionSemanticCatalog | None = None) -> None:
        """初始化构建器。

        参数：catalog 可选注入，用于单测或审查污染目录；为空时加载默认目录。
        返回：无。
        """

        self.catalog = catalog or InventorySalesProductionSemanticCatalogLoader().load()

    def build_documents(self) -> list[InventorySalesProductionM6CatalogRecallDocument]:
        """构建产销存 M6 catalog recall 文档列表。"""

        documents: list[InventorySalesProductionM6CatalogRecallDocument] = []
        documents.extend(self._table_document(table) for table in self.catalog.allowed_tables())
        documents.extend(self._metric_document(metric) for metric in self.catalog.metrics if metric.support_status == "supported")
        documents.extend(
            self._dimension_document(dimension)
            for dimension in self.catalog.dimensions
            if dimension.support_status == "supported"
        )
        documents.extend(self._business_rule_documents())
        return documents

    def _table_document(
        self,
        table: InventorySalesProductionCatalogTable,
    ) -> InventorySalesProductionM6CatalogRecallDocument:
        """把中间库白名单表转换为召回文档。"""

        column_names = [column.business_name or column.name for column in table.columns]
        return InventorySalesProductionM6CatalogRecallDocument(
            catalog_id=f"table:{table.table_name}",
            doc_type="table",
            title=table.display_name,
            retrieval_text="；".join(
                [
                    table.display_name,
                    "智能助手中间库产销存月度事实和指标目录",
                    f"粒度：{table.grain or '标准业务粒度'}",
                    "字段：" + "、".join(column_names),
                ]
            ),
            keywords=[table.display_name, "中间库", "产销存", "经营分析"],
            metadata={"source_system": "middle_db", "allowed_read": bool(table.allowed_read)},
        )

    def _metric_document(
        self,
        metric: InventorySalesProductionCatalogMetric,
    ) -> InventorySalesProductionM6CatalogRecallDocument:
        """把标准指标转换为召回文档，并补齐本地声明的依赖引用。"""

        dependencies = [f"table:{metric.table}", "dimension:business_year"]
        if "business_month" in metric.source_columns:
            dependencies.append("dimension:business_month")
        if metric.metric_id == "shipment_volume":
            dependencies.append("rule:sales_defaults_to_shipment_volume")
        if metric.aggregation == "period_end":
            dependencies.append("rule:inventory_period_end_snapshot")
        if metric.metric_id == "production_budget_achievement_rate":
            dependencies.append("rule:budget_achievement_recalculated")
        dependencies.extend(f"metric:{metric_id}" for metric_id in metric.depends_on_metrics)
        text_parts = [
            metric.display_name,
            "、".join(metric.aliases),
            f"聚合口径：{metric.aggregation or '标准聚合'}",
            f"单位：{metric.unit or '按指标标准单位'}",
            metric.business_note or "",
        ]
        return InventorySalesProductionM6CatalogRecallDocument(
            catalog_id=f"metric:{metric.metric_id}",
            doc_type="metric",
            title=metric.display_name,
            retrieval_text="；".join(part for part in text_parts if part),
            keywords=_dedupe([metric.metric_id, metric.display_name, *metric.aliases]),
            required_catalog_refs=_dedupe(dependencies),
            metadata={
                "aggregation": metric.aggregation,
                "unit": metric.unit,
                "default_for_sales": metric.default_for_sales,
            },
        )

    def _dimension_document(
        self,
        dimension: InventorySalesProductionCatalogDimension,
    ) -> InventorySalesProductionM6CatalogRecallDocument:
        """把标准维度转换为召回文档。"""

        return InventorySalesProductionM6CatalogRecallDocument(
            catalog_id=f"dimension:{dimension.dimension_id}",
            doc_type="dimension",
            title=dimension.display_name,
            retrieval_text="；".join(
                part
                for part in [
                    dimension.display_name,
                    "、".join(dimension.aliases),
                    dimension.business_note or "产销存可分组或过滤维度",
                ]
                if part
            ),
            keywords=_dedupe([dimension.dimension_id, dimension.display_name, *dimension.aliases]),
            required_catalog_refs=[f"table:{dimension.table}"],
            metadata={"column_role": "dimension"},
        )

    @staticmethod
    def _business_rule_documents() -> list[InventorySalesProductionM6CatalogRecallDocument]:
        """返回 M6 必须可召回的业务规则文档。"""

        return [
            InventorySalesProductionM6CatalogRecallDocument(
                catalog_id="rule:policy_current_year_use_published_months_only",
                doc_type="rule",
                title="当前年度仅使用已发布月份",
                retrieval_text="今年、当前年、最近数据只按已发布月份统计，未来月份不能当作实际值。",
                keywords=["今年", "当前年", "已发布月份", "未来月份"],
                required_catalog_refs=["dimension:business_year", "dimension:business_month"],
            ),
            InventorySalesProductionM6CatalogRecallDocument(
                catalog_id="rule:sales_defaults_to_shipment_volume",
                doc_type="rule",
                title="销量默认等同发货量",
                retrieval_text="销量、销售量默认按发货量或实际发出量口径回答，除非用户显式要求开票销量。",
                keywords=["销量", "销售量", "发货量", "实际发出量"],
                required_catalog_refs=["metric:shipment_volume"],
            ),
            InventorySalesProductionM6CatalogRecallDocument(
                catalog_id="rule:inventory_period_end_snapshot",
                doc_type="rule",
                title="库存使用期末快照",
                retrieval_text="库存、存货、寄存仓等期末类指标默认使用 period_end 快照口径，不做跨月求和。",
                keywords=["库存", "存货", "寄存仓", "期末"],
                required_catalog_refs=["metric:ending_inventory_volume"],
            ),
            InventorySalesProductionM6CatalogRecallDocument(
                catalog_id="rule:budget_achievement_recalculated",
                doc_type="rule",
                title="预算达成率确定性重算",
                retrieval_text="产量预算达成率由实际产量和预算目标确定性计算，不能由语言模型直接计算业务事实。",
                keywords=["预算达成率", "目标", "实际产量"],
                required_catalog_refs=["metric:production_actual_including_oem", "metric:production_budget"],
            ),
        ]


class InventorySalesProductionM6CatalogRecallService:
    """产销存 M6 本地 recall 服务。

    业务逻辑：
        当前类提供确定性本地召回和依赖扩展，后续真实 embedding/Milvus/rerank 只应替换检索实现，
        不能绕过本地 canonical catalog 依赖边界。
    """

    def __init__(self, documents: list[InventorySalesProductionM6CatalogRecallDocument]) -> None:
        """初始化召回服务。参数 documents 为已构建的本地目录文档。"""

        self.documents = list(documents)
        self.by_id = {document.catalog_id: document for document in self.documents}

    @classmethod
    def from_documents(
        cls,
        documents: list[InventorySalesProductionM6CatalogRecallDocument],
    ) -> "InventorySalesProductionM6CatalogRecallService":
        """从文档列表创建召回服务，便于测试注入。"""

        return cls(documents)

    def recall(self, question: str, *, top_k: int = 12) -> InventorySalesProductionM6CatalogRecallResult:
        """按问题文本执行轻量本地召回，并补充文档依赖。"""

        normalized_question = _normalize_text(question)
        hits: list[InventorySalesProductionM6CatalogRecallHit] = []
        for document in self.documents:
            score = self._score_document(document, normalized_question)
            if score > 0:
                hits.append(InventorySalesProductionM6CatalogRecallHit(document=document, score=score))
        hits.sort(key=lambda item: item.score, reverse=True)
        expanded = self._expand_dependencies(hits[:top_k])
        if not expanded:
            return InventorySalesProductionM6CatalogRecallResult(status="empty", hits=[])
        return InventorySalesProductionM6CatalogRecallResult(status="ok", hits=expanded[:top_k])

    @staticmethod
    def _score_document(document: InventorySalesProductionM6CatalogRecallDocument, normalized_question: str) -> float:
        """根据关键词和召回文本给本地文档打分。"""

        score = 0.0
        haystack = _normalize_text(" ".join([document.title, document.retrieval_text, *document.keywords]))
        for keyword in document.keywords:
            normalized_keyword = _normalize_text(keyword)
            if normalized_keyword and normalized_keyword in normalized_question:
                score += 3.0
            elif normalized_keyword and normalized_keyword in haystack and normalized_keyword[:2] in normalized_question:
                score += 1.0
        if document.doc_type == "rule":
            if document.catalog_id == "rule:policy_current_year_use_published_months_only" and any(
                token in normalized_question for token in ("今年", "当前", "最近")
            ):
                score += 0.5
            elif document.catalog_id == "rule:sales_defaults_to_shipment_volume" and any(
                token in normalized_question for token in ("销量", "销售量", "发货量")
            ):
                score += 0.5
            elif document.catalog_id == "rule:inventory_period_end_snapshot" and any(
                token in normalized_question for token in ("库存", "存货", "寄存")
            ):
                score += 0.5
            elif document.catalog_id == "rule:budget_achievement_recalculated" and "预算达成" in normalized_question:
                score += 0.5
        return score

    def _expand_dependencies(
        self,
        hits: list[InventorySalesProductionM6CatalogRecallHit],
    ) -> list[InventorySalesProductionM6CatalogRecallHit]:
        """只从本地目录声明扩展依赖，禁止由 LLM 输出发明依赖。"""

        by_id: dict[str, InventorySalesProductionM6CatalogRecallHit] = {hit.document.catalog_id: hit for hit in hits}
        for hit in list(hits):
            for catalog_id in hit.document.required_catalog_refs:
                document = self.by_id.get(catalog_id)
                if document is not None and catalog_id not in by_id:
                    by_id[catalog_id] = InventorySalesProductionM6CatalogRecallHit(
                        document=document,
                        score=max(hit.score - 0.1, 0.1),
                        source="local_dependency",
                    )
        return list(by_id.values())


class InventorySalesProductionM6ProviderGateResult(BaseModel):
    """单项 provider smoke 门禁结果。"""

    model_config = ConfigDict(extra="forbid")

    name: Literal["embedding", "vector_store", "rerank", "llm"]
    status: Literal["PASS", "FAIL", "BLOCKED"]
    reason: str | None = None


class InventorySalesProductionM6ProviderSmokeResult(BaseModel):
    """M6 provider smoke 汇总结果。"""

    model_config = ConfigDict(extra="forbid")

    version: str = M6_ISP_LIVE_PROVIDER_GATE_VERSION
    gates: list[InventorySalesProductionM6ProviderGateResult] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        """全部 provider 门禁为 PASS 时返回 True。"""

        return bool(self.gates) and all(gate.status == "PASS" for gate in self.gates)


class InventorySalesProductionM6ProviderSmokeRunner:
    """M6 provider smoke 运行器。

    业务逻辑：
        provider smoke 必须拆分 embedding、vector_store、rerank、LLM 四类检查；公开输出仅保留
        PASS/FAIL/BLOCKED 和脱敏后的稳定原因，不输出模型名、集合名、密钥或连接细节。
    """

    def __init__(
        self,
        *,
        embedding_probe: Callable[[], Any],
        vector_store_probe: Callable[[], Any],
        rerank_probe: Callable[[], Any],
        llm_probe: Callable[[], Any],
    ) -> None:
        """初始化 runner，四个 probe 用于单测或真实 provider 检查。"""

        self._probes: list[tuple[Literal["embedding", "vector_store", "rerank", "llm"], Callable[[], Any]]] = [
            ("embedding", embedding_probe),
            ("vector_store", vector_store_probe),
            ("rerank", rerank_probe),
            ("llm", llm_probe),
        ]

    def run(self) -> InventorySalesProductionM6ProviderSmokeResult:
        """执行 provider smoke 并返回分项结果。"""

        gates: list[InventorySalesProductionM6ProviderGateResult] = []
        for name, probe in self._probes:
            try:
                probe_result = probe()
                gates.append(_provider_gate_from_probe_result(name, probe_result))
            except Exception as exc:  # noqa: BLE001 - provider smoke 必须把外部异常转成脱敏门禁结果。
                gates.append(
                    InventorySalesProductionM6ProviderGateResult(
                        name=name,
                        status="BLOCKED",
                        reason=_safe_public_reason(str(exc)),
                    )
                )
        return InventorySalesProductionM6ProviderSmokeResult(gates=gates)


class InventorySalesProductionM6FakeSqlPlanProvider:
    """测试用 LLM SQLPlan provider。

    业务逻辑：
        该类模拟“真实 provider 已被调用并返回候选 JSON”的边界；生产路径可以用同样接口接入
        百炼/OpenAI 兼容 provider，但候选仍必须通过本地 validator。
    """

    def __init__(self, candidate_payload: dict[str, Any]) -> None:
        """初始化 fake provider。参数 candidate_payload 为模拟 LLM 返回的候选结构。"""

        self.candidate_payload = deepcopy(candidate_payload)
        self.live_called = False

    def generate(self, *, question: str, recall_result: InventorySalesProductionM6CatalogRecallResult) -> dict[str, Any]:
        """返回候选 payload，并记录 provider 已调用。"""

        self.live_called = True
        return deepcopy(self.candidate_payload)


class InventorySalesProductionM6OpenAiSqlPlanProvider:
    """产销存 M6 真实 LLM SQLPlan provider。

    业务逻辑：
        该 provider 只负责把用户问题和本轮召回 catalog 上下文发给项目配置的 OpenAI 兼容
        LLM，并要求返回严格 JSON candidate；它不生成 SQL、不查询数据库，后续仍必须经过
        normalize + SQLPlan validator fail-closed。
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        """初始化真实 provider。

        参数：base_url/api_key/model 可测试注入；为空时读取项目 settings。
        返回：无。
        """

        from backend.app.core.config import settings

        self.base_url = settings.llm_base_url if base_url is None else base_url
        self.api_key = settings.llm_api_key if api_key is None else api_key
        self.model = settings.llm_model if model is None else model
        self.timeout_seconds = timeout_seconds
        self.live_called = False

    def is_available(self) -> bool:
        """判断真实 LLM provider 是否已具备最小配置。"""

        return bool(str(self.base_url or "").strip() and str(self.api_key or "").strip() and str(self.model or "").strip())

    def generate(self, *, question: str, recall_result: InventorySalesProductionM6CatalogRecallResult) -> dict[str, Any]:
        """调用真实 LLM 生成 candidate JSON。

        参数：question 为用户问题；recall_result 为本轮召回上下文。
        返回：provider 返回并解析后的 candidate dict。
        """

        if not self.is_available():
            raise RuntimeError("provider_blocked::missing_config::llm_base_url,llm_api_key,llm_model")
        try:
            from openai import OpenAI

            from backend.app.domains.logistics.services.nl2sql.catalog_retrieval import (
                _build_provider_openai_client_kwargs,
            )

            self.live_called = True
            client = OpenAI(
                **_build_provider_openai_client_kwargs(
                    base_url=self.base_url,
                    api_key=self.api_key,
                    timeout_seconds=self.timeout_seconds,
                    max_retries=0,
                )
            )
            completion = client.chat.completions.create(
                model=self.model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=self._build_messages(question=question, recall_result=recall_result),
            )
            content = completion.choices[0].message.content or "{}"
            payload = json.loads(content)
            if not isinstance(payload, dict):
                raise ValueError("provider_candidate_not_object")
            return payload
        except Exception as exc:  # noqa: BLE001 - provider 异常交由 runner/summary 脱敏并 fail-closed。
            raise RuntimeError(_safe_public_reason(str(exc))) from exc

    def _build_messages(
        self,
        *,
        question: str,
        recall_result: InventorySalesProductionM6CatalogRecallResult,
    ) -> list[dict[str, str]]:
        """构造真实 provider 提示词。"""

        context = [
            {
                "catalog_id": hit.document.catalog_id,
                "doc_type": hit.document.doc_type,
                "title": hit.document.title,
                "retrieval_text": hit.document.retrieval_text,
                "required_catalog_refs": hit.document.required_catalog_refs,
            }
            for hit in recall_result.hits[:12]
        ]
        # 给真实 provider 一个可直接仿照的最小合格 candidate；
        # 这样既能提高 live gate 稳定性，又不放宽后续 validator 的白名单校验。
        schema_example = {
            "schema_version": "business_analysis_inventory_sales_production_sqlplan_candidate.v1",
            "domain": "business_analysis",
            "sub_domain": "inventory_sales_production",
            "strategy": "sql_direct",
            "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION,
            "catalog_refs": [
                {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION},
                {"catalog_id": "metric:shipment_volume", "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION},
                {"catalog_id": "dimension:business_year", "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION},
            ],
            "plan": {
                "query_key": "ba_isp_metric_summary",
                "tables": ["dwd_ba_isp_monthly_fact"],
                "metrics": ["shipment_volume"],
                "dimensions": [],
                "filters": [{"dimension": "business_year", "operator": "=", "values": [2025]}],
                "group_by": [],
                "order_by": [],
                "business_rules": [],
                "business_flags": {},
                "period_type": "year",
                "year": 2025,
                "calculation_policy": "sum",
                "limit": 200,
            },
            "clarification_questions": [],
            "unsupported_reason": None,
            "confidence": 0.8,
        }
        return [
            {
                "role": "system",
                "content": (
                    "你是经营分析产销存 SQLPlan 候选生成器。只返回严格 JSON 对象，不要返回 SQL。"
                    "必须使用 business_analysis_inventory_sales_production_sqlplan_candidate.v1 合同。"
                    "不确定时 strategy 只能返回 clarify 或 unsupported。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question,
                        "catalog_context": context,
                        "required_schema": "business_analysis_inventory_sales_production_sqlplan_candidate.v1",
                        "strict_output_contract": schema_example,
                        "strict_rules": [
                            "只能返回一个 JSON 对象，不能返回 markdown、解释、reasoning 或 SQL。",
                            "strategy 必须是 sql_direct、clarify、unsupported 之一；可答问题使用 sql_direct，不能使用 sql。",
                            "plan.tables、plan.metrics、plan.dimensions、plan.group_by 必须是字符串数组，不能是对象数组。",
                            "plan.filters 必须是数组；每项只允许 dimension/operator/values/source。",
                            "plan.tables 使用表名，如 dwd_ba_isp_monthly_fact；catalog_refs 才使用 table: 前缀。",
                            "年度汇总问题使用 query_key=ba_isp_metric_summary、period_type=year、year=业务年份。",
                            "销量/销售量默认映射 metric:shipment_volume，calculation_policy 使用 sum。",
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ]


class InventorySalesProductionM6SqlPlanGenerationResult(BaseModel):
    """M6 SQLPlan 生成与校验结果。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    provider_live_called: bool = False
    candidate_payload: dict[str, Any] | None = None
    validation: InventorySalesProductionSqlPlanValidationResult
    normalized_plan: InventorySalesProductionSqlPlan | None = None
    error_codes: list[str] = Field(default_factory=list)


class InventorySalesProductionM6SqlPlanGenerator:
    """产销存 M6 LLM SQLPlan 生成器。

    业务逻辑：
        1. 先执行 catalog recall；
        2. 调用 provider 取得 JSON candidate；
        3. 只做字段名/聚合策略的窄归一化和本地 catalog 依赖补齐；
        4. 立即交给现有 M5 SQLPlan validator fail-closed 校验；
        5. 全程不接受、生成或执行 SQL 文本。
    """

    def __init__(
        self,
        *,
        recall_service: InventorySalesProductionM6CatalogRecallService,
        llm_provider: Any,
        validator: InventorySalesProductionSqlPlanValidator | None = None,
    ) -> None:
        """初始化生成器。参数 recall_service/llm_provider/validator 均可注入，便于 TDD。"""

        self.recall_service = recall_service
        self.llm_provider = llm_provider
        self.validator = validator or InventorySalesProductionSqlPlanValidator()

    def generate(self, question: str) -> InventorySalesProductionM6SqlPlanGenerationResult:
        """生成并校验一个 SQLPlan candidate。"""

        recall_result = self.recall_service.recall(question)
        if recall_result.status != "ok":
            validation = InventorySalesProductionSqlPlanValidationResult(
                ok=False,
                normalized_plan=None,
                errors=[f"m6_catalog_recall_not_ok::{recall_result.status}"],
            )
            return InventorySalesProductionM6SqlPlanGenerationResult(
                provider_live_called=False,
                validation=validation,
                error_codes=validation.error_codes,
            )
        candidate = self.llm_provider.generate(question=question, recall_result=recall_result)
        provider_live_called = bool(getattr(self.llm_provider, "live_called", True))
        normalized_candidate = normalize_m6_sqlplan_candidate_payload(candidate, recall_result=recall_result)
        validation = self.validator.validate(normalized_candidate)
        return InventorySalesProductionM6SqlPlanGenerationResult(
            provider_live_called=provider_live_called,
            candidate_payload=normalized_candidate,
            validation=validation,
            normalized_plan=validation.normalized_plan,
            error_codes=validation.error_codes,
        )


class InventorySalesProductionM6FakeSqlPlanGenerator:
    """测试用 M6 SQLPlan generator。

    业务逻辑：用于验证 live shadow runner 的后半段，不连接 LLM，也不生成 SQL。
    """

    def __init__(self, metric_id: str) -> None:
        """初始化 fake generator。参数 metric_id 为要模拟成功的标准指标。"""

        self.metric_id = metric_id
        self.validator = InventorySalesProductionSqlPlanValidator()

    @classmethod
    def success_for_metric(cls, metric_id: str) -> "InventorySalesProductionM6FakeSqlPlanGenerator":
        """创建一个返回校验通过 SQLPlan 的 fake generator。"""

        return cls(metric_id)

    def generate(self, question: str) -> InventorySalesProductionM6SqlPlanGenerationResult:
        """返回通过 validator 的受控 SQLPlan 生成结果。"""

        candidate = _build_success_candidate(self.metric_id)
        validation = self.validator.validate(candidate)
        return InventorySalesProductionM6SqlPlanGenerationResult(
            provider_live_called=True,
            candidate_payload=candidate,
            validation=validation,
            normalized_plan=validation.normalized_plan,
            error_codes=validation.error_codes,
        )


class InventorySalesProductionM6LiveShadowSample(BaseModel):
    """M6 live shadow 样例声明。"""

    model_config = ConfigDict(extra="forbid")

    sample_id: str
    question: str
    expected_status: Literal["matched", "empty", "validation_failed", "shadow_error"] = "matched"


class InventorySalesProductionM6FakeReadonlyShadowExecutor:
    """测试用只读中间库 shadow executor。

    业务逻辑：模拟只读中间库查询结果，用于验证 runner 确实在 SQLPlan 校验通过后才执行 shadow。
    """

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        """初始化 fake executor。参数 rows 为模拟返回行。"""

        self.rows = list(rows)
        self.executed = False

    def execute(self, plan: InventorySalesProductionSqlPlan) -> list[dict[str, Any]]:
        """执行只读 shadow；测试实现仅返回注入行。"""

        self.executed = True
        return list(self.rows)


class InventorySalesProductionM6ReadonlyMiddleDbShadowExecutor:
    """真实只读中间库 shadow executor。

    业务逻辑：
        将校验通过的 M6 SQLPlan 映射为现有产销存 QueryPlan，并复用后端确定性查询执行器。
        该 executor 不写正式 QA、不写 query log、不接触 SAP/Oracle，只读智能助手中间库。
    """

    def __init__(self, session_factory: Callable[[], Any] | None = None) -> None:
        """初始化 executor。参数 session_factory 用于测试或 CLI 注入数据库会话工厂。"""

        self.session_factory = session_factory
        # M6 live shadow gate 只做验收期影子验证，不接管正式 QA 链路。
        self.shadow_only = True
        # 显式暴露“不写正式问答”的合同，便于 review/static test 防止后续误接主链路。
        self.formal_qa_executed = False
        # 显式暴露“不写 query log”的合同，shadow 只写脱敏验收材料。
        self.write_query_log = False

    def execute(self, plan: InventorySalesProductionSqlPlan) -> list[dict[str, Any]]:
        """执行只读中间库 shadow 查询。

        参数：plan 为已通过 validator 的 SQLPlan。
        返回：业务结果行列表；非 success 状态返回空列表，由 gate 记为 empty。
        """

        from backend.app.db.session import SessionLocal
        from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
            InventorySalesProductionPeriodSpec,
            InventorySalesProductionQueryPlan,
        )
        from backend.app.domains.business_analysis.services.inventory_sales_production.query_executor import (
            InventorySalesProductionQueryExecutor,
        )

        db = (self.session_factory or SessionLocal)()
        try:
            query_plan = InventorySalesProductionQueryPlan(
                query_key=plan.query_key,
                metrics=list(plan.metrics),
                dimensions=list(plan.dimensions or plan.group_by),
                filters=self._filters_to_query_plan_dict(plan),
                period=InventorySalesProductionPeriodSpec(
                    period_type="year" if plan.period_type == "month_range" else plan.period_type,
                    year=plan.year,
                    month=plan.month,
                    quarter=plan.quarter,
                    start_month=plan.start_month,
                    end_month=plan.end_month,
                ),
                calculation_policy=plan.calculation_policy,
                display_preference="shadow_gate",
            )
            result = InventorySalesProductionQueryExecutor(db).execute(query_plan)
            if result.status != "success":
                return []
            return [row.model_dump(mode="json") for row in result.rows]
        finally:
            close = getattr(db, "close", None)
            if callable(close):
                close()

    @staticmethod
    def _filters_to_query_plan_dict(plan: InventorySalesProductionSqlPlan) -> dict[str, Any]:
        """把 SQLPlan 过滤列表映射为 QueryPlan 白名单过滤字典。"""

        filters: dict[str, Any] = dict(plan.business_flags or {})
        for item in plan.filters:
            if item.dimension in {"business_year", "business_month"}:
                continue
            if item.operator in {"=", "like"}:
                filters[item.dimension] = item.values[0] if item.values else None
            elif item.operator == "in":
                filters[item.dimension] = list(item.values)
        return filters


class InventorySalesProductionM6LiveShadowGateRun(BaseModel):
    """M6 live shadow gate 运行结果。"""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    report: dict[str, Any]
    records_path: Path
    report_path: Path


class InventorySalesProductionM6LiveShadowGateRunner:
    """M6 live-provider SQLPlan shadow gate runner。

    业务逻辑：
        串联 provider candidate、SQLPlan validator 和只读中间库 shadow；runner 只写验收材料，
        不接管正式 QA，不向用户可见接口写入内部 SQLPlan/debug 信息。
    """

    def __init__(self, *, sqlplan_generator: Any, readonly_shadow_executor: Any) -> None:
        """初始化 runner。参数 sqlplan_generator 负责候选生成，readonly_shadow_executor 负责只读 shadow。"""

        self.sqlplan_generator = sqlplan_generator
        self.readonly_shadow_executor = readonly_shadow_executor

    def run(
        self,
        *,
        samples: list[InventorySalesProductionM6LiveShadowSample],
        artifact_dir: Path,
    ) -> InventorySalesProductionM6LiveShadowGateRun:
        """执行 M6 live shadow gate 并写入 JSONL/JSON 验收材料。"""

        artifact_dir.mkdir(parents=True, exist_ok=True)
        records_path = artifact_dir / DEFAULT_M6_RECORDS_FILENAME
        report_path = artifact_dir / DEFAULT_M6_REPORT_FILENAME
        records: list[dict[str, Any]] = []
        validation_pass_count = 0
        readonly_executed = False
        provider_live_called = False
        mismatch_count = 0
        success_count = 0

        for sample in samples:
            record = self._run_one(sample)
            records.append(record)
            provider_live_called = provider_live_called or bool(record.get("provider_live_called"))
            validation_pass_count += 1 if record.get("sqlplan_validation_ok") else 0
            readonly_executed = readonly_executed or bool(record.get("readonly_middle_db_shadow_executed"))
            success_count += 1 if record.get("actual_status") == "matched" else 0
            mismatch_count += 1 if record.get("actual_status") != sample.expected_status else 0

        report = {
            "version": M6_ISP_LIVE_PROVIDER_GATE_VERSION,
            "total": len(samples),
            "success_count": success_count,
            "provider_live_called": provider_live_called,
            "sqlplan_validation_pass_count": validation_pass_count,
            "readonly_middle_db_shadow_executed": readonly_executed,
            "formal_qa_executed": False,
            "expected_status_mismatch_count": mismatch_count,
        }
        records_path.write_text("\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in records) + "\n", encoding="utf-8")
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return InventorySalesProductionM6LiveShadowGateRun(report=report, records_path=records_path, report_path=report_path)

    def _run_one(self, sample: InventorySalesProductionM6LiveShadowSample) -> dict[str, Any]:
        """执行单条样例；异常按 shadow_error fail-closed。"""

        provider_live_called = False
        try:
            generation = self.sqlplan_generator.generate(sample.question)
            provider_live_called = bool(generation.provider_live_called)
            if not generation.validation.ok or generation.normalized_plan is None:
                return {
                    "sample_id": sample.sample_id,
                    "actual_status": "validation_failed",
                    "provider_live_called": provider_live_called,
                    "sqlplan_validation_ok": False,
                    "error_codes": render_safe_m6_live_shadow_summary({"error_codes": generation.error_codes}).get("error_codes", []),
                    "readonly_middle_db_shadow_executed": False,
                }
            rows = self.readonly_shadow_executor.execute(generation.normalized_plan)
            return {
                "sample_id": sample.sample_id,
                "actual_status": "matched" if rows else "empty",
                "provider_live_called": provider_live_called,
                "sqlplan_validation_ok": True,
                "row_count": len(rows),
                "readonly_middle_db_shadow_executed": True,
            }
        except Exception as exc:  # noqa: BLE001 - shadow gate 必须失败关闭并输出公开安全原因。
            return {
                "sample_id": sample.sample_id,
                "actual_status": "shadow_error",
                "provider_live_called": provider_live_called,
                "sqlplan_validation_ok": False,
                "error_message": _safe_public_reason(str(exc)),
                "readonly_middle_db_shadow_executed": False,
            }


def normalize_m6_sqlplan_candidate_payload(
    candidate_payload: dict[str, Any],
    *,
    recall_result: InventorySalesProductionM6CatalogRecallResult,
) -> dict[str, Any]:
    """归一化 provider SQLPlan candidate 并补齐本地 catalog 依赖。

    参数：
        candidate_payload: provider 返回的 JSON candidate。
        recall_result: 当前问题的 catalog recall 结果。
    返回：
        可交给现有 M5 validator 的 candidate dict。
    """

    candidate = deepcopy(candidate_payload)
    candidate.setdefault("catalog_version", REQUIRED_ISP_SEMANTIC_CATALOG_VERSION)
    plan = candidate.setdefault("plan", {})
    if isinstance(plan, dict):
        plan.pop("safety", None)
        if plan.get("calculation_policy") == "flow_sum":
            plan["calculation_policy"] = "sum"
        for item in plan.get("filters", []) or []:
            if isinstance(item, dict) and "field" in item and "dimension" not in item:
                item["dimension"] = item.pop("field")
            if isinstance(item, dict) and "op" in item and "operator" not in item:
                item["operator"] = item.pop("op")
        plan.setdefault("group_by", [])
        plan.setdefault("order_by", [])
        plan.setdefault("business_rules", [])
        plan.setdefault("business_flags", {})
        plan.setdefault("limit", 200)
    candidate["catalog_refs"] = _normalized_catalog_refs(candidate, recall_result=recall_result)
    return candidate


def render_safe_m6_provider_smoke_summary_json(result: InventorySalesProductionM6ProviderSmokeResult) -> str:
    """渲染 provider smoke 公开安全 JSON 摘要。"""

    payload = {
        "version": result.version,
        "ok": result.ok,
        "gates": [
            {
                "name": gate.name,
                "status": gate.status,
                **({"reason": _safe_public_reason(gate.reason)} if gate.reason else {}),
            }
            for gate in result.gates
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def render_safe_m6_live_shadow_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """渲染 M6 live shadow 公开安全摘要。

    业务逻辑：公开摘要可能进入 outbox、历史记录或前端可读 metadata，因此必须删除 SQLPlan、
    表字段名、provider 名称、连接串和密钥样式片段。
    """

    safe: dict[str, Any] = {}
    if "version" in summary:
        safe["version"] = M6_ISP_LIVE_PROVIDER_GATE_VERSION
    if "total" in summary:
        safe["total"] = int(summary.get("total") or 0)
    if "expected_status_mismatch_count" in summary:
        safe["expected_status_mismatch_count"] = int(summary.get("expected_status_mismatch_count") or 0)
    if "error_codes" in summary:
        safe["error_codes"] = [_safe_error_code(code) for code in summary.get("error_codes") or []]
    if "error_message" in summary:
        safe["error_message"] = "shadow_error_redacted"
    if "candidate_sql_gate_reason" in summary:
        safe["candidate_sql_gate_reason"] = _safe_error_code(summary.get("candidate_sql_gate_reason"))
    if not safe:
        safe["error_message"] = "shadow_error_redacted"
    return safe


def _normalized_catalog_refs(
    candidate: dict[str, Any],
    *,
    recall_result: InventorySalesProductionM6CatalogRecallResult,
) -> list[dict[str, str]]:
    """只基于召回上下文补齐 catalog_ref，禁止 provider plan 反向发明引用。

    参数：
        candidate: provider 返回的 candidate。
        recall_result: 当前问题的召回结果。
    返回：
        catalog_ref 列表；仅包含本轮召回命中及其 canonical 依赖中的 table/metric/dimension。
    业务逻辑：
        LLM 可以在 plan 中写指标/维度，但不能因为写了这些名称就自动获得 catalog_ref。
        否则 provider 只要猜到内部 ID 就可能绕过召回边界。这里采用 fail-closed：未召回的
        plan 引用不补 ref，交由 validator 报 missing catalog_ref。
    """

    allowed_refs = {
        ref
        for ref in recall_result.catalog_refs()
        if ref.startswith(("table:", "metric:", "dimension:"))
    }
    refs: list[str] = []
    for item in candidate.get("catalog_refs") or []:
        if isinstance(item, dict):
            catalog_id = str(item.get("catalog_id") or "").strip()
        elif isinstance(item, str):
            catalog_id = item.strip()
        else:
            continue
        if catalog_id in allowed_refs:
            refs.append(catalog_id)
    refs.extend(sorted(allowed_refs))
    return [
        {"catalog_id": catalog_id, "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION}
        for catalog_id in _dedupe(refs)
    ]


def _build_success_candidate(metric_id: str) -> dict[str, Any]:
    """构造测试用、可通过 validator 的产销存 SQLPlan candidate。"""

    return {
        "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION,
        "catalog_refs": [
            {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION},
            {"catalog_id": f"metric:{metric_id}", "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION},
            {"catalog_id": "dimension:business_year", "catalog_version": REQUIRED_ISP_SEMANTIC_CATALOG_VERSION},
        ],
        "plan": {
            "query_key": "ba_isp_metric_summary",
            "tables": ["dwd_ba_isp_monthly_fact"],
            "metrics": [metric_id],
            "dimensions": [],
            "filters": [{"dimension": "business_year", "operator": "=", "values": [2025]}],
            "group_by": [],
            "order_by": [],
            "business_rules": [],
            "business_flags": {},
            "period_type": "year",
            "year": 2025,
            "calculation_policy": "sum",
            "limit": 200,
        },
    }


def _safe_error_code(value: Any) -> str:
    """把内部错误码映射到公开安全枚举。"""

    text = str(value or "")
    if _SECRET_KEY_RE.search(text) or _SECRET_VALUE_RE.search(text) or _URL_RE.search(text) or _HOST_RE.search(text):
        return "shadow_error_redacted"
    if _INTERNAL_TOKEN_RE.search(text):
        return "shadow_error_redacted"
    prefix = text.split("::", 1)[0].strip().lower()
    allowed = {
        "recall_failed",
        "validation_failed",
        "shadow_error",
        "provider_blocked",
        "m6_catalog_recall_not_ok",
    }
    return prefix if prefix in allowed else "redacted"


def _safe_public_reason(value: Any) -> str:
    """把 provider/shadow 异常原因映射为公开安全枚举。

    参数：value 为外部 provider、向量库、重排、LLM 或 shadow 执行返回的原始原因。
    返回：仅返回稳定公开枚举；未知异常默认返回 shadow_error_redacted。

    重要业务逻辑：provider 异常文本不可控，可能包含模型名、内部网关、trace、debug 或连接上下文。
    因此这里不能“替换已知敏感词后回显剩余文本”，必须 fail-closed。
    """

    text = str(value or "").strip()
    if not text:
        return "shadow_error_redacted"
    if _SECRET_VALUE_RE.search(text) or _URL_RE.search(text) or _HOST_RE.search(text):
        return "shadow_error_redacted"
    if _SECRET_KEY_RE.search(text) or _INTERNAL_TOKEN_RE.search(text):
        return "shadow_error_redacted"

    public_reason = text.split("::", 1)[0].strip().lower()
    allowed_public_reasons = {
        "missing_config",
        "provider_blocked",
        "empty_response",
        "empty_embedding_vector",
        "empty_rerank_scores",
        "provider_candidate_not_object",
        "candidate_parse_failed",
        "probe_status_missing",
    }
    if public_reason in allowed_public_reasons:
        return public_reason
    return "shadow_error_redacted"


def _provider_gate_from_probe_result(
    name: Literal["embedding", "vector_store", "rerank", "llm"],
    value: Any,
) -> InventorySalesProductionM6ProviderGateResult:
    """把 probe 返回值转换为门禁结果，保留 BLOCKED/FAIL 语义。

    参数：
        name: provider 分项名称。
        value: probe 返回值；可为 {status, reason} 字典或普通 truthy/falsy 值。
    返回：
        单项门禁结果。BLOCKED 代表外部环境/配置阻塞，FAIL 代表调用完成但结果不合格。
    """

    if isinstance(value, dict):
        status_text = str(value.get("status") or "").upper()
        if not status_text:
            return InventorySalesProductionM6ProviderGateResult(
                name=name,
                status="FAIL",
                reason="probe_status_missing",
            )
        if status_text == "OK":
            status_text = "PASS"
        if status_text in {"PASS", "FAIL", "BLOCKED"}:
            reason = _safe_public_reason(value.get("reason")) if value.get("reason") else None
            status: Literal["PASS", "FAIL", "BLOCKED"] = "BLOCKED"
            if status_text == "PASS":
                status = "PASS"
            elif status_text == "FAIL":
                status = "FAIL"
            return InventorySalesProductionM6ProviderGateResult(name=name, status=status, reason=reason)
    status = "PASS" if _probe_result_is_pass(value) else "FAIL"
    return InventorySalesProductionM6ProviderGateResult(name=name, status=status)


def _probe_result_is_pass(value: Any) -> bool:
    """判断 probe 返回是否表示通过；空值或显式 FAIL/BLOCKED 不算通过。"""

    if isinstance(value, dict):
        status = str(value.get("status") or "").upper()
        if status in {"FAIL", "BLOCKED"}:
            return False
        if status == "PASS":
            return True
        return bool(value)
    return bool(value)


def _normalize_text(value: Any) -> str:
    """统一文本，便于本地召回评分。"""

    return "".join(str(value or "").lower().split())


def _dedupe(values: list[str] | Any) -> list[str]:
    """保持顺序去重，并丢弃空字符串。"""

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result
