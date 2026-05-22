"""
gcl-bp-ai 统一问数 E2E + SSE 集成测试。

验证:
1. builder_v2 全节点连通性
2. 各域路由正确性
3. SQL 验证→校正循环
4. SSE 流式事件格式
"""

from __future__ import annotations

import json
import asyncio
import importlib
import sys
from typing import Any, TypedDict

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, '/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/hermes-cf4c35ae/backend')
sys.path.insert(0, '/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai/.worktrees/hermes-cf4c35ae')

from backend.app.domains.business_qa_graph.builder_v2 import (
    build_unified_graph,
    _route_after_domain,
    _route_after_validate_sql,
)
from backend.app.domains.business_qa_graph.schemas.state import (
    BusinessQaGraphState,
    build_business_qa_initial_state,
)
from backend.app.domains.business_qa_graph.schemas.request import BusinessQaGraphRequest


class SQLiteE2EGraphState(BusinessQaGraphState, total=False):
    """SQLite E2E 专用 state schema。

    参数：
        继承 BusinessQaGraphState，并补充 builder_v2 ZG 节点会写入的中间字段。
    返回：
        供测试内 StateGraph 编译使用的 TypedDict。
    业务逻辑：
        生产 schema 当前未声明 ZG 中间字段；测试通过扩展 schema 验证
        `_db_session`、`table_infos`、`sql` 能沿真实节点链路传递。
    """

    _db_session: Any
    keywords: list[str]
    retrieved_columns: list[dict[str, Any]]
    retrieved_values: list[dict[str, Any]]
    retrieved_metrics: list[dict[str, Any]]
    table_infos: list[dict[str, Any]]
    metric_infos: list[dict[str, Any]]
    date_info: dict[str, Any]
    db_info: dict[str, Any]
    sql: str
    error: str | None


@pytest.fixture
def sqlite_session() -> Session:
    """创建 SQLite 临时库并写入 E2E 测试数据。

    参数：
        无。
    返回：
        已建好物流和计划 BOM 测试表的 SQLAlchemy Session。
    业务逻辑：
        只在内存库中构造最小中间库数据，验证 Graph 最终会真实执行 SQL。
    """
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as session:
        session.execute(text("""
            CREATE TABLE logistics_shipment (
                id INTEGER PRIMARY KEY,
                biz_year INTEGER NOT NULL,
                base_name TEXT NOT NULL,
                shipment_mw REAL NOT NULL,
                carrier_name TEXT NOT NULL
            )
        """))
        session.execute(text("""
            CREATE TABLE plan_bom_detail (
                id INTEGER PRIMARY KEY,
                biz_year INTEGER NOT NULL,
                project_name TEXT NOT NULL,
                material_name TEXT NOT NULL,
                supplier_name TEXT NOT NULL
            )
        """))
        session.execute(
            text("""
                INSERT INTO logistics_shipment
                    (id, biz_year, base_name, shipment_mw, carrier_name)
                VALUES
                    (1, 2026, '合肥', 12.5, '测试承运商'),
                    (2, 2026, '合肥', 7.5, '测试承运商二')
            """)
        )
        session.execute(
            text("""
                INSERT INTO plan_bom_detail
                    (id, biz_year, project_name, material_name, supplier_name)
                VALUES
                    (1, 2026, '测试项目', '玻璃', '测试供应商')
            """)
        )
        session.commit()
        yield session


