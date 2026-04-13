from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from textwrap import dedent
from typing import Any

from backend.app.domains.logistics.schemas.query import LogisticsNLQuery
from backend.app.domains.logistics.services.dictionary_loader import LogisticsDictionaryLoader
from backend.app.domains.logistics.services.domain_router import LogisticsDomainRouter
from backend.app.domains.logistics.services.hot_reload_service import LogisticsHotReloadService
from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService
from backend.app.domains.logistics.services.query_executor import LogisticsQueryExecutor
from backend.app.domains.logistics.services.query_plan_store import LogisticsQueryPlanStore
from backend.app.domains.logistics.services.sql_renderer import LogisticsSQLRenderer
from backend.app.domains.logistics.services.sql_template_registry import LogisticsSQLTemplateRegistry
from backend.app.domains.logistics.services.template_loader import LogisticsTemplateLoader


class FakeRepository:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> None:
        self.rows.append(payload)


class FakeDB:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakeQueryService:
    def __init__(self) -> None:
        self.db = FakeDB()
        self.repository = FakeRepository()

    def aggregate(self, payload, trace_id=None):  # noqa: ANN001
        return {
            "route": "aggregate",
            "execution_mode": "database",
            "items": [{"metric": 1}],
            "summary": {},
            "trace_id": trace_id,
        }

    def compare(self, payload, trace_id=None):  # noqa: ANN001
        return {
            "route": "compare",
            "execution_mode": "database",
            "items": [{"metric": 1}],
            "trace_id": trace_id,
        }

    def detail(self, payload, trace_id=None):  # noqa: ANN001
        return {
            "route": "detail",
            "execution_mode": "database",
            "items": [{"id": 1}],
            "total": 1,
            "trace_id": trace_id,
        }


class NL2QueryServiceV7Test(unittest.TestCase):
    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dedent(content).strip() + "\n", encoding="utf-8")

    def _build_service(self, config_dir: Path) -> tuple[LogisticsNL2QueryService, FakeQueryService]:
        fake_query_service = FakeQueryService()
        template_loader = LogisticsTemplateLoader(base_dir=str(config_dir))
        dictionary_loader = LogisticsDictionaryLoader(str(config_dir))
        domain_router = LogisticsDomainRouter(str(config_dir / "global" / "domain_keywords.yaml"))
        hot_reload_service = LogisticsHotReloadService(template_loader)
        sql_template_registry = LogisticsSQLTemplateRegistry(str(config_dir / "sql_templates"))
        sql_renderer = LogisticsSQLRenderer()
        query_executor = LogisticsQueryExecutor(fake_query_service)
        query_plan_store = LogisticsQueryPlanStore(fake_query_service)

        service = LogisticsNL2QueryService(
            fake_query_service,
            template_loader=template_loader,
            dictionary_loader=dictionary_loader,
            domain_router=domain_router,
            hot_reload_service=hot_reload_service,
            sql_template_registry=sql_template_registry,
            sql_renderer=sql_renderer,
            query_executor=query_executor,
            query_plan_store=query_plan_store,
        )
        return service, fake_query_service

    def test_should_bind_sql_template_and_store_query_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write(config_dir / "synonyms.yaml", "terms: {}\n")
            self._write(config_dir / "enum_mappings.yaml", "enums: {}\n")
            self._write(
                config_dir / "metric_dictionary.yaml",
                """
                metrics:
                  shipment_watt:
                    display_name: 运量（瓦数口径）
                    aliases: [运量, 发货量]
                """,
            )
            self._write(
                config_dir / "global" / "domain_keywords.yaml",
                """
                domains:
                  logistics: [物流, 承运商, 运量, 发货量]
                """,
            )
            self._write(
                config_dir / "domains" / "logistics" / "query_templates.yaml",
                """
                templates:
                  - id: logistics.aggregate.company_metric_rank
                    name: 物流公司指标排名
                    priority: 95
                    mode: aggregate
                    required_slots: [single_period_or_year]
                    metric_candidates: [shipment_watt]
                    keywords_any: [承运商, 发货量]
                    group_by: [logistics_company_name]
                    sql_template_id: logistics.carrier_month_rank
                """,
            )
            self._write(
                config_dir / "sql_templates" / "logistics" / "carrier_month_rank.sql",
                """
                SELECT * FROM dws_logistics_monthly_metric WHERE metric = '{{ metric_type }}';
                """,
            )

            service, fake_query_service = self._build_service(config_dir)
            result = service.parse_and_query(
                LogisticsNLQuery(question="2025年各承运商发货量分别是多少"),
                trace_id="v7-1",
            )

            parsed = result["parsed"]
            self.assertTrue(parsed["template_hit"])
            self.assertEqual(parsed["sql_template_id"], "logistics.carrier_month_rank")
            self.assertIn("execution_binding", parsed)
            self.assertTrue(parsed["execution_binding"]["sql_template"]["exists"])
            self.assertIn(
                "SELECT * FROM dws_logistics_monthly_metric",
                parsed["execution_binding"]["sql_preview"]["rendered"],
            )
            self.assertEqual(result["query_result"]["route"], "aggregate")
            self.assertEqual(len(fake_query_service.repository.rows), 1)
            self.assertTrue(fake_query_service.db.committed)

    def test_detail_scene_should_bind_detail_sql_template(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            self._write(config_dir / "synonyms.yaml", "terms: {}\n")
            self._write(config_dir / "enum_mappings.yaml", "enums: {}\n")
            self._write(
                config_dir / "metric_dictionary.yaml",
                """
                metrics:
                  shipment_watt:
                    display_name: 运量（瓦数口径）
                    aliases: [运量]
                """,
            )
            self._write(
                config_dir / "global" / "domain_keywords.yaml",
                """
                domains:
                  logistics: [合同编号, 明细]
                """,
            )
            self._write(
                config_dir / "domains" / "logistics" / "query_templates.yaml",
                """
                templates:
                  - id: logistics.detail.by_business_no
                    name: 业务编号明细查询
                    priority: 110
                    mode: detail
                    required_slots: [business_no]
                    metric_candidates: [shipment_watt]
                    keywords_any: [合同编号, 明细]
                    order_by: biz_date
                    order_direction: desc
                    sql_template_id: logistics.detail_by_business_no
                """,
            )
            self._write(
                config_dir / "sql_templates" / "logistics" / "detail_by_business_no.sql",
                """
                SELECT * FROM dws_logistics_detail_union WHERE contract_no = '{{ contract_no }}';
                """,
            )

            service, _ = self._build_service(config_dir)
            result = service.parse_and_query(
                LogisticsNLQuery(question="合同编号 HT20250301 的明细"),
                trace_id="v7-2",
            )

            parsed = result["parsed"]
            self.assertEqual(parsed["mode"], "detail")
            self.assertEqual(parsed["sql_template_id"], "logistics.detail_by_business_no")
            self.assertIn("HT20250301", parsed["execution_binding"]["sql_preview"]["rendered"])
            self.assertEqual(result["query_result"]["route"], "detail")


if __name__ == "__main__":
    unittest.main()
