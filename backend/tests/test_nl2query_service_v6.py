from __future__ import annotations

import tempfile
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


class NL2QueryServiceV6Test(unittest.TestCase):
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

    def test_conflict_resolution_should_choose_higher_priority_template(self) -> None:
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
                    aliases: ["运量", "发货量"]
                """,
            )
            self._write(config_dir / "enum_mappings.yaml", "enums: {}\n")
            self._write(
                config_dir / "global" / "domain_keywords.yaml",
                """
                domains:
                  logistics: ["物流", "承运商", "运量"]
                """,
            )
            self._write(
                config_dir / "domains" / "logistics" / "query_templates.yaml",
                """
                templates:
                  - id: logistics.aggregate.company_metric_rank_low
                    name: 物流公司指标排名-低优先级
                    priority: 60
                    mode: aggregate
                    required_slots: [single_period_or_year]
                    metric_candidates: [shipment_watt]
                    keywords_any: ["承运商", "发货量"]
                    group_by: [logistics_company_name]
                  - id: logistics.aggregate.company_metric_rank_high
                    name: 物流公司指标排名-高优先级
                    priority: 95
                    mode: aggregate
                    required_slots: [single_period_or_year]
                    metric_candidates: [shipment_watt]
                    keywords_any: ["承运商", "发货量"]
                    group_by: [logistics_company_name]
                """,
            )

            service = self._build_service(config_dir)
            result = service.parse_and_query(
                LogisticsNLQuery(question="2025年各承运商发货量分别是多少"),
                trace_id="v6-1",
            )

            parsed = result["parsed"]
            self.assertTrue(parsed["template_hit"])
            self.assertEqual(parsed["template_id"], "logistics.aggregate.company_metric_rank_high")
            self.assertEqual(parsed["template_conflict_type"], "high_score_win")
            self.assertIn("template_conflict_explanation", parsed)
            self.assertIn("discarded_template_candidates", parsed)
            self.assertGreaterEqual(len(parsed["template_candidates"]), 2)

    def test_version_detail_should_be_returned(self) -> None:
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
                  logistics: ["运量"]
                """,
            )
            self._write(
                config_dir / "domains" / "logistics" / "query_templates.yaml",
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
            result = service.parse_and_query(LogisticsNLQuery(question="2025年运量是多少"), trace_id="v6-2")
            parsed = result["parsed"]

            self.assertIn("config_version", parsed)
            self.assertIn("config_version_detail", parsed)
            self.assertEqual(parsed["config_version_detail"]["file_count"], len(parsed["config_version_detail"]["files"]))
            self.assertGreater(parsed["config_version_detail"]["file_count"], 0)


if __name__ == "__main__":
    unittest.main()