def _install_sqlite_e2e_nodes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """安装仅用于 SQLite E2E 的确定性节点桩。

    参数：
        monkeypatch: pytest monkeypatch 夹具。
    返回：
        无。
    业务逻辑：
        保留 builder_v2 的真实 13 节点编排，只替换会访问 LLM/Milvus
        的召回与过滤节点；SQL 生成、验证和执行仍使用真实节点。
    """
    from backend.app.domains.business_qa_graph import builder_v2
    generate_sql_module = importlib.import_module(
        "backend.app.domains.business_qa_graph.nodes.generate_sql_node"
    )

    def recall_column_for_sqlite(state: dict[str, Any]) -> dict[str, Any]:
        """返回物流测试表字段，驱动后续 merge 生成 table_infos。"""
        return {
            "retrieved_columns": [
                {
                    "catalog_id": "column:logistics_shipment.biz_year",
                    "name": "biz_year",
                    "type": "integer",
                    "role": "partition_key",
                    "examples": [2026],
                    "description": "业务年份",
                    "alias": ["年份"],
                    "source_table": "logistics_shipment",
                },
                {
                    "catalog_id": "column:logistics_shipment.base_name",
                    "name": "base_name",
                    "type": "varchar",
                    "role": "dimension",
                    "examples": ["合肥"],
                    "description": "基地名称",
                    "alias": ["基地"],
                    "source_table": "logistics_shipment",
                },
                {
                    "catalog_id": "column:logistics_shipment.shipment_mw",
                    "name": "shipment_mw",
                    "type": "decimal",
                    "role": "metric",
                    "examples": [],
                    "description": "发运量 MW",
                    "alias": ["发运量"],
                    "source_table": "logistics_shipment",
                },
            ]
        }

    def recall_metric_for_sqlite(state: dict[str, Any]) -> dict[str, Any]:
        """返回发运量指标，补齐 Graph 指标分支。"""
        return {
            "retrieved_metrics": [
                {
                    "catalog_id": "metric:shipment_mw",
                    "name": "发运量",
                    "description": "按业务年份查询发运量明细。",
                    "relevant_columns": [],
                    "alias": ["发运量", "MW"],
                    "unit": "MW",
                }
            ]
        }

    def recall_value_for_sqlite(state: dict[str, Any]) -> dict[str, Any]:
        """返回合肥维度值，验证三路召回合并不依赖外部检索。"""
        return {
            "retrieved_values": [
                {
                    "value_id": "logistics_shipment.base_name:合肥",
                    "column_id": "column:logistics_shipment.base_name",
                    "column_name": "base_name",
                    "value": "合肥",
                    "table_name": "logistics_shipment",
                }
            ]
        }

    def passthrough_table_filter(state: dict[str, Any]) -> dict[str, Any]:
        """过滤节点测试桩：只保留 SQLite 测试表实际存在的字段。"""
        return {
            "table_infos": [
                {
                    "name": "logistics_shipment",
                    "role": "fact",
                    "description": "SQLite E2E 物流发运测试表",
                    "columns": [
                        {"name": "biz_year", "type": "integer", "role": "partition_key"},
                        {"name": "base_name", "type": "varchar", "role": "dimension"},
                        {"name": "shipment_mw", "type": "decimal", "role": "metric"},
                        {"name": "id", "type": "integer", "role": "primary_key"},
                    ],
                }
            ]
        }

    def passthrough_metric_filter(state: dict[str, Any]) -> dict[str, Any]:
        """过滤节点测试桩：保留 merge 后生成的指标上下文。"""
        return {"metric_infos": state.get("metric_infos", [])}

    class NoLlmSettings:
        """让 generate_sql_node 走关键词兜底，避免 E2E 依赖外部 LLM。"""

        llm_api_key = ""
        llm_base_url = ""
        llm_model = ""

    monkeypatch.setattr(builder_v2, "BusinessQaGraphState", SQLiteE2EGraphState)
    monkeypatch.setattr(builder_v2, "recall_column_node", recall_column_for_sqlite)
    monkeypatch.setattr(builder_v2, "recall_metric_node", recall_metric_for_sqlite)
    monkeypatch.setattr(builder_v2, "recall_value_node", recall_value_for_sqlite)
    monkeypatch.setattr(builder_v2, "filter_table_node", passthrough_table_filter)
    monkeypatch.setattr(builder_v2, "filter_metric_node", passthrough_metric_filter)
    monkeypatch.setattr(generate_sql_module, "get_settings", lambda: NoLlmSettings())


async def _collect_sse_events(service: Any, question: str) -> list[str]:
    """消费 SSE async generator 并返回原始事件文本。"""
    return [event async for event in service.query(question)]


class TestGraphStructure:
    """验证 Graph 节点和边结构。"""

    def test_graph_compiles(self):
        graph = build_unified_graph()
        assert graph is not None

    def test_all_nodes_present(self):
        graph = build_unified_graph()
        nodes = list(graph.nodes.keys())
        required = [
            "receive", "domain_route", "extract_keywords",
            "recall_column", "recall_value", "recall_metric",
            "merge_retrieved_info", "filter_table", "filter_metric",
            "add_extra_context",
            "generate_sql", "validate_sql", "correct_sql", "execute_sql",
        ]
        for n in required:
            assert n in nodes, f"Missing node: {n}"

    def test_graph_invoke_no_crash(self):
        """端到端：无 LLM/DB 环境时 Graph 应正常降级而非崩溃。"""
        graph = build_unified_graph()
        request = BusinessQaGraphRequest(question="2024年合肥发运量")
        state = build_business_qa_initial_state(request)
        result = graph.invoke(state)
        assert result is not None
        assert "status" in result or "domain" in result


class TestSQLiteUnifiedGraphE2E:
    """验证 SQLite 临时库下的 builder_v2 全链路。"""

    def test_unified_graph_executes_against_sqlite_session(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sqlite_session: Session,
    ) -> None:
        """端到端：13 节点 Graph 应能在 SQLite 上完成真实 SQL 执行。"""
        _install_sqlite_e2e_nodes(monkeypatch)

        graph = build_unified_graph()
        request = BusinessQaGraphRequest(
            question="2026年合肥基地发运量是多少？",
            domain_hint="logistics",
            trace_id="zg-2-sqlite-e2e",
        )
        state = build_business_qa_initial_state(request)
        state["_db_session"] = sqlite_session
        state["understanding_status"] = "PLANNED"
        state["shadow_plan_raw"] = {
            "intent": "direct_retrieval",
            "slots": {"year": 2026, "base_name": "合肥"},
        }

        final_state = graph.invoke(state)

        assert final_state["execution_status"] == "EXECUTED"
        assert final_state["status"] == "EXECUTED"
        result_table = final_state["execution_result"]["result_table"]
        assert [column["name"] for column in result_table["columns"]] == [
            "biz_year",
            "base_name",
            "shipment_mw",
            "id",
        ]
        assert len(result_table["rows"]) == 2
        assert {row["base_name"] for row in result_table["rows"]} == {"合肥"}
        assert sum(row["shipment_mw"] for row in result_table["rows"]) == pytest.approx(20.0)


