"""
gcl-bp-ai 统一问数 — DomainQaService 抽象层。

解决三个域独立 service 类互不兼容的问题。
所有业务域（物流/计划BOM/经营分析/物控物管）统一实现此接口。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DomainQaService(ABC):
    """统一领域问数服务抽象。

    每个业务域必须实现:
    - domain_id: 域标识符
    - execute_sql: 执行 SQL 返回业务化结果
    - get_catalog_tables: 获取该域的表/字段定义（供 LLM 生成 SQL）
    - get_domain_rules: 获取该域的业务口径规则（供 prompt 注入）
    """

    @property
    @abstractmethod
    def domain_id(self) -> str:
        """返回业务域 ID: logistics / plan_bom / business_analysis / material_management。"""
        ...

    @abstractmethod
    def execute_sql(self, sql: str, question: str) -> dict[str, Any]:
        """执行 SQL，返回业务化结果。

        Args:
            sql: 经受控校验的可执行 SQL。
            question: 用户原始问题（供结果清洗时参考）。

        Returns:
            {
                "answer_summary": str,        # 业务化摘要
                "result_table": {             # 结果表格
                    "columns": [{"name": str, "type": str}],
                    "rows": [dict],
                },
                "warnings": [str],            # 数据质量/边界说明
                "row_count": int,
            }
        """
        ...

    @abstractmethod
    def get_catalog_tables(self) -> list[dict[str, Any]]:
        """获取该域所有可用表的 schema。

        Returns:
            [
                {
                    "name": "table_name",
                    "description": "表说明",
                    "columns": [
                        {"name": "col", "type": "varchar", "description": "字段说明"},
                    ],
                },
            ]
        """
        ...

    def get_domain_rules(self) -> dict[str, Any]:
        """获取该域的业务口径映射规则（可选重写）。

        Returns:
            {
                "person_to_field": {"刘娟": "委托人"},
                "alias_to_field": {"经营计划": "扩充部门"},
                "default_time_range": {"field": "biz_year", "value": "current_year"},
            }
        """
        return {}


# ================================================================
# 域注册表
# ================================================================

_DOMAIN_REGISTRY: dict[str, DomainQaService] = {}


def _empty_execution_result(answer_summary: str, warnings: list[str] | None = None) -> dict[str, Any]:
    """构造统一空结果。

    参数：
        answer_summary: 用户可见摘要。
        warnings: 业务边界或错误提醒。
    返回：
        DomainQaService.execute_sql 约定的统一 dict 结构。
    """

    return {
        "answer_summary": answer_summary,
        "result_table": {"columns": [], "rows": []},
        "warnings": list(warnings or []),
        "row_count": 0,
    }


def _normalize_columns(columns: Any, rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    """统一不同领域返回的列定义。

    参数：
        columns: 原始列定义，可能是字符串列表、字典列表或空值。
        rows: 原始结果行，用于在列定义缺失时从首行推断列名。
    返回：
        统一为 [{"name": 字段名, "type": 字段类型}] 的列定义。
    """

    raw_columns = list(columns or [])
    if not raw_columns and rows:
        raw_columns = list(rows[0].keys())

    normalized: list[dict[str, str]] = []
    for column in raw_columns:
        if isinstance(column, dict):
            name = str(column.get("name") or column.get("key") or column.get("label") or "")
            column_type = str(column.get("type") or "string")
        else:
            name = str(column)
            column_type = "string"
        if name:
            normalized.append({"name": name, "type": column_type})
    return normalized


def _normalize_rows(rows: Any) -> list[dict[str, Any]]:
    """统一不同领域返回的行数据。

    参数：
        rows: 原始行数据，通常为 dict 列表，也可能是 Pydantic 对象列表。
    返回：
        dict 列表，便于前端表格统一消费。
    """

    normalized: list[dict[str, Any]] = []
    for row in list(rows or []):
        if isinstance(row, dict):
            normalized.append(row)
        elif hasattr(row, "model_dump"):
            normalized.append(row.model_dump(mode="json"))
        else:
            normalized.append(dict(row))
    return normalized


def _normalize_domain_response(response: Any) -> dict[str, Any]:
    """把各业务域 QA 响应归一为 DomainQaService 返回格式。

    参数：
        response: Logistics/BOM/经营分析问答服务返回对象或 dict。
    返回：
        统一包含 answer_summary、result_table、warnings、row_count 的 dict。
    """

    if isinstance(response, dict):
        answer_summary = str(response.get("answer_summary") or "")
        result_table = response.get("result_table") or {}
        warnings = list(response.get("warnings") or [])
    else:
        answer_summary = str(getattr(response, "answer_summary", "") or "")
        result_table = getattr(response, "result_table", None) or {}
        warnings = list(getattr(response, "warnings", []) or [])

    if isinstance(result_table, dict):
        rows = _normalize_rows(result_table.get("rows") or [])
        columns = _normalize_columns(result_table.get("columns") or [], rows)
        row_count = int(result_table.get("row_count") or len(rows))
    else:
        rows = _normalize_rows(getattr(result_table, "rows", []) or [])
        columns = _normalize_columns(getattr(result_table, "columns", []) or [], rows)
        row_count = int(getattr(result_table, "row_count", len(rows)) or len(rows))

    return {
        "answer_summary": answer_summary,
        "result_table": {"columns": columns, "rows": rows},
        "warnings": warnings,
        "row_count": row_count,
    }


def register_domain_service(service: DomainQaService) -> None:
    """注册领域服务到全局 registry。"""
    _DOMAIN_REGISTRY[service.domain_id] = service


def get_domain_service(domain_id: str) -> DomainQaService | None:
    """按域 ID 获取已注册的领域服务。"""
    return _DOMAIN_REGISTRY.get(domain_id)


def list_registered_domains() -> list[str]:
    """列出所有已注册的业务域。"""
    return list(_DOMAIN_REGISTRY.keys())


# ================================================================
# 物流域适配器
# ================================================================

class LogisticsDomainService(DomainQaService):
    """物流域服务适配器（包装 LogisticsDataQaService）。

    提供统一接口的同时保留原有复杂 QA 链路（QueryPlanningV2 + NL2SQL shadow）。
    """

    domain_id = "logistics"

    def __init__(self, db_session: Any = None):
        self._db_session = db_session

    def execute_sql(self, sql: str, question: str) -> dict[str, Any]:
        """执行 SQL 并返回业务化结果。"""
        if self._db_session is None:
            return _empty_execution_result("物流数据库连接未就绪，SQL 未实际执行。", ["DB_NOT_READY"])

        try:
            from backend.app.domains.logistics.services.data_qa_service import (
                LogisticsDataQaService,
            )
            from sqlalchemy import text

            service = LogisticsDataQaService(db=self._db_session)
            result = service.db.execute(text(sql))
            rows = _normalize_rows(result.mappings().fetchall())
            columns = _normalize_columns([], rows)
            return {
                "answer_summary": f"物流查询完成，共返回 {len(rows)} 条结果。",
                "result_table": {"columns": columns, "rows": rows},
                "warnings": [],
                "row_count": len(rows),
            }
        except Exception as exc:
            return _empty_execution_result(f"查询失败: {exc}", [str(exc)])

    def get_catalog_tables(self) -> list[dict[str, Any]]:
        """从物流 catalog YAML 加载表 schema。"""
        try:
            from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
                LogisticsSemanticCatalogLoader,
            )
            loader = LogisticsSemanticCatalogLoader()
            catalog = loader.load()
            return [t.model_dump(mode="json") if hasattr(t, "model_dump") else dict(t) for t in catalog.tables]
        except Exception:
            return []

    def get_domain_rules(self) -> dict[str, Any]:
        return {
            "person_to_field": {"刘娟": "委托人"},
            "alias_to_field": {"经营计划": "扩充部门", "出货": "发货"},
            "default_time_range": {"field": "biz_year", "value": "2023-2026"},
        }


# ================================================================
# 计划 BOM 域适配器
# ================================================================

class PlanBomDomainService(DomainQaService):
    """计划 BOM 域服务适配器（包装 PlanBomQaService）。"""

    domain_id = "plan_bom"

    def __init__(self, db_session: Any = None):
        self._db_session = db_session

    def execute_sql(self, sql: str, question: str) -> dict[str, Any]:
        if self._db_session is None:
            return _empty_execution_result("计划 BOM 数据库连接未就绪，问题未实际执行。", ["DB_NOT_READY"])

        try:
            from backend.app.domains.logistics.repositories.query_repository import (
                LogisticsQueryRepository,
            )
            from backend.app.domains.plan_bom.repositories.query_repository import (
                PlanBomQueryRepository,
            )
            from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
            from backend.app.domains.plan_bom.services.answer_presentation_service import (
                PlanBomAnswerPresentationService,
            )
            from backend.app.domains.plan_bom.services.nlu_center_service import (
                PlanBomNluCenterService,
            )
            from backend.app.domains.plan_bom.services.power_config_resolver_service import (
                PlanBomPowerConfigResolverService,
            )
            from backend.app.domains.plan_bom.services.power_prediction_engine import (
                PowerPredictionEngine,
            )
            from backend.app.domains.plan_bom.services.power_recommendation_service import (
                PowerRecommendationService,
            )
            from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService

            repository = PlanBomQueryRepository(self._db_session)
            power_engine = PowerPredictionEngine(self._db_session)
            service = PlanBomQaService(
                repository=repository,
                query_service=PlanBomQueryService(repository=repository),
                nlu_service=PlanBomNluCenterService(repository=repository),
                presentation_service=PlanBomAnswerPresentationService(),
                power_config_resolver=PlanBomPowerConfigResolverService(self._db_session, repository=repository),
                power_prediction_engine=power_engine,
                power_recommendation_service=PowerRecommendationService(self._db_session, engine=power_engine),
                query_log_repository=LogisticsQueryRepository(),
            )
            response = service.ask(question)
            return _normalize_domain_response(response)
        except Exception as exc:
            return _empty_execution_result(f"查询失败: {exc}", [str(exc)])

    def get_catalog_tables(self) -> list[dict[str, Any]]:
        try:
            from backend.app.domains.logistics.services.nl2sql.domain_registry import (
                PlanBomCatalogLoader,
            )
            loader = PlanBomCatalogLoader()
            catalog = loader.load()
            return [t.model_dump(mode="json") if hasattr(t, "model_dump") else dict(t) for t in catalog.tables]
        except Exception:
            return []


# ================================================================
# 经营分析域适配器
# ================================================================

class BusinessAnalysisDomainService(DomainQaService):
    """经营分析域服务适配器（包装 InventorySalesProductionQaService）。"""

    domain_id = "business_analysis"

    def __init__(self, db_session: Any = None):
        self._db_session = db_session

    def execute_sql(self, sql: str, question: str) -> dict[str, Any]:
        if self._db_session is None:
            return _empty_execution_result("经营分析数据库连接未就绪，问题未实际执行。", ["DB_NOT_READY"])

        try:
            from backend.app.domains.business_analysis.services.inventory_sales_production.qa_service import (
                InventorySalesProductionQaService,
            )

            service = InventorySalesProductionQaService(db=self._db_session)
            response = service.ask(question)
            return _normalize_domain_response(response)
        except Exception as exc:
            return _empty_execution_result(f"查询失败: {exc}", [str(exc)])

    def get_catalog_tables(self) -> list[dict[str, Any]]:
        try:
            from backend.app.domains.logistics.services.nl2sql.domain_registry import (
                BusinessAnalysisCatalogLoader,
            )
            loader = BusinessAnalysisCatalogLoader()
            catalog = loader.load()
            return [t.model_dump(mode="json") if hasattr(t, "model_dump") else dict(t) for t in catalog.tables]
        except Exception:
            return []


# ================================================================
# 物控物管域适配器（M2 骨架）
# ================================================================

class MaterialMgmtDomainService(DomainQaService):
    """物控物管域服务适配器（M2 阶段：库存/出入库 MVP）。

    当前为骨架实现，M2 完成后端中间库同步后启用完整链路。
    """

    domain_id = "material_management"

    def __init__(self, db_session: Any = None):
        self._db_session = db_session

    def execute_sql(self, sql: str, question: str) -> dict[str, Any]:
        if self._db_session is None:
            return {"answer_summary": "物控物管数据库连接未就绪（M2 进行中）。", "result_table": {"columns": [], "rows": []}, "warnings": ["DB_NOT_READY"], "row_count": 0}

        from sqlalchemy import text
        try:
            result = self._db_session.execute(text(sql))
            rows = [dict(r) for r in result.mappings().fetchall()]
            return {
                "answer_summary": f"查询完成，共 {len(rows)} 条。",
                "result_table": {"columns": [{"name": k, "type": "string"} for k in rows[0].keys()] if rows else [], "rows": rows[:100]},
                "warnings": [],
                "row_count": len(rows),
            }
        except Exception as exc:
            return {"answer_summary": f"查询失败: {exc}", "result_table": {"columns": [], "rows": []}, "warnings": [str(exc)], "row_count": 0}

    def get_catalog_tables(self) -> list[dict[str, Any]]:
        """M2 首批白名单视图: V_HF_SAP_INOUT_DAILY, V_SAP_HFFN_CRKLSZ。"""
        return [
            {
                "name": "V_HF_SAP_INOUT_DAILY", "description": "SAP 出入库日表（M2 首批）",
                "columns": [
                    {"name": "id", "type": "integer", "description": "主键"},
                    {"name": "biz_date", "type": "date", "description": "业务日期"},
                    {"name": "material_code", "type": "varchar", "description": "物料编码"},
                    {"name": "in_qty", "type": "decimal", "description": "入库数量"},
                    {"name": "out_qty", "type": "decimal", "description": "出库数量"},
                ],
            },
            {
                "name": "V_SAP_HFFN_CRKLSZ", "description": "SAP 物料库存表（M2 首批）",
                "columns": [
                    {"name": "id", "type": "integer", "description": "主键"},
                    {"name": "material_code", "type": "varchar", "description": "物料编码"},
                    {"name": "stocked_qty", "type": "decimal", "description": "库存数量"},
                    {"name": "warehouse_name", "type": "varchar", "description": "仓库名称"},
                ],
            },
        ]
