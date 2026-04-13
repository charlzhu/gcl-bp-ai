import tempfile
import unittest
from pathlib import Path

from backend.app.domains.logistics.schemas.query import LogisticsNLQuery
from backend.app.domains.logistics.services.dictionary_loader import LogisticsDictionaryLoader
from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService
from backend.app.domains.logistics.services.template_loader import LogisticsTemplateLoader


class FakeQueryService:
    def aggregate(self, payload, trace_id=None):
        return {"route": "aggregate", "trace_id": trace_id}

    def compare(self, payload, trace_id=None):
        return {"route": "compare", "trace_id": trace_id}

    def detail(self, payload, trace_id=None):
        return {"route": "detail", "trace_id": trace_id}


class NL2QueryServiceV4Test(unittest.TestCase):
    def test_synonyms_and_metric_dictionary_work_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            (config_dir / "synonyms.yaml").write_text(
                'terms:\n  shipment_watt:\n    aliases: ["发货量", "出货量"]\n  logistics_company_name:\n    aliases: ["承运商"]\n',
                encoding="utf-8",
            )
            (config_dir / "metric_dictionary.yaml").write_text(
                'metrics:\n  shipment_watt:\n    display_name: "运量（瓦数口径）"\n    aliases: ["shipment_watt", "运量"]\n',
                encoding="utf-8",
            )
            (config_dir / "enum_mappings.yaml").write_text(
                'enums:\n  transport_mode:\n    铁路: ["铁运"]\n  region_name:\n    华东: ["华东"]\n',
                encoding="utf-8",
            )
            yaml_path = config_dir / "query_templates.yaml"
            yaml_path.write_text(
                'templates:\n  - id: logistics.aggregate.company_metric_rank\n    name: 物流公司指标排名\n    priority: 90\n    mode: aggregate\n    required_slots: [single_period_or_year]\n    metric_candidates: [shipment_watt]\n    keywords_any: ["logistics_company_name"]\n    group_by: [logistics_company_name]\n    order_by: metric\n    order_direction: desc\n',
                encoding="utf-8",
            )

            service = LogisticsNL2QueryService(
                FakeQueryService(),
                template_loader=LogisticsTemplateLoader(str(yaml_path)),
                dictionary_loader=LogisticsDictionaryLoader(str(config_dir)),
            )
            result = service.parse_and_query(LogisticsNLQuery(question="2025年承运商发货量分别是多少"), trace_id="v4-1")
            self.assertEqual(result["parsed"]["metric_type"], "shipment_watt")
            self.assertEqual(result["parsed"]["template_id"], "logistics.aggregate.company_metric_rank")
            self.assertEqual(result["parsed"]["group_by"], ["logistics_company_name"])
            self.assertIn("发货量", result["parsed"]["hit_synonyms"])

    def test_enum_mapping_can_unify_transport_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_dir = Path(tmp)
            (config_dir / "synonyms.yaml").write_text("terms: {}\n", encoding="utf-8")
            (config_dir / "metric_dictionary.yaml").write_text(
                'metrics:\n  shipment_watt:\n    display_name: "运量（瓦数口径）"\n    aliases: ["运量"]\n',
                encoding="utf-8",
            )
            (config_dir / "enum_mappings.yaml").write_text(
                'enums:\n  transport_mode:\n    铁路: ["铁运"]\n  region_name:\n    华东: ["华东"]\n',
                encoding="utf-8",
            )
            yaml_path = config_dir / "query_templates.yaml"
            yaml_path.write_text("templates: []\n", encoding="utf-8")

            service = LogisticsNL2QueryService(
                FakeQueryService(),
                template_loader=LogisticsTemplateLoader(str(yaml_path)),
                dictionary_loader=LogisticsDictionaryLoader(str(config_dir)),
            )
            result = service.parse_and_query(LogisticsNLQuery(question="2026年华东铁运运量是多少"), trace_id="v4-2")
            self.assertEqual(result["parsed"]["transport_mode"], "铁路")
            self.assertEqual(result["parsed"]["region_name"], "华东")
            self.assertEqual(result["query_result"]["route"], "aggregate")


if __name__ == "__main__":
    unittest.main()