class TestDomainRouting:
    """验证领域路由逻辑。"""

    def test_known_domain_routes_to_extract(self):
        state = {"domain": "logistics", "status": "DOMAIN_ROUTED"}
        assert _route_after_domain(state) == "extract_keywords"

    def test_unknown_domain_routes_to_clarify(self):
        state = {"domain": "unknown", "status": ""}
        assert _route_after_domain(state) == "clarify"

    def test_clarify_status_routes_to_clarify(self):
        state = {"domain": "logistics", "status": "CLARIFY"}
        assert _route_after_domain(state) == "clarify"


class TestValidateSqlLoop:
    """验证 SQL 验证→校正循环（≤3次）。"""

    def test_no_error_routes_to_execute(self):
        state = {"error": None}
        assert _route_after_validate_sql(state) == "execute_sql"

    def test_error_with_retry_routes_to_correct(self):
        state = {"error": "syntax error", "_sql_retry_count": 0}
        assert _route_after_validate_sql(state) == "correct_sql"
        assert state["_sql_retry_count"] == 1

    def test_exceed_max_retry_routes_to_error(self):
        state = {"error": "syntax error", "_sql_retry_count": 3}
        assert _route_after_validate_sql(state) == "error_handler"

    def test_retry_count_increments(self):
        state = {"error": "err", "_sql_retry_count": 2}
        _route_after_validate_sql(state)
        assert state["_sql_retry_count"] == 3


class TestDomainServiceRegistry:
    """验证统一域服务注册表。"""

    def test_import_domain_qa_service(self):
        from backend.app.domains.business_qa_graph.services.domain_qa_service import (
            DomainQaService,
            LogisticsDomainService,
            PlanBomDomainService,
            BusinessAnalysisDomainService,
            MaterialMgmtDomainService,
        )
        assert LogisticsDomainService.domain_id == "logistics"
        assert PlanBomDomainService.domain_id == "plan_bom"
        assert BusinessAnalysisDomainService.domain_id == "business_analysis"
        assert MaterialMgmtDomainService.domain_id == "material_management"

    def test_register_and_get(self):
        from backend.app.domains.business_qa_graph.services.domain_qa_service import (
            register_domain_service,
            get_domain_service,
            list_registered_domains,
            LogisticsDomainService,
        )
        svc = LogisticsDomainService()
        register_domain_service(svc)
        assert get_domain_service("logistics") is svc
        assert "logistics" in list_registered_domains()


class TestZgQueryServiceSse:
    """验证 ZgQueryService 的 SSE 流式事件格式。"""

    def test_query_returns_valid_sse_events(self) -> None:
        """SSE 事件必须使用 data 前缀、双换行结尾，并包含可解析 JSON。"""
        from backend.app.domains.business_qa_graph.services.zg_query_service import ZgQueryService

        class FakeSseGraph:
            """提供 astream_events 的测试图，避免调用外部 LLM/DB。"""

            async def astream_events(self, initial_state: dict[str, Any], version: str):
                """按 LangGraph 事件格式输出进度和最终结果。"""
                assert initial_state["question"] == "查询合肥发运量"
                assert version == "v2"
                yield {"event": "on_chain_start", "name": "extract_keywords"}
                yield {"event": "on_chain_end", "name": "extract_keywords"}
                yield {
                    "event": "on_chain_end",
                    "name": "LangGraph",
                    "data": {
                        "output": {
                            "execution_result": {
                                "answer_summary": "查询完成，共返回 1 条结果。",
                                "result_table": {
                                    "columns": [{"name": "base_name", "type": "string"}],
                                    "rows": [{"base_name": "合肥"}],
                                },
                                "warnings": [],
                            }
                        }
                    },
                }

        service = ZgQueryService(graph=FakeSseGraph())

        raw_events = asyncio.run(_collect_sse_events(service, "查询合肥发运量"))

        assert len(raw_events) == 3
        assert all(event.startswith("data: ") for event in raw_events)
        assert all(event.endswith("\n\n") for event in raw_events)

        payloads = [
            json.loads(event.removeprefix("data: ").strip())
            for event in raw_events
        ]
        assert payloads[0] == {"type": "progress", "step": "抽取关键字", "status": "running"}
        assert payloads[1] == {"type": "progress", "step": "抽取关键字", "status": "success"}
        assert payloads[2]["type"] == "result"
        assert payloads[2]["data"]["answer_summary"] == "查询完成，共返回 1 条结果。"
        assert payloads[2]["data"]["result_table"]["rows"] == [{"base_name": "合肥"}]
