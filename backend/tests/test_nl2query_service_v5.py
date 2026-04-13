from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from textwrap import dedent

from backend.app.domains.logistics.schemas.query import LogisticsNLQuery
from backend.app.domains.logistics.services.dictionary_loader import LogisticsDictionaryLoader
from backend.app.domains.logistics.services.domain_router import LogisticsDomainRouter
from backend.app.domains.logistics.services.hot_reload_service import LogisticsHotReloadService
from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService
from backend.app.domains.logistics.services.template_loader import LogisticsTemplateLoader


class FakeQueryService:
    def aggregate(self, payload, trace_id=None):  # noqa: ANN001
        return {"route": "aggregate", "trace_id": trace_id}

    def compare(self, payload, trace_id=None):  # noqa: ANN001
        return {"route": "compare", "trace_id": trace_id}

    def detail(self, payload, trace_id=None):  # noqa: ANN001
        return {"route": "detail", "trace_id": trace_id}


class NL2QueryServiceV5Test(unittest.TestCase):
    def _write(self, path: Path, content: str) -> None:
        path.write_text(dedent(content).strip() + "\n", encoding="utf-8")

    def _build_service(self, config_dir: Path) -> LogisticsNL2QueryService:
        template_loader = LogisticsTemplateLoader(base_dir=str(config_dir))
        dictionary_loader = LogisticsDictionaryLoader(str(config_dir))
        domain_router = LogisticsDomainRouter(str(config_dir / "global" / "domain_keywords.yaml"))
        hot_reload_service = LogisticsHotReloadService(template_loader)
        return LogisticsNL2QueryService(
            FakeQueryService(),
            template_loader=template_loader,
            dictionary_loader=dictionary_loader,
            domain_router=domain_router,
            hot_reload_service=hot_reload_service,
        )

    def test_multi_domain_layering_and_hit_explanation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            (config_dir / "global").mkdir(parents=True, exist_ok=True)
            (config_dir / "domains" / "logistics").mkdir(parents=True, exist_ok=True)
            (config_dir / "domains" / "plan_bom").mkdir(parents=True, exist_ok=True)

            self._write(
                config_dir / "synonyms.yaml",
                """
                terms: {}
                """,
            )
            self._write(
                config_dir / "metric_dictionary.yaml",
                """
                metrics:
                  shipment_watt:
                    display_name: "运量（瓦数口径）"
                    aliases: ["运量", "发货量"]
                """,
            )
            self._write(
                config_dir / "enum_mappings.yaml",
                """
                enums: {}
                """,
            )
            self._write(
                config_dir / "global" / "domain_keywords.yaml",
                """
                domains:
                  logistics: ["物流", "承运商", "运量"]
                  plan_bom: ["BOM", "物料清单"]
                """,
            )
            self._write(
                config_dir / "domains" / "logistics" / "query_templates.yaml",
                """
                templates:
                  - id: logistics.aggregate.company_metric_rank
                    name: 物流公司指标排名
                    priority: 90
                    mode: aggregate
                    required_slots: [single_period_or_year]
                    metric_candidates: [shipment_watt]
                    keywords_any: ["承运商"]
                    group_by: [logistics_company_name]
                """,
            )
            self._write(
                config_dir / "domains" / "plan_bom" / "query_templates.yaml",
                """
                templates: []
                """,
            )

            service = self._build_service(config_dir)
            result = service.parse_and_query(
                LogisticsNLQuery(question="2025年各承运商发货量分别是多少"),
                trace_id="v5-1",
            )

            parsed = result["parsed"]
            self.assertEqual(parsed["selected_domain"], "logistics")
            self.assertEqual(parsed["template_id"], "logistics.aggregate.company_metric_rank")
            self.assertTrue(parsed["template_hit"])
            self.assertIn("template_candidates", parsed)
            self.assertIn("domain_candidates", parsed)
            self.assertIn("config_version", parsed)
            self.assertEqual(result["query_result"]["route"], "aggregate")

    def test_hot_reload_can_take_effect_without_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            (config_dir / "global").mkdir(parents=True, exist_ok=True)
            (config_dir / "domains" / "logistics").mkdir(parents=True, exist_ok=True)

            self._write(config_dir / "synonyms.yaml", "terms: {}\n")
            self._write(
                config_dir / "metric_dictionary.yaml",
                """
                metrics:
                  shipment_watt:
                    display_name: "运量（瓦数口径）"
                    aliases: ["运量"]
                """,
            )
            self._write(config_dir / "enum_mappings.yaml", "enums: {}\n")
            self._write(
                config_dir / "global" / "domain_keywords.yaml",
                """
                domains:
                  logistics: ["物流", "运量"]
                """,
            )

            template_file = config_dir / "domains" / "logistics" / "query_templates.yaml"
            self._write(
                template_file,
                """
                templates:
                  - id: logistics.aggregate.month_total
                    name: 月度总量
                    priority: 50
                    mode: aggregate
                    required_slots: [single_period_or_year]
                    metric_candidates: [shipment_watt]
                    keywords_any: ["运量"]
                """,
            )

            service = self._build_service(config_dir)
            first = service.parse_and_query(LogisticsNLQuery(question="2025年运量是多少"), trace_id="v5-2")
            first_version = first["parsed"]["config_version"]
            self.assertEqual(first["parsed"]["template_id"], "logistics.aggregate.month_total")

            # 修改模板文件，模拟运行期热更新。
            time.sleep(0.01)
            self._write(
                template_file,
                """
                templates:
                  - id: logistics.aggregate.month_total_v2
                    name: 月度总量V2
                    priority: 80
                    mode: aggregate
                    required_slots: [single_period_or_year]
                    metric_candidates: [shipment_watt]
                    keywords_any: ["运量"]
                """,
            )

            second = service.parse_and_query(LogisticsNLQuery(question="2025年运量是多少"), trace_id="v5-3")
            second_version = second["parsed"]["config_version"]
            self.assertEqual(second["parsed"]["template_id"], "logistics.aggregate.month_total_v2")
            self.assertNotEqual(first_version, second_version)


if __name__ == "__main__":
    unittest.main()
