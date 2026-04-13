import unittest

from backend.app.domains.logistics.schemas.query import LogisticsNLQuery
from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService


class FakeQueryService:
    def __init__(self) -> None:
        self.aggregate_called = False
        self.compare_called = False
        self.detail_called = False
        self.aggregate_payload = None
        self.compare_payload = None
        self.detail_payload = None

    def aggregate(self, payload, trace_id=None):  # noqa: ANN001
        self.aggregate_called = True
        self.aggregate_payload = payload
        return {"route": "aggregate", "trace_id": trace_id}

    def compare(self, payload, trace_id=None):  # noqa: ANN001
        self.compare_called = True
        self.compare_payload = payload
        return {"route": "compare", "trace_id": trace_id}

    def detail(self, payload, trace_id=None):  # noqa: ANN001
        self.detail_called = True
        self.detail_payload = payload
        return {"route": "detail", "trace_id": trace_id}


class Nl2QueryServiceTest(unittest.TestCase):
    def test_compare_question_with_two_digit_years_uses_compare_query(self) -> None:
        fake_query_service = FakeQueryService()
        service = LogisticsNL2QueryService(fake_query_service)  # type: ignore[arg-type]

        result = service.parse_and_query(
            LogisticsNLQuery(question="请帮我查询 25 年 3 月份和 26 年 3 月份的运量是多少？"),
            trace_id="trace-1",
        )

        self.assertTrue(fake_query_service.compare_called)
        self.assertFalse(fake_query_service.aggregate_called)
        self.assertEqual(result["query_result"]["route"], "compare")
        self.assertEqual(result["parsed"]["mode"], "compare")
        self.assertEqual(result["parsed"]["left"]["year_month_list"], ["2025-03"])
        self.assertEqual(result["parsed"]["right"]["year_month_list"], ["2026-03"])
        self.assertEqual(fake_query_service.compare_payload.left.year_month_list, ["2025-03"])
        self.assertEqual(fake_query_service.compare_payload.right.year_month_list, ["2026-03"])
        self.assertEqual(result["parsed"]["source_scope"], "all")

    def test_single_month_question_stays_aggregate(self) -> None:
        fake_query_service = FakeQueryService()
        service = LogisticsNL2QueryService(fake_query_service)  # type: ignore[arg-type]

        result = service.parse_and_query(
            LogisticsNLQuery(question="请帮我查询 2025 年 3 月份的运量是多少？"),
            trace_id="trace-2",
        )

        self.assertTrue(fake_query_service.aggregate_called)
        self.assertFalse(fake_query_service.compare_called)
        self.assertEqual(result["query_result"]["route"], "aggregate")
        self.assertEqual(result["parsed"]["year_month_list"], ["2025-03"])
        self.assertEqual(result["parsed"]["source_scope"], "hist")

    def test_year_question_group_by_company(self) -> None:
        fake_query_service = FakeQueryService()
        service = LogisticsNL2QueryService(fake_query_service)  # type: ignore[arg-type]

        result = service.parse_and_query(
            LogisticsNLQuery(question="2025年各物流公司年度运输量各是多少"),
            trace_id="trace-3",
        )

        self.assertTrue(fake_query_service.aggregate_called)
        self.assertEqual(result["parsed"]["group_by"], ["logistics_company_name"])
        self.assertEqual(result["parsed"]["start_date"], "2025-01-01")
        self.assertEqual(result["parsed"]["end_date"], "2025-12-31")
        self.assertEqual(result["parsed"]["source_scope"], "hist")

    def test_fee_question_uses_total_fee_metric(self) -> None:
        fake_query_service = FakeQueryService()
        service = LogisticsNL2QueryService(fake_query_service)  # type: ignore[arg-type]

        result = service.parse_and_query(
            LogisticsNLQuery(question="2026年1月各物流公司运费总额是多少"),
            trace_id="trace-4",
        )

        self.assertTrue(fake_query_service.aggregate_called)
        self.assertEqual(result["parsed"]["metric_type"], "total_fee")
        self.assertEqual(result["parsed"]["group_by"], ["logistics_company_name"])
        self.assertEqual(result["parsed"]["source_scope"], "sys")

    def test_detail_question_with_contract_no_routes_to_detail(self) -> None:
        fake_query_service = FakeQueryService()
        service = LogisticsNL2QueryService(fake_query_service)  # type: ignore[arg-type]

        result = service.parse_and_query(
            LogisticsNLQuery(question="请查询合同编号 ABC123 的发运明细"),
            trace_id="trace-5",
        )

        self.assertTrue(fake_query_service.detail_called)
        self.assertEqual(result["query_result"]["route"], "detail")
        self.assertEqual(result["parsed"]["mode"], "detail")
        self.assertEqual(result["parsed"]["contract_no"], "ABC123")

    def test_transport_mode_and_region_are_extracted(self) -> None:
        fake_query_service = FakeQueryService()
        service = LogisticsNL2QueryService(fake_query_service)  # type: ignore[arg-type]

        result = service.parse_and_query(
            LogisticsNLQuery(question="2026年华东区域铁路运输方式的运量是多少"),
            trace_id="trace-6",
        )

        self.assertTrue(fake_query_service.aggregate_called)
        self.assertEqual(result["parsed"]["region_name"], "华东")
        self.assertEqual(result["parsed"]["transport_mode"], "铁路")
        self.assertEqual(result["parsed"]["source_scope"], "sys")


if __name__ == "__main__":
    unittest.main()
