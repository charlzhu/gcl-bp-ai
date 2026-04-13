import tempfile
import unittest
from pathlib import Path

from backend.app.domains.logistics.schemas.query import LogisticsNLQuery
from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService
from backend.app.domains.logistics.services.template_loader import LogisticsTemplateLoader


class FakeQueryService:
    def aggregate(self, payload, trace_id=None):
        return {'route': 'aggregate', 'trace_id': trace_id}

    def compare(self, payload, trace_id=None):
        return {'route': 'compare', 'trace_id': trace_id}

    def detail(self, payload, trace_id=None):
        return {'route': 'detail', 'trace_id': trace_id}


class NL2QueryServiceV3Test(unittest.TestCase):
    def test_template_can_route_company_rank(self):
        with tempfile.TemporaryDirectory() as tmp:
            yaml_path = Path(tmp) / 'query_templates.yaml'
            yaml_path.write_text("""templates:
  - id: logistics.aggregate.company_metric_rank
    name: 物流公司指标排名
    priority: 95
    mode: aggregate
    required_slots: [single_period]
    metric_candidates: [shipment_watt]
    keywords_any: ["物流公司", "承运商", "分别"]
    group_by: [logistics_company_name]
    order_by: metric
    order_direction: desc
    limit: 20
""", encoding='utf-8')
            service = LogisticsNL2QueryService(FakeQueryService(),
                                               template_loader=LogisticsTemplateLoader(str(yaml_path)))
            result = service.parse_and_query(LogisticsNLQuery(question='2025年物流公司发货量分别是多少'), trace_id='t1')
            self.assertEqual(result['parsed']['template_id'], 'logistics.aggregate.company_metric_rank')
            self.assertEqual(result['parsed']['group_by'], ['logistics_company_name'])
            self.assertEqual(result['parsed']['order_by'], 'shipment_watt')
            self.assertEqual(result['query_result']['route'], 'aggregate')

    def test_template_can_route_detail(self):
        with tempfile.TemporaryDirectory() as tmp:
            yaml_path = Path(tmp) / 'query_templates.yaml'
            yaml_path.write_text("""templates:
  - id: logistics.detail.by_business_no
    name: 业务编号明细查询
    priority: 110
    mode: detail
    required_slots: [business_no]
    metric_candidates: [shipment_watt]
    keywords_any: ["合同编号", "明细"]
    order_by: biz_date
    order_direction: desc
""", encoding='utf-8')
            service = LogisticsNL2QueryService(FakeQueryService(),
                                               template_loader=LogisticsTemplateLoader(str(yaml_path)))
            result = service.parse_and_query(LogisticsNLQuery(question='请查询合同编号 ABC123 的发运明细'),
                                             trace_id='t2')
            self.assertEqual(result['parsed']['template_id'], 'logistics.detail.by_business_no')
            self.assertEqual(result['parsed']['mode'], 'detail')
            self.assertEqual(result['query_result']['route'], 'detail')


if __name__ == '__main__':
    unittest.main()
